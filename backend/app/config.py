from __future__ import annotations

from pydantic_settings import BaseSettings


def _to_asyncpg_url(url: str) -> str:
    """Convert Neon/Supabase postgresql:// URLs to postgresql+asyncpg://.

    Neon returns:  postgresql://user:pass@host/db?sslmode=require
    asyncpg needs: postgresql+asyncpg://user:pass@host/db?ssl=require
    """
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        converted = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        # asyncpg uses ssl=require, not sslmode=require
        converted = converted.replace("sslmode=require", "ssl=require")
        return converted
    return url


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://localhost:5432/cortex"

    # Redis (empty string = use in-memory job tracking, no Redis)
    redis_url: str = ""

    # Auth
    api_key: str = "dev-api-key-change-me"
    secret_key: str = "dev-secret-key-change-me"

    # Embedding config
    embedding_provider: str = "openai"  # openai | ollama | huggingface | gemini
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Default LLM config
    default_llm_provider: str = "openai"  # openai | anthropic | ollama | gemini | huggingface | qwen
    default_llm_model: str = "gpt-4o"

    # Provider credentials
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""  # Gemini
    huggingface_api_key: str = ""  # HuggingFace Inference API
    qwen_api_key: str = ""  # Alibaba Cloud DashScope
    ollama_base_url: str = "http://localhost:11434"
    ollama_api_key: str = ""  # For cloud-hosted Ollama (optional)

    # Chunking config
    chunk_size_tokens: int = 800
    chunk_overlap_tokens: int = 150

    # RAG config
    rag_top_k: int = 5
    rag_similarity_threshold: float = 0.7

    # File upload
    max_upload_size_mb: int = 100

    # Honcho memory layer (optional — empty key disables)
    honcho_api_key: str = ""
    honcho_base_url: str = ""  # Leave empty for managed (api.honcho.dev)
    honcho_workspace_id: str = "cortex"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def asyncpg_url(self) -> str:
        return _to_asyncpg_url(self.database_url)


settings = Settings()
