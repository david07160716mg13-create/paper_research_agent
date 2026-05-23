"""
PDF Analyzer Agent — Extracts text from PDFs and uses OLLAMA for deep analysis.
"""
import os
import json
import re
import requests
import fitz  # PyMuPDF
from config import OLLAMA_CHAT_ENDPOINT, OLLAMA_MODEL, MAX_CHUNK_CHARS, ANALYSIS_TEMPERATURE

ANALYSIS_SYSTEM_PROMPT = (
    "You are an expert academic paper analyst. Analyze the given paper content "
    "and return ONLY valid JSON (no markdown fences) with these keys: "
    "title_analyzed, core_problem, methodology, key_findings (array), "
    "contributions, mathematical_formulas (array of LaTeX strings), "
    "limitations, future_work, summary (200-300 words in Traditional Chinese), "
    "user_research_comparison (string, if applicable)."
)


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract all text from a PDF file using PyMuPDF."""
    try:
        doc = fitz.open(pdf_path)
        parts = []
        for page_num in range(len(doc)):
            parts.append(doc.load_page(page_num).get_text())
        doc.close()
        return "\n".join(parts)
    except Exception as exc:
        return f"[Error extracting text: {exc}]"


def _chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split text into chunks that fit within the LLM context window."""
    if len(text) <= max_chars:
        return [text]
    chunks = []
    paragraphs = text.split("\n\n")
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 2 > max_chars:
            if current:
                chunks.append(current.strip())
            if len(para) > max_chars:
                for i in range(0, len(para), max_chars):
                    chunks.append(para[i:i + max_chars])
                current = ""
            else:
                current = para
        else:
            current += "\n\n" + para
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _call_ollama(system_prompt: str, user_prompt: str, model: str = None) -> str:
    """Send a chat request to OLLAMA and return the response content."""
    payload = {
        "model": model or OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {"temperature": ANALYSIS_TEMPERATURE},
    }
    resp = requests.post(OLLAMA_CHAT_ENDPOINT, json=payload, timeout=300)
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def _parse_json(raw: str) -> dict:
    """Parse LLM response as JSON with fallback."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {"summary": raw, "core_problem": "", "methodology": "",
                "key_findings": [], "contributions": "",
                "mathematical_formulas": [], "limitations": "", "future_work": ""}


def analyze_paper(paper: dict, progress_callback=None, model: str = None, user_context: str = None) -> dict:
    """Analyze a single paper: extract PDF text -> send to OLLAMA."""
    title = paper.get("title", "Unknown")
    pdf_path = paper.get("local_pdf_path")

    if not pdf_path or not os.path.exists(pdf_path):
        paper["analysis"] = {"summary": "PDF not available.", "error": "No PDF"}
        return paper

    if progress_callback:
        progress_callback(f"📖 Extracting text: {title[:60]}...")

    full_text = extract_text_from_pdf(pdf_path)
    if not full_text or full_text.startswith("[Error"):
        paper["analysis"] = {"summary": "Text extraction failed.", "error": full_text}
        return paper

    active_model = model or OLLAMA_MODEL
    if progress_callback:
        progress_callback(f"🤖 Analyzing with {active_model}: {title[:60]}...")

    chunks = _chunk_text(full_text)
    content = "\n\n".join(chunks[:3])
    authors_str = ", ".join(a.get("name", "?") for a in paper.get("authors", [])[:10])

    user_prompt = (
        f"Analyze this paper (respond in 繁體中文):\n"
        f"Title: {title}\nAuthors: {authors_str}\n"
        f"Venue: {paper.get('venue', 'N/A')}\nYear: {paper.get('year', 'N/A')}\n"
        f"---\n{content}\n---\n"
    )

    if user_context:
        user_prompt += (
            f"\n\nAlso, compare this paper to the user's research context below:\n"
            f"--- User Research Context ---\n{user_context}\n--------------------------\n"
            f"Please populate the 'user_research_comparison' field with a detailed analysis of how this paper relates to, supports, or contrasts with the user's research. Provide specific insights."
        )

    try:
        raw = _call_ollama(ANALYSIS_SYSTEM_PROMPT, user_prompt, model=model)
        paper["analysis"] = _parse_json(raw)
    except Exception as exc:
        paper["analysis"] = {"summary": f"Analysis failed: {exc}", "error": str(exc)}

    if progress_callback:
        progress_callback(f"✅ Done: {title[:60]}")
    return paper


def analyze_all_papers(papers: list[dict], progress_callback=None, model: str = None, user_context: str = None) -> list[dict]:
    """Analyze all downloaded papers."""
    downloadable = [p for p in papers if p.get("local_pdf_path")]
    total = len(downloadable)
    if progress_callback:
        progress_callback(f"📊 Starting analysis of {total} papers...")

    for idx, paper in enumerate(downloadable, 1):
        if progress_callback:
            progress_callback(f"📄 [{idx}/{total}] Analyzing...")
        analyze_paper(paper, progress_callback, model=model, user_context=user_context)

    for paper in papers:
        if "analysis" not in paper:
            paper["analysis"] = {"summary": "PDF not downloaded."}

    if progress_callback:
        progress_callback(f"🎉 All {total} papers analyzed!")
    return papers
