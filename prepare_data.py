
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "dataset-tickets-multi-lang-4-20k.csv"
OUTPUT_DIR = BASE_DIR / "data"

print("Loading original dataset...")
df = pd.read_csv(DATA_PATH)

print(f"Original rows: {len(df)}")

# Keep English-language tickets
df = df[df["language"].astype(str).str.lower() == "en"].copy()
print(f"English tickets: {len(df)}")

# Remove rows missing required fields
df = df.dropna(subset=["body", "queue", "priority"])

# Clean complaint text and labels
for column in ["body", "queue", "priority"]:
    df[column] = df[column].astype(str).str.strip()

df = df[
    (df["body"] != "")
    & (df["queue"] != "")
    & (df["priority"] != "")
]

# Remove exact duplicate complaint text
before = len(df)
df = df.drop_duplicates(subset=["body"])
print(f"Duplicate complaint rows removed: {before - len(df)}")

# Save cleaned data
clean_path = OUTPUT_DIR / "tickets_clean.csv"
df.to_csv(clean_path, index=False)

# Create reproducible training and test splits
from sklearn.model_selection import train_test_split

train_df, test_df = train_test_split(
    df,
    test_size=0.2,
    random_state=42,
    stratify=df["queue"],
)

train_df.to_csv(OUTPUT_DIR / "train.csv", index=False)
test_df.to_csv(OUTPUT_DIR / "test.csv", index=False)

# Save a summary report
report_path = OUTPUT_DIR / "report.txt"
with open(report_path, "w", encoding="utf-8") as report:
    report.write(f"Original rows: {20000}\n")
    report.write(f"Cleaned English rows: {len(df)}\n")
    report.write(f"Training rows: {len(train_df)}\n")
    report.write(f"Testing rows: {len(test_df)}\n\n")
    report.write("Category counts:\n")
    report.write(df["queue"].value_counts().to_string())
    report.write("\n\nPriority counts:\n")
    report.write(df["priority"].value_counts().to_string())

print("\nDataset preparation complete!")
print(f"Clean dataset: {clean_path}")
print(f"Training set: {len(train_df)} rows")
print(f"Test set: {len(test_df)} rows")
print(f"Report: {report_path}")
