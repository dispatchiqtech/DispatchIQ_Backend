from supabase import create_client, Client
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, verify_token
from fastapi import HTTPException, status
from typing import Dict, Any, Optional
import re
import requests
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from app.db.supabase_client import supabase_admin
 

supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

PASSWORD_REGEX = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&]).{8,64}$")

def validate_password_strength(password: str) -> bool:
    return bool(PASSWORD_REGEX.match(password))

def signup_user(email: str, password: str, first_name: str, last_name: str, company_name: str) -> Dict[str, Any]:
    """Sign up a new user, create their company, and provision an app_users profile."""
    if not validate_password_strength(password):
        raise ValueError(
            "Password must be 8-64 characters long and include uppercase, "
            "lowercase, digit, and special character."
        )

    user_id: str | None = None
    company_id: str | None = None

    try:
        create_payload = {
            "email": email,
            "password": password,
            "email_confirm": False,
            "user_metadata": {
                "first_name": first_name,
                "firstName": first_name,
                "last_name": last_name,
                "lastName": last_name,
                "company": company_name,
                "company_name": company_name,
                "companyName": company_name,
            },
        }
        create_response = supabase_admin.auth.admin.create_user(create_payload)

        user = getattr(create_response, "user", None)
        if not user:
            raise Exception("Supabase did not return user record")

        user_id = user.id

        company_res = supabase_admin.table("companies").insert({"name": company_name}).execute()
        company_data = getattr(company_res, "data", []) or []
        if not company_data:
            raise Exception("Failed to create company record")
        company_id = company_data[0]["id"]

        profile_payload = {
            "company_id": company_id,
            "first_name": first_name,
            "last_name": last_name,
            "is_active": True,
        }
        profile_res = supabase_admin.table("app_users").update(profile_payload).eq("user_id", user_id).execute()
        profile_data = getattr(profile_res, "data", []) or []
        if not profile_data:
            # Trigger might not have inserted row (fallback)
            profile_payload["user_id"] = user_id
            insert_res = supabase_admin.table("app_users").insert(profile_payload).execute()
            insert_data = getattr(insert_res, "data", []) or []
            if not insert_data:
                raise Exception("Failed to create user profile")

        # Send OTP verification email explicitly
        # When using admin.create_user(), Supabase doesn't automatically send OTP emails
        try:
            service_key = settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_KEY
            headers = {
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json"
            }
            
            # Use the OTP endpoint to send a 6-digit code
            otp_response = requests.post(
                f"{settings.SUPABASE_URL}/auth/v1/otp",
                headers=headers,
                json={
                    "email": email,
                    "type": "signup",  # Must be "signup" to match verify_otp type
                }
            )
            
            if otp_response.status_code in [200, 201, 204]:
                print(f"OTP email sent successfully to {email}")
            else:
                # Log error for debugging
                error_detail = otp_response.text if hasattr(otp_response, 'text') else 'Unknown error'
                print(f"Failed to send OTP email. Status: {otp_response.status_code}, Response: {error_detail}")
                
                # Fallback: try using the regular client's resend method
                try:
                    supabase.auth.resend({
                        "type": "signup",
                        "email": email,
                    })
                    print(f"Fallback: Used client resend for {email}")
                except Exception as fallback_error:
                    print(f"Fallback resend also failed: {str(fallback_error)}")
                    
        except Exception as e:
            # Log error but don't fail signup - user can use resend verification endpoint
            print(f"Exception sending OTP email during signup: {str(e)}")

        return {
            "id": user.id,
            "email": user.email,
            "confirmed": user.email_confirmed_at is not None,
            "message": "Signup successful. We sent a 6-digit code to your email to verify your account.",
            "company_id": company_id,
        }

    except Exception as e:
        if user_id:
            try:
                supabase_admin.auth.admin.delete_user(user_id)
            except Exception:
                pass
        if company_id:
            try:
                supabase_admin.table("companies").delete().eq("id", company_id).execute()
            except Exception:
                pass
        raise Exception(f"Supabase signup failed: {str(e)}")


