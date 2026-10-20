
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, f1_score, classification_report
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC


# All outputs stay inside this experiment folder.
ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = Path(__file__).resolve().parent
TRAIN_PATH = ROOT / "data" / "train.csv"
TEST_PATH = ROOT / "data" / "test.csv"


def load_dataset(path):
    df = pd.read_csv(path)

    required = {"body", "queue", "priority"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path.name} is missing columns: {sorted(missing)}")

    if "subject" not in df.columns:
        df["subject"] = ""

    df["subject"] = df["subject"].fillna("").astype(str)
    df["body"] = df["body"].fillna("").astype(str)

    df["text"] = (
        df["subject"].str.strip()
        + " "
        + df["body"].str.strip()
    ).str.strip()

    return df


def main():
    if not TRAIN_PATH.exists() or not TEST_PATH.exists():
        raise FileNotFoundError(
            "Could not find data/train.csv or data/test.csv."
        )

    train = load_dataset(TRAIN_PATH)
    test = load_dataset(TEST_PATH)

    print(f"Training rows: {len(train)}")
    print(f"Test rows: {len(test)}")
    print("\nExperiment: subject + body")
    print("Existing model files will not be changed.")

    for target in ("queue", "priority"):
        train_part = train.dropna(subset=[target])
        test_part = test.dropna(subset=[target])

        model = Pipeline([
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
                    C=1.0,
                    class_weight="balanced",
                    max_iter=5000,
                    random_state=42,
                ),
            ),
        ])

        model.fit(train_part["text"], train_part[target])
        predictions = model.predict(test_part["text"])

        accuracy = accuracy_score(test_part[target], predictions)
        macro_f1 = f1_score(
            test_part[target],
            predictions,
            average="macro",
            zero_division=0,
        )

        print(f"\n{'=' * 55}")
        print(f"Target: {target}")
        print(f"Accuracy: {accuracy:.4f}")
        print(f"Macro F1: {macro_f1:.4f}")
        print("\nClassification report:")
        print(
            classification_report(
                test_part[target],
                predictions,
                zero_division=0,
            )
        )

        report_path = OUTPUT_DIR / f"subject_body_{target}_report.txt"
        report_path.write_text(
            f"Target: {target}\n"
            f"Features: subject + body\n"
            f"Accuracy: {accuracy:.4f}\n"
            f"Macro F1: {macro_f1:.4f}\n\n"
            + classification_report(
                test_part[target],
                predictions,
                zero_division=0,
            ),
            encoding="utf-8",
        )

    print(f"\nReports saved in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
