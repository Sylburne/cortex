"""Knowledge card compiler: transforms chunks into structured knowledge cards."""
from app.config import settings


async def compile_source_to_card(
    source_filename: str,
    chunks: list[str],
    card_type: str = "concept",
) -> str:
    """Compile source chunks into a structured knowledge card using LLM."""
    combined_text = "\n\n".join(chunks[:20])  # Limit to first 20 chunks

    prompt = f"""You are a knowledge compiler. Given the following document content from "{source_filename}",
create a structured {card_type} knowledge card.

Document content:
{combined_text}

Create a well-organized {card_type} card that:
1. Has a clear title and summary
2. Extracts key concepts, definitions, and relationships
3. Organizes information hierarchically
4. Preserves technical accuracy
5. Uses markdown formatting

Output the knowledge card content in markdown format:"""

    messages = [
        {"role": "system", "content": "You are a precise knowledge compiler that creates structured knowledge cards from document content."},
        {"role": "user", "content": prompt},
    ]

    if settings.default_llm_provider == "anthropic":
        from app.services.rag_engine import _anthropic_chat
        return await _anthropic_chat(settings.default_llm_model, messages)
    else:
        from app.services.rag_engine import _openai_chat
        return await _openai_chat(settings.default_llm_model, messages)
