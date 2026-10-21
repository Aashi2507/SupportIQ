
from pathlib import Path

import joblib
import pandas as pd

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC
from sklearn.metrics import accuracy_score, f1_score, classification_report


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "models"

TRAIN_PATH = DATA_DIR / "train.csv"
TEST_PATH = DATA_DIR / "test.csv"

# These are NEW files. The app's current models remain unchanged.
CANDIDATES = {
    "queue": "category_svm_candidate_v2.joblib",
    "priority": "priority_svm_candidate.joblib",
}


def load_data(path):
    df = pd.read_csv(path)
    df = df.dropna(subset=["body", "queue", "priority"]).copy()

    for column in ["body", "queue", "priority"]:
        df[column] = df[column].astype(str).str.strip()

    return df[
        (df["body"] != "")
        & (df["queue"] != "")
        & (df["priority"] != "")
    ].copy()


def build_model():
    return Pipeline([
        (
            "tfidf",
            TfidfVectorizer(
                lowercase=True,
                ngram_range=(1, 2),
                max_features=50000,
                sublinear_tf=True,
            ),
        ),
        (
            "classifier",
            LinearSVC(
                class_weight="balanced",
                max_iter=3000,
                random_state=42,
            ),
        ),
    ])


def main():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    train_df = load_data(TRAIN_PATH)
    test_df = load_data(TEST_PATH)

    print("Training rows:", len(train_df))
    print("Testing rows:", len(test_df))

    reports = []

    for target, filename in CANDIDATES.items():
        print(f"\nTraining SVM for {target}...")

        model = build_model()
        model.fit(train_df["body"], train_df[target])

        predictions = model.predict(test_df["body"])
        actual = test_df[target]

        accuracy = accuracy_score(actual, predictions)
        macro_f1 = f1_score(
            actual, predictions, average="macro", zero_division=0
        )

        report = classification_report(
            actual, predictions, zero_division=0
        )

        print(f"Accuracy: {accuracy:.4f}")
        print(f"Macro F1: {macro_f1:.4f}")
        print(report)

        model_path = MODEL_DIR / filename
        joblib.dump(model, model_path)

        reports.append(
            f"TASK: {target}\n"
            f"MODEL: {filename}\n"
            f"TEST ROWS: {len(test_df)}\n"
            f"ACCURACY: {accuracy:.4f}\n"
            f"MACRO F1: {macro_f1:.4f}\n\n"
            f"{report}\n"
            f"{'=' * 60}\n"
        )

        print("Saved candidate:", model_path)

    report_path = MODEL_DIR / "svm_candidate_evaluation.txt"
    report_path.write_text("\n".join(reports), encoding="utf-8")

    print("\nCandidate training and evaluation complete.")
    print("Evaluation report:", report_path)
    print("The app's current models were not modified.")


if __name__ == "__main__":
    main()

