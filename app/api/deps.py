from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.security import verify_token
from app.db.supabase_client import supabase
from app.core.config import settings
from supabase import create_client
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request

# Rate limiter setup
limiter = Limiter(key_func=get_remote_address)

# Security scheme
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency to get current authenticated user."""
    token = credentials.credentials
    
    # First try to verify our custom JWT token
    try:
        payload = verify_token(token)
        user_id = payload.get("sub")
        email = payload.get("email")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        # Get user from Supabase using admin client (requires service role key)
        try:
            admin_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_KEY)
            response = admin_client.auth.admin.get_user_by_id(user_id)
            if not getattr(response, "user", None):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found"
                )
            return response.user
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate user"
            )
            
    except HTTPException as e:
        try:
            print(f"[auth] Custom JWT path failed: {getattr(e, 'detail', str(e))}")
        except Exception:
            pass
        # If custom JWT fails, try Supabase token
        try:
            response = supabase.auth.get_user(token)
            if not response.user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token"
                )
            return response.user
        except Exception as e:
            try:
                print(f"[auth] Supabase token path failed: {str(e)}")
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )

def get_current_active_user(current_user = Depends(get_current_user)):
    """Dependency to get current active user (email verified)."""
    if not current_user.email_confirmed_at:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified"
        )
    return current_user

def get_optional_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))):
    """Optional authentication dependency."""
    if not credentials:
        return None
    
    try:
        return get_current_user(credentials)
    except HTTPException:
        return None
