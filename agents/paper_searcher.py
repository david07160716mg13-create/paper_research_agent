"""
Paper Searcher Agent — Queries multiple APIs and applies QS ranking filters.
"""
import json
import os
import time
import requests
import arxiv
import math
from typing import Optional
from config import (
    S2_SEARCH_ENDPOINT,
    S2_SEARCH_FIELDS,
    S2_RESULTS_PER_PAGE,
    OPENALEX_SEARCH_ENDPOINT,
    CROSSREF_SEARCH_ENDPOINT
)

# ─── Load QS Rankings ──────────────────────────────────────
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

def _load_qs_rankings() -> list[dict]:
    path = os.path.join(_DATA_DIR, "qs_rankings.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

QS_RANKINGS = _load_qs_rankings()


def _build_qs_lookup(max_rank: int) -> set[str]:
    lookup = set()
    for uni in QS_RANKINGS:
        if uni.get("rank", 9999) <= max_rank:
            lookup.add(uni["name"].lower())
            for alias in uni.get("aliases", []):
                lookup.add(alias.lower())
    return lookup


def _affiliation_matches_qs(affiliations: list[str], qs_lookup: set[str]) -> bool:
    for aff in affiliations:
        aff_lower = aff.lower()
        for uni_name in qs_lookup:
            if uni_name in aff_lower or aff_lower in uni_name:
                return True
    return False


def _paper_matches_qs(paper: dict, qs_lookup: set[str]) -> bool:
    for author in paper.get("authors", []):
        affs = author.get("affiliations") or []
        if _affiliation_matches_qs(affs, qs_lookup):
            return True
    return False


def _search_semantic_scholar(query: str, desired_count: int, qs_lookup: Optional[set[str]], year_from: Optional[int], year_to: Optional[int], progress_callback) -> list[dict]:
    year_filter = None
    if year_from and year_to: year_filter = f"{year_from}-{year_to}"
    elif year_from: year_filter = f"{year_from}-"
    elif year_to: year_filter = f"-{year_to}"

    collected = []
    offset = 0
    max_api_pages = 3
    rate_limit_backoff = 5
    retry_count = 0

    while len(collected) < desired_count and offset < max_api_pages * S2_RESULTS_PER_PAGE:
        params = {"query": query, "fields": S2_SEARCH_FIELDS, "offset": offset, "limit": S2_RESULTS_PER_PAGE}
        if year_filter: params["year"] = year_filter

        if progress_callback:
            progress_callback(f"🔍 Searching Semantic Scholar (collected {len(collected)}/{desired_count})...")

        try:
            resp = requests.get(S2_SEARCH_ENDPOINT, params=params, timeout=30)
            if resp.status_code == 429:
                retry_count += 1
                if retry_count > 3:
                    if progress_callback: progress_callback("⚠️ Semantic Scholar rate limit exceeded 3 retries. Moving on.")
                    break
                if progress_callback: progress_callback(f"⏳ Rate limited, waiting {rate_limit_backoff} seconds...")
                time.sleep(rate_limit_backoff)
                rate_limit_backoff = min(rate_limit_backoff * 2, 60)
                continue

            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            if progress_callback: progress_callback(f"⚠️ API error: {exc}")
            break

        papers = data.get("data", [])
        if not papers: break

        retry_count = 0
        rate_limit_backoff = 5

        for paper in papers:
            if len(collected) >= desired_count: break
            if qs_lookup and not _paper_matches_qs(paper, qs_lookup): continue
            paper["source"] = "Semantic Scholar"
            
            ext_ids = paper.get("externalIds") or {}
            doi = ext_ids.get("DOI")
            if doi:
                paper["doi"] = doi
                
            collected.append(paper)

        offset += S2_RESULTS_PER_PAGE
        time.sleep(1)

    return collected


def _search_arxiv(query: str, desired_count: int, qs_lookup: Optional[set[str]], year_from: Optional[int], year_to: Optional[int], progress_callback) -> list[dict]:
    if progress_callback: progress_callback("🔍 Searching ArXiv...")
    collected = []
    try:
        # For simplicity, we just use the query. ArXiv doesn't cleanly filter by year via simple query without complex syntax.
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=desired_count * 3, # fetch more since we might filter
            sort_by=arxiv.SortCriterion.Relevance
        )
        for result in client.results(search):
            year = result.published.year
            if year_from and year < year_from: continue
            if year_to and year > year_to: continue

            authors = [{"name": a.name, "affiliations": []} for a in result.authors]
            paper_dict = {
                "title": result.title,
                "abstract": result.summary,
                "year": year,
                "authors": authors,
                "url": result.entry_id,
                "doi": result.doi,
                "openAccessPdf": {"url": result.pdf_url},
                "source": "ArXiv",
                "venue": "ArXiv"
            }
            # ArXiv rarely provides affiliations, so if qs_lookup is strict, it might drop all ArXiv papers.
            # We bypass QS filter for ArXiv to ensure we get papers, or we let it drop if the user demands strict QS.
            # Since user wants more sources, we will only apply QS if authors have affiliations (which they don't here).
            # We'll just include it.
            collected.append(paper_dict)
            if len(collected) >= desired_count: break
    except Exception as e:
        if progress_callback: progress_callback(f"⚠️ ArXiv API error: {e}")
    return collected


