"""Review service - AI-powered file comparison and update generation."""
from app.config import settings
from app.services.rag_engine import (
    _openai_chat, _anthropic_chat, _ollama_chat, 
    _gemini_chat, _huggingface_chat, _qwen_chat
)


async def generate_review(
    provider: str,
    model: str,
    original_files: list[dict],
    updated_files: list[dict],
    instructions: str = "",
) -> dict:
    """
    Compare original and updated files, generate updated versions.
    
    Args:
        provider: AI provider name
        model: AI model name
        original_files: List of {"filename": str, "content": str}
        updated_files: List of {"filename": str, "content": str}
        instructions: Optional user instructions for the review
    
    Returns:
        {"summary": str, "updated_files": [{"filename": str, "content": str, "changes": str}]}
    """
    
    # Build the review prompt
    system_prompt = """You are an expert document reviewer and editor. Your task is to:
1. Review the original files from a knowledge base
2. Compare them with updated versions
3. Generate improved/updated versions of the original files based on the differences and any user instructions

For each file, provide:
- The full updated content
- A summary of what changed and why

Be thorough but preserve the original structure and intent unless instructed otherwise.
If no updated version exists for a file, keep it unchanged but note any suggestions.

Output your response as a JSON object with this exact structure:
{
  "summary": "Overall summary of the review",
  "updated_files": [
    {
      "filename": "original_filename.ext",
      "content": "the full updated content here",
      "changes": "description of changes made"
    }
  ]
}

Do NOT include markdown code fences around the JSON. Just output valid JSON directly."""

    # Format the files for the prompt
    original_section = "=== ORIGINAL FILES ===\n\n"
    for f in original_files:
        original_section += f"--- {f['filename']} ---\n{f['content']}\n\n"
    
    updated_section = "=== UPDATED FILES (for reference) ===\n\n"
    if updated_files:
        for f in updated_files:
            updated_section += f"--- {f['filename']} ---\n{f['content']}\n\n"
    else:
        updated_section += "(No updated files provided - review originals only)\n\n"
    
    instructions_section = ""
    if instructions:
        instructions_section = f"\n\n=== USER INSTRUCTIONS ===\n{instructions}\n"
    
    user_prompt = f"""{original_section}
{updated_section}
{instructions_section}
Please review these files and generate updated versions. Output as JSON as specified."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    # Select the appropriate provider
    providers = {
        "openai": _openai_chat,
        "anthropic": _anthropic_chat,
        "ollama": _ollama_chat,
        "gemini": _gemini_chat,
        "huggingface": _huggingface_chat,
        "qwen": _qwen_chat,
    }
    
    handler = providers.get(provider, _gemini_chat)
    response = await handler(model, messages)
    
    # Parse the JSON response
    import json
    try:
        # Clean up response - remove markdown code fences if present
        cleaned = response.strip()
        if cleaned.startswith("```"):
            # Remove ```json or ``` at start
            first_newline = cleaned.find("\n")
            if first_newline != -1:
                cleaned = cleaned[first_newline + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        
        result = json.loads(cleaned)
        return result
    except json.JSONDecodeError as e:
        # If JSON parsing fails, return the raw response
        return {
            "summary": f"Review completed but response was not valid JSON: {str(e)}",
            "updated_files": [],
            "raw_response": response
        }


async def review_single_file(
    provider: str,
    model: str,
    original_content: str,
    updated_content: str,
    filename: str,
    instructions: str = "",
) -> dict:
    """Review and update a single file."""
    
    result = await generate_review(
        provider=provider,
        model=model,
        original_files=[{"filename": filename, "content": original_content}],
        updated_files=[{"filename": filename, "content": updated_content}] if updated_content else [],
        instructions=instructions,
    )
    
    if result.get("updated_files"):
        return result["updated_files"][0]
    
    return {
        "filename": filename,
        "content": original_content,
        "changes": "No changes suggested"
    }
