from pydantic import BaseModel, EmailStr, constr, Field, AliasChoices, ConfigDict


class SignupRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    first_name: constr(strip_whitespace=True, min_length=1) = Field(
        ...,
        validation_alias=AliasChoices("firstName", "first_name"),
        serialization_alias="firstName",
    )
    last_name: constr(strip_whitespace=True, min_length=1) = Field(
        ...,
        validation_alias=AliasChoices("lastName", "last_name"),
        serialization_alias="lastName",
    )
    company: constr(strip_whitespace=True, min_length=1) = Field(
        ...,
        validation_alias=AliasChoices("company", "companyName"),
        serialization_alias="company",
    )
    email: EmailStr
    password: constr(min_length=8, max_length=64)

class SignupResponse(BaseModel):
    id: str
    email: EmailStr
    confirmed: bool
    message: str
    company_id: str

class SigninRequest(BaseModel):
    email: EmailStr
    password: str

class SigninResponse(BaseModel):
    access_token: str
    refresh_token: str
    user_id: str
    email: str
    email_confirmed: bool
    company_id: str | None = None
    is_onboarded: bool

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

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordOtpRequest(BaseModel):
    email: EmailStr
    code: constr(pattern=r"^\d{6}$")
    new_password: constr(min_length=8, max_length=64)

class ResetPasswordResponse(BaseModel):
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
    company_id: str
