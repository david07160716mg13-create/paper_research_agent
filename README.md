# 📚 Paper Research Agent

A fully local, AI-powered academic paper research assistant. It automatically searches, downloads, and analyzes research papers, then generates a comprehensive HTML report — all running on your own machine using **Ollama** as the LLM backend.

---

## ✨ Features

- 🧠 **Natural language query parsing** via local Ollama models (e.g., `gemma4`, `llama3`)
- 🔍 **Multi-source paper search**:
  - [Semantic Scholar](https://www.semanticscholar.org/) — peer-reviewed journals & conferences
  - [arXiv](https://arxiv.org/) — preprints & cutting-edge research
  - Combined mode (both sources simultaneously)
- 📥 **Automatic PDF download** with Sci-Hub fallback support
- 🤖 **AI-powered analysis** — summarizes each paper's key contributions, methods, and findings
- 📊 **HTML report generation** with structured comparison tables
- 📄 **RAG support** — upload your own research reports for comparative analysis
- 🌐 **Web UI** — clean browser-based interface with real-time progress streaming (SSE)

---

## 🏗️ Architecture

```
paper_research_agent/
├── main.py                  # FastAPI app & pipeline orchestrator
├── config.py                # All configurable settings (Ollama, APIs, paths)
├── requirements.txt
├── run.bat                  # One-click startup script (Windows)
├── agents/
│   ├── query_parser.py      # LLM-based NL → structured query
│   ├── paper_searcher.py    # Semantic Scholar search
│   ├── arxiv_searcher.py    # arXiv search & download
│   ├── pdf_downloader.py    # PDF download + Sci-Hub fallback
│   ├── pdf_analyzer.py      # Text extraction & LLM analysis
│   └── report_generator.py  # HTML + JSON report generation
├── static/
│   └── style.css
├── templates/
│   └── index.html
└── paper_downloads/         # Downloaded PDFs (auto-created, git-ignored)
```

---

## 🚀 Quick Start

### Prerequisites

1. **Python 3.10+**
2. **[Ollama](https://ollama.com/)** installed and running locally
3. At least one Ollama model pulled, e.g.:
   ```bash
   ollama pull gemma4
   # or
   ollama pull llama3
   ```

### Installation

```bash
# Clone the repository
git clone https://github.com/david07160716mg13-create/paper_research_agent.git
cd paper_research_agent

# Install dependencies
pip install -r requirements.txt
```

### Running

**Windows (one-click):**
```
Double-click run.bat
```

**Manual:**
```bash
python main.py
```

Then open your browser at **http://localhost:8000**

---

## 🖥️ Usage

1. **Enter your research query** in plain language, e.g.:
   - `"Find 10 papers on transformer-based NLP published after 2022"`
   - `"Search 5 papers on federated learning from top-ranked venues"`

2. **Select a paper source**: Semantic Scholar / arXiv / Both

3. **(Optional)** Upload your own research report (PDF or TXT) for comparative RAG analysis

4. **(Optional)** Enable **Sci-Hub fallback** to improve PDF download success rate

5. Click **Search** and watch the pipeline run in real time

6. Download the generated **HTML report** when complete

---

## ⚙️ Configuration

Edit `config.py` to customize behavior:

| Setting | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `gemma4` | Default LLM model |
| `DEFAULT_DOWNLOAD_DIR` | `./paper_downloads` | PDF save location |
| `MAX_CHUNK_CHARS` | `6000` | Max characters per LLM prompt chunk |
| `DOWNLOAD_TIMEOUT_SECONDS` | `60` | PDF download timeout |
| `PORT` | `8000` | Web server port |

Environment variables take precedence over defaults:
```bash
set OLLAMA_MODEL=llama3
set OLLAMA_BASE_URL=http://192.168.1.100:11434
python main.py
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Web UI |
| `GET` | `/api/models` | List available Ollama models |
| `POST` | `/api/search` | Start a research task |
| `GET` | `/api/stream/{task_id}` | Real-time progress (SSE) |
| `GET` | `/api/report/{task_id}` | Download HTML report |
| `GET` | `/api/report-json/{task_id}` | Download JSON report |
| `GET` | `/api/tasks` | List all tasks |

---

## 🔒 Privacy

All processing runs **100% locally**:
- No data is sent to any external AI service
- Paper metadata is fetched from public academic APIs (Semantic Scholar, arXiv)
- PDFs are stored only on your local machine

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `fastapi` + `uvicorn` | Web framework & ASGI server |
| `jinja2` | HTML templating |
| `pymupdf` | PDF text extraction |
| `requests` + `aiohttp` | HTTP client |
| `sse-starlette` | Server-Sent Events for real-time logs |
| `arxiv` | arXiv API client |
| `beautifulsoup4` | Sci-Hub page parsing |
| `python-multipart` | File upload support |

---

## 📄 License

MIT License — feel free to use, modify, and distribute.
