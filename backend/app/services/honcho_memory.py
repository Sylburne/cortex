"""Honcho memory layer integration for persistent user context.

Honcho gives your AI persistent memory about each user across sessions.
It tracks conversation patterns, user preferences, and builds a model
of what each user knows and cares about.

Setup:
    - Managed: sign up at app.honcho.dev, get API key ($100 free credits)
    - Self-host: docker run and point HONCHO_BASE_URL to your instance

Env vars (optional — if empty, Honcho is skipped gracefully):
    HONCHO_API_KEY=your-key
    HONCHO_BASE_URL=https://api.honcho.dev   (or http://localhost:8000)
    HONCHO_WORKSPACE_ID=qmind                (logical grouping)
"""
from __future__ import annotations

import traceback
from app.config import settings

# Lazy singleton
_honcho_client = None


def get_honcho():
    """Return the Honcho client, or None if not configured."""
    global _honcho_client
    if not settings.honcho_api_key:
        return None

    if _honcho_client is None:
        try:
            from honcho import Honcho
            kwargs = {
                "workspace_id": settings.honcho_workspace_id,
                "api_key": settings.honcho_api_key,
            }
            if settings.honcho_base_url:
                kwargs["base_url"] = settings.honcho_base_url
            _honcho_client = Honcho(**kwargs)
        except Exception as e:
            print(f"[honcho] Failed to initialize: {e}")
            return None

    return _honcho_client


def is_enabled() -> bool:
    """Check if Honcho is configured and available."""
    return bool(settings.honcho_api_key)


async def store_message(user_id: str, session_id: str, role: str, content: str) -> None:
    """Store a user or assistant message in Honcho for long-term memory.

    This is fire-and-forget — failures are logged but don't block the RAG flow.
    """
    client = get_honcho()
    if not client:
        return

    try:
        peer = client.peer(user_id)
        session = client.session(session_id)

        if role == "user":
            msg = peer.message(content)
        else:
            # For assistant messages, create an "assistant" peer
            assistant = client.peer("qmind-assistant")
            msg = assistant.message(content)

        session.add_messages([msg])
    except Exception as e:
        # Don't break RAG if Honcho is down
        print(f"[honcho] store_message failed: {e}")


async def get_session_context(session_id: str, tokens: int = 4000) -> str | None:
    """Get Honcho's memory context for a session.

    Returns a string summary Honcho has built about the conversation,
    or None if unavailable.
    """
    client = get_honcho()
    if not client:
        return None

    try:
        session = client.session(session_id)
        context = session.context(summary=True, tokens=tokens)
        # context.to_openai() gives messages; we want the summary text
        if hasattr(context, "summary"):
            return context.summary
        # Fallback: try string conversion
        return str(context) if context else None
    except Exception as e:
        print(f"[honcho] get_session_context failed: {e}")
        return None


async def get_user_insights(user_id: str, question: str) -> str | None:
    """Ask Honcho what it knows about the user.

    This is the "peer chat" feature — Honcho reasons about the user's
    knowledge, preferences, and conversation patterns.

    Example: get_user_insights("alice", "What topics does this user care about most?")
    """
    client = get_honcho()
    if not client:
        return None

    try:
        peer = client.peer(user_id)
        answer = peer.chat(question)
        return str(answer) if answer else None
    except Exception as e:
        print(f"[honcho] get_user_insights failed: {e}")
        return None


def to_openai_context(session_id: str, assistant_name: str = "qmind-assistant"):
    """Get Honcho session context as OpenAI-formatted messages.

    Returns a list of message dicts ready to inject into an OpenAI call,
    or None if unavailable.
    """
    client = get_honcho()
    if not client:
        return None

    try:
        session = client.session(session_id)
        context = session.context(summary=True, tokens=8000)
        assistant = client.peer(assistant_name)
        return context.to_openai(assistant=assistant)
    except Exception as e:
        print(f"[honcho] to_openai_context failed: {e}")
        return None
