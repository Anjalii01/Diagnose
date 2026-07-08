"""
Maps free-text symptom descriptions (typed by the user in their own words,
English or Hinglish) onto the fixed set of 132 symptom columns the model
was trained on.

Two layers are combined:
1. A hand-written synonym map for common ways people describe symptoms
   (including common Hinglish terms) -> the exact training-data symptom key.
2. Fuzzy string matching (stdlib difflib, no extra dependency) against the
   readable symptom names, to catch phrasings not covered by the synonym map.

This does NOT expand the list of diseases/symptoms the model knows about —
it only makes it easier for the user to reach the existing 132 symptoms by
typing naturally instead of picking from a checklist.
"""

import re
import json
import difflib
from typing import List, Dict, Tuple

# ---- Synonym map: phrase -> one or more exact symptom keys from Training.csv ----
# Keys are checked as substrings of the (lowercased) input text.
SYMPTOM_SYNONYMS: Dict[str, List[str]] = {
    "fever": ["high_fever", "mild_fever"],
    "bukhar": ["high_fever", "mild_fever"],
    "high temperature": ["high_fever"],
    "cold": ["chills", "shivering", "runny_nose", "congestion"],
    "thand lagna": ["chills", "shivering"],
    "sardi": ["runny_nose", "congestion", "continuous_sneezing"],
    "cough": ["cough"],
    "khansi": ["cough"],
    "sneeze": ["continuous_sneezing"],
    "chheenk": ["continuous_sneezing"],
    "headache": ["headache"],
    "sar dard": ["headache"],
    "sir dard": ["headache"],
    "migraine": ["headache", "pain_behind_the_eyes", "visual_disturbances"],
    "stomach ache": ["stomach_pain", "abdominal_pain"],
    "stomach pain": ["stomach_pain", "abdominal_pain"],
    "pet dard": ["stomach_pain", "abdominal_pain", "belly_pain"],
    "pet me dard": ["stomach_pain", "abdominal_pain", "belly_pain"],
    "vomit": ["vomiting"],
    "ulti": ["vomiting"],
    "throw up": ["vomiting"],
    "diarrhea": ["diarrhoea"],
    "diarrhoea": ["diarrhoea"],
    "loose motion": ["diarrhoea"],
    "loose motions": ["diarrhoea"],
    "tired": ["fatigue", "lethargy"],
    "thakan": ["fatigue", "lethargy"],
    "weak": ["weakness_in_limbs", "muscle_weakness"],
    "kamzori": ["weakness_in_limbs", "muscle_weakness", "fatigue"],
    "rash": ["skin_rash"],
    "skin rash": ["skin_rash"],
    "khujli": ["itching"],
    "itch": ["itching"],
    "itchy": ["itching"],
    "joint pain": ["joint_pain"],
    "jodo me dard": ["joint_pain"],
    "back pain": ["back_pain"],
    "kamar dard": ["back_pain"],
    "dizzy": ["dizziness", "spinning_movements"],
    "chakkar": ["dizziness", "spinning_movements"],
    "chest pain": ["chest_pain"],
    "seene me dard": ["chest_pain"],
    "breathless": ["breathlessness"],
    "shortness of breath": ["breathlessness"],
    "saans lene me": ["breathlessness"],
    "jaundice": ["yellowing_of_eyes", "yellowish_skin", "dark_urine"],
    "peela": ["yellowing_of_eyes", "yellowish_skin"],
    "weight loss": ["weight_loss"],
    "wajan kam": ["weight_loss"],
    "weight gain": ["weight_gain"],
    "wajan zyada": ["weight_gain"],
    "sore throat": ["throat_irritation", "patches_in_throat"],
    "gale me kharash": ["throat_irritation"],
    "runny nose": ["runny_nose"],
    "nak behna": ["runny_nose"],
    "nausea": ["nausea"],
    "jee michalna": ["nausea"],
    "loss of appetite": ["loss_of_appetite"],
    "bhookh na lagna": ["loss_of_appetite"],
    "anxiety": ["anxiety"],
    "depression": ["depression"],
    "constipation": ["constipation"],
    "kabj": ["constipation"],
    "gas": ["acidity", "passage_of_gases"],
    "acidity": ["acidity"],
    "body pain": ["muscle_pain", "joint_pain"],
    "body ache": ["muscle_pain"],
    "neck pain": ["neck_pain"],
    "gardan dard": ["neck_pain"],
    "knee pain": ["knee_pain"],
    "ghutno me dard": ["knee_pain"],
    "swelling": ["swelling_joints", "swollen_legs"],
    "soojan": ["swelling_joints", "swollen_legs"],
    "sweating": ["sweating"],
    "paseena": ["sweating"],
    "blurred vision": ["blurred_and_distorted_vision", "visual_disturbances"],
    "dhundla dikhna": ["blurred_and_distorted_vision"],
    "urination": ["burning_micturition", "polyuria"],
    "peshab me jalan": ["burning_micturition"],
    "excessive thirst": ["polyuria", "excessive_hunger"],
    "excessive hunger": ["excessive_hunger"],
    "bhookh zyada": ["excessive_hunger"],
    "red eyes": ["redness_of_eyes"],
    "aankhen lal": ["redness_of_eyes"],
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _readable(symptom_key: str) -> str:
    return symptom_key.replace("_", " ").replace(".1", "").strip()


def match_text_to_symptoms(
    text: str, valid_symptoms: List[str], fuzzy_threshold: float = 0.72, max_results: int = 15
) -> List[Tuple[str, float, str]]:
    """
    Returns a list of (symptom_key, confidence_0_to_1, matched_on) tuples,
    sorted by confidence descending, deduplicated by symptom_key.
    'matched_on' is either 'synonym' or 'fuzzy', for transparency in the UI.
    """
    normalized = _normalize(text)
    valid_set = set(valid_symptoms)
    found: Dict[str, Tuple[float, str]] = {}

    # Layer 1: synonym substring matches (high confidence, exact intent match)
    for phrase, symptom_keys in SYMPTOM_SYNONYMS.items():
        if phrase in normalized:
            for key in symptom_keys:
                if key in valid_set:
                    # Keep the highest-confidence match if a symptom is hit twice
                    if key not in found or found[key][0] < 0.95:
                        found[key] = (0.95, "synonym")

    # Layer 2: fuzzy matching of readable symptom names against the free text,
    # word-by-word and using bigrams, to catch phrasings the synonym map misses.
    words = normalized.split()
    windows = words + [
        " ".join(words[i : i + 2]) for i in range(len(words) - 1)
    ] + [
        " ".join(words[i : i + 3]) for i in range(len(words) - 2)
    ]

    for key in valid_symptoms:
        if key in found:
            continue
        readable = _readable(key)
        best_ratio = 0.0
        for w in windows:
            ratio = difflib.SequenceMatcher(None, w, readable).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
        if best_ratio >= fuzzy_threshold:
            found[key] = (round(best_ratio, 2), "fuzzy")

    results = [(k, conf, source) for k, (conf, source) in found.items()]
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:max_results]


