"""
PDF Downloader Agent — Downloads open-access PDFs from Semantic Scholar results.
"""
import os
import re
import time
import requests
from bs4 import BeautifulSoup
from typing import Optional
from config import DEFAULT_DOWNLOAD_DIR, MAX_DOWNLOAD_RETRIES, DOWNLOAD_TIMEOUT_SECONDS, SCIHUB_BASE_URLS


def _sanitize_filename(title: str, max_len: int = 80) -> str:
    """Create a safe filename from a paper title."""
    # Remove special characters
    safe = re.sub(r'[<>:"/\\|?*]', '', title)
    safe = re.sub(r'\s+', '_', safe.strip())
    if len(safe) > max_len:
        safe = safe[:max_len]
    return safe


def download_from_scihub(doi: str, filepath: str) -> bool:
    """Attempt to download a paper from Sci-Hub using its DOI."""
    for base_url in SCIHUB_BASE_URLS:
        try:
            url = f"{base_url}/{doi}"
            # Fetch the Sci-Hub page
            resp = requests.get(
                url, 
                timeout=15, 
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            # Look for iframe or embed
            pdf_iframe = soup.find('iframe', id='pdf')
            pdf_embed = soup.find('embed', id='pdf')
            
            pdf_url = None
            if pdf_iframe and pdf_iframe.has_attr('src'):
                pdf_url = pdf_iframe['src']
            elif pdf_embed and pdf_embed.has_attr('src'):
                pdf_url = pdf_embed['src']
                
            if not pdf_url:
                continue
                
            # Handle relative URLs (e.g. //sci-hub.ru/...)
            if pdf_url.startswith('//'):
                pdf_url = 'https:' + pdf_url
            elif pdf_url.startswith('/'):
                pdf_url = base_url + pdf_url
                
            # Now download the actual PDF
            pdf_resp = requests.get(
                pdf_url, 
                timeout=DOWNLOAD_TIMEOUT_SECONDS,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                stream=True
            )
            pdf_resp.raise_for_status()
            
            with open(filepath, "wb") as f:
                for chunk in pdf_resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            # Check header
            with open(filepath, "rb") as f:
                header = f.read(5)
            if header != b"%PDF-":
                os.remove(filepath)
                continue # Try next domain if downloaded file is invalid
                
            return True
            
        except Exception:
            continue
            
    return False

def download_papers(
    papers: list[dict],
    download_dir: Optional[str] = None,
    progress_callback=None,
    use_scihub: bool = False,
) -> list[dict]:
    """
    Download open-access PDFs for the given papers.

    Parameters
    ----------
    papers : list[dict]
        Papers from Semantic Scholar (must include openAccessPdf field).
    download_dir : str or None
        Directory to save PDFs. Defaults to config.DEFAULT_DOWNLOAD_DIR.
    progress_callback : callable or None
        Called with (message: str) to report progress.

    Returns
    -------
    list[dict]
        Updated paper dicts with 'local_pdf_path' added for successfully
        downloaded papers, and 'download_error' for failures.
    """
    if download_dir is None:
        download_dir = DEFAULT_DOWNLOAD_DIR

    os.makedirs(download_dir, exist_ok=True)

    results = []
    total = len(papers)

    for idx, paper in enumerate(papers, 1):
        title = paper.get("title", "untitled")
        oa_pdf = paper.get("openAccessPdf")

        if not oa_pdf or not oa_pdf.get("url"):
            # Try Sci-Hub Fallback if enabled and DOI exists
            if use_scihub and paper.get("doi"):
                filename = f"{idx:03d}_{_sanitize_filename(title)}.pdf"
                filepath = os.path.join(download_dir, filename)
                if progress_callback:
                    progress_callback(f"📥 [{idx}/{total}] Attempting Sci-Hub fallback for: {title[:50]}...")
                
                if download_from_scihub(paper["doi"], filepath):
                    paper["local_pdf_path"] = filepath
                    if progress_callback: progress_callback(f"✅ [{idx}/{total}] Downloaded via Sci-Hub: {filename}")
                    results.append(paper)
                    continue
                else:
                    if progress_callback: progress_callback(f"❌ [{idx}/{total}] Sci-Hub fallback failed.")

            if progress_callback:
                progress_callback(
                    f"⏭️ [{idx}/{total}] No open-access PDF: {title[:60]}"
                )
            paper["download_error"] = "No open-access PDF available"
            results.append(paper)
            continue

        pdf_url = oa_pdf["url"]
        filename = f"{idx:03d}_{_sanitize_filename(title)}.pdf"
        filepath = os.path.join(download_dir, filename)

        if progress_callback:
            progress_callback(
                f"📥 [{idx}/{total}] Downloading: {title[:60]}..."
            )

        success = False
        for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):
            try:
                resp = requests.get(
                    pdf_url,
                    timeout=DOWNLOAD_TIMEOUT_SECONDS,
                    headers={"User-Agent": "PaperResearchAgent/1.0"},
                    stream=True,
                )
                resp.raise_for_status()

                # Verify it's actually a PDF
                content_type = resp.headers.get("Content-Type", "")
                if "pdf" not in content_type and not pdf_url.endswith(".pdf"):
                    # Try downloading anyway, some servers don't set content-type
                    pass

                with open(filepath, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)

                # Verify the file is valid (at least check header)
                with open(filepath, "rb") as f:
                    header = f.read(5)
                if header != b"%PDF-":
                    os.remove(filepath)
                    raise ValueError("Downloaded file is not a valid PDF")

                paper["local_pdf_path"] = filepath
                success = True
                if progress_callback:
                    progress_callback(
                        f"✅ [{idx}/{total}] Downloaded: {filename}"
                    )
                break

            except Exception as exc:
                if attempt < MAX_DOWNLOAD_RETRIES:
                    time.sleep(2 * attempt)  # Exponential backoff
                else:
                    # Attempt Sci-Hub fallback on failure
                    if use_scihub and paper.get("doi"):
                        if progress_callback:
                            progress_callback(f"⚠️ [{idx}/{total}] Normal download failed, trying Sci-Hub...")
                        if download_from_scihub(paper["doi"], filepath):
                            paper["local_pdf_path"] = filepath
                            paper.pop("download_error", None)
                            if progress_callback: progress_callback(f"✅ [{idx}/{total}] Downloaded via Sci-Hub: {filename}")
                            success = True
                            break
                        
                    paper["download_error"] = str(exc)
                    if progress_callback:
                        progress_callback(
                            f"❌ [{idx}/{total}] Failed after {MAX_DOWNLOAD_RETRIES} "
                            f"attempts: {title[:50]} — {exc}"
                        )

        results.append(paper)
        # Be polite
        time.sleep(0.5)

    downloaded = sum(1 for p in results if "local_pdf_path" in p)
    if progress_callback:
        progress_callback(
            f"📦 Download complete: {downloaded}/{total} PDFs saved to {download_dir}"
        )

    return results
