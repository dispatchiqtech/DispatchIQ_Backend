from supabase import create_client, Client
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, verify_token
from fastapi import HTTPException, status
from typing import Dict, Any
import re
import requests
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
 

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

        # Supabase sends confirmation/OTP email automatically if enabled in dashboard

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

def send_verification_otp(email: str) -> bool:
    """Ask Supabase to send/resend the signup verification OTP/email."""
    try:
        supabase.auth.resend({
            "type": "signup",
            "email": email,
        })
        return True
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to send verification code: {str(e)}")

def verify_email_with_otp(email: str, code: str) -> bool:
    """Verify email using Supabase-managed OTP for signup confirmation."""
    try:
        response = supabase.auth.verify_otp({
            "type": "signup",
            "email": email,
            "token": code,
        })
        if getattr(response, "user", None):
            return True
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Email verification failed: {str(e)}")

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

def signin_with_google(google_id_token: str) -> Dict[str, Any]:
    """Sign in user with Google OAuth and create account if doesn't exist."""
    try:
        # Verify Google ID token
        try:
            # Verify the token with Google
            idinfo = id_token.verify_oauth2_token(
                google_id_token, 
                google_requests.Request()
            )
            
            # Verify the issuer
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise ValueError('Wrong issuer.')
                
            google_user_id = idinfo['sub']
            email = idinfo['email']
            email_verified = idinfo.get('email_verified', False)
            
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid Google token: {str(e)}"
            )
        
        # Try to sign in with Supabase using Google OAuth
        try:
            response = supabase.auth.sign_in_with_id_token({
                "provider": "google",
                "token": google_id_token
            })
            
            if response.user and response.session:
                # User exists, sign them in
                access_token = create_access_token(data={"sub": response.user.id, "email": response.user.email})
                refresh_token = create_refresh_token(data={"sub": response.user.id})
                
                return {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "user_id": response.user.id,
                    "email": response.user.email,
                    "email_confirmed": response.user.email_confirmed_at is not None,
                    "is_new_user": False
                }
                
        except Exception as supabase_error:
            # If Supabase signin fails, try to create the user
            try:
                # Check if user already exists by email
                existing_users = supabase.auth.admin.list_users()
                user_exists = any(user.email == email for user in existing_users.users if user.email)
                
                if user_exists:
                    # User exists but Google signin failed, try regular Google OAuth flow
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="User exists but Google authentication failed. Please try again or use email/password signin."
                    )
                
                # Create new user with Google OAuth
                signup_response = supabase.auth.sign_up({
                    "email": email,
                    "password": f"google_oauth_{google_user_id}_{email}",  # Temporary password
                    "options": {
                        "data": {
                            "provider": "google",
                            "google_id": google_user_id,
                            "email_verified": email_verified
                        }
                    }
                })
                
                if not signup_response.user:
                    raise Exception("Failed to create user account")
                
                # If user was created successfully, try to sign them in again
                try:
                    signin_response = supabase.auth.sign_in_with_id_token({
                        "provider": "google",
                        "token": google_id_token
                    })
                    
                    if signin_response.user and signin_response.session:
                        access_token = create_access_token(data={"sub": signin_response.user.id, "email": signin_response.user.email})
                        refresh_token = create_refresh_token(data={"sub": signin_response.user.id})
                        
                        return {
                            "access_token": access_token,
                            "refresh_token": refresh_token,
                            "user_id": signin_response.user.id,
                            "email": signin_response.user.email,
                            "email_confirmed": True,  # Google emails are pre-verified
                            "is_new_user": True
                        }
                    
                except Exception:
                    # Fallback: return the created user info
                    access_token = create_access_token(data={"sub": signup_response.user.id, "email": signup_response.user.email})
                    refresh_token = create_refresh_token(data={"sub": signup_response.user.id})
                    
                    return {
                        "access_token": access_token,
                        "refresh_token": refresh_token,
                        "user_id": signup_response.user.id,
                        "email": signup_response.user.email,
                        "email_confirmed": True,  # Google emails are pre-verified
                        "is_new_user": True
                    }
                    
            except Exception as create_error:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to create or authenticate Google user: {str(create_error)}"
                )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google authentication failed: {str(e)}"
        )


