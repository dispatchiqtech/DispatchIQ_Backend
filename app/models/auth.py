from pydantic import BaseModel, EmailStr, constr

class SignupRequest(BaseModel):
    email: EmailStr
    password: constr(min_length=8, max_length=64)  # enforce strong passwords

class SignupResponse(BaseModel):
    id: str
    email: EmailStr
    confirmed: bool
    message: str
