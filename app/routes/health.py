from fastapi import APIRouter, HTTPException

from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Check API, database connectivity, and whether BGE-M3 is loaded. Does not call DeepSeek."""
    raise HTTPException(status_code=501, detail="Not implemented")