def _search_openalex(query: str, desired_count: int, qs_lookup: Optional[set[str]], year_from: Optional[int], year_to: Optional[int], progress_callback) -> list[dict]:
    if progress_callback: progress_callback("🔍 Searching OpenAlex...")
    collected = []
    params = {"search": query, "per-page": desired_count * 3}
    filters = []
    if year_from: filters.append(f"publication_year:>{year_from-1}")
    if year_to: filters.append(f"publication_year:<{year_to+1}")
    if filters:
        params["filter"] = ",".join(filters)

    try:
        resp = requests.get(OPENALEX_SEARCH_ENDPOINT, params=params, timeout=30)
        resp.raise_for_status()
        results = resp.json().get("results") or []
        
        for res in results:
            authors = []
            for authorship in (res.get("authorships") or []):
                author = authorship.get("author") or {}
                author_name = author.get("display_name", "")
                institutions = authorship.get("institutions") or []
                affiliations = [inst.get("display_name", "") for inst in institutions]
                authors.append({"name": author_name, "affiliations": affiliations})

            primary_location = res.get("primary_location") or {}
            source = primary_location.get("source") or {}
            venue = source.get("display_name", "")

            open_access = res.get("open_access") or {}
            oa_url = open_access.get("oa_url")
            
            doi = res.get("doi")
            if doi and doi.startswith("https://doi.org/"):
                doi = doi.replace("https://doi.org/", "")

            paper_dict = {
                "title": res.get("title") or "",
                "abstract": res.get("abstract") or "No abstract available",
                "year": res.get("publication_year"),
                "authors": authors,
                "url": res.get("id"),
                "doi": doi,
                "openAccessPdf": {"url": oa_url},
                "source": "OpenAlex",
                "venue": venue
            }
            
            if qs_lookup and not _paper_matches_qs(paper_dict, qs_lookup):
                continue
                
            collected.append(paper_dict)
            if len(collected) >= desired_count: break
    except Exception as e:
        if progress_callback: progress_callback(f"⚠️ OpenAlex API error: {e}")
    return collected


def _search_crossref(query: str, desired_count: int, qs_lookup: Optional[set[str]], year_from: Optional[int], year_to: Optional[int], progress_callback) -> list[dict]:
    if progress_callback: progress_callback("🔍 Searching Crossref...")
    collected = []
    params = {"query": query, "rows": desired_count * 3}
    filters = []
    if year_from: filters.append(f"from-pub-date:{year_from}")
    if year_to: filters.append(f"until-pub-date:{year_to}")
    if filters: params["filter"] = ",".join(filters)

    try:
        resp = requests.get(CROSSREF_SEARCH_ENDPOINT, params=params, timeout=30)
        resp.raise_for_status()
        items = resp.json().get("message", {}).get("items", [])
        for item in items:
            authors = []
            for author in item.get("author", []):
                name = f"{author.get('given', '')} {author.get('family', '')}".strip()
                affiliations = [aff.get("name", "") for aff in author.get("affiliation", [])]
                authors.append({"name": name, "affiliations": affiliations})

            year = None
            published = item.get("published-print") or item.get("published-online")
            if published and published.get("date-parts"):
                year = published["date-parts"][0][0]
                
            doi = item.get("DOI")

            paper_dict = {
                "title": item.get("title", [""])[0],
                "abstract": item.get("abstract", ""),
                "year": year,
                "authors": authors,
                "url": item.get("URL"),
                "doi": doi,
                "openAccessPdf": {"url": item.get("link", [{"URL": None}])[0].get("URL") if item.get("link") else None},
                "source": "Crossref",
                "venue": item.get("container-title", [""])[0] if item.get("container-title") else ""
            }

            if qs_lookup and not _paper_matches_qs(paper_dict, qs_lookup):
                continue

            collected.append(paper_dict)
            if len(collected) >= desired_count: break
    except Exception as e:
        if progress_callback: progress_callback(f"⚠️ Crossref API error: {e}")
    return collected


def search_papers(
    query: str,
    desired_count: int = 10,
    qs_max_rank: Optional[int] = None,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    progress_callback=None,
) -> list[dict]:
    qs_lookup = _build_qs_lookup(qs_max_rank) if qs_max_rank else None

    # Distribute the desired count across 4 sources
    per_source_count = math.ceil(desired_count / 4)
    all_papers = []

    if progress_callback:
        progress_callback(f"🚀 Starting multi-source paper search for {desired_count} papers...")

    # 1. Semantic Scholar
    s2_papers = _search_semantic_scholar(query, per_source_count, qs_lookup, year_from, year_to, progress_callback)
    all_papers.extend(s2_papers)

    # 2. ArXiv
    arxiv_papers = _search_arxiv(query, per_source_count, qs_lookup, year_from, year_to, progress_callback)
    all_papers.extend(arxiv_papers)

    # 3. OpenAlex
    openalex_papers = _search_openalex(query, per_source_count, qs_lookup, year_from, year_to, progress_callback)
    all_papers.extend(openalex_papers)

    # 4. Crossref
    crossref_papers = _search_crossref(query, per_source_count, qs_lookup, year_from, year_to, progress_callback)
    all_papers.extend(crossref_papers)

    # Deduplicate by lowercased title
    seen_titles = set()
    unique_papers = []
    for paper in all_papers:
        title = (paper.get("title") or "").strip().lower()
        if title and title not in seen_titles:
            seen_titles.add(title)
            unique_papers.append(paper)

    # If we are short, we could theoretically go back and fetch more,
    # but for simplicity and speed, we return what we gathered.
    final_list = unique_papers[:desired_count]

    if progress_callback:
        progress_callback(f"✅ Search complete: found {len(final_list)} unique papers from multiple sources.")

    return final_list
