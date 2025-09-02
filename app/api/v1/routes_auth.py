from fastapi import APIRouter

router = APIRouter()

@router.get("/test")
async def test_auth():
    return {"message": "Auth routes working!"}

