"""RAG answer generation using multi-provider LLMs."""
from app.config import settings
import httpx


async def generate_answer(
    provider: str,
    model: str,
    system_prompt: str,
    history: list[dict],
    context_chunks: list[str],
    question: str,
) -> str:
    """Generate an answer from retrieved context + conversation history."""
    context = "\n\n---\n\n".join(context_chunks) if context_chunks else "No relevant context found."

    messages = [
        {"role": "system", "content": f"{system_prompt}\n\nUse the following context to answer the question:\n\n{context}"},
    ]

    # Add conversation history (last 10 messages)
    for msg in history[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Add current question
    messages.append({"role": "user", "content": question})

    providers = {
        "openai": _openai_chat,
        "anthropic": _anthropic_chat,
        "ollama": _ollama_chat,
        "gemini": _gemini_chat,
        "huggingface": _huggingface_chat,
        "qwen": _qwen_chat,
    }

    handler = providers.get(provider, _openai_chat)
    return await handler(model, messages)


async def _openai_chat(model: str, messages: list[dict]) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp = await client.chat.completions.create(model=model, messages=messages, max_tokens=2048)
    return resp.choices[0].message.content or ""


async def _anthropic_chat(model: str, messages: list[dict]) -> str:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    system = ""
    chat_msgs = []
    for m in messages:
        if m["role"] == "system":
            system = m["content"]
        else:
            chat_msgs.append({"role": m["role"], "content": m["content"]})

    resp = await client.messages.create(
        model=model, max_tokens=2048,
        system=system, messages=chat_msgs,
    )
    return resp.content[0].text if resp.content else ""


async def _ollama_chat(model: str, messages: list[dict]) -> str:
    base_url = settings.ollama_base_url.rstrip("/")
    headers = {}
    if settings.ollama_api_key:
        headers["Authorization"] = f"Bearer {settings.ollama_api_key}"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{base_url}/api/chat",
            json={"model": model, "messages": messages, "stream": False},
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "")


async def _gemini_chat(model: str, messages: list[dict]) -> str:
    """Google Gemini via google-generativeai SDK."""
    import google.generativeai as genai

    genai.configure(api_key=settings.google_api_key)

    # Extract system instruction
    system_instruction = ""
    chat_messages = []
    for m in messages:
        if m["role"] == "system":
            system_instruction = m["content"]
        elif m["role"] == "user":
            chat_messages.append({"role": "user", "parts": [m["content"]]})
        elif m["role"] == "assistant":
            chat_messages.append({"role": "model", "parts": [m["content"]]})

    model_name = model or "gemini-2.0-flash"
    gemini_model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_instruction if system_instruction else None,
    )

    # Use chat session for multi-turn
    chat = gemini_model.start_chat(history=chat_messages[:-1] if chat_messages else [])
    last_msg = chat_messages[-1]["parts"][0] if chat_messages else ""

    response = await chat.send_message_async(last_msg)
    return response.text if response.text else ""


async def _huggingface_chat(model: str, messages: list[dict]) -> str:
    """HuggingFace Inference API for chat models."""
    api_url = f"https://api-inference.huggingface.co/models/{model}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.huggingface_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 2048,
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(api_url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")


async def _qwen_chat(model: str, messages: list[dict]) -> str:
    """Alibaba Cloud Qwen via DashScope API (OpenAI-compatible)."""
    # DashScope uses OpenAI-compatible API
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=settings.qwen_api_key,
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )

    model_name = model or "qwen-plus"
    resp = await client.chat.completions.create(
        model=model_name,
        messages=messages,
        max_tokens=2048,
    )
    return resp.choices[0].message.content or ""
"""RAG answer generation using multi-provider LLMs."""
from app.config import settings
import httpx


async def generate_answer(
    provider: str,
    model: str,
    system_prompt: str,
    history: list[dict],
    context_chunks: list[str],
    question: str,
) -> str:
    """Generate an answer from retrieved context + conversation history."""
    context = "\n\n---\n\n".join(context_chunks) if context_chunks else "No relevant context found."

    messages = [
        {"role": "system", "content": f"{system_prompt}\n\nUse the following context to answer the question:\n\n{context}"},
    ]

    # Add conversation history (last 10 messages)
    for msg in history[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Add current question
    messages.append({"role": "user", "content": question})

    if provider == "openai":
        return await _openai_chat(model, messages)
    elif provider == "anthropic":
        return await _anthropic_chat(model, messages)
    elif provider == "ollama":
        return await _ollama_chat(model, messages)
    else:
        return await _openai_chat(model, messages)


async def _openai_chat(model: str, messages: list[dict]) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    resp = await client.chat.completions.create(model=model, messages=messages, max_tokens=2048)
    return resp.choices[0].message.content or ""


async def _anthropic_chat(model: str, messages: list[dict]) -> str:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    system = ""
    chat_msgs = []
    for m in messages:
        if m["role"] == "system":
            system = m["content"]
        else:
            chat_msgs.append({"role": m["role"], "content": m["content"]})

    resp = await client.messages.create(
        model=model, max_tokens=2048,
        system=system, messages=chat_msgs,
    )
    return resp.content[0].text if resp.content else ""


async def _ollama_chat(model: str, messages: list[dict]) -> str:
    base_url = settings.ollama_base_url.rstrip("/")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{base_url}/api/chat",
            json={"model": model, "messages": messages, "stream": False},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "")
