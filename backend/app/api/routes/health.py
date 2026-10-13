from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    # Liveness only: Render restarts the service when this fails, so a DB blip must not trigger it.
    return {"status": "ok"}
