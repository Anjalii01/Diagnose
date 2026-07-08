"""
ONE-TIME migration script.

Reads all the CSV files in ./data and inserts their rows into the database
defined in database.py (SQLite by default, Postgres if you set DATABASE_URL).

Run this once after setting up the project, and again any time you replace
the CSVs with updated data.

Usage:
    python migrate_csv_to_db.py
"""

import json
import ast
import pandas as pd

from database import engine, SessionLocal, Base
import models

DATA_DIR = "data"


def parse_list_string(value: str):
    """
    The medications/diets columns store python-list-looking strings, e.g.
        "['Antifungal Cream', 'Fluconazole']"
    Convert them into a real Python list safely (no eval of arbitrary code).
    """
    try:
        parsed = ast.literal_eval(value)
        if isinstance(parsed, list):
            return parsed
        return [str(parsed)]
    except (ValueError, SyntaxError):
        return [value]


def migrate():
    print("Creating tables (if they don't already exist)...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        # ---- Symptoms ----
        print("Migrating symptoms...")
        df = pd.read_csv(f"{DATA_DIR}/Symptom-severity.csv")
        df.columns = [c.strip() for c in df.columns]
        df = df.drop_duplicates(subset="Symptom")  # source CSV has a duplicate row
        for _, row in df.iterrows():
            name = str(row["Symptom"]).strip()
            existing = db.query(models.Symptom).filter_by(name=name).first()
            if not existing:
                db.add(models.Symptom(name=name, weight=int(row["weight"])))
        db.commit()

        # ---- Descriptions ----
        print("Migrating disease descriptions...")
        df = pd.read_csv(f"{DATA_DIR}/description.csv")
        for _, row in df.iterrows():
            disease = str(row["Disease"]).strip()
            existing = db.query(models.DiseaseDescription).filter_by(disease=disease).first()
            if not existing:
                db.add(models.DiseaseDescription(disease=disease, description=str(row["Description"]).strip()))
        db.commit()

        # ---- Precautions ----
        print("Migrating precautions...")
        df = pd.read_csv(f"{DATA_DIR}/precautions_df.csv")
        df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
        for _, row in df.iterrows():
            disease = str(row["Disease"]).strip()
            existing = db.query(models.DiseasePrecaution).filter_by(disease=disease).first()
            if not existing:
                db.add(models.DiseasePrecaution(
                    disease=disease,
                    precaution_1=row.get("Precaution_1"),
                    precaution_2=row.get("Precaution_2"),
                    precaution_3=row.get("Precaution_3"),
                    precaution_4=row.get("Precaution_4"),
                ))
        db.commit()

        # ---- Medications ----
        print("Migrating medications...")
        df = pd.read_csv(f"{DATA_DIR}/medications.csv")
        for _, row in df.iterrows():
            disease = str(row["Disease"]).strip()
            existing = db.query(models.DiseaseMedication).filter_by(disease=disease).first()
            if not existing:
                meds = parse_list_string(row["Medication"])
                db.add(models.DiseaseMedication(disease=disease, medications=json.dumps(meds)))
        db.commit()

        # ---- Diets ----
        print("Migrating diets...")
        df = pd.read_csv(f"{DATA_DIR}/diets.csv")
        for _, row in df.iterrows():
            disease = str(row["Disease"]).strip()
            existing = db.query(models.DiseaseDiet).filter_by(disease=disease).first()
            if not existing:
                diet_list = parse_list_string(row["Diet"])
                db.add(models.DiseaseDiet(disease=disease, diet=json.dumps(diet_list)))
        db.commit()

        # ---- Workouts ----
        print("Migrating workouts...")
        df = pd.read_csv(f"{DATA_DIR}/workout_df.csv")
        df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
        for _, row in df.iterrows():
            db.add(models.DiseaseWorkout(disease=str(row["disease"]).strip(), workout=str(row["workout"]).strip()))
        db.commit()

        print("Migration complete!")

        # Quick sanity counts
        print("\nRow counts:")
        print("  symptoms:", db.query(models.Symptom).count())
        print("  descriptions:", db.query(models.DiseaseDescription).count())
        print("  precautions:", db.query(models.DiseasePrecaution).count())
        print("  medications:", db.query(models.DiseaseMedication).count())
        print("  diets:", db.query(models.DiseaseDiet).count())
        print("  workouts:", db.query(models.DiseaseWorkout).count())

    finally:
        db.close()


if __name__ == "__main__":
    migrate()
