# 🔥 Failure Memory Copilot

An intelligent failure memory system that transforms recurring software failures into searchable organizational knowledge. It normalizes incoming error logs, retrieves the most relevant historical resolutions using semantic search, and falls back to LLM-powered suggestions via Groq whenever no confident match is found.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [Usage](#usage)
  - [Streamlit UI](#streamlit-ui)
  - [CLI — Analyze Errors](#cli--analyze-errors)
  - [CLI — Add Incidents](#cli--add-incidents)
- [API Reference](#api-reference)
- [How It Works](#how-it-works)
- [Configuration](#configuration)
- [Knowledge Base](#knowledge-base)

---

## Overview

Software failures often repeat across applications, yet engineers spend valuable time rediscovering solutions to issues that have already been resolved. Failure Memory Copilot acts as an **organizational memory** by normalizing raw error logs with an LLM, retrieving the most relevant historical incidents through semantic search (RAG), and presenting ranked resolutions in an interactive human-in-the-loop review workflow. When no suitable historical match exists, it generates context-aware suggestions using Groq.
---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Streamlit Chat UI                           │
│              (multi-chat, screenshot OCR upload)                │
└──────────────────────────┬──────────────────────────────────────┘
                           │  HTTP (localhost:8501 → :8000)
┌──────────────────────────▼──────────────────────────────────────┐
│                     FastAPI Server                              │
│         /analyze   /respond   /extract   /health                │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                   LangGraph Pipeline                            │
│                                                                 │
│  normalize_error ──► analyze_code ──► normalize_resolution      │
│         │                                     │                 │
│         ▼                                     ▼                 │
│  retrieve_candidates (ChromaDB) ──► rag_rank_candidates (Groq)  │
│         │                                                       │
│         ▼                                                       │
│  present_and_confirm  ◄──► (human-in-the-loop interrupt)        │
│    │       │       │                                            │
│    ▼       ▼       ▼                                            │
│  Accept   Next   Groq Suggest ──► groq_suggest_node ──► END     │
└─────────────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  ChromaDB Vector Store          │   incidents.json (JSON KB)    │
│  (BAAI/bge-base-en-v1.5)       │   12 curated incidents        │
└─────────────────────────────────┴───────────────────────────────┘
```

---

## Key Features

| Feature | Description |
|---|---|
| **LLM Error Normalization** | Strips stack frames, memory addresses, and noise — extracts clean error messages, severity, and tags using Groq (Llama 3.1) |
| **Code Context Analysis** | When code is provided, identifies the structural pattern (wrong API, missing operation) that caused the failure |
| **RAG-Based Retrieval** | Semantic search over historical incidents using sentence-transformers (`bge-base-en-v1.5`) + ChromaDB |
| **LLM Re-Ranking** | Groq re-ranks retrieved candidates for relevance and assigns a confidence score |
| **Human-in-the-Loop** | Interactive review loop — accept, skip, request Groq suggestion, or quit — powered by LangGraph interrupts |
| **Groq Fallback** | When no historical match is confident enough, Groq generates a novel suggestion based on the error and code |
| **Screenshot OCR** | Upload error screenshots — Tesseract extracts text, Groq separates error vs. code |
| **Multi-Chat UI** | Streamlit chat interface with session management, dark theme, and IBM Plex Mono typography |
| **Duplicate Detection** | When adding new incidents, the system detects near-duplicates via RAG similarity before writing |
| **CLI Tools** | Full CLI for both analyzing errors and adding new incidents to the knowledge base |

---

## Tech Stack

| Layer | Technology |
|---|---|
| **LLM** | [Groq](https://groq.com/) — Llama 3.1 8B Instant / Llama 3.3 70B Versatile |
| **Orchestration** | [LangGraph](https://github.com/langchain-ai/langgraph) — stateful multi-step pipeline with human-in-the-loop |
| **Embeddings** | [sentence-transformers](https://www.sbert.net/) — `BAAI/bge-base-en-v1.5` |
| **Vector Store** | [ChromaDB](https://www.trychroma.com/) — persistent local vector database |
| **Backend** | [FastAPI](https://fastapi.tiangolo.com/) + Uvicorn |
| **Frontend** | [Streamlit](https://streamlit.io/) — chat-based UI |
| **OCR** | [Tesseract](https://github.com/tesseract-ocr/tesseract) + Pillow |
| **Language** | Python 3.13+ |

---

## Project Structure

```
Databricks_Failure_Memory_Copilot/
├── app/                          # Core application logic
│   ├── main.py                   # CLI entry point — analyze errors
│   ├── add_incident.py           # CLI entry point — add incidents to KB
│   ├── graph.py                  # LangGraph pipeline definition (main + add-incident graphs)
│   ├── groq_normalizer.py        # Groq LLM calls — error/code/resolution normalization
│   ├── knowledge_base.py         # JSON knowledge base I/O and validation
│   ├── matcher.py                # (Legacy) TF-IDF + cosine similarity matcher
│   ├── utils.py                  # Text cleaning, error extraction, output formatting
│   └── rag/                      # RAG subsystem
│       ├── embedder.py           # Sentence-transformer embedding wrapper
│       ├── vector_store.py       # ChromaDB client and CRUD operations
│       ├── index_builder.py      # One-time script to index incidents into ChromaDB
│       ├── retriever.py          # Semantic retrieval from vector store
│       └── rag_ranker.py         # Groq-based re-ranking of retrieved candidates
│
├── server/                       # FastAPI backend
│   ├── main.py                   # API routes — /analyze, /respond, /extract, /health
│   └── ocr_extractor.py          # Tesseract OCR + Groq text separation
│
├── UI/                           # Frontend
│   └── streamlit_app.py          # Streamlit multi-chat interface
│
├── data/                         # Data layer
│   ├── incidents.json            # Historical incident knowledge base (12 incidents)
│   └── vector_index/             # ChromaDB persistent storage (gitignored)
│
├── tests/
│   └── test_matcher.py           # Unit tests
│
├── config.py                     # Central configuration — all tuneable parameters
├── requirements.txt              # Python dependencies
├── pyproject.toml                # Project metadata (uv / pip)
└── .gitignore
```

---

## Setup & Installation

### Prerequisites

- **Python 3.13+**
- **Tesseract OCR** — install and ensure it's on your `PATH`
  - Windows: [UB Mannheim installer](https://github.com/UB-Mannheim/tesseract/wiki)
  - macOS: `brew install tesseract`
  - Linux: `sudo apt install tesseract-ocr`
- **Groq API Key** — sign up at [console.groq.com](https://console.groq.com/)

### Install

```bash
# Clone the repository
git clone https://github.com/Shivansh-Raj/Databricks_Failure_Memory_Copilot.git
cd Databricks_Failure_Memory_Copilot

# Create and activate virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=gsk_your_api_key_here

```

### Build the Vector Index

Before first use, index the knowledge base into ChromaDB:

```bash
python app/rag/index_builder.py
```

---

## Usage

### Streamlit UI

The primary interface is a chat-based web UI. Start both the backend and frontend:

```bash
# Terminal 1 — FastAPI server
uvicorn server.main:app --reload --port 8000

# Terminal 2 — Streamlit app
streamlit run UI/streamlit_app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

**Workflow:**
1. Paste an error message (and optionally code) — **or** upload a screenshot
2. The pipeline normalizes the error, retrieves similar historical incidents, and presents the best match
3. Review each candidate:
   - **✅ Accept** — use this resolution
   - **⏭ Next** — skip to the next candidate
   - **🤖 Groq** — get an LLM-generated suggestion
   - **🚪 Quit** — exit the review loop

### CLI — Analyze Errors

```bash
# From raw text
python app/main.py --error-text "OutOfMemoryError: Java heap space during shuffle"

# From a file
python app/main.py --error-file error.log

# With code context
python app/main.py --error-text "AnalysisException: table not found" --code-file job.py

# Skip Groq normalization
python app/main.py --error-text "OOM error" --no-groq
```

### CLI — Add Incidents

```bash
# Full flow with code analysis
python app/add_incident.py \
  --error-file error.log \
  --code-file job.py \
  --resolution "Increased executor memory and added repartition before join"

# Dry run (preview without writing)
python app/add_incident.py \
  --error-text "OutOfMemoryError: Java heap space" \
  --resolution "Increase executor memory to 16g" \
  --dry-run

# Skip Groq normalization
python app/add_incident.py \
  --error-text "OOM error" \
  --resolution "Add more memory" \
  --no-groq
```

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/analyze` | `POST` | Start a new analysis session. Body: `{ "error_text": str, "code_text": str? }` |
| `/respond` | `POST` | Continue an interactive session. Body: `{ "session_id": str, "choice": "y\|n\|g\|q" }` |
| `/extract` | `POST` | OCR extract from screenshots. Multipart form with 1–2 image files |
| `/status/{session_id}` | `GET` | Check if a session is awaiting input or resolved |
| `/health` | `GET` | Health check — returns `{ "status": "ok" }` |

---

## How It Works

### Main Analysis Pipeline (LangGraph)

1. **`normalize_error`** — Groq cleans the raw error into a structured format: normalized message, tags (e.g. `oom`, `dlt`, `schema`), and severity (`low` / `medium` / `high` / `critical`)

2. **`analyze_code`** — If code is provided, Groq identifies the structural pattern: operation type, APIs used, the specific wrong API or missing operation, and likely hotspot

3. **`normalize_resolution`** — If a resolution is provided (add-incident flow), normalizes it into consistent `Root cause: ... Fix: ...` prose

4. **`retrieve_candidates`** — Embeds the normalized error using `bge-base-en-v1.5` and queries ChromaDB for the top 5 most similar historical incidents

5. **`rag_rank_candidates`** — Groq re-ranks the candidates, selects the best match, assigns a confidence score, and extracts the resolution

6. **`present_and_confirm`** — Human-in-the-loop interrupt: presents the top candidate and waits for user input (accept / next / groq / quit)

7. **`groq_suggest`** — If confidence is low or the user requests it, Groq generates a novel resolution based on the full error and code context

### Add-Incident Pipeline

A separate LangGraph pipeline for adding new incidents:
1. Normalizes error, code, and resolution through the same Groq nodes
2. Checks for duplicates via RAG similarity (threshold: 0.8)
3. Warns if a near-duplicate exists, otherwise allows writing to `incidents.json`

---

## Configuration

All tuneable parameters are centralized in [`config.py`](config.py):

| Parameter | Default | Description |
|---|---|---|
| `TOP_N_RESULTS` | `3` | Number of top results to return |
| `MIN_SIMILARITY_THRESHOLD` | `0.15` | Minimum cosine similarity to surface a result |
| `MAX_ERROR_CHARS` | `4000` | Max characters of error text to process |
| `TAIL_LINES` | `100` | Lines from end of log to inspect |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | Primary Groq model |
| `GROQ_MODEL_2` | `llama-3.3-70b-versatile` | Secondary Groq model |
| `GROQ_TIMEOUT` | `60` | Groq API timeout (seconds) |
| `GROQ_MAX_TOKENS` | `800` | Max tokens per Groq response |

---

## Knowledge Base

The knowledge base is stored in [`data/incidents.json`](data/incidents.json) and contains a curated collection of historical software failure incidents used for semantic retrieval and resolution matching. The current knowledge base primarily consists of Databricks and Apache Spark incidents, serving as sample data that demonstrates the system's retrieval and recommendation capabilities.

- **OOM / Memory** — Heap space during shuffle, driver OOM from `.collect()`
- **DLT Pipelines** — Table not found, circular dependencies, streaming/batch mode mismatch
- **Schema Issues** — Type casting failures, missing columns, schema evolution
- **Data Quality** — Expectation violations, silent data loss, null handling
- **Streaming** — State growth, checkpoint corruption, watermark configuration

Each incident includes: normalized error message, resolution, tags, severity, and optional code context (operation type, APIs used, pattern, hotspot).

---

## License

This project is for educational and internal use.
