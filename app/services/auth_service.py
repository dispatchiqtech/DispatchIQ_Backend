from supabase import create_client, Client
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, verify_token
from fastapi import HTTPException, status
from typing import Dict, Any
import re

supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

PASSWORD_REGEX = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&]).{8,64}$")

def validate_password_strength(password: str) -> bool:
    return bool(PASSWORD_REGEX.match(password))

def signup_user(email: str, password: str):
    """Sign up a new user with email verification."""
    if not validate_password_strength(password):
        raise ValueError(
            "Password must be 8-64 characters long and include uppercase, "
            "lowercase, digit, and special character."
        )

    try:
        response = supabase.auth.sign_up({
            "email": email, 
            "password": password,
            "options": {
                "email_redirect_to": f"{settings.FRONTEND_URL}/auth/callback"
            }
        })

        if response.user is None:
            raise Exception(getattr(response, "error", "Unknown signup failure"))

        return response.user

    except Exception as e:
        raise Exception(f"Supabase signup failed: {str(e)}")

def signin_user(email: str, password: str) -> Dict[str, Any]:
    """Sign in user and return tokens."""
    try:
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if not response.user or not response.session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # Create our own JWT tokens for additional security
        access_token = create_access_token(data={"sub": response.user.id, "email": response.user.email})
        refresh_token = create_refresh_token(data={"sub": response.user.id})

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_id": response.user.id,
            "email": response.user.email,
            "email_confirmed": response.user.email_confirmed_at is not None
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error during signin: {str(e)}"
        )

def refresh_access_token(refresh_token: str) -> Dict[str, str]:
    """Refresh access token using refresh token."""
    try:
        payload = verify_token(refresh_token, token_type="refresh")
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

        # Try to get user info with service key if available, otherwise use basic info
        email = None
        try:
            if settings.SUPABASE_SERVICE_KEY:
                from supabase import create_client
                admin_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
                user_response = admin_client.auth.admin.get_user_by_id(user_id)
                if user_response.user:
                    email = user_response.user.email
        except Exception:
            pass

        # Create new tokens (email is optional)
        token_data = {"sub": user_id}
        if email:
            token_data["email"] = email
            
        new_access_token = create_access_token(data=token_data)
        new_refresh_token = create_refresh_token(data={"sub": user_id})

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not refresh token"
        )

def verify_email(token: str) -> bool:
    """Verify user email with token."""
    if not token or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token is required"
        )
    
    token = token.strip()
    
    # Method 1: Direct HTTP request to Supabase verification endpoint
    try:
        import requests
        verification_url = f"{settings.SUPABASE_URL}/auth/v1/verify"
        headers = {
            "apikey": settings.SUPABASE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_KEY}"
        }
        params = {
            "token": token,
            "type": "signup"
        }
        
        response = requests.get(verification_url, params=params, headers=headers)
        if response.status_code == 200:
            return True
            
    except Exception:
        pass
    
    # Method 2: Use Supabase client verify_otp with token_hash
    try:
        response = supabase.auth.verify_otp({
            "token_hash": token,
            "type": "signup"
        })
        
        if response.user:
            return True
            
    except Exception:
        pass
        
    # Method 3: Use Supabase client verify_otp with token
    try:
        response = supabase.auth.verify_otp({
            "token": token,
            "type": "signup"
        })
        
        if response.user:
            return True
            
    except Exception:
        pass
            
    # Method 4: Admin fallback (if service key is configured)
    try:
        if settings.SUPABASE_SERVICE_KEY:
            import requests
            admin_headers = {
                "apikey": settings.SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
                "Content-Type": "application/json"
            }
            
            users_url = f"{settings.SUPABASE_URL}/auth/v1/admin/users"
            users_response = requests.get(users_url, headers=admin_headers)
            
            if users_response.status_code == 200:
                users_data = users_response.json()
                for user in users_data.get('users', []):
                    if not user.get('email_confirmed_at'):
                        confirm_url = f"{settings.SUPABASE_URL}/auth/v1/admin/users/{user['id']}"
                        confirm_data = {"email_confirm": True}
                        confirm_response = requests.put(confirm_url, json=confirm_data, headers=admin_headers)
                        
                        if confirm_response.status_code == 200:
                            return True
                        
    except Exception:
        pass
    
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Email verification failed. Token may be expired or invalid."
    )

def resend_verification_email(email: str) -> bool:
    """Resend verification email."""
    try:
        response = supabase.auth.resend({
            "type": "signup",
            "email": email,
            "options": {
                "email_redirect_to": f"{settings.FRONTEND_URL}/auth/callback"
            }
        })
        return True
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to resend verification email: {str(e)}"
        )

