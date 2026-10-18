
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

# Project paths
BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "tickets_clean.csv"
MODEL_DIR = BASE_DIR / "models"

MODEL_DIR.mkdir(parents=True, exist_ok=True)


def main():
    print("Loading historical tickets...")

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATA_PATH}. "
            "Run prepare_data.py first."
        )

    df = pd.read_csv(DATA_PATH)
    df = df.dropna(subset=["body", "queue", "priority"]).copy()

    for column in ["body", "queue", "priority"]:
        df[column] = df[column].astype(str).str.strip()

    df = df[df["body"] != ""].reset_index(drop=True)

    print(f"Historical tickets: {len(df)}")

    print("Building TF-IDF index...")

    vectorizer = TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        max_features=50000,
        sublinear_tf=True,
    )

    ticket_vectors = vectorizer.fit_transform(df["body"])

    # Save the fitted vectorizer and ticket vectors
    joblib.dump(
        vectorizer,
        MODEL_DIR / "similarity_vectorizer.joblib",
    )

    joblib.dump(
        ticket_vectors,
        MODEL_DIR / "similarity_vectors.joblib",
    )

    # Save tickets in the same order as the vectors
    df.to_csv(
        MODEL_DIR / "similarity_tickets.csv",
        index=False,
    )

    print("\nSimilarity index built successfully!")
    print(f"Vectorizer: {MODEL_DIR / 'similarity_vectorizer.joblib'}")
    print(f"Ticket vectors: {MODEL_DIR / 'similarity_vectors.joblib'}")
    print(f"Ticket data: {MODEL_DIR / 'similarity_tickets.csv'}")


if __name__ == "__main__":
    main()
