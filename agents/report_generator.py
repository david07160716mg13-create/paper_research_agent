"""
Report Generator — Produces HTML reports with MathJax support for paper analyses.
"""
import os
import json
from datetime import datetime


def _escape_html(text) -> str:
    """Escape HTML special characters."""
    if not text:
        return ""
    if isinstance(text, list):
        text = ", ".join(str(item) for item in text)
    elif not isinstance(text, str):
        text = str(text)
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _render_latex(formulas: list) -> str:
    """Render LaTeX formulas as HTML blocks."""
    if not formulas:
        return ""
    items = []
    for f in formulas:
        escaped = _escape_html(str(f))
        items.append(f'<div class="formula">\\({escaped}\\)</div>')
    return "\n".join(items)


def generate_html_report(
    papers: list[dict],
    query_info: dict,
    output_dir: str,
    progress_callback=None,
    uploaded_filenames: list[str] = None,
) -> str:
    """
    Generate a comprehensive HTML report with all paper analyses.

    Returns the path to the generated HTML file.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    topic = query_info.get("topic_original", "research")
    
    file_suffix = ""
    if uploaded_filenames:
        import re
        safe_names = [re.sub(r'[^\w\-]', '', os.path.splitext(n)[0])[:10] for n in uploaded_filenames]
        file_suffix = "_" + "_".join(safe_names)
        
    filename = f"report_{timestamp}{file_suffix}.html"
    filepath = os.path.join(output_dir, filename)
    os.makedirs(output_dir, exist_ok=True)

    downloaded = [p for p in papers if p.get("local_pdf_path")]
    analyzed = [p for p in papers if p.get("analysis") and not p["analysis"].get("error")]

    if progress_callback:
        progress_callback("📝 Generating HTML report...")

    # Build paper cards
    paper_cards = []
    for idx, paper in enumerate(papers, 1):
        title = _escape_html(paper.get("title", "Untitled"))
        year = paper.get("year", "N/A")
        venue = _escape_html(paper.get("venue", "N/A") or "N/A")
        citations = paper.get("citationCount", 0)
        authors = ", ".join(a.get("name", "?") for a in paper.get("authors", [])[:8])
        authors_esc = _escape_html(authors)
        url = paper.get("url", "#")
        analysis = paper.get("analysis", {})

        summary = _escape_html(analysis.get("summary", "No analysis available."))
        core = _escape_html(analysis.get("core_problem", ""))
        method = _escape_html(analysis.get("methodology", ""))
        findings = analysis.get("key_findings", [])
        contribs = _escape_html(analysis.get("contributions", ""))
        formulas = analysis.get("mathematical_formulas", [])
        limits = _escape_html(analysis.get("limitations", ""))
        future = _escape_html(analysis.get("future_work", ""))
        rag_comp = _escape_html(analysis.get("user_research_comparison", ""))

        findings_html = ""
        if findings:
            items = "".join(f"<li>{_escape_html(str(f))}</li>" for f in findings)
            findings_html = f"<ul>{items}</ul>"

        formulas_html = _render_latex(formulas) if formulas else ""

        has_pdf = "local_pdf_path" in paper
        status_badge = (
            '<span class="badge badge-success">已下載</span>' if has_pdf
            else '<span class="badge badge-warning">無PDF</span>'
        )

        card = f"""
        <div class="paper-card" id="paper-{idx}">
          <div class="paper-header" onclick="togglePaper({idx})">
            <div class="paper-num">{idx}</div>
            <div class="paper-title-block">
              <h3>{title}</h3>
              <div class="paper-meta">
                <span class="meta-item">📅 {year}</span>
                <span class="meta-item">📰 {venue}</span>
                <span class="meta-item">📚 {citations} citations</span>
                {status_badge}
              </div>
              <div class="paper-authors">{authors_esc}</div>
            </div>
            <div class="expand-icon" id="icon-{idx}">▼</div>
          </div>
          <div class="paper-body" id="body-{idx}" style="display:none;">
            <div class="analysis-section">
              <h4>📋 總結</h4>
              <p>{summary}</p>
            </div>
            {"<div class='analysis-section'><h4>🎯 核心問題</h4><p>" + core + "</p></div>" if core else ""}
            {"<div class='analysis-section'><h4>🔬 研究方法</h4><p>" + method + "</p></div>" if method else ""}
            {"<div class='analysis-section'><h4>💡 關鍵發現</h4>" + findings_html + "</div>" if findings_html else ""}
            {"<div class='analysis-section'><h4>🏆 主要貢獻</h4><p>" + contribs + "</p></div>" if contribs else ""}
            {"<div class='analysis-section' style='border-left-color:#e74c3c;'><h4>🎯 與你的研究比對結果</h4><p>" + rag_comp + "</p></div>" if rag_comp else ""}
            {"<div class='analysis-section'><h4>📐 重要公式</h4>" + formulas_html + "</div>" if formulas_html else ""}
            {"<div class='analysis-section'><h4>⚠️ 研究限制</h4><p>" + limits + "</p></div>" if limits else ""}
            {"<div class='analysis-section'><h4>🔮 未來展望</h4><p>" + future + "</p></div>" if future else ""}
            <div class="paper-link">
              <a href="{url}" target="_blank">🔗 View on Semantic Scholar</a>
            </div>
          </div>
        </div>"""
        paper_cards.append(card)

    cards_html = "\n".join(paper_cards)
    topic_esc = _escape_html(topic)
    qs_rank = query_info.get("filters", {}).get("qs_ranking")
    qs_text = f"QS 排名前 {qs_rank}" if qs_rank else "無限制"
    
    rag_info = ""
    if uploaded_filenames:
        rag_files = ", ".join(_escape_html(f) for f in uploaded_filenames)
        rag_info = f" ｜ 📂 RAG 比對檔案：{rag_files}"

    html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>論文研究報告 — {topic_esc}</title>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js" async></script>
<style>
:root {{
  --bg-primary: #0f0f1a;
  --bg-card: #1a1a2e;
  --bg-section: #16213e;
  --accent: #6c63ff;
  --accent-glow: rgba(108, 99, 255, 0.3);
  --text-primary: #e8e8f0;
  --text-secondary: #a0a0b8;
  --success: #2ecc71;
  --warning: #f39c12;
  --border: rgba(108, 99, 255, 0.2);
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: 'Segoe UI', 'Noto Sans TC', sans-serif;
  background: var(--bg-primary);
  color: var(--text-primary);
  line-height: 1.7;
  min-height: 100vh;
}}
.hero {{
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
  padding: 60px 40px;
  text-align: center;
  border-bottom: 2px solid var(--border);
  position: relative;
  overflow: hidden;
}}
.hero::before {{
  content: '';
  position: absolute;
  top: -50%; left: -50%;
  width: 200%; height: 200%;
  background: radial-gradient(circle at 30% 50%, var(--accent-glow) 0%, transparent 50%);
  animation: heroGlow 8s ease-in-out infinite alternate;
}}
@keyframes heroGlow {{
  from {{ transform: translate(0, 0); }}
  to {{ transform: translate(5%, 3%); }}
}}
.hero h1 {{
  font-size: 2.5em;
  font-weight: 700;
  position: relative;
  background: linear-gradient(135deg, #fff, var(--accent));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin-bottom: 16px;
}}
.hero p {{ color: var(--text-secondary); font-size: 1.1em; position: relative; }}
.stats {{
  display: flex; gap: 24px; justify-content: center;
  margin-top: 30px; flex-wrap: wrap; position: relative;
}}
.stat-box {{
  background: rgba(255,255,255,0.05);
  backdrop-filter: blur(10px);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 20px 32px;
  text-align: center;
  min-width: 140px;
}}
.stat-box .num {{
  font-size: 2.2em; font-weight: 700; color: var(--accent);
  display: block;
}}
.stat-box .label {{ color: var(--text-secondary); font-size: 0.9em; }}
.container {{ max-width: 1000px; margin: 0 auto; padding: 40px 20px; }}
.paper-card {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 16px;
  margin-bottom: 16px;
  overflow: hidden;
  transition: all 0.3s ease;
}}
.paper-card:hover {{
  border-color: var(--accent);
  box-shadow: 0 4px 30px var(--accent-glow);
  transform: translateY(-2px);
}}
.paper-header {{
  display: flex; align-items: flex-start; gap: 16px;
  padding: 24px; cursor: pointer; user-select: none;
}}
.paper-num {{
  background: var(--accent);
  color: #fff; font-weight: 700;
  min-width: 36px; height: 36px;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 0.9em; flex-shrink: 0;
}}
.paper-title-block {{ flex: 1; }}
.paper-title-block h3 {{ font-size: 1.1em; line-height: 1.4; margin-bottom: 8px; }}
.paper-meta {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 4px; }}
.meta-item {{ color: var(--text-secondary); font-size: 0.85em; }}
.paper-authors {{ color: var(--text-secondary); font-size: 0.85em; font-style: italic; }}
.expand-icon {{
  color: var(--accent); font-size: 1.2em;
  transition: transform 0.3s; flex-shrink: 0; padding-top: 4px;
}}
.expand-icon.open {{ transform: rotate(180deg); }}
.badge {{
  font-size: 0.75em; padding: 2px 10px; border-radius: 20px;
  font-weight: 600; display: inline-block;
}}
.badge-success {{ background: rgba(46,204,113,0.15); color: var(--success); border: 1px solid rgba(46,204,113,0.3); }}
.badge-warning {{ background: rgba(243,156,18,0.15); color: var(--warning); border: 1px solid rgba(243,156,18,0.3); }}
.paper-body {{ padding: 0 24px 24px; }}
.analysis-section {{
  background: var(--bg-section);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 12px;
  border-left: 3px solid var(--accent);
}}
.analysis-section h4 {{ color: var(--accent); margin-bottom: 10px; font-size: 1em; }}
.analysis-section p {{ color: var(--text-secondary); font-size: 0.95em; }}
.analysis-section ul {{ padding-left: 20px; color: var(--text-secondary); }}
.analysis-section li {{ margin-bottom: 6px; font-size: 0.95em; }}
.formula {{
  background: rgba(108,99,255,0.08);
  padding: 12px 16px; border-radius: 8px;
  margin: 8px 0; font-size: 1.1em; text-align: center;
  overflow-x: auto;
}}
.paper-link {{ text-align: right; padding-top: 8px; }}
.paper-link a {{
  color: var(--accent); text-decoration: none; font-size: 0.9em;
  transition: opacity 0.2s;
}}
.paper-link a:hover {{ opacity: 0.8; text-decoration: underline; }}
.footer {{
  text-align: center; padding: 40px;
  color: var(--text-secondary); font-size: 0.85em;
  border-top: 1px solid var(--border);
}}
@media (max-width: 600px) {{
  .hero {{ padding: 30px 16px; }}
  .hero h1 {{ font-size: 1.6em; }}
  .stats {{ gap: 12px; }}
  .paper-header {{ padding: 16px; gap: 10px; }}
  .container {{ padding: 20px 12px; }}
}}
</style>
</head>
<body>
<div class="hero">
  <h1>📑 論文研究報告</h1>
  <p>主題：{topic_esc} ｜ 學校篩選：{qs_text}{rag_info}</p>
  <div class="stats">
    <div class="stat-box"><span class="num">{len(papers)}</span><span class="label">搜尋到</span></div>
    <div class="stat-box"><span class="num">{len(downloaded)}</span><span class="label">已下載</span></div>
    <div class="stat-box"><span class="num">{len(analyzed)}</span><span class="label">已分析</span></div>
  </div>
</div>
<div class="container">
  {cards_html}
</div>
<div class="footer">
  Generated by Paper Research Agent — {datetime.now().strftime("%Y-%m-%d %H:%M")}
  <br>Powered by OLLAMA + Semantic Scholar + arXiv
</div>
<script>
function togglePaper(id) {{
  const body = document.getElementById('body-' + id);
  const icon = document.getElementById('icon-' + id);
  if (body.style.display === 'none') {{
    body.style.display = 'block';
    icon.classList.add('open');
  }} else {{
    body.style.display = 'none';
    icon.classList.remove('open');
  }}
}}
</script>
</body>
</html>"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    # Also save JSON data
    json_path = filepath.replace(".html", ".json")
    json_data = {
        "query": query_info,
        "generated_at": datetime.now().isoformat(),
        "total_papers": len(papers),
        "downloaded": len(downloaded),
        "analyzed": len(analyzed),
        "papers": [
            {
                "title": p.get("title"),
                "year": p.get("year"),
                "venue": p.get("venue"),
                "citations": p.get("citationCount"),
                "authors": [a.get("name") for a in p.get("authors", [])],
                "has_pdf": "local_pdf_path" in p,
                "analysis": p.get("analysis", {}),
            }
            for p in papers
        ],
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    if progress_callback:
        progress_callback(f"📄 Report saved: {filepath}")

    return filepath
