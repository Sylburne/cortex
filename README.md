# Cortex — Personal AI Knowledge Base

Cortex is your **personal AI knowledge base** a self-hosted RAG system that lets you upload documents, chat with your knowledge, and keep AI-powered notes organized across notebooks. Built for individuals who want their own AI-augmented second brain, not a team wiki.

Think of it as **Notion meets ChatGPT, but you own it** your documents, your API keys, your data. Deploy for free on Render, connect your preferred AI provider, and access everything through a terminal-native CLI, MCP server, or REST API.

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

### Connect via MCP (AI Assistant Integration)

Cortex exposes a full MCP (Model Context Protocol) server so AI assistants can directly search, chat, and manage your knowledge base.

> **Prerequisite:** Run `cortex login` first to configure your credentials. The MCP server reads from `~/.cortex/config.json`.

All setups use the same server configuration — replace `/path/to/cortex` with the actual path to your cortex repository.

```json
{
  "mcpServers": {
    "cortex": {
      "command": "python",
      "args": ["/path/to/cortex/cortex-mcp/server.py"],
      "cwd": "/path/to/cortex/cortex-mcp"
    }
  }
}
```

#### Qoder

Add to `.qoder/mcp.json` or via the MCP settings UI.

#### Claude Desktop

Add to `claude_desktop_config.json` (`%APPDATA%\Claude` on Windows, `~/Library/Application Support/Claude` on macOS).

#### VS Code / GitHub Copilot

Add to `.vscode/mcp.json` in your workspace or use the Copilot Chat MCP settings.

#### Gemini CLI

Add to `~/.gemini/mcp.json` or pass via `gemini mcp add cortex -- python /path/to/cortex/cortex-mcp/server.py`.

#### OpenAI Codex CLI

Add to `~/.codex/mcp.json` or use `codex mcp add cortex -- python /path/to/cortex/cortex-mcp/server.py`.

#### Generic / Other MCP Clients

Add the server block above to any MCP-compatible client's `mcp.json` configuration file. Works with any tool that supports the Model Context Protocol — Cursor, Continue.dev, Zed, Goose, and others.

#### Available MCP Tools

| Category | Tool | Description |
|----------|------|-------------|
| Notebooks | `cortex_list_notebooks` | List all notebooks |
| | `cortex_create_notebook` | Create a new notebook |
| | `cortex_delete_notebook` | Delete a notebook |
| Sources | `cortex_list_sources` | List files in a notebook |
| | `cortex_upload_file` | Upload a file to a notebook |
| | `cortex_delete_source` | Delete a source file |
| Search | `cortex_search` | Semantic search across notebook |
| | `cortex_retrieve` | Retrieve chunks grouped by source |
| Chat | `cortex_create_session` | Create a RAG chat session |
| | `cortex_list_sessions` | List chat sessions |
| | `cortex_delete_session` | Delete a chat session |
| | `cortex_chat` | Send message and get RAG response |
| Review | `cortex_review` | AI-powered file comparison |
| | `cortex_upload_review_results` | Save reviewed files |

## CLI Usage

The Cortex CLI is an interactive AI agent terminal with tab-completion, filesystem access, and knowledge base management:

```
$ cortex
   ██████╗ ██████╗ ██████╗ ████████╗███████╗██╗  ██╗
  ██╔════╝██╔═══██╗██╔══██╗╚══██╔══╝██╔════╝╚██╗██╔╝
  ██║     ██║   ██║██████╔╝   ██║   █████╗   ╚███╔╝
  ██║     ██║   ██║██╔══██╗   ██║   ██╔══╝   ██╔██╗
  ╚██████╗╚██████╔╝██║  ██║   ██║   ███████╗██╔╝ ██╗
   ╚═════╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝

  Personal AI Knowledge Base — v0.1.0

  ● Online       https://cortex-api-cpjo.onrender.com
  ▣ Notebook     Project Aeon Research  (12 sources)
  ◆ AI           gemini / gemini-2.0-flash
  ◇ Workspace    ~/projects

cortex [~/projects] (Project Aeon Research)>

> /model
  #  Provider    Model
  1  gemini      gemini-2.0-flash
  2  gemini      gemini-2.5-pro
  ...
  Pick model (name or number): 2
  Model set to: gemini-2.5-pro

> /ask What are the key specs of the dilution refrigerator?

AI (gemini/gemini-2.5-pro):
  Based on the Aeon-Graphene Material Spec Sheet, the dilution
  refrigerator operates at 10mK base temperature with a cooling
  power of 400uW at 100mK...
  Sources:
    - Aeon-Graphene Material Spec Sheet.docx (score: 0.94)
    - A cutaway internal diagram of the dilution refrigerator.png (score: 0.87)
```

### Command Reference

| Category | Command | Description |
|----------|---------|-------------|
| **Filesystem** | `ls [path]` | List directory contents |
| | `cd [path]` | Change working directory |
| | `pwd` | Show working directory |
| | `cat <file>` | Display file with syntax highlighting |
| | `read <file>` | Read file contents |
| | `write <file>` | Create/edit a file |
| | `mkdir <dir>` | Create directory |
| | `rm <path>` | Remove file or directory |
| | `tree [path]` | Show directory tree |
| **Knowledge Base** | `/kb list` | List all notebooks |
| | `/kb create <name>` | Create a new notebook |
| | `/kb upload <file...>` | Upload files to active notebook |
| | `/kb search <query>` | Semantic search |
| | `/kb select <id>` | Set active notebook |
| | `/kb status` | Show active notebook info |
| **AI** | `/ask <question>` | Ask AI with knowledge base context |
| | `/chat` | Enter interactive chat mode |
| | `/model` | Interactive model picker |
| | `/model <name>` | Set model directly |
| | `/provider` | Interactive provider picker |
| | `/provider <name>` | Set provider directly |
| | `/provider add <name> <api_base> <key>` | Add custom provider |
| | `/provider remove <key>` | Remove custom provider |
| | `/provider list` | List all providers |
| **Settings & Sync** | `/settings` | Interactive settings menu |
| | `/deploy` | Trigger Render deploy |
| | `/sync github` | Push config to GitHub |
| | `/sync render` | Alias for /deploy |
| | `/honcho` | Show Honcho memory status |
| | `/honcho enable <key>` | Enable Honcho |
| | `/honcho disable` | Disable Honcho |
| **Session** | `/login` | Configure connection |
| | `/workspace <path>` | Set working directory |
| | `/status` | Show full status |
| | `/help` | Show command help |
| | `/quit` | Exit CLI |

### Tab Completion

Press **TAB** to auto-complete:
- `/` shows all slash commands
- `/kb ` shows knowledge base sub-commands
- `/model ` shows available models
- `/provider ` shows available providers
- File paths auto-complete for `ls`, `cd`, `cat`, `read`, `write`, `rm`, `tree`

### Custom Providers

Add any OpenAI-compatible API as a custom provider:

```
> /provider add "My LLM" https://api.example.com/v1 sk-xxx
  Added custom provider: My LLM (my-llm)

> /provider
  #  Key        Description
  1  gemini     Google Gemini           (google_api_key)
  2  openai     OpenAI                  (openai_api_key)
  3  my-llm     My LLM (custom: https://api.example.com/v1)

> /provider my-llm
  Provider set to: my-llm
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
