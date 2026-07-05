"""Multi-provider embedding service."""
from app.config import settings
import httpx


class BaseEmbeddingProvider:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.embedding_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = await self.client.embeddings.create(input=texts, model=self.model)
        return [item.embedding for item in resp.data]


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self):
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.embedding_model
        self.api_key = settings.ollama_api_key

    async def embed(self, texts: list[str]) -> list[list[float]]:
        results = []
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient() as client:
            for text in texts:
                resp = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                    headers=headers,
                )
                resp.raise_for_status()
                results.append(resp.json()["embedding"])
        return results


class HuggingFaceEmbeddingProvider(BaseEmbeddingProvider):
    """HuggingFace Inference API for sentence-transformer models."""
    def __init__(self):
        self.model = settings.embedding_model or "sentence-transformers/all-MiniLM-L6-v2"
        self.api_key = settings.huggingface_api_key
        self.api_url = f"https://api-inference.huggingface.co/models/{self.model}"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        results = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            # HuggingFace feature-extraction endpoint
            resp = await client.post(
                self.api_url,
                json={"inputs": texts, "options": {"wait_for_model": True}},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            # Response is either a list of lists or nested list
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, list) and isinstance(item[0], list):
                        # Nested: [[embeddings...]]
                        results.extend(item)
                    else:
                        results.append(item)
        return results


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    """Google Gemini embedding models."""
    def __init__(self):
        self.model = settings.embedding_model or "models/embedding-001"
        self.api_key = settings.google_api_key

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        import google.generativeai as genai
        genai.configure(api_key=self.api_key)

        results = []
        for text in texts:
            result = genai.embed_content(
                model=self.model,
                content=text,
                task_type="retrieval_document",
            )
            results.append(result["embedding"])
        return results


class QwenEmbeddingProvider(BaseEmbeddingProvider):
    """Alibaba Cloud Qwen/DashScope text embeddings (OpenAI-compatible)."""
    def __init__(self):
        self.model = settings.embedding_model or "text-embedding-v3"
        self.api_key = settings.qwen_api_key

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        )

        resp = await client.embeddings.create(input=texts, model=self.model)
        return [item.embedding for item in resp.data]


def get_embedding_provider() -> BaseEmbeddingProvider:
    provider = settings.embedding_provider.lower()
    providers = {
        "openai": OpenAIEmbeddingProvider,
        "ollama": OllamaEmbeddingProvider,
        "huggingface": HuggingFaceEmbeddingProvider,
        "gemini": GeminiEmbeddingProvider,
        "qwen": QwenEmbeddingProvider,
    }
    provider_class = providers.get(provider, OpenAIEmbeddingProvider)
    return provider_class()
"""Multi-provider embedding service."""
from app.config import settings
import httpx


class BaseEmbeddingProvider:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.embedding_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = await self.client.embeddings.create(input=texts, model=self.model)
        return [item.embedding for item in resp.data]


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self):
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.embedding_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        results = []
        async with httpx.AsyncClient() as client:
            for text in texts:
                resp = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                )
                resp.raise_for_status()
                results.append(resp.json()["embedding"])
        return results


def get_embedding_provider() -> BaseEmbeddingProvider:
    if settings.embedding_provider == "ollama":
        return OllamaEmbeddingProvider()
    return OpenAIEmbeddingProvider()
