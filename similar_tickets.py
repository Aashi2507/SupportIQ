
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

# Project paths
BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"

VECTORIZER_PATH = MODEL_DIR / "similarity_vectorizer.joblib"
VECTORS_PATH = MODEL_DIR / "similarity_vectors.joblib"
TICKETS_PATH = MODEL_DIR / "similarity_tickets.csv"


def load_similarity_index():
    """Load the saved TF-IDF index and historical tickets."""
    required_files = [
        VECTORIZER_PATH,
        VECTORS_PATH,
        TICKETS_PATH,
    ]

    for path in required_files:
        if not path.exists():
            raise FileNotFoundError(
                f"Required file not found: {path}\n"
                "Run build_similarity_index.py first."
            )

    vectorizer = joblib.load(VECTORIZER_PATH)
    ticket_vectors = joblib.load(VECTORS_PATH)
    tickets = pd.read_csv(TICKETS_PATH)

    if ticket_vectors.shape[0] != len(tickets):
        raise ValueError(
            "Ticket data and saved vectors do not match."
        )

    return vectorizer, ticket_vectors, tickets


def find_similar_tickets(complaint, top_n=5):
    """Find the most similar historical complaints."""
    if not complaint or not complaint.strip():
        raise ValueError("Please enter a complaint.")

    vectorizer, ticket_vectors, tickets = load_similarity_index()

    complaint_vector = vectorizer.transform([complaint.strip()])

    scores = cosine_similarity(
        complaint_vector,
        ticket_vectors,
    ).flatten()

    results = tickets.copy()
    results["similarity_score"] = scores

    results = results[results["similarity_score"] > 0]
    results = results.sort_values(
        "similarity_score",
        ascending=False,
    ).head(top_n)

    columns = [
        column
        for column in ["subject", "body", "queue", "priority"]
        if column in results.columns
    ]
    columns.append("similarity_score")

    return results[columns]


if __name__ == "__main__":
    print("SupportIQ - Similar Ticket Search")
    print("-" * 40)

    complaint = input("Enter a customer complaint: ")

    try:
        matches = find_similar_tickets(complaint, top_n=5)

        if matches.empty:
            print("\nNo similar tickets found.")
        else:
            print("\nMost similar historical tickets:\n")

            for rank, (_, ticket) in enumerate(
                matches.iterrows(), start=1
            ):
                print(f"Match #{rank}")
                print(
                    f"Similarity: "
                    f"{ticket['similarity_score']:.2%}"
                )
                print(f"Category: {ticket['queue']}")
                print(f"Priority: {ticket['priority']}")
                print(f"Complaint: {ticket['body'][:300]}")
                print("-" * 40)

    except (ValueError, FileNotFoundError) as error:
        print(f"\nError: {error}")
