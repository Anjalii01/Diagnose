"""
SQLAlchemy ORM models — one class per database table.

Reference tables (filled once from the CSVs by migrate_csv_to_db.py):
    - Symptom
    - DiseaseDescription
    - DiseasePrecaution
    - DiseaseMedication
    - DiseaseDiet
    - DiseaseWorkout

App-generated tables:
    - User                 created on signup, password is hashed (never stored in plain text)
    - PredictionHistory     one row per prediction, linked to the User who ran it
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Email verification
    is_verified = Column(Boolean, default=False, nullable=False)
    verification_code = Column(String, nullable=True)
    verification_code_expires = Column(DateTime(timezone=True), nullable=True)

    predictions = relationship("PredictionHistory", back_populates="user")


class Symptom(Base):
    __tablename__ = "symptoms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    weight = Column(Integer, nullable=False)  # severity weight from Symptom-severity.csv


class DiseaseDescription(Base):
    __tablename__ = "disease_description"

    id = Column(Integer, primary_key=True, index=True)
    disease = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, nullable=False)


class DiseasePrecaution(Base):
    __tablename__ = "disease_precautions"

    id = Column(Integer, primary_key=True, index=True)
    disease = Column(String, unique=True, index=True, nullable=False)
    precaution_1 = Column(String)
    precaution_2 = Column(String)
    precaution_3 = Column(String)
    precaution_4 = Column(String)


class DiseaseMedication(Base):
    __tablename__ = "disease_medications"

    id = Column(Integer, primary_key=True, index=True)
    disease = Column(String, unique=True, index=True, nullable=False)
    medications = Column(Text, nullable=False)  # stored as JSON string list


class DiseaseDiet(Base):
    __tablename__ = "disease_diets"

    id = Column(Integer, primary_key=True, index=True)
    disease = Column(String, unique=True, index=True, nullable=False)
    diet = Column(Text, nullable=False)  # stored as JSON string list


class DiseaseWorkout(Base):
    __tablename__ = "disease_workouts"

    id = Column(Integer, primary_key=True, index=True)
    disease = Column(String, index=True, nullable=False)
    workout = Column(String, nullable=False)


class PredictionHistory(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    symptoms_submitted = Column(Text, nullable=False)  # JSON string list
    predicted_disease = Column(String, nullable=False)
    confidence = Column(Integer, nullable=True)  # approximate confidence, 0-100
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)  # soft delete

    user = relationship("User", back_populates="predictions")
