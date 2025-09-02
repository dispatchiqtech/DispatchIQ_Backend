from supabase import create_client, Client
from app.core.config import settings
import re

supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

PASSWORD_REGEX = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&]).{8,64}$")

def validate_password_strength(password: str) -> bool:
    return bool(PASSWORD_REGEX.match(password))

def signup_user(email: str, password: str):
    if not validate_password_strength(password):
        raise ValueError(
            "Password must be 8-64 characters long and include uppercase, "
            "lowercase, digit, and special character."
        )

    try:
        response = supabase.auth.sign_up({"email": email, "password": password})

        if response.user is None:
            raise Exception(getattr(response, "error", "Unknown signup failure"))

        return response.user

    except Exception as e:
        raise Exception(f"Supabase signup failed: {str(e)}")