def match_text_to_symptoms_llm(
    text: str, valid_symptoms: List[str], api_key: str, model: str = "claude-sonnet-4-6"
) -> List[Tuple[str, float, str]]:
    """
    Uses the Claude API to map free-text symptom descriptions onto the known
    symptom list. This understands phrasing, context, and language far better
    than the offline synonym+fuzzy matcher, at the cost of needing an API key
    and a network call.

    Raises on any failure (missing key, network error, bad response) -- the
    caller is expected to catch this and fall back to match_text_to_symptoms().
    """
    import anthropic  # imported lazily so the app runs fine without the package installed

    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set.")

    client = anthropic.Anthropic(api_key=api_key)

    symptom_list_str = ", ".join(valid_symptoms)
    system_prompt = (
        "You match a patient's free-text symptom description to a fixed list of "
        "known symptom codes. You must ONLY use symptom codes from the provided "
        "list -- never invent new ones. Respond with ONLY a JSON array of "
        "strings (the matched symptom codes), nothing else -- no explanation, "
        "no markdown fences, no preamble."
    )
    user_prompt = (
        f"Known symptom codes:\n{symptom_list_str}\n\n"
        f"Patient description (may be in English, Hindi, or Hinglish):\n\"{text}\"\n\n"
        "Return a JSON array of the symptom codes from the list above that this "
        "description matches. Only include codes that are a reasonably confident "
        "match. Return [] if nothing matches."
    )

    response = client.messages.create(
        model=model,
        max_tokens=500,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    ).strip()

    # Defensive parsing in case the model wraps the JSON in markdown fences anyway.
    raw_text = re.sub(r"^```json|^```|```$", "", raw_text.strip(), flags=re.MULTILINE).strip()

    try:
        matched_codes = json.loads(raw_text)
    except json.JSONDecodeError:
        raise ValueError(f"LLM did not return valid JSON: {raw_text[:200]}")

    valid_set = set(valid_symptoms)
    results = [
        (code, 0.9, "llm") for code in matched_codes if isinstance(code, str) and code in valid_set
    ]
    return results


def match_text_to_symptoms_gemini(
    text: str, valid_symptoms: List[str], api_key: str, model: str = "gemini-2.5-flash"
) -> List[Tuple[str, float, str]]:
    """
    Same idea as match_text_to_symptoms_llm, but uses Google's Gemini API
    instead of Claude. Gemini has a genuinely free tier (rate-limited, e.g.
    ~10 requests/minute on Flash as of mid-2026) so this is a good zero-cost
    LLM option for a student/demo project.

    Raises on any failure -- the caller should catch this and fall back to
    match_text_to_symptoms() (the offline matcher).
    """
    from google import genai  # imported lazily so the app runs fine without the package installed

    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")

    client = genai.Client(api_key=api_key)

    symptom_list_str = ", ".join(valid_symptoms)
    prompt = (
        "You match a patient's free-text symptom description to a fixed list of "
        "known symptom codes. You must ONLY use symptom codes from the provided "
        "list -- never invent new ones. Respond with ONLY a JSON array of "
        "strings (the matched symptom codes), nothing else -- no explanation, "
        "no markdown fences, no preamble.\n\n"
        f"Known symptom codes:\n{symptom_list_str}\n\n"
        f"Patient description (may be in English, Hindi, or Hinglish):\n\"{text}\"\n\n"
        "Return a JSON array of the symptom codes from the list above that this "
        "description matches. Only include codes that are a reasonably confident "
        "match. Return [] if nothing matches."
    )

    response = client.models.generate_content(model=model, contents=prompt)
    raw_text = (response.text or "").strip()
    raw_text = re.sub(r"^```json|^```|```$", "", raw_text, flags=re.MULTILINE).strip()

    try:
        matched_codes = json.loads(raw_text)
    except json.JSONDecodeError:
        raise ValueError(f"Gemini did not return valid JSON: {raw_text[:200]}")

    valid_set = set(valid_symptoms)
    results = [
        (code, 0.9, "llm") for code in matched_codes if isinstance(code, str) and code in valid_set
    ]
    return results
