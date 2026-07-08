"""Pydantic schemas used for request validation & response shaping."""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import List, Optional
from datetime import datetime


# ---------------- Auth ----------------

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number.")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter.")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------------- Prediction ----------------

class PredictionRequest(BaseModel):
    symptoms: List[str] = Field(min_length=1, max_length=30)


class TopPrediction(BaseModel):
    disease: str
    confidence: int  # 0-100, approximate


class PredictionResponse(BaseModel):
    disease: str
    confidence: int  # 0-100, approximate model confidence for the top prediction
    top_predictions: List[TopPrediction]  # top 3, for transparency
    description: str
    precautions: List[str]
    medications: List[str]
    diet: List[str]
    workout: List[str]


class SymptomOut(BaseModel):
    name: str
    weight: int

    class Config:
        from_attributes = True


# ---------------- Free-text symptom matching ----------------

class SymptomMatchRequest(BaseModel):
    text: str = Field(min_length=3, max_length=1000)


class MatchedSymptom(BaseModel):
    name: str
    confidence: float  # 0-1
    matched_on: str  # "synonym" or "fuzzy"


class SymptomMatchResponse(BaseModel):
    matches: List[MatchedSymptom]


# ---------------- History ----------------

class HistoryOut(BaseModel):
    id: int
    symptoms_submitted: List[str]
    predicted_disease: str
    confidence: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class HistoryPage(BaseModel):
    items: List[HistoryOut]
    total: int


# ---------------- Admin ----------------

class DiseaseCount(BaseModel):
    disease: str
    count: int


class AdminStats(BaseModel):
    total_users: int
    total_predictions: int
    predictions_last_7_days: int
    new_users_last_7_days: int
    top_diseases: List[DiseaseCount]


class AdminUserOut(BaseModel):
    id: int
    email: EmailStr
    is_admin: bool
    created_at: datetime
    prediction_count: int

    class Config:
        from_attributes = True


class AdminUserPage(BaseModel):
    items: List[AdminUserOut]
    total: int


class AdminPredictionOut(BaseModel):
    id: int
    user_email: EmailStr
    symptoms_submitted: List[str]
    predicted_disease: str
    confidence: Optional[int] = None
    created_at: datetime


class AdminPredictionPage(BaseModel):
    items: List[AdminPredictionOut]
    total: int
