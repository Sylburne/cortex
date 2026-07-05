from fastapi import Request, HTTPException, status
from app.config import settings


async def verify_api_key(request: Request) -> str:
    """Validate API key from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header. Use 'Bearer <api-key>'.",
        )
    token = auth_header[7:]
    if token != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )
    return "default"  # owner_id
