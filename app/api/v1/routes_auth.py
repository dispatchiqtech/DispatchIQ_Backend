from fastapi import APIRouter, HTTPException, Request
from app.models.auth import SignupRequest, SignupResponse, SigninRequest, SigninResponse
from app.services.auth_service import signup_user
from fastapi.responses import RedirectResponse, JSONResponse
from app.db.supabase_client import supabase

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
    
# @router.get("/login/google")
# def login_google():
#     redirect_url = supabase.auth.sign_in_with_oauth(
#         {"provider": "google"},
#         options={"redirect_to": "https://oqiqruvfrplnhyxkbemv.supabase.co/auth/v1/callback"}
#     )
#     return RedirectResponse(redirect_url.url)


# # Step 2: Handle the callback
# @router.get("/callback")
# def auth_callback(request: Request):
#     # Supabase will send the `access_token` & `refresh_token` in query params
#     token = request.query_params.get("access_token")
#     refresh_token = request.query_params.get("refresh_token")

#     if not token:
#         return JSONResponse({"error": "OAuth login failed"}, status_code=400)

#     # Optional: fetch user info
#     user = supabase.auth.get_user(token)

#     return JSONResponse({
#         "message": "Google login successful",
#         "user": user.user if user else None,
#         "access_token": token,
#         "refresh_token": refresh_token
#     })


@router.post("/signin", response_model=SigninResponse)
def signin_user(request: SigninRequest):
    try:
        response = supabase.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password
        })

        if not response.user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "user_id": response.user.id,
            "email": response.user.email
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error during signin: {str(e)}")