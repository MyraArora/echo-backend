import re
import spacy

# Load spaCy small English model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    # Fallback if model hasn't been downloaded yet
    import spacy.cli
    spacy.cli.download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

FILLER_WORDS = {"uh", "um", "like", "hmm", "ah", "er", "you know", "basically", "actually"}

def extract_lexical_syntactic_features(transcript: str) -> dict:
    """
    Extracts lexical diversity and syntactic complexity markers from a transcript:
    - Type-Token Ratio (TTR) - Vocabulary Richness
    - Filler Word Count & Ratio
    - Mean Sentence Length / Words per Sentence
    - Pronoun-to-Noun Ratio
    """
    if not transcript or not transcript.strip():
        return {
            "total_words": 0,
            "unique_words": 0,
            "ttr_score": 0.0,
            "filler_count": 0,
            "filler_ratio": 0.0,
            "mean_sentence_length": 0.0,
            "pronoun_noun_ratio": 0.0
        }

    # Normalize text for token analysis
    clean_text = transcript.lower()
    doc = nlp(clean_text)

    # 1. Total Words & Type-Token Ratio (TTR)
    words = [token.text for token in doc if token.is_alpha]
    total_words = len(words)
    unique_words = len(set(words))
    ttr = unique_words / total_words if total_words > 0 else 0.0

    # 2. Filler Word Detection
    filler_count = 0
    # Single-word fillers
    for word in words:
        if word in FILLER_WORDS:
            filler_count += 1
            
    # Multi-word fillers (e.g., "you know")
    for filler in {"you know"}:
        filler_count += len(re.findall(r'\b' + re.escape(filler) + r'\b', clean_text))

    filler_ratio = filler_count / total_words if total_words > 0 else 0.0

    # 3. Syntactic Complexity (Sentence Lengths)
    sentences = list(doc.sents)
    num_sentences = len(sentences)
    words_per_sentence = total_words / num_sentences if num_sentences > 0 else 0.0

    # 4. Pronoun vs Noun balance
    nouns = sum(1 for token in doc if token.pos_ in {"NOUN", "PROPN"})
    pronouns = sum(1 for token in doc if token.pos_ == "PRON")
    pronoun_noun_ratio = pronouns / nouns if nouns > 0 else float(pronouns)

    return {
        "total_words": total_words,
        "unique_words": unique_words,
        "ttr_score": round(float(ttr), 4),
        "filler_count": filler_count,
        "filler_ratio": round(float(filler_ratio), 4),
        "mean_sentence_length": round(float(words_per_sentence), 2),
        "pronoun_noun_ratio": round(float(pronoun_noun_ratio), 2)
    }
