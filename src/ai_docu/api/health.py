from fastapi import APIRouter

router = APIRouter()


@router.get(
    "/health",
    tags=["Health Check"],
    response_model=dict,
    summary="Health Check Endpoint",
    description="Returns the health status of the API.",
)
async def health_check() -> dict[str, str]:
    return {"status": "Server is healthy and running!"}