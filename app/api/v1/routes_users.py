from fastapi import APIRouter

router = APIRouter()

@router.get("/test")
async def test_users():
    return {"message": "Users routes working!"}

