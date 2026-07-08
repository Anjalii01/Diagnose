"""
Retrains the disease-prediction SVM with probability=True so /predict can
return real, calibrated confidence scores (via predict_proba) instead of
the old softmax-over-decision_function approximation.

Run this once from the backend/ folder:
    python retrain_model.py

It reads data/Training.csv, trains a linear SVC with probability estimates
enabled, and overwrites data/svc.pkl. Your existing venv already has
scikit-learn and pandas installed (they're in requirements.txt), so no new
dependencies are needed.
"""

import joblib
import pandas as pd
from sklearn.svm import SVC
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split

DATA_PATH = "data/Training.csv"
MODEL_OUT = "data/svc.pkl"

print(f"Loading {DATA_PATH} ...")
df = pd.read_csv(DATA_PATH)

feature_columns = [c for c in df.columns if c != "prognosis"]
X = df[feature_columns]

le = LabelEncoder()
y = le.fit_transform(df["prognosis"])

print(f"{len(feature_columns)} features, {len(le.classes_)} disease classes, {len(df)} rows")

# Hold out a small test split just to sanity-check accuracy after training.
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

print("Training SVC with probability=True (this enables predict_proba)...")
model = SVC(kernel="linear", probability=True, random_state=42)
model.fit(X_train, y_train)

train_acc = model.score(X_train, y_train)
test_acc = model.score(X_test, y_test)
print(f"Train accuracy: {train_acc:.4f}")
print(f"Test accuracy:  {test_acc:.4f}")

# Retrain on the FULL dataset for the final saved model (more data = better),
# now that we've confirmed accuracy looks sane on the held-out split.
print("Refitting on full dataset for the final saved model...")
final_model = SVC(kernel="linear", probability=True, random_state=42)
final_model.fit(X, y)

joblib.dump(final_model, MODEL_OUT)
print(f"Saved new model to {MODEL_OUT}")
print("Done. Restart your backend server (uvicorn) to load the new model.")
