#!/usr/bin/env python3
"""
Cortex MCP Server - Integrates Cortex knowledge base into AI assistants.

Provides tools for:
- Managing notebooks (list, create, delete)
- Uploading and managing source files
- Semantic search across knowledge
- RAG-powered chat conversations
- AI-powered file review and updates
"""

import os
import json
import sys
from typing import Any
from pathlib import Path

# Load config
CONFIG_DIR = os.path.expanduser("~/.cortex")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


def load_config() -> dict[str, Any]:
    """Load Cortex configuration."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def get_cortex_client():
    """Get configured Cortex client."""
    from cortex_mcp_client import CortexClient
    config = load_config()
    if not config.get("api_url") or not config.get("api_key"):
        raise ValueError(
            "Cortex not configured. Run: cortex login "
            f"or create {CONFIG_FILE} with api_url and api_key"
        )
    return CortexClient(config["api_url"], config["api_key"])


# MCP Server setup
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("Warning: mcp package not installed. Install with: pip install mcp", file=sys.stderr)


if MCP_AVAILABLE:
    server = Server("cortex")

    # Define all tools
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="cortex_list_notebooks",
                description="List all notebooks in Cortex knowledge base",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="cortex_create_notebook",
                description="Create a new notebook in Cortex",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name for the new notebook",
                        },
                    },
                    "required": ["name"],
                },
            ),
            Tool(
                name="cortex_delete_notebook",
                description="Delete a notebook from Cortex",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "notebook_id": {
                            "type": "string",
                            "description": "ID of the notebook to delete",
                        },
                    },
                    "required": ["notebook_id"],
                },
            ),
            Tool(
                name="cortex_list_sources",
                description="List all source files in a notebook",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "notebook_id": {
                            "type": "string",
                            "description": "ID of the notebook",
                        },
                    },
                    "required": ["notebook_id"],
                },
            ),
            Tool(
                name="cortex_upload_file",
                description="Upload a file to a notebook for processing",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "notebook_id": {
                            "type": "string",
                            "description": "ID of the notebook",
                        },
                        "file_path": {
                            "type": "string",
                            "description": "Path to the file to upload",
                        },
                    },
                    "required": ["notebook_id", "file_path"],
                },
            ),
            Tool(
                name="cortex_delete_source",
                description="Delete a source file from a notebook",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "notebook_id": {
                            "type": "string",
                            "description": "ID of the notebook",
                        },
                        "source_id": {
                            "type": "string",
                            "description": "ID of the source to delete",
                        },
                    },
                    "required": ["notebook_id", "source_id"],
                },
            ),
            Tool(
                name="cortex_search",
                description="Perform semantic search across a notebook's knowledge",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "notebook_id": {
                            "type": "string",
                            "description": "ID of the notebook to search",
                        },
                        "query": {
                            "type": "string",
                            "description": "Search query",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of results to return (default: 5)",
                            "default": 5,
                        },
                    },
                    "required": ["notebook_id", "query"],
                },
            ),
            Tool(
                name="cortex_retrieve",
                description="Retrieve relevant chunks for RAG (grouped by source)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "notebook_id": {
                            "type": "string",
                            "description": "ID of the notebook",
                        },
                        "query": {
                            "type": "string",
                            "description": "Query for retrieval",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of source groups (default: 3)",
                            "default": 3,
                        },
                    },
                    "required": ["notebook_id", "query"],
                },
            ),
            Tool(
                name="cortex_chat",
                description="Chat with AI using RAG over notebook knowledge",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "notebook_id": {
                            "type": "string",
                            "description": "ID of the notebook",
                        },
                        "message": {
                            "type": "string",
                            "description": "User message/question",
                        },
                        "session_id": {
                            "type": "string",
                            "description": "Optional session ID to continue conversation",
                        },
                        "provider": {
                            "type": "string",
                            "description": "AI provider (gemini/openai/qwen/huggingface/ollama/anthropic)",
                            "default": "gemini",
                        },
                        "model": {
                            "type": "string",
                            "description": "AI model name",
                            "default": "gemini-2.0-flash",
                        },
                    },
                    "required": ["notebook_id", "message"],
                },
            ),
            Tool(
                name="cortex_create_session",
                description="Create a new RAG chat session",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "notebook_id": {
                            "type": "string",
                            "description": "ID of the notebook",
                        },
                        "provider": {
                            "type": "string",
                            "description": "AI provider",
                            "default": "gemini",
                        },
                        "model": {
                            "type": "string",
                            "description": "AI model name",
                            "default": "gemini-2.0-flash",
                        },
                    },
                    "required": ["notebook_id"],
                },
            ),
            Tool(
                name="cortex_list_sessions",
                description="List all chat sessions for a notebook",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "notebook_id": {
                            "type": "string",
                            "description": "ID of the notebook",
                        },
                    },
                    "required": ["notebook_id"],
                },
            ),
            Tool(
                name="cortex_delete_session",
                description="Delete a chat session",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "notebook_id": {
                            "type": "string",
                            "description": "ID of the notebook",
                        },
                        "session_id": {
                            "type": "string",
                            "description": "ID of the session to delete",
                        },
                    },
                    "required": ["notebook_id", "session_id"],
                },
            ),
            Tool(
                name="cortex_review",
                description="AI-powered review: compare notebooks and generate updated files",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "notebook_id": {
                            "type": "string",
                            "description": "Original notebook ID",
                        },
                        "updated_notebook_id": {
                            "type": "string",
                            "description": "Optional updated notebook for comparison",
                        },
                        "instructions": {
                            "type": "string",
                            "description": "Custom instructions for the review",
                        },
                        "provider": {
                            "type": "string",
                            "description": "AI provider",
                            "default": "gemini",
                        },
                        "model": {
                            "type": "string",
                            "description": "AI model name",
                            "default": "gemini-2.0-flash",
                        },
                    },
                    "required": ["notebook_id"],
                },
            ),
            Tool(
                name="cortex_upload_review_results",
                description="Save AI-reviewed updated files to a target notebook",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "notebook_id": {
                            "type": "string",
                            "description": "Original notebook ID",
                        },
                        "target_notebook_id": {
                            "type": "string",
                            "description": "Target notebook ID to save updated files",
                        },
                        "review_response": {
                            "type": "object",
                            "description": "The review response from cortex_review",
                        },
                    },
                    "required": ["notebook_id", "target_notebook_id", "review_response"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        try:
            client = get_cortex_client()
        except ValueError as e:
            return [TextContent(type="text", text=f"Error: {e}")]

        try:
            if name == "cortex_list_notebooks":
                result = client.list_notebooks()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "cortex_create_notebook":
                result = client.create_notebook(arguments["name"])
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "cortex_delete_notebook":
                result = client.delete_notebook(arguments["notebook_id"])
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "cortex_list_sources":
                result = client.list_sources(arguments["notebook_id"])
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "cortex_upload_file":
                result = client.upload_file(
                    arguments["notebook_id"],
                    arguments["file_path"]
                )
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "cortex_delete_source":
                result = client.delete_source(
                    arguments["notebook_id"],
                    arguments["source_id"]
                )
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "cortex_search":
                result = client.search(
                    arguments["notebook_id"],
                    arguments["query"],
                    arguments.get("top_k", 5)
                )
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "cortex_retrieve":
                result = client.retrieve(
                    arguments["notebook_id"],
                    arguments["query"],
                    arguments.get("top_k", 3)
                )
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "cortex_chat":
                result = client.chat(
                    arguments["notebook_id"],
                    arguments["message"],
                    arguments.get("session_id"),
                    arguments.get("provider", "gemini"),
                    arguments.get("model", "gemini-2.0-flash")
                )
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "cortex_create_session":
                result = client.create_session(
                    arguments["notebook_id"],
                    arguments.get("provider", "gemini"),
                    arguments.get("model", "gemini-2.0-flash")
                )
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "cortex_list_sessions":
                result = client.list_sessions(arguments["notebook_id"])
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "cortex_delete_session":
                result = client.delete_session(
                    arguments["notebook_id"],
                    arguments["session_id"]
                )
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "cortex_review":
                result = client.review(
                    arguments["notebook_id"],
                    arguments.get("updated_notebook_id"),
                    arguments.get("instructions"),
                    arguments.get("provider", "gemini"),
                    arguments.get("model", "gemini-2.0-flash")
                )
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "cortex_upload_review_results":
                result = client.upload_review_results(
                    arguments["notebook_id"],
                    arguments["target_notebook_id"],
                    arguments["review_response"]
                )
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    async def main():
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    if __name__ == "__main__":
        import asyncio
        asyncio.run(main())
