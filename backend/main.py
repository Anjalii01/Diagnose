"""
FastAPI backend for the Disease Prediction System.

Public endpoints:
    GET  /                   -> health check
    GET  /symptoms           -> list of all symptoms (for the frontend checklist)
    POST /auth/signup        -> create an account, returns a login token
    POST /auth/login         -> log in, returns a login token

Protected endpoints (require "Authorization: Bearer <token>"):
    GET    /auth/me          -> current logged-in user's info
    POST   /predict          -> takes a list of symptoms, returns prediction + details
    GET    /history          -> your own paginated, searchable, filterable history
    DELETE /history/{id}     -> soft-delete a single history entry (recoverable)
    POST   /history/{id}/restore -> undo a soft-delete
    DELETE /history          -> soft-delete all of your history
    GET    /history/export   -> download your history as CSV or PDF

Run with:
    uvicorn main:app --reload
"""

import csv
import io
import json
import math
from datetime import datetime, date, timedelta
from typing import List, Optional

import joblib
import pandas as pd
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sklearn.preprocessing import LabelEncoder
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import func
from sqlalchemy.orm import Session

import auth
import models
import schemas
from config import settings
from symptom_matcher import match_text_to_symptoms, match_text_to_symptoms_llm, match_text_to_symptoms_gemini
from database import engine, get_db, Base

# ---- Create tables on startup if they don't exist ----
Base.metadata.create_all(bind=engine)

# ---- Rate limiter ----
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Disease Prediction API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS is locked to the origins listed in CORS_ORIGINS (see config.py / .env)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Load the trained model once at startup ----
MODEL_PATH = "data/svc.pkl"
model = joblib.load(MODEL_PATH)

# ---- Load the exact feature column order the model was trained on ----
_training_df = pd.read_csv("data/Training.csv")
FEATURE_COLUMNS = [c for c in _training_df.columns if c != "prognosis"]
VALID_SYMPTOMS = set(FEATURE_COLUMNS)

# ---- Rebuild the LabelEncoder the original notebook used, to decode predictions ----
_label_encoder = LabelEncoder()
_label_encoder.fit(_training_df["prognosis"])


def parse_json_list(value: str) -> List[str]:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []


def softmax_confidence(scores) -> List[float]:
    """Legacy fallback: turns raw SVM decision_function scores into a 0-1
    distribution. Only used if the loaded model wasn't trained with
    probability=True (i.e. predict_proba isn't available). Run
    retrain_model.py to get real calibrated probabilities instead."""
    max_score = max(scores)
    exps = [math.exp(s - max_score) for s in scores]
    total = sum(exps)
    return [e / total for e in exps]


# ============================================================
# Public endpoints
# ============================================================

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Disease Prediction API is running"}


@app.get("/symptoms", response_model=List[schemas.SymptomOut])
def get_symptoms(db: Session = Depends(get_db)):
    symptoms = db.query(models.Symptom).order_by(models.Symptom.name).all()
    if not symptoms:
        raise HTTPException(status_code=404, detail="No symptoms found. Did you run migrate_csv_to_db.py?")
    return symptoms


@app.post("/symptoms/match", response_model=schemas.SymptomMatchResponse)
def match_symptoms(payload: schemas.SymptomMatchRequest):
    """
    Takes free-text symptom description (any language/phrasing) and maps it
    onto the fixed list of symptoms the model was trained on. This does NOT
    predict a disease -- it only suggests which known symptoms to select.
    The frontend should show these as pre-checked suggestions the user can
    review/adjust before running /predict.

    Tries Gemini first (genuinely free tier) if GEMINI_API_KEY is set, then
    Claude if ANTHROPIC_API_KEY is set, then falls back to the offline
    synonym+fuzzy matcher if neither key is configured or both calls fail.
    """
    matches = None

    if settings.GEMINI_API_KEY:
        try:
            matches = match_text_to_symptoms_gemini(
                payload.text, FEATURE_COLUMNS, settings.GEMINI_API_KEY
            )
        except Exception:
            matches = None

    if matches is None and settings.ANTHROPIC_API_KEY:
        try:
            matches = match_text_to_symptoms_llm(
                payload.text, FEATURE_COLUMNS, settings.ANTHROPIC_API_KEY
            )
        except Exception:
            matches = None  # fall through to offline matcher below

    if matches is None:
        matches = match_text_to_symptoms(payload.text, FEATURE_COLUMNS)

    return schemas.SymptomMatchResponse(
        matches=[
            schemas.MatchedSymptom(name=name, confidence=conf, matched_on=source)
            for name, conf, source in matches
        ]
    )


