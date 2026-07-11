# Cortex

Personal AI knowledge base with RAG, vector search, and multi-provider AI. Upload your documents, chat with your knowledge, and let AI help you organize, search, and update your information.

## Features

### Knowledge Management
- **Notebooks** — Organize documents into isolated knowledge bases
- **Document Upload** — PDF, DOCX, PPTX, Markdown, TXT, PNG, JPG, GIF, SVG, WEBP
- **Auto-Processing** — Parse → chunk → embed pipeline runs automatically on upload
- **Binary Storage** — Original files preserved for download (PDFs, images, etc.)

### Search & Retrieval
- **Vector Search** — Semantic search across your knowledge using pgvector with HNSW indexing
- **Hybrid Retrieval** — Combine keyword and semantic matching for accurate results
- **RAG Q&A** — Chat with your documents, get AI answers with source citations

### AI Features
- **Multi-Provider** — OpenAI, Anthropic, Gemini, HuggingFace, Qwen (DashScope), Ollama
- **AI Review** — Compare notebooks, generate updated files with AI
- **Knowledge Compilation** — Compile knowledge into structured cards
- **Honcho Memory** — Persistent user memory across sessions (optional)

### Integration
- **MCP Server** — Native integration with AI assistants (Qoder, Claude, etc.)
- **CLI** — Full-featured interactive terminal with filesystem + knowledge base access
- **REST API** — Complete API for building custom integrations

## Architecture

```
Client (CLI / MCP / API)
    |
    v
Cortex API (FastAPI on Render)
    |
    +-- Neon Postgres (pgvector + HNSW)
    |       |
    |       +-- notebooks, sources, chunks tables
    |       +-- vector embeddings (1536-dim)
    |
    +-- AI Providers (OpenAI / Gemini / Anthropic / Ollama)
    |
    +-- Honcho (optional memory layer)
```

## Quick Start

### Deploy to Render (free)

1. **Create a Neon database** at [neon.tech](https://neon.tech) — enable pgvector
2. **Deploy to Render** using the `render.yaml` blueprint or manually:
   - Root directory: `backend`
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. **Set environment variables**: `DATABASE_URL`, `API_KEY`, `OPENAI_API_KEY`
4. **Your API is live!** See [DEPLOY.md](DEPLOY.md) for detailed instructions.

### Install the CLI

```bash
cd cli
pip install -r requirements.txt
python cortex.py
```

### Connect via MCP

Add to your AI assistant's MCP config:

```json
{
  "mcpServers": {
    "cortex": {
      "command": "python",
      "args": ["cortex-mcp/server.py"],
      "cwd": "cortex-mcp"
    }
  }
}
```

## CLI Usage

The Cortex CLI is an interactive AI agent terminal:

```
$ cortex

Cortex v0.1.0 | Workspace: ~/projects | Notebook: Project Aeon Research

Commands:
  ls, cd, pwd, cat, read, write, mkdir, rm, tree    Filesystem
  /kb list|create|upload|search|select|status        Knowledge Base
  /ask <question>                                     AI Query
  /chat                                               Interactive Chat
  /workspace <path>                                   Set working directory
  /login, /status, /help, /quit                       Session

> /ask What are the key specs of the dilution refrigerator?

AI (gemini/gemini-2.0-flash):
  Based on the Aeon-Graphene Material Spec Sheet, the dilution
  refrigerator operates at 10mK base temperature with a cooling
  power of 400uW at 100mK...
  Sources:
    - Aeon-Graphene Material Spec Sheet.docx (score: 0.94)
    - A cutaway internal diagram of the dilution refrigerator.png (score: 0.87)
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Service info |
| GET | `/health` | Health check |
| POST | `/api/v1/notebooks` | Create notebook |
| GET | `/api/v1/notebooks` | List notebooks |
| GET | `/api/v1/notebooks/{id}` | Get notebook |
| DELETE | `/api/v1/notebooks/{id}` | Delete notebook |
| POST | `/api/v1/notebooks/{id}/sources` | Upload file |
| GET | `/api/v1/notebooks/{id}/sources` | List sources |
| GET | `/api/v1/notebooks/{id}/sources/{sid}/download` | Download original file |
| DELETE | `/api/v1/notebooks/{id}/sources/{id}` | Delete source |
| POST | `/api/v1/notebooks/{id}/search` | Vector search |
| POST | `/api/v1/notebooks/{id}/retrieve` | Semantic retrieval |
| POST | `/api/v1/notebooks/{id}/rag/sessions` | Create RAG session |
| POST | `/api/v1/notebooks/{id}/rag/sessions/{sid}/messages` | Send RAG message |
| POST | `/api/v1/notebooks/{id}/review` | AI review files |
| POST | `/api/v1/notebooks/{id}/review/upload-updated/{target}` | Save reviewed files |
| GET | `/api/v1/memory/status` | Honcho memory status |
| POST | `/api/v1/memory/insights` | User insights (Honcho) |
| POST | `/api/v1/memory/context` | Session context (Honcho) |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI (Python 3.11+) |
| Database | PostgreSQL + pgvector (Neon) |
| Vector Index | HNSW (cosine similarity) |
| Embeddings | OpenAI / Gemini / HuggingFace / Ollama |
| LLM | OpenAI / Anthropic / Gemini / HuggingFace / Qwen / Ollama |
| Memory | Honcho (optional) |
| CLI | Python + Rich + Prompt Toolkit |
| MCP | Python MCP SDK |
| Deployment | Render (free tier) |

## Supported Providers

| Provider | Embeddings | Chat | Setup |
|----------|-----------|------|-------|
| OpenAI | ✓ | ✓ | `OPENAI_API_KEY` |
| Anthropic | — | ✓ | `ANTHROPIC_API_KEY` |
| Gemini | ✓ | ✓ | `GOOGLE_API_KEY` |
| HuggingFace | ✓ | ✓ | `HUGGINGFACE_API_KEY` |
| Qwen (DashScope) | ✓ | ✓ | `QWEN_API_KEY` |
| Ollama | ✓ | ✓ | `OLLAMA_BASE_URL` |

## Supported File Types

| Format | Extensions | Text Extraction | Binary Storage |
|--------|-----------|----------------|----------------|
| PDF | `.pdf` | ✓ (pymupdf) | ✓ |
| Word | `.docx` | ✓ (python-docx) | ✓ |
| PowerPoint | `.pptx` | ✓ (python-pptx) | ✓ |
| Markdown | `.md`, `.mdx` | ✓ | — |
| Text | `.txt` | ✓ | — |
| PNG | `.png` | — | ✓ |
| JPEG | `.jpg`, `.jpeg` | — | ✓ |
| GIF | `.gif` | — | ✓ |
| SVG | `.svg` | — | ✓ |
| WebP | `.webp` | — | ✓ |

## Cost

| Service | Free Tier | Cost |
|---------|-----------|------|
| Render | 512MB RAM | $0 |
| Neon | 0.5GB storage | $0 |
| AI API | Pay per token | ~$0.01-0.10/query |
| Honcho | $100 credits | $0 (initial) |

**Total: $0 hosting + your AI API keys**

## License

MIT
