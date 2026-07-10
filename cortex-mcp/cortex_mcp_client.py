"""
Cortex API Client for MCP Server.

Clean Python client for the Cortex REST API.
"""

import os
import requests
from typing import Any, Optional


class CortexClient:
    """HTTP client for Cortex API."""

    def __init__(self, api_url: str, api_key: str, timeout: int = 120):
        self.base_url = api_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, **kwargs) -> Any:
        """Make HTTP request to Cortex API."""
        url = f"{self.base_url}{path}"
        kwargs.setdefault("headers", self.headers)
        kwargs.setdefault("timeout", self.timeout)
        
        response = requests.request(method, url, **kwargs)
        response.raise_for_status()
        
        if response.content:
            return response.json()
        return {"status": "ok"}

    # Notebooks
    def list_notebooks(self) -> list[dict]:
        """List all notebooks."""
        result = self._request("GET", "/api/v1/notebooks")
        return result.get("notebooks", [])

    def create_notebook(self, name: str) -> dict:
        """Create a new notebook."""
        return self._request("POST", "/api/v1/notebooks", json={"name": name})

    def delete_notebook(self, notebook_id: str) -> dict:
        """Delete a notebook."""
        return self._request("DELETE", f"/api/v1/notebooks/{notebook_id}")

    # Sources
    def list_sources(self, notebook_id: str) -> list[dict]:
        """List all sources in a notebook."""
        result = self._request("GET", f"/api/v1/notebooks/{notebook_id}/sources")
        return result.get("sources", [])

    def upload_file(self, notebook_id: str, file_path: str) -> dict:
        """Upload a file to a notebook."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        filename = os.path.basename(file_path)
        with open(file_path, "rb") as f:
            # For multipart upload, don't set Content-Type header
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = requests.post(
                f"{self.base_url}/api/v1/notebooks/{notebook_id}/sources",
                headers=headers,
                files={"file": (filename, f)},
                data={"path": file_path},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()

    def delete_source(self, notebook_id: str, source_id: str) -> dict:
        """Delete a source file."""
        return self._request(
            "DELETE",
            f"/api/v1/notebooks/{notebook_id}/sources/{source_id}"
        )

    def download_source(self, notebook_id: str, source_id: str) -> bytes:
        """Download the original file for a source."""
        url = f"{self.base_url}/api/v1/notebooks/{notebook_id}/sources/{source_id}/download"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = requests.get(url, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.content

    def get_source_content(self, notebook_id: str, source_id: str) -> dict:
        """Get extracted text content for a source."""
        return self._request(
            "GET",
            f"/api/v1/notebooks/{notebook_id}/sources/{source_id}/content"
        )

    # Search & Retrieval
    def search(self, notebook_id: str, query: str, top_k: int = 5) -> dict:
        """Semantic search across notebook."""
        return self._request(
            "POST",
            f"/api/v1/notebooks/{notebook_id}/search",
            json={"query": query, "top_k": top_k}
        )

    def retrieve(self, notebook_id: str, query: str, top_k: int = 3) -> dict:
        """Retrieve chunks grouped by source."""
        return self._request(
            "POST",
            f"/api/v1/notebooks/{notebook_id}/retrieve",
            json={"query": query, "top_k": top_k}
        )

    # RAG Chat
    def create_session(
        self,
        notebook_id: str,
        provider: str = "gemini",
        model: str = "gemini-2.0-flash"
    ) -> dict:
        """Create a new RAG chat session."""
        return self._request(
            "POST",
            f"/api/v1/notebooks/{notebook_id}/rag/sessions",
            json={"provider": provider, "model": model}
        )

    def list_sessions(self, notebook_id: str) -> list[dict]:
        """List all sessions for a notebook."""
        result = self._request(
            "GET",
            f"/api/v1/notebooks/{notebook_id}/rag/sessions"
        )
        # Handle both list and paginated response
        if isinstance(result, list):
            return result
        return result.get("sessions", [])

    def delete_session(self, notebook_id: str, session_id: str) -> dict:
        """Delete a chat session."""
        return self._request(
            "DELETE",
            f"/api/v1/notebooks/{notebook_id}/rag/sessions/{session_id}"
        )

    def chat(
        self,
        notebook_id: str,
        message: str,
        session_id: Optional[str] = None,
        provider: str = "gemini",
        model: str = "gemini-2.0-flash"
    ) -> dict:
        """Send message and get RAG response."""
        # Create session if not provided
        if not session_id:
            session = self.create_session(notebook_id, provider, model)
            session_id = session["id"]

        # Send message
        return self._request(
            "POST",
            f"/api/v1/notebooks/{notebook_id}/rag/sessions/{session_id}/messages",
            json={
                "content": message,
                "provider": provider,
                "model": model,
            }
        )

    # Review
    def review(
        self,
        notebook_id: str,
        updated_notebook_id: Optional[str] = None,
        instructions: Optional[str] = None,
        provider: str = "gemini",
        model: str = "gemini-2.0-flash"
    ) -> dict:
        """AI-powered review of notebook files."""
        body = {"provider": provider, "model": model}
        if updated_notebook_id:
            body["updated_notebook_id"] = updated_notebook_id
        if instructions:
            body["instructions"] = instructions

        return self._request(
            "POST",
            f"/api/v1/notebooks/{notebook_id}/review",
            json=body
        )

    def upload_review_results(
        self,
        notebook_id: str,
        target_notebook_id: str,
        review_response: dict
    ) -> dict:
        """Upload reviewed/updated files to target notebook."""
        return self._request(
            "POST",
            f"/api/v1/notebooks/{notebook_id}/review/upload-updated/{target_notebook_id}",
            json=review_response
        )

    # Health check
    def health(self) -> dict:
        """Check API health."""
        return self._request("GET", "/health")