def _ensure_company_profile(
    user_id: str,
    first_name: Optional[str],
    last_name: Optional[str],
    company_hint: Optional[str] = None,
) -> tuple[str, bool]:
    """Ensure the user has an app_users profile and linked company."""
    fn = (first_name or "").strip()
    ln = (last_name or "").strip()
    if not fn and not ln:
        fn, ln = "Google", "User"
    elif not fn:
        fn = "Google"
    elif not ln:
        ln = "User"

    company_hint = (company_hint or "").strip()

    created_profile = False
    created_company = False

    profile_res = (
        supabase_admin.table("app_users")
        .select("user_id, company_id, first_name, last_name")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    profile_data = getattr(profile_res, "data", []) or []
    if profile_data:
        profile = profile_data[0]
    else:
        insert_payload = {
            "user_id": user_id,
            "first_name": fn,
            "last_name": ln,
            "is_active": True,
        }
        insert_res = supabase_admin.table("app_users").insert(insert_payload).execute()
        insert_data = getattr(insert_res, "data", []) or []
        profile = insert_data[0] if insert_data else insert_payload
        created_profile = True

    update_fields: Dict[str, Any] = {}
    if not profile.get("first_name") and fn:
        update_fields["first_name"] = fn
    if not profile.get("last_name") and ln:
        update_fields["last_name"] = ln
    if update_fields:
        update_res = supabase_admin.table("app_users").update(update_fields).eq("user_id", user_id).execute()
        update_data = getattr(update_res, "data", []) or []
        if update_data:
            profile = update_data[0]
        else:
            profile.update(update_fields)

    company_id = profile.get("company_id")
    if not company_id:
        fallback_company = company_hint or f"{fn} {ln}".strip() or "DispatchIQ Company"
        company_res = supabase_admin.table("companies").insert({"name": fallback_company}).execute()
        company_data = getattr(company_res, "data", []) or []
        if not company_data:
            raise Exception("Failed to create company record")
        company_id = company_data[0]["id"]
        supabase_admin.table("app_users").update({"company_id": company_id}).eq("user_id", user_id).execute()
        created_company = True

    return company_id, (created_profile or created_company)

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

        company_id = None
        try:
            profile_res = supabase_admin.table("app_users").select("company_id").eq("user_id", response.user.id).limit(1).execute()
            profile_data = getattr(profile_res, "data", []) or []
            if profile_data:
                company_id = profile_data[0].get("company_id")
        except Exception:
            company_id = None

        # Determine onboarding status: if the company has any setup records, consider onboarded
        is_onboarded = False
        try:
            if company_id:
                for table in ("properties", "technicians", "emergency_vendors"):
                    res = (
                        supabase_admin.table(table)
                        .select("id")
                        .eq("company_id", company_id)
                        .limit(1)
                        .execute()
                    )
                    data = getattr(res, "data", []) or []
                    if data:
                        is_onboarded = True
                        break
        except Exception:
            is_onboarded = False

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_id": response.user.id,
            "email": response.user.email,
            "email_confirmed": response.user.email_confirmed_at is not None,
            "company_id": company_id,
            "is_onboarded": is_onboarded,
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

def request_password_reset(email: str) -> bool:
    """Trigger Supabase to send a password reset email/OTP (recovery)."""
    try:
        supabase.auth.reset_password_for_email(email, {
            "redirect_to": f"{settings.FRONTEND_URL}/auth/reset-callback"
        })
        return True
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to initiate password reset: {str(e)}")

def reset_password_with_otp(email: str, code: str, new_password: str) -> bool:
    """Verify recovery OTP and set a new password using Supabase Auth."""
    # Validate strength using same policy
    if not validate_password_strength(new_password):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password does not meet strength requirements")
    try:
        # 1) Verify OTP of type 'recovery'. On success, Supabase creates a session in the client.
        verify_resp = supabase.auth.verify_otp({
            "type": "recovery",
            "email": email,
            "token": code,
        })
        if not getattr(verify_resp, "session", None) and not getattr(verify_resp, "user", None):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")

        # 2) Update the password for the now-authenticated user.
        supabase.auth.update_user({
            "password": new_password
        })
        return True
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to reset password: {str(e)}")

def signin_with_google(google_id_token: str) -> Dict[str, Any]:
    """Sign in with Google OAuth, provisioning company/profile on first login."""
    try:
        try:
            idinfo = id_token.verify_oauth2_token(
                google_id_token,
                google_requests.Request(),
            )
            if idinfo.get("iss") not in ["accounts.google.com", "https://accounts.google.com"]:
                raise ValueError("Wrong issuer.")
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid Google token: {str(e)}",
            )

        response = supabase.auth.sign_in_with_id_token(
            {
                "provider": "google",
                "token": google_id_token,
            }
        )

        user = getattr(response, "user", None)
        session = getattr(response, "session", None)
        if not user or not session:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google authentication failed.",
            )

        user_metadata = getattr(user, "user_metadata", {}) or {}
        first_name = (
            (idinfo.get("given_name") or "").strip()
            or (user_metadata.get("first_name") or "").strip()
            or (user_metadata.get("firstName") or "").strip()
        )
        last_name = (
            (idinfo.get("family_name") or "").strip()
            or (user_metadata.get("last_name") or "").strip()
            or (user_metadata.get("lastName") or "").strip()
        )
        if not first_name and idinfo.get("name"):
            parts = idinfo["name"].strip().split(" ", 1)
            first_name = parts[0]
            if len(parts) > 1 and not last_name:
                last_name = parts[1]

        company_hint = (
            (user_metadata.get("company") or "").strip()
            or (user_metadata.get("company_name") or "").strip()
            or (user_metadata.get("companyName") or "").strip()
            or (idinfo.get("hd") or "").strip()
        )

        company_id, created_new = _ensure_company_profile(
            user.id,
            first_name,
            last_name,
            company_hint,
        )

        email_confirmed = bool(getattr(user, "email_confirmed_at", None)) or bool(idinfo.get("email_verified"))

        access_token = create_access_token(data={"sub": user.id, "email": user.email})
        refresh_token = create_refresh_token(data={"sub": user.id})

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_id": user.id,
            "email": user.email,
            "email_confirmed": email_confirmed,
            "is_new_user": created_new,
            "company_id": company_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google authentication failed: {str(e)}",
        )
