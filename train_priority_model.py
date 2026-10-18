
from pathlib import Path

import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report

# Project paths
BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "polaris_tickets_v2.csv"
MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Load dataset
df = pd.read_csv(DATA_PATH)

# Keep rows with valid complaint text and priority labels
df = df.dropna(subset=["body", "priority"])
df["body"] = df["body"].astype(str).str.strip()
df["priority"] = df["priority"].astype(str).str.strip()
df = df[(df["body"] != "") & (df["priority"] != "")]

# Avoid duplicate text-label pairs
df = df.drop_duplicates(subset=["body", "priority"])

# Features and target
X = df["body"]
y = df["priority"]

# Split into training and testing data
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y,
)

# Build and train the model
model = Pipeline([
    ("tfidf", TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        max_features=50000,
        sublinear_tf=True,
    )),
    ("classifier", LogisticRegression(
        max_iter=1000,
        class_weight="balanced",
    )),
])

print("Training priority classifier...")
model.fit(X_train, y_train)

# Evaluate the model
predictions = model.predict(X_test)

print("\nAccuracy:", round(accuracy_score(y_test, predictions), 4))
print("\nClassification report:")
print(classification_report(y_test, predictions, zero_division=0))

# Save the model
model_path = MODEL_DIR / "priority_model.joblib"
joblib.dump(model, model_path)

print(f"\nModel saved to: {model_path}")
print("Priority model training complete!")