# ============================================================
# Auth endpoints
# ============================================================

@app.post("/auth/signup", response_model=schemas.Token, status_code=201)
@limiter.limit(settings.AUTH_RATE_LIMIT)
def signup(request: Request, payload: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = models.User(email=payload.email, hashed_password=auth.hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    token = auth.create_access_token(data={"sub": str(user.id)})
    return schemas.Token(access_token=token, user=user)


@app.post("/auth/login", response_model=schemas.Token)
@limiter.limit(settings.AUTH_RATE_LIMIT)
def login(request: Request, payload: schemas.UserLogin, db: Session = Depends(get_db)):
    # Deliberately vague error message — never reveal whether the email exists,
    # to avoid leaking which addresses are registered.
    invalid_creds = HTTPException(status_code=401, detail="Incorrect email or password.")

    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not auth.verify_password(payload.password, user.hashed_password):
        raise invalid_creds

    token = auth.create_access_token(data={"sub": str(user.id)})
    return schemas.Token(access_token=token, user=user)


@app.get("/auth/me", response_model=schemas.UserOut)
def get_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


# ============================================================
# Prediction (protected)
# ============================================================

@app.post("/predict", response_model=schemas.PredictionResponse)
@limiter.limit(settings.PREDICT_RATE_LIMIT)
def predict_disease(
    request: Request,
    payload: schemas.PredictionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    # Validate every symptom against the known list (prevents injection / garbage input)
    cleaned = [s.strip() for s in payload.symptoms]
    unknown = [s for s in cleaned if s not in VALID_SYMPTOMS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown symptom(s): {unknown}")

    input_vector = {col: 0 for col in FEATURE_COLUMNS}
    for s in cleaned:
        input_vector[s] = 1

    input_df = pd.DataFrame([input_vector])[FEATURE_COLUMNS]

    if hasattr(model, "predict_proba") and getattr(model, "probability", False):
        # Real, calibrated probabilities (model trained with probability=True).
        confidences = model.predict_proba(input_df)[0]
    else:
        # Fallback for the old model file: approximate confidence from decision_function.
        decision_scores = model.decision_function(input_df)[0]
        confidences = softmax_confidence(decision_scores)

    # Rank diseases by confidence, take top 3
    ranked = sorted(
        zip(_label_encoder.classes_, confidences), key=lambda x: x[1], reverse=True
    )
    top_3 = ranked[:3]
    predicted_disease, top_confidence = top_3[0]

    # ---- Look up supporting info from the database ----
    description = db.query(models.DiseaseDescription).filter_by(disease=predicted_disease).first()
    precaution = db.query(models.DiseasePrecaution).filter_by(disease=predicted_disease).first()
    medication = db.query(models.DiseaseMedication).filter_by(disease=predicted_disease).first()
    diet = db.query(models.DiseaseDiet).filter_by(disease=predicted_disease).first()
    workouts = db.query(models.DiseaseWorkout).filter_by(disease=predicted_disease).all()

    confidence_pct = round(top_confidence * 100)

    response = schemas.PredictionResponse(
        disease=predicted_disease,
        confidence=confidence_pct,
        top_predictions=[
            schemas.TopPrediction(disease=d, confidence=round(c * 100)) for d, c in top_3
        ],
        description=description.description if description else "No description available.",
        precautions=[p for p in [
            precaution.precaution_1 if precaution else None,
            precaution.precaution_2 if precaution else None,
            precaution.precaution_3 if precaution else None,
            precaution.precaution_4 if precaution else None,
        ] if p and str(p).lower() != "nan"],
        medications=parse_json_list(medication.medications) if medication else [],
        diet=parse_json_list(diet.diet) if diet else [],
        workout=[w.workout for w in workouts],
    )

    # ---- Log this prediction into the database, tied to the logged-in user ----
    history_entry = models.PredictionHistory(
        user_id=current_user.id,
        symptoms_submitted=json.dumps(cleaned),
        predicted_disease=predicted_disease,
        confidence=confidence_pct,
    )
    db.add(history_entry)
    db.commit()

    return response


# ============================================================
# History (protected, scoped to the logged-in user only)
# ============================================================

def _build_history_query(db: Session, user_id: int, search: Optional[str],
                          start_date: Optional[date], end_date: Optional[date],
                          include_deleted: bool = False):
    q = db.query(models.PredictionHistory).filter(models.PredictionHistory.user_id == user_id)
    if not include_deleted:
        q = q.filter(models.PredictionHistory.is_deleted.is_(False))
    if search:
        q = q.filter(models.PredictionHistory.predicted_disease.ilike(f"%{search}%"))
    if start_date:
        q = q.filter(models.PredictionHistory.created_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        q = q.filter(models.PredictionHistory.created_at <= datetime.combine(end_date, datetime.max.time()))
    return q


@app.get("/history", response_model=schemas.HistoryPage)
def get_history(
    search: Optional[str] = Query(None, description="Filter by disease name (partial match)"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    q = _build_history_query(db, current_user.id, search, start_date, end_date)
    total = q.count()
    rows = q.order_by(models.PredictionHistory.created_at.desc()).offset(skip).limit(limit).all()

    items = [
        schemas.HistoryOut(
            id=row.id,
            symptoms_submitted=parse_json_list(row.symptoms_submitted),
            predicted_disease=row.predicted_disease,
            confidence=row.confidence,
            created_at=row.created_at,
        )
        for row in rows
    ]
    return schemas.HistoryPage(items=items, total=total)


@app.delete("/history/{entry_id}")
def delete_history_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    entry = (
        db.query(models.PredictionHistory)
        .filter_by(id=entry_id, user_id=current_user.id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="History entry not found.")
    entry.is_deleted = True
    db.commit()
    return {"status": "deleted", "id": entry_id, "recoverable": True}


@app.post("/history/{entry_id}/restore")
def restore_history_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    entry = (
        db.query(models.PredictionHistory)
        .filter_by(id=entry_id, user_id=current_user.id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="History entry not found.")
    entry.is_deleted = False
    db.commit()
    return {"status": "restored", "id": entry_id}


@app.delete("/history")
def clear_history(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    q = db.query(models.PredictionHistory).filter_by(user_id=current_user.id, is_deleted=False)
    count = q.update({"is_deleted": True}, synchronize_session=False)
    db.commit()
    return {"status": "cleared", "deleted_count": count, "recoverable": True}


@app.get("/history/export")
def export_history(
    format: str = Query("csv", pattern="^(csv|pdf)$"),
    search: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    q = _build_history_query(db, current_user.id, search, start_date, end_date)
    rows = q.order_by(models.PredictionHistory.created_at.desc()).all()

    if format == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["ID", "Date", "Predicted Disease", "Confidence %", "Symptoms Submitted"])
        for row in rows:
            symptoms = ", ".join(parse_json_list(row.symptoms_submitted))
            writer.writerow([
                row.id, row.created_at.strftime("%Y-%m-%d %H:%M"),
                row.predicted_disease, row.confidence, symptoms,
            ])
        buffer.seek(0)
        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=diagnosis_history.csv"},
        )

    # ---- PDF export ----
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Diagnosis History", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 8, f"Account: {current_user.email}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    for row in rows:
        symptoms = ", ".join(parse_json_list(row.symptoms_submitted))
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_x(pdf.l_margin)
        confidence_str = f" ({row.confidence}% confidence)" if row.confidence is not None else ""
        pdf.multi_cell(0, 7, f"{row.predicted_disease}{confidence_str}  -  {row.created_at.strftime('%Y-%m-%d %H:%M')}")
        pdf.set_font("Helvetica", "", 10)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 6, f"Symptoms: {symptoms}")
        pdf.ln(3)

    pdf_bytes = bytes(pdf.output())
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=diagnosis_history.pdf"},
    )


# ============================================================
# Admin dashboard (requires an admin account — see make_admin.py)
# ============================================================

@app.get("/admin/stats", response_model=schemas.AdminStats)
def admin_stats(db: Session = Depends(get_db), _: models.User = Depends(auth.require_admin)):
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    total_users = db.query(models.User).count()
    total_predictions = db.query(models.PredictionHistory).filter_by(is_deleted=False).count()
    predictions_last_7_days = (
        db.query(models.PredictionHistory)
        .filter(models.PredictionHistory.is_deleted.is_(False))
        .filter(models.PredictionHistory.created_at >= seven_days_ago)
        .count()
    )
    new_users_last_7_days = db.query(models.User).filter(models.User.created_at >= seven_days_ago).count()

    top_diseases_rows = (
        db.query(models.PredictionHistory.predicted_disease, func.count(models.PredictionHistory.id).label("cnt"))
        .filter(models.PredictionHistory.is_deleted.is_(False))
        .group_by(models.PredictionHistory.predicted_disease)
        .order_by(func.count(models.PredictionHistory.id).desc())
        .limit(10)
        .all()
    )

    return schemas.AdminStats(
        total_users=total_users,
        total_predictions=total_predictions,
        predictions_last_7_days=predictions_last_7_days,
        new_users_last_7_days=new_users_last_7_days,
        top_diseases=[schemas.DiseaseCount(disease=d, count=c) for d, c in top_diseases_rows],
    )


@app.get("/admin/users", response_model=schemas.AdminUserPage)
def admin_list_users(
    search: Optional[str] = Query(None, description="Filter by email (partial match)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.require_admin),
):
    q = db.query(
        models.User,
        func.count(models.PredictionHistory.id).label("prediction_count"),
    ).outerjoin(
        models.PredictionHistory,
        (models.PredictionHistory.user_id == models.User.id) & (models.PredictionHistory.is_deleted.is_(False)),
    ).group_by(models.User.id)

    if search:
        q = q.filter(models.User.email.ilike(f"%{search}%"))

    total = q.count()
    rows = q.order_by(models.User.created_at.desc()).offset(skip).limit(limit).all()

    items = [
        schemas.AdminUserOut(
            id=user.id,
            email=user.email,
            is_admin=user.is_admin,
            created_at=user.created_at,
            prediction_count=count,
        )
        for user, count in rows
    ]
    return schemas.AdminUserPage(items=items, total=total)


@app.get("/admin/predictions", response_model=schemas.AdminPredictionPage)
def admin_list_predictions(
    search: Optional[str] = Query(None, description="Filter by disease name"),
    user_email: Optional[str] = Query(None, description="Filter by a specific user's email"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.require_admin),
):
    q = (
        db.query(models.PredictionHistory, models.User.email)
        .join(models.User, models.PredictionHistory.user_id == models.User.id)
        .filter(models.PredictionHistory.is_deleted.is_(False))
    )
    if search:
        q = q.filter(models.PredictionHistory.predicted_disease.ilike(f"%{search}%"))
    if user_email:
        q = q.filter(models.User.email.ilike(f"%{user_email}%"))
    if start_date:
        q = q.filter(models.PredictionHistory.created_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        q = q.filter(models.PredictionHistory.created_at <= datetime.combine(end_date, datetime.max.time()))

    total = q.count()
    rows = q.order_by(models.PredictionHistory.created_at.desc()).offset(skip).limit(limit).all()

    items = [
        schemas.AdminPredictionOut(
            id=row.id,
            user_email=email,
            symptoms_submitted=parse_json_list(row.symptoms_submitted),
            predicted_disease=row.predicted_disease,
            confidence=row.confidence,
            created_at=row.created_at,
        )
        for row, email in rows
    ]
    return schemas.AdminPredictionPage(items=items, total=total)
