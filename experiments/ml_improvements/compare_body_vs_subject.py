
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, f1_score
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = Path(__file__).resolve().parent
TRAIN_PATH = ROOT / "data" / "train.csv"
TEST_PATH = ROOT / "data" / "test.csv"
RESULT_PATH = OUTPUT_DIR / "body_vs_subject_comparison.csv"


def load_data(path):
    df = pd.read_csv(path)

    required = {"body", "queue", "priority"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path.name} is missing columns: {sorted(missing)}")

    if "subject" not in df.columns:
        df["subject"] = ""

    df["subject"] = df["subject"].fillna("").astype(str)
    df["body"] = df["body"].fillna("").astype(str)
    df["body_text"] = df["body"].str.strip()
    df["combined_text"] = (
        df["subject"].str.strip() + " " + df["body"].str.strip()
    ).str.strip()

    return df


def make_model():
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            max_features=50000,
            sublinear_tf=True,
        )),
        ("classifier", LinearSVC(
            C=1.0,
            class_weight="balanced",
            max_iter=5000,
            random_state=42,
        )),
    ])


def main():
    if RESULT_PATH.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing results: {RESULT_PATH}"
        )

    train = load_data(TRAIN_PATH)
    test = load_data(TEST_PATH)

    results = []

    for target in ("queue", "priority"):
        train_part = train.dropna(subset=[target])
        test_part = test.dropna(subset=[target])

        for feature_name, column in (
            ("body_only", "body_text"),
            ("subject_plus_body", "combined_text"),
        ):
            model = make_model()
            model.fit(train_part[column], train_part[target])
            predictions = model.predict(test_part[column])

            accuracy = accuracy_score(test_part[target], predictions)
            macro_f1 = f1_score(
                test_part[target],
                predictions,
                average="macro",
                zero_division=0,
            )

            results.append({
                "target": target,
                "features": feature_name,
                "accuracy": round(accuracy, 4),
                "macro_f1": round(macro_f1, 4),
                "test_rows": len(test_part),
            })

            print(
                f"{target:8} | {feature_name:18} | "
                f"accuracy={accuracy:.4f} | macro_f1={macro_f1:.4f}"
            )

    pd.DataFrame(results).to_csv(RESULT_PATH, index=False)
    print(f"\nComparison saved to: {RESULT_PATH}")


if __name__ == "__main__":
    main()
