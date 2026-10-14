import re
from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator, ConfigDict

class UserRegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    confirm_password: str
    terms_accepted: bool

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or len(v) > 32:
            raise ValueError("Username must be between 3 and 32 characters")
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Username may only contain letters, numbers, underscores, and dashes")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8 or len(v) > 128:
            raise ValueError("Password must be between 8 and 128 characters")
        if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one letter and one number")
        return v

class UserLoginRequest(BaseModel):
    email_or_username: str
    password: str

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SessionResponse(BaseModel):
    user: UserResponse
    csrf_token: str
