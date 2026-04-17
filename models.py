import os
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import Column, String, Float, Integer, DateTime, UniqueConstraint

from config import Base


def generate_uuid7() -> str:
    """
    Generate RFC 9562 compliant UUID v7.
    Uses os.urandom for cryptographically secure randomness.
    """
    timestamp_ms = int(time.time() * 1000)
    random_bytes = bytearray(os.urandom(10))
    
    uuid_bytes = bytearray(16)
    uuid_bytes[0:6] = timestamp_ms.to_bytes(6, byteorder='big')
    uuid_bytes[6:16] = random_bytes
    
    uuid_bytes[6] = (uuid_bytes[6] & 0x0F) | 0x70
    uuid_bytes[8] = (uuid_bytes[8] & 0x3F) | 0x80
    
    return str(uuid.UUID(bytes=bytes(uuid_bytes)))


class ProfileModel(Base):
    __tablename__ = "profiles"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    gender = Column(String(50), nullable=False)
    gender_probability = Column(Float, nullable=False)
    sample_size = Column(Integer, nullable=False)
    age = Column(Integer, nullable=False)
    age_group = Column(String(20), nullable=False)
    country_id = Column(String(10), nullable=False)
    country_probability = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    
    __table_args__ = (UniqueConstraint('name', name='uq_profile_name'),)


class CreateProfileRequest(BaseModel):
    name: str
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip().lower()


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    name: str
    gender: str
    gender_probability: float
    sample_size: int
    age: int
    age_group: str
    country_id: str
    country_probability: float
    created_at: datetime


class ProfileSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    name: str
    gender: str
    age: int
    age_group: str
    country_id: str


class CreateSuccessResponse(BaseModel):
    status: str = "success"
    data: ProfileResponse
    message: Optional[str] = None


class ExistingSuccessResponse(BaseModel):
    status: str = "success"
    message: str
    data: ProfileResponse


class ListSuccessResponse(BaseModel):
    status: str = "success"
    count: int
    data: List[ProfileSummaryResponse]


class GetSuccessResponse(BaseModel):
    status: str = "success"
    data: ProfileResponse


class ErrorResponse(BaseModel):
    status: str = "error"
    message: str


def get_age_group(age: int) -> str:
    if 0 <= age <= 12:
        return "child"
    elif 13 <= age <= 19:
        return "teenager"
    elif 20 <= age <= 59:
        return "adult"
    else:
        return "senior"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def validate_uuid7(uuid_str: str) -> bool:
    """Validate that string is a proper UUID v7."""
    try:
        u = uuid.UUID(uuid_str)
        return u.version == 7
    except ValueError:
        return False
