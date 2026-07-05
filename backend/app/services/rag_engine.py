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
