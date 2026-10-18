
from pathlib import Path

import joblib
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    ConfusionMatrixDisplay,
)

# Project folders
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "models"

MODEL_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_PATH = DATA_DIR / "train.csv"
TEST_PATH = DATA_DIR / "test.csv"


def load_data(path):
    """Load and clean the prepared ticket dataset."""
    df = pd.read_csv(path)

    df = df.dropna(
        subset=["body", "queue", "priority"]
    ).copy()

    for column in ["body", "queue", "priority"]:
        df[column] = df[column].astype(str).str.strip()

    df = df[
        (df["body"] != "")
        & (df["queue"] != "")
        & (df["priority"] != "")
    ]

    return df


def train_classifier(train_df, test_df, target, model_name):
    """Train, evaluate, and save a text classification model."""

    X_train = train_df["body"]
    y_train = train_df[target]

    X_test = test_df["body"]
    y_test = test_df[target]

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
            LogisticRegression(
                max_iter=1000,
                class_weight="balanced",
            ),
        ),
    ])

    print(f"\nTraining {model_name} model...")

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    # Evaluate the model
    accuracy = accuracy_score(y_test, predictions)

    print(f"\n{model_name} accuracy: {accuracy:.4f}")
    print("\nClassification report:")

    report = classification_report(
        y_test,
        predictions,
        zero_division=0,
    )

    print(report)

    # Save the evaluation report
    report_path = MODEL_DIR / f"{model_name}_report.txt"

    with open(report_path, "w", encoding="utf-8") as file:
        file.write(f"Model: {model_name}\n")
        file.write(f"Accuracy: {accuracy:.4f}\n\n")
        file.write(report)

    print(f"Evaluation report saved: {report_path}")

    # Save the trained model
    model_path = MODEL_DIR / f"{model_name}_model.joblib"

    joblib.dump(model, model_path)

    print(f"Saved model: {model_path}")

    # Save a confusion matrix for the category model only
    if model_name == "category":
        disp = ConfusionMatrixDisplay.from_predictions(
            y_test,
            predictions,
            xticks_rotation="vertical",
            cmap="Blues",
        )

        disp.figure_.tight_layout()

        matrix_path = MODEL_DIR / "category_confusion_matrix.png"

        disp.figure_.savefig(
            matrix_path,
            dpi=200,
            bbox_inches="tight",
        )

        plt.close(disp.figure_)

        print(f"Confusion matrix saved: {matrix_path}")


def main():
    print("Loading prepared datasets...")

    if not TRAIN_PATH.exists() or not TEST_PATH.exists():
        raise FileNotFoundError(
            "Training or testing data is missing. "
            "Run prepare_data.py first."
        )

    train_df = load_data(TRAIN_PATH)
    test_df = load_data(TEST_PATH)

    print(f"Training rows: {len(train_df)}")
    print(f"Testing rows: {len(test_df)}")

    # Train the category classifier
    train_classifier(
        train_df,
        test_df,
        target="queue",
        model_name="category",
    )

    # Train the priority classifier
    train_classifier(
        train_df,
        test_df,
        target="priority",
        model_name="priority",
    )

    print("\nBoth models trained and evaluated successfully!")


if __name__ == "__main__":
    main()
