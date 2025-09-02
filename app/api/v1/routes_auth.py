from fastapi import APIRouter, HTTPException
from app.models.auth import SignupRequest, SignupResponse
from app.services.auth_service import signup_user

router = APIRouter()

@router.post("/signup", response_model=SignupResponse)
async def signup(request: SignupRequest):
    try:
        user = signup_user(request.email, request.password)

        return {
            "id": user.id,
            "email": user.email,
            "confirmed": user.confirmed_at is not None,
            "message": "Signup successful. Please confirm your email if required."
        }

    except ValueError as ve:  # validation issue
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:  # supabase or unknown issue
        raise HTTPException(status_code=400, detail=str(e))
