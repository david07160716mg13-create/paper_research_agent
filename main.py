"""
Paper Research Agent — FastAPI Application
"""
import os
import sys
import uuid
import json
import asyncio
import threading
from datetime import datetime

from typing import List
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(__file__))

import config
from agents.query_parser import parse_query
from agents.paper_searcher import search_papers
from agents.pdf_downloader import download_papers
from agents.pdf_analyzer import analyze_all_papers, extract_text_from_pdf
from agents.report_generator import generate_html_report
from agents.arxiv_searcher import search_and_download_arxiv

app = FastAPI(title="Paper Research Agent", version="1.0.0")

# Static files and templates
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# ─── In-memory task store ──────────────────────────────────
tasks: dict[str, dict] = {}


def _run_pipeline(task_id: str, user_query: str, download_dir: str, selected_model: str = None, source: str = "semantic_scholar", user_context: str = None, uploaded_filenames: List[str] = None, use_scihub: bool = False):
    """Run the full search → download → analyze → report pipeline in a thread."""
    task = tasks[task_id]
    task["status"] = "running"

    def log(msg: str):
        task["logs"].append({"time": datetime.now().isoformat(), "msg": msg})

    try:
        # Step 1: Parse query
        log(f"🧠 Parsing your query with OLLAMA ({selected_model or config.OLLAMA_MODEL})...")
        task["stage"] = "parsing"
        query_info = parse_query(user_query, model=selected_model)
        task["query_info"] = query_info
        log(f"✅ Parsed: topic='{query_info['topic_en']}', "
            f"count={query_info['count']}, "
            f"QS={query_info['filters'].get('qs_ranking', 'any')}")

        # Step 2: Search papers
        log(f"🔍 Searching for papers via {source}...")
        task["stage"] = "searching"
        
        if source == "arxiv":
            papers = search_and_download_arxiv(
                query=query_info["topic_en"],
                desired_count=query_info["count"],
                download_dir=download_dir,
                progress_callback=log,
            )
        elif source == "both":
            half_count = max(1, query_info["count"] // 2)
            log("🔄 Searching Semantic Scholar first half...")
            papers_ss = search_papers(
                query=query_info["topic_en"],
                desired_count=half_count,
                qs_max_rank=query_info["filters"].get("qs_ranking"),
                year_from=query_info["filters"].get("year_from"),
                year_to=query_info["filters"].get("year_to"),
                progress_callback=log,
            )
            log("🔄 Searching arXiv second half...")
            papers_arxiv = search_and_download_arxiv(
                query=query_info["topic_en"],
                desired_count=query_info["count"] - len(papers_ss),
                download_dir=download_dir,
                progress_callback=log,
            )
            papers = papers_ss + papers_arxiv
        else:
            papers = search_papers(
                query=query_info["topic_en"],
                desired_count=query_info["count"],
                qs_max_rank=query_info["filters"].get("qs_ranking"),
                year_from=query_info["filters"].get("year_from"),
                year_to=query_info["filters"].get("year_to"),
                progress_callback=log,
            )
            
        task["papers"] = papers
        log(f"📋 Found {len(papers)} papers matching criteria")

        if not papers:
            log("⚠️ No papers found. Try broadening your search criteria.")
            task["status"] = "completed"
            task["stage"] = "done"
            return

        # Step 3: Download PDFs
        log("📥 Starting PDF downloads...")
        task["stage"] = "downloading"
        papers = download_papers(
            papers=papers,
            download_dir=download_dir,
            progress_callback=log,
            use_scihub=use_scihub,
        )
        task["papers"] = papers

        # Step 4: Analyze papers
        log(f"🤖 Analyzing papers with OLLAMA ({selected_model or config.OLLAMA_MODEL})...")
        task["stage"] = "analyzing"
        papers = analyze_all_papers(papers=papers, progress_callback=log, model=selected_model, user_context=user_context)
        task["papers"] = papers

        # Step 5: Generate report
        log("📝 Generating HTML report...")
        task["stage"] = "reporting"
        report_path = generate_html_report(
            papers=papers,
            query_info=query_info,
            output_dir=download_dir,
            progress_callback=log,
            uploaded_filenames=uploaded_filenames,
        )
        task["report_path"] = report_path
        log(f"🎉 All done! Report saved at: {report_path}")

        task["status"] = "completed"
        task["stage"] = "done"

    except Exception as exc:
        log(f"❌ Pipeline error: {exc}")
        task["status"] = "error"
        task["error"] = str(exc)


# ─── Routes ───────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/models")
async def get_models():
    import requests
    try:
        resp = requests.get(config.OLLAMA_TAGS_ENDPOINT, timeout=10)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        return {"models": [m.get("name") for m in models]}
    except Exception as exc:
        return JSONResponse({"error": f"Failed to fetch models: {exc}"}, status_code=500)


@app.post("/api/search")
async def start_search(
    query: str = Form(...),
    download_dir: str = Form(""),
    model: str = Form(""),
    source: str = Form("semantic_scholar"),
    use_scihub: str = Form("false"),
    report_files: List[UploadFile] = File(None)
):
    user_query = query.strip()
    download_dir = download_dir.strip() or config.DEFAULT_DOWNLOAD_DIR
    selected_model = model.strip() or None
    is_scihub_enabled = use_scihub.lower() == "true"

    if not user_query:
        return JSONResponse({"error": "Query is required"}, status_code=400)
        
    user_context = None
    uploaded_filenames = []
    
    if report_files:
        contexts = []
        for file in report_files:
            if not file.filename:
                continue
            try:
                content = await file.read()
                file_text = ""
                if file.filename.endswith(".pdf"):
                    temp_pdf = f"temp_{uuid.uuid4().hex}.pdf"
                    with open(temp_pdf, "wb") as f:
                        f.write(content)
                    file_text = extract_text_from_pdf(temp_pdf)
                    if os.path.exists(temp_pdf):
                        os.remove(temp_pdf)
                else:
                    file_text = content.decode('utf-8', errors='ignore')
                
                if file_text.strip():
                    contexts.append(f"--- File: {file.filename} ---\n{file_text.strip()}\n")
                    uploaded_filenames.append(file.filename)
            except Exception as e:
                return JSONResponse({"error": f"Failed to read uploaded file {file.filename}: {e}"}, status_code=400)
                
        if contexts:
            user_context = "\n".join(contexts)
            # Truncate user context to avoid blowing up the prompt
            if len(user_context) > 6000:
                user_context = user_context[:6000] + "\n...[truncated]"

    task_id = str(uuid.uuid4())[:8]
    tasks[task_id] = {
        "id": task_id,
        "query": user_query,
        "download_dir": download_dir,
        "status": "pending",
        "stage": "init",
        "logs": [],
        "papers": [],
        "query_info": {},
        "report_path": None,
        "error": None,
        "created_at": datetime.now().isoformat(),
    }

    thread = threading.Thread(
        target=_run_pipeline, args=(task_id, user_query, download_dir, selected_model, source, user_context, uploaded_filenames, is_scihub_enabled), daemon=True
    )
    thread.start()

    return {"task_id": task_id}


@app.get("/api/stream/{task_id}")
async def stream_progress(task_id: str):
    if task_id not in tasks:
        return JSONResponse({"error": "Task not found"}, status_code=404)

    async def event_generator():
        last_idx = 0
        while True:
            task = tasks.get(task_id)
            if not task:
                break

            # Send new log entries
            logs = task["logs"]
            while last_idx < len(logs):
                entry = logs[last_idx]
                yield {
                    "event": "log",
                    "data": json.dumps(entry, ensure_ascii=False),
                }
                last_idx += 1

            # Send status update
            yield {
                "event": "status",
                "data": json.dumps({
                    "status": task["status"],
                    "stage": task["stage"],
                    "total_papers": len(task["papers"]),
                    "report_ready": task["report_path"] is not None,
                }, ensure_ascii=False),
            }

            if task["status"] in ("completed", "error"):
                # Send final summary
                yield {
                    "event": "done",
                    "data": json.dumps({
                        "status": task["status"],
                        "total_papers": len(task["papers"]),
                        "downloaded": sum(
                            1 for p in task["papers"] if p.get("local_pdf_path")
                        ),
                        "report_path": task.get("report_path"),
                        "error": task.get("error"),
                    }, ensure_ascii=False),
                }
                break

            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())


@app.get("/api/report/{task_id}")
async def get_report(task_id: str):
    task = tasks.get(task_id)
    if not task:
        return JSONResponse({"error": "Task not found"}, status_code=404)
    if not task.get("report_path"):
        return JSONResponse({"error": "Report not ready"}, status_code=404)
    return FileResponse(
        task["report_path"],
        media_type="text/html",
        filename=os.path.basename(task["report_path"]),
    )


@app.get("/api/report-json/{task_id}")
async def get_report_json(task_id: str):
    task = tasks.get(task_id)
    if not task:
        return JSONResponse({"error": "Task not found"}, status_code=404)
    if not task.get("report_path"):
        return JSONResponse({"error": "Report not ready"}, status_code=404)
    json_path = task["report_path"].replace(".html", ".json")
    if os.path.exists(json_path):
        return FileResponse(json_path, media_type="application/json")
    return JSONResponse({"error": "JSON report not found"}, status_code=404)


@app.get("/api/tasks")
async def list_tasks():
    return [
        {
            "id": t["id"],
            "query": t["query"],
            "status": t["status"],
            "stage": t["stage"],
            "papers": len(t["papers"]),
            "created_at": t["created_at"],
        }
        for t in tasks.values()
    ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT)
