
import logging
from pathlib import Path

import joblib


logger = logging.getLogger(__name__)

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


# Load required classification models once.
category_model = _load_model(CATEGORY_MODEL_PATH)
priority_model = _load_model(PRIORITY_MODEL_PATH)


def analyze_ticket(complaint: str) -> dict:
    """Analyze a complaint; secondary-feature failures are non-fatal."""
    if not isinstance(complaint, str) or not complaint.strip():
        raise ValueError("Please enter a valid complaint.")

    complaint = complaint.strip()

    # Core predictions are required. Do not invent them if prediction fails.
    category = str(category_model.predict([complaint])[0])
    priority = str(priority_model.predict([complaint])[0])

    sentiment = None
    similar_tickets = []
    warnings = []

    # Sentiment is optional. Its failure should not block ticket submission.
    try:
        from sentiment_analysis import analyze_sentiment

        sentiment = analyze_sentiment(complaint)
    except Exception:
        logger.exception("Sentiment analysis failed")
        warnings.append("Sentiment analysis is temporarily unavailable.")

    # Similar-ticket search is optional too.
    try:
        from similar_tickets import find_similar_tickets

        matches = find_similar_tickets(complaint, top_n=5)
        similar_tickets = matches.to_dict(orient="records")

        for ticket in similar_tickets:
            if "similarity_score" in ticket:
                ticket["similarity_score"] = float(
                    ticket["similarity_score"]
                )
    except Exception:
        logger.exception("Similar-ticket search failed")
        warnings.append("Similar-ticket search is temporarily unavailable.")

    return {
        "category": category,
        "priority": priority,
        "sentiment": sentiment,
        "similar_tickets": similar_tickets,
        "warnings": warnings,
    }
