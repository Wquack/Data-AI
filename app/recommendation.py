from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import logging

logger = logging.getLogger(__name__)

# Load model and tokenizer
MODEL_NAME = "distilbert-base-uncased-finetuned-sst-2-english"
try:
    logger.info("Loading model and tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
    logger.info("Model and tokenizer loaded successfully")
except Exception as e:
    logger.error(f"Failed to load model: {e}")
    raise

def select_task(event_summary, predicted_class):
    """Select task based on event summary keywords and model prediction."""
    event_summary = event_summary.lower()
    if 'meeting' in event_summary or 'conference' in event_summary:
        return "Prepare slides"
    elif 'deadline' in event_summary or 'project' in event_summary:
        return "Review notes"
    elif 'appointment' in event_summary or 'doctor' in event_summary:
        return "Bring documents"
    else:
        return "Plan schedule" if predicted_class == 1 else "No task recommended"

def get_recommendation(event_summary):
    """Generate task recommendation using DistilBERT."""
    inputs = tokenizer(event_summary, return_tensors="pt", padding=True, truncation=True)
    logger.info(f"Tokenized input: {inputs['input_ids']}")
    with torch.no_grad():
        outputs = model(**inputs)
    logits = outputs.logits
    predicted_class = torch.argmax(logits, dim=1).item()
    logger.info(f"Predicted class: {predicted_class}")
    return select_task(event_summary, predicted_class)