from fastapi import APIRouter, HTTPException, Request
from app.models.auth import (
    SignupRequest, SignupResponse, SigninRequest, SigninResponse,
    TokenRefreshRequest, TokenRefreshResponse, ResendVerificationRequest,
    GoogleSigninRequest, GoogleSigninResponse, VerifyOtpRequest, VerifyOtpResponse,
    ForgotPasswordRequest, ResetPasswordOtpRequest, ResetPasswordResponse
)
from app.services.auth_service import (
    signup_user, signin_user, refresh_access_token,
    signin_with_google, send_verification_otp, verify_email_with_otp,
    request_password_reset, reset_password_with_otp
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
            "message": "Signup successful. We sent a 6-digit code to your email to verify your account."
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

@router.post("/verify-otp", response_model=VerifyOtpResponse)
@limiter.limit("10/minute")
async def verify_email_with_code(request: Request, data: VerifyOtpRequest):
    """Verify user email using a 6-digit OTP sent by email."""
    try:
        ok = verify_email_with_otp(data.email, data.code)
        return {"success": True, "message": "Email verified successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Email verification failed: {str(e)}")

@router.post("/resend-verification")
@limiter.limit("3/minute")
async def resend_verification(request: Request, resend_data: ResendVerificationRequest):
    """Send or resend a verification OTP to the user's email."""
    try:
        success = send_verification_otp(resend_data.email)
        if success:
            return {"message": "Verification code sent successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to send verification code")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to send verification code: {str(e)}")

@router.post("/forgot-password")
@limiter.limit("5/minute")
async def forgot_password(request: Request, data: ForgotPasswordRequest):
    """Send a Supabase-managed recovery OTP/email to reset password."""
    try:
        request_password_reset(data.email)
        return {"message": "If the email exists, a reset code has been sent."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to initiate password reset: {str(e)}")

@router.post("/reset-password-otp", response_model=ResetPasswordResponse)
@limiter.limit("5/minute")
async def reset_password_with_code(request: Request, data: ResetPasswordOtpRequest):
    """Verify recovery OTP and set a new password using Supabase."""
    try:
        reset_password_with_otp(data.email, data.code, data.new_password)
        return {"success": True, "message": "Password has been reset successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Password reset failed: {str(e)}")

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
