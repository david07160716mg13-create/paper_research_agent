"""
arXiv Searcher Agent — Queries arXiv API and downloads PDFs directly.
"""
import os
import arxiv
import re
from typing import Optional

def _sanitize_filename(title: str, max_len: int = 80) -> str:
    """Create a safe filename from a paper title."""
    safe = re.sub(r'[<>:"/\\|?*]', '', title)
    safe = re.sub(r'\s+', '_', safe.strip())
    if len(safe) > max_len:
        safe = safe[:max_len]
    return safe


def search_and_download_arxiv(
    query: str,
    desired_count: int = 10,
    download_dir: str = "./paper_downloads",
    progress_callback=None,
) -> list[dict]:
    """
    Search arXiv and immediately download PDFs (since all are Open Access).
    Returns a list of paper dicts in a unified format similar to Semantic Scholar.
    """
    if progress_callback:
        progress_callback(f"🔍 Searching arXiv for '{query}'...")

    os.makedirs(download_dir, exist_ok=True)
    
    # arXiv client
    client = arxiv.Client(page_size=100, delay_seconds=3, num_retries=3)
    
    # Fallback to general search if the query is complex
    search = arxiv.Search(
        query=query,
        max_results=desired_count,
        sort_by=arxiv.SortCriterion.Relevance
    )

    collected = []
    
    try:
        results = list(client.results(search))
    except Exception as exc:
        if progress_callback:
            progress_callback(f"⚠️ arXiv search error: {exc}")
        return collected

    total = min(len(results), desired_count)
    if progress_callback:
        progress_callback(f"📋 Found {len(results)} papers on arXiv, fetching {total}...")

    for idx, result in enumerate(results[:desired_count], 1):
        if progress_callback:
            progress_callback(f"📥 [{idx}/{total}] Downloading arXiv: {result.title[:50]}...")
            
        filename = f"arxiv_{idx:03d}_{_sanitize_filename(result.title)}.pdf"
        filepath = os.path.join(download_dir, filename)
        
        try:
            result.download_pdf(dirpath=download_dir, filename=filename)
            success = True
            error = None
        except Exception as exc:
            success = False
            error = str(exc)
            
        paper_dict = {
            "title": result.title,
            "abstract": result.summary,
            "venue": "arXiv",
            "year": result.published.year,
            "citationCount": 0,  # arXiv doesn't provide citation count directly
            "authors": [{"name": a.name} for a in result.authors],
            "url": result.pdf_url,
            "source": "arXiv"
        }
        
        if success:
            paper_dict["local_pdf_path"] = filepath
            if progress_callback:
                progress_callback(f"✅ Downloaded: {filename}")
        else:
            paper_dict["download_error"] = error
            if progress_callback:
                progress_callback(f"❌ Failed to download: {error}")
                
        collected.append(paper_dict)

    if progress_callback:
        progress_callback(f"✅ arXiv search complete: downloaded {len(collected)} papers.")
        
    return collected
