import re
from typing import Optional, Literal
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict

class UserPreferences(BaseModel):
    font: Literal["system", "mono"] = "system"
    model_config = ConfigDict(extra="forbid")

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
    display_name: Optional[str] = None
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    role: str = "user"
    is_suspended: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SessionResponse(BaseModel):
    user: UserResponse
    csrf_token: str

class UserProfileUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=100)
    preferences: Optional[UserPreferences] = None
    username: Optional[str] = None
    email: Optional[EmailStr] = None

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() or None if v is not None else None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if len(v) < 3 or len(v) > 32:
            raise ValueError("Username must be between 3 and 32 characters")
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Username may only contain letters, numbers, underscores, and dashes")
        return v

class UserChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8 or len(v) > 128:
            raise ValueError("Password must be between 8 and 128 characters")
        if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one letter and one number")
        return v
