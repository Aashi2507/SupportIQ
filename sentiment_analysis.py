
from transformers import pipeline

# Load a pretrained sentiment-analysis model
print("Loading sentiment analysis model...")
print("The first run may download model files.")

sentiment_model = pipeline(
    "sentiment-analysis",
    model="distilbert/distilbert-base-uncased-finetuned-sst-2-english",
)


def analyze_sentiment(text):
    """Classify English text as POSITIVE or NEGATIVE."""
    if not text or not text.strip():
        raise ValueError("Please enter a complaint.")

    result = sentiment_model(text.strip(), truncation=True)[0]

    return {
        "sentiment": result["label"].lower(),
        "score": round(float(result["score"]), 4),
    }


if __name__ == "__main__":
    print("\nSupportIQ - Sentiment Analysis")
    print("-" * 40)

    complaint = input("Enter a customer complaint: ")

    try:
        result = analyze_sentiment(complaint)

        print(f"\nSentiment: {result['sentiment']}")
        print(f"Model score: {result['score']:.2%}")

    except ValueError as error:
        print(f"Error: {error}")
