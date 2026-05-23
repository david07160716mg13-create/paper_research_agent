"""
Paper Research Agent - Configuration
"""
import os

# ─── OLLAMA Settings ───────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4")
OLLAMA_CHAT_ENDPOINT = f"{OLLAMA_BASE_URL}/api/chat"
OLLAMA_TAGS_ENDPOINT = f"{OLLAMA_BASE_URL}/api/tags"

# ─── Semantic Scholar API ──────────────────────────────────
S2_API_BASE = "https://api.semanticscholar.org/graph/v1"
S2_SEARCH_ENDPOINT = f"{S2_API_BASE}/paper/search"
S2_SEARCH_FIELDS = (
    "title,abstract,venue,year,citationCount,"
    "openAccessPdf,authors.name,authors.affiliations,"
    "externalIds,url"
)
S2_RESULTS_PER_PAGE = 100  # max allowed by the API

# ─── OpenAlex API ──────────────────────────────────────────
OPENALEX_SEARCH_ENDPOINT = "https://api.openalex.org/works"

# ─── Crossref API ──────────────────────────────────────────
CROSSREF_SEARCH_ENDPOINT = "https://api.crossref.org/works"

# ─── Sci-Hub ───────────────────────────────────────────────
SCIHUB_BASE_URLS = [
    "https://sci-hub.se",
    "https://sci-hub.st",
    "https://sci-hub.ru",
]

# ─── PDF Download ──────────────────────────────────────────
DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "paper_downloads")
MAX_DOWNLOAD_RETRIES = 3
DOWNLOAD_TIMEOUT_SECONDS = 60

# ─── Analysis ─────────────────────────────────────────────
MAX_CHUNK_CHARS = 6000  # max characters per chunk sent to LLM
ANALYSIS_TEMPERATURE = 0.3

# ─── Server ───────────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 8000
