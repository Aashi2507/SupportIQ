
from pathlib import Path

import joblib

from similar_tickets import find_similar_tickets
from sentiment_analysis import analyze_sentiment


# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE_DIR / "models"

CATEGORY_MODEL_PATH = MODEL_DIR / "category_model.joblib"
PRIORITY_MODEL_PATH = MODEL_DIR / "priority_model.joblib"


def _load_model(path: Path):
    """Load a saved machine learning pipeline."""
    if not path.exists():
        raise FileNotFoundError(f"Model file not found: {path}")

    return joblib.load(path)


# Load classification models once when this module is imported.
category_model = _load_model(CATEGORY_MODEL_PATH)
priority_model = _load_model(PRIORITY_MODEL_PATH)


def analyze_ticket(complaint: str) -> dict:
    """
    Analyze a customer complaint.

    Returns category, priority, sentiment, and similar historical tickets.
    """
    if not isinstance(complaint, str) or not complaint.strip():
        raise ValueError("Please enter a valid complaint.")

    complaint = complaint.strip()

    # Predict the support queue and ticket priority.
    category = str(category_model.predict([complaint])[0])
    priority = str(priority_model.predict([complaint])[0])

    # Analyze customer sentiment.
    sentiment = analyze_sentiment(complaint)

    # Find similar historical tickets.
    matches = find_similar_tickets(complaint, top_n=5)

    # Convert the DataFrame into a list of dictionaries for the UI.
    similar_tickets = matches.to_dict(orient="records")

    # Convert NumPy numeric values to standard Python floats.
    for ticket in similar_tickets:
        if "similarity_score" in ticket:
            ticket["similarity_score"] = float(ticket["similarity_score"])

    return {
        "category": category,
        "priority": priority,
        "sentiment": sentiment,
        "similar_tickets": similar_tickets,
    }
