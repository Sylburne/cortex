# Cortex MCP Server

MCP (Model Context Protocol) server for integrating Cortex knowledge base into AI assistants like Qoder.

## Installation

```bash
cd cortex-mcp
pip install -r requirements.txt
```

## Configuration

Cortex credentials are read from `~/.cortex/config.json`:

```json
{
  "api_url": "https://cortex-api-cpjo.onrender.com",
  "api_key": "your-api-key-here"
}
```

You can set this up using the Cortex CLI:

```bash
python cli/cortex.py login
```

## Qoder Integration

Add this to your Qoder MCP settings (`.qoder/mcp.json` or via UI):

```json
{
  "mcpServers": {
    "cortex": {
      "command": "python",
      "args": ["c:/Projects/Projrct Aeon/qmind/cortex-mcp/server.py"],
      "cwd": "c:/Projects/Projrct Aeon/qmind/cortex-mcp"
    }
  }
}
```

## Available Tools

### Notebook Management
- `cortex_list_notebooks` - List all notebooks
- `cortex_create_notebook` - Create a new notebook
- `cortex_delete_notebook` - Delete a notebook

### Source Files
- `cortex_list_sources` - List files in a notebook
- `cortex_upload_file` - Upload a file to a notebook
- `cortex_delete_source` - Delete a source file

### Search & Retrieval
- `cortex_search` - Semantic search across notebook
- `cortex_retrieve` - Retrieve chunks grouped by source (for RAG)

### RAG Chat
- `cortex_create_session` - Create a chat session
- `cortex_list_sessions` - List chat sessions
- `cortex_delete_session` - Delete a chat session
- `cortex_chat` - Send message and get RAG response

### AI Review
- `cortex_review` - AI-powered file comparison and update generation
- `cortex_upload_review_results` - Save reviewed files to target notebook

## Example Usage

Once configured in Qoder, you can use natural language:

- "List all my Cortex notebooks"
- "Search my Work Notes notebook for information about machine learning"
- "Chat with my Research notebook about quantum computing"
- "Review and update my Documentation notebook"
