from pydantic import BaseModel, EmailStr, constr

class SignupRequest(BaseModel):
    email: EmailStr
    password: constr(min_length=8, max_length=64)

class SignupResponse(BaseModel):
    id: str
    email: EmailStr
    confirmed: bool
    message: str

class SigninRequest(BaseModel):
    email: EmailStr
    password: str

class SigninResponse(BaseModel):
    access_token: str
    refresh_token: str
    user_id: str
    email: str
    email_confirmed: bool

class TokenRefreshRequest(BaseModel):
    refresh_token: str

class TokenRefreshResponse(BaseModel):
    access_token: str
    refresh_token: str

class ResendVerificationRequest(BaseModel):
    email: EmailStr

class VerifyOtpRequest(BaseModel):
    email: EmailStr
    code: constr(pattern=r"^\d{6}$")

class VerifyOtpResponse(BaseModel):
    success: bool
    message: str

class GoogleSigninRequest(BaseModel):
    id_token: str

class GoogleSigninResponse(BaseModel):
    access_token: str
    refresh_token: str
    user_id: str
    email: str
    email_confirmed: bool
    is_new_user: bool
