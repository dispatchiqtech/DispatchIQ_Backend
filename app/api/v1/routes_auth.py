from fastapi import APIRouter, HTTPException, Request
from app.models.auth import (
    SignupRequest, SignupResponse, SigninRequest, SigninResponse,
    TokenRefreshRequest, TokenRefreshResponse, ResendVerificationRequest,
    GoogleSigninRequest, GoogleSigninResponse
)
from app.services.auth_service import (
    signup_user, signin_user, refresh_access_token, verify_email,
    resend_verification_email, signin_with_google
)
from app.api.deps import limiter
from app.core.config import settings
from fastapi.responses import JSONResponse

router = APIRouter()

@router.post("/signup", response_model=SignupResponse)
@limiter.limit("5/minute")
async def signup(request: Request, signup_data: SignupRequest):
    """Register a new user with email verification."""
    try:
        user = signup_user(signup_data.email, signup_data.password)

        return {
            "id": user.id,
            "email": user.email,
            "confirmed": user.email_confirmed_at is not None,
            "message": "Signup successful. Please check your email to verify your account."
        }

    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/signin", response_model=SigninResponse)
@limiter.limit("10/minute")
async def signin(request: Request, signin_data: SigninRequest):
    """Sign in user and return JWT tokens."""
    try:
        result = signin_user(signin_data.email, signin_data.password)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error during signin: {str(e)}")

@router.post("/refresh", response_model=TokenRefreshResponse)
@limiter.limit("20/minute")
async def refresh_token(request: Request, refresh_data: TokenRefreshRequest):
    """Refresh access token using refresh token."""
    try:
        result = refresh_access_token(refresh_data.refresh_token)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Could not refresh token")

@router.get("/verify")
@limiter.limit("10/minute")
async def verify_email_from_link(request: Request, token: str, type: str = "signup", redirect_to: str = None):
    """Handle email verification from Supabase email links."""
    try:
        verify_email(token)
        
        # If redirect_to is provided, redirect to that URL
        if redirect_to:
            return JSONResponse(
                status_code=302,
                headers={"Location": redirect_to},
                content={"message": "Email verified successfully", "redirect": redirect_to}
            )
        
        # Default redirect to frontend
        return JSONResponse(
            status_code=200,
            content={
                "message": "Email verified successfully", 
                "success": True,
                "redirect": f"{settings.FRONTEND_URL}/auth/verified"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Email verification failed: {str(e)}")

@router.post("/resend-verification")
@limiter.limit("3/minute")
async def resend_verification(request: Request, resend_data: ResendVerificationRequest):
    """Resend email verification."""
    try:
        success = resend_verification_email(resend_data.email)
        if success:
            return {"message": "Verification email sent successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to send verification email")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to send verification email: {str(e)}")

@router.post("/google-signin", response_model=GoogleSigninResponse)
@limiter.limit("10/minute")
async def google_signin(request: Request, google_data: GoogleSigninRequest):
    """
    Sign in with Google OAuth. Creates account if doesn't exist.
    
    ## Frontend Integration:
    
    ### 1. Install Google Sign-In Library:
    ```html
    <script src="https://accounts.google.com/gsi/client" async defer></script>
    ```
    
    ### 2. Initialize Google Sign-In:
    ```javascript
    function handleCredentialResponse(response) {
        // response.credential contains the ID token
        fetch('/api/v1/auth/google-signin', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id_token: response.credential })
        })
        .then(res => res.json())
        .then(data => {
            // Store tokens and redirect user
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('refresh_token', data.refresh_token);
            // Handle is_new_user flag for onboarding flow
            if (data.is_new_user) {
                window.location.href = '/onboarding';
            } else {
                window.location.href = '/dashboard';
            }
        });
    }
    ```
    
    ### 3. HTML Button:
    ```html
    <div id="g_id_onload"
         data-client_id="YOUR_GOOGLE_CLIENT_ID"
         data-callback="handleCredentialResponse">
    </div>
    <div class="g_id_signin" data-type="standard"></div>
    ```
    
    ### 4. Google Cloud Console Setup:
    - Add your domain to "Authorized JavaScript origins"
    - Use Client ID: CLIENT ID
    
    ## Response:
    - `is_new_user`: true if account was just created, false if existing user
    - `email_confirmed`: always true for Google users (pre-verified)
    - Same token structure as regular signin for consistent auth flow
    """
    try:
        result = signin_with_google(google_data.id_token)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Google signin failed: {str(e)}")
