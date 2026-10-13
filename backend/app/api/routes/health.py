from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.api_route("/health", methods=["GET", "HEAD"])
async def health() -> dict[str, str]:
    # Liveness only: Render restarts the service when this fails, so a DB blip must not trigger it.
    return {"status": "ok"}
