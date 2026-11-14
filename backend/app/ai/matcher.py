"""Arabic/English menu matching utilities used by the AI kiosk.

The matcher only ranks records that already exist in MySQL. It never
fabricates a product, description or price.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
TATWEEL = "\u0640"
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

QTY_WORDS = {
    "واحد": 1, "واحدة": 1, "1": 1, "one": 1, "single": 1, "a": 1,
    "اتنين": 2, "اثنين": 2, "اتنان": 2, "2": 2, "two": 2, "double": 2,
    "تلاتة": 3, "ثلاثة": 3, "تلات": 3, "3": 3, "three": 3, "triple": 3,
    "اربعة": 4, "أربعة": 4, "4": 4, "four": 4,
    "خمسة": 5, "5": 5, "five": 5,
    "ستة": 6, "6": 6, "six": 6,
    "سبعة": 7, "7": 7, "seven": 7,
    "تمانية": 8, "ثمانية": 8, "8": 8, "eight": 8,
    "تسعة": 9, "9": 9, "nine": 9,
    "عشرة": 10, "10": 10, "ten": 10,
}

STOPWORDS_AR = {
    "عايز", "عاوز", "عايزة", "محتاج", "محتاجة", "هات", "هاتي", "لي", "لو",
    "سمحت", "من", "في", "على", "مع", "و", "او", "أو", "ال", "يا", "بس",
    "كمان", "شوية", "طبق", "وجبة", "حاجة", "حاجه", "ممكن", "اضف", "ضيف",
    "أضف", "زود", "زودلي", "مش", "دلوقتي", "الحساب", "الأوردر", "اوردر",
}
STOPWORDS_EN = {
    "i", "want", "would", "like", "please", "add", "give", "me", "some",
    "a", "an", "the", "and", "or", "with", "of", "for", "to", "can", "you",
    "my", "order", "get", "one", "two", "three", "four", "five",
}


def normalize(text: str) -> str:
    if not text:
        return ""
    text = text.translate(ARABIC_DIGITS)
    text = unicodedata.normalize("NFKC", text)
    text = ARABIC_DIACRITICS.sub("", text).replace(TATWEEL, "")
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    text = text.lower()
    text = re.sub(r"[^\w\s\u0600-\u06FF]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokens(text: str) -> list[str]:
    return [token for token in normalize(text).split() if token]


def content_tokens(text: str) -> list[str]:
    return [
        token
        for token in tokens(text)
        if token not in STOPWORDS_AR and token not in STOPWORDS_EN and len(token) > 1
    ]


def extract_quantity(text: str) -> tuple[int, str]:
    """Return (quantity, text without quantity words)."""
    normalized = normalize(text)
    quantity = 1
    remaining: list[str] = []
    for word in normalized.split():
        if word in QTY_WORDS:
            quantity = QTY_WORDS[word]
        else:
            remaining.append(word)
    return quantity, " ".join(remaining)


@dataclass
class Match:
    item_id: int
    score: float
    item: object


def score_item(item, query: str) -> float:
    q_norm = normalize(query)
    if not q_norm:
        return 0.0
    q_tokens = set(content_tokens(query))
    names = [item.item_name, item.item_name_ar]
    aliases = item.synonyms_list if hasattr(item, "synonyms_list") else []
    best = 0.0
    for name in names + aliases:
        n_norm = normalize(name)
        if not n_norm:
            continue
        if q_norm == n_norm:
            score = 100.0
        elif n_norm in q_norm or q_norm in n_norm:
            score = 88.0 - abs(len(n_norm) - len(q_norm)) * 0.25
        else:
            n_tokens = set(content_tokens(name))
            overlap = len(q_tokens & n_tokens)
            if overlap:
                score = 45.0 + 35.0 * (overlap / max(len(q_tokens), 1))
            else:
                score = 0.0
            score = max(score, SequenceMatcher(None, q_norm, n_norm).ratio() * 62.0)
        best = max(best, score)
    if item.category is not None:
        for category_name in (item.category.category_name, item.category.category_name_ar):
            c_norm = normalize(category_name or "")
            if c_norm and (c_norm in q_norm or any(t in c_norm for t in q_tokens)):
                best = max(best, 38.0)
    return round(best, 2)


def rank_items(items, query: str, limit: int = 5) -> list[tuple[object, float]]:
    scored = [(item, score_item(item, query)) for item in items]
    scored = [row for row in scored if row[1] >= 38]
    scored.sort(key=lambda row: (-row[1], row[0].item_name))
    return scored[:limit]


def split_order_segments(text: str) -> list[str]:
    normalized_text = unicodedata.normalize("NFKC", text).translate(ARABIC_DIGITS)
    normalized_text = ARABIC_DIACRITICS.sub("", normalized_text)
    parts = re.split(r"[\n,،;؛+]|\s+و\s+|\s+and\s+|\s+مع\s+|\s+plus\s+", normalized_text, flags=re.I)
    # Arabic often attaches the conjunction: "دبل وبيبسي". Split a word that
    # starts with و only when the remainder is long enough to be a real word
    # (so "واحد", "وجبة" and similar words are left intact).
    expanded: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        expanded.extend(
            seg.strip()
            for seg in re.split(r"\s+و(?=[\u0600-\u06FF]{4,})", part)
            if seg.strip()
        )
    return expanded


def detect_intent(text: str) -> str:
    norm = normalize(text)
    if re.search(r"\b(confirm|checkout|place order|yes|ok|okay|submit)\b", norm) or any(
        phrase in norm
        for phrase in ("اكد", "تاكيد", "تمام اكد", "اطلب", "اطلب الاوردر", "خلاص", "ينفع", "ماشي")
    ):
        return "confirm"
    if any(phrase in norm for phrase in ("الغ الاوردر", "الغي الاوردر", "cancel order")):
        return "cancel"
    if re.search(r"\b(remove|delete|clear)\b", norm) or any(
        phrase in norm for phrase in ("شيل", "امسح", "الغي", "الغ")
    ):
        return "remove"
    if re.search(r"\b(summary|total|subtotal|bill|cart)\b", norm) or any(
        phrase in norm for phrase in ("ملخص", "الحساب", "الاجمالي", "الاجمالى", "عايز ايه", "الاوردر فيه ايه")
    ):
        return "summary"
    if re.search(r"\b(price|cost|how much)\b", norm) or any(
        phrase in norm for phrase in ("بكام", "سعر", "بكم", "كام")
    ):
        return "price"
    if re.search(r"\b(available|availability|in stock)\b", norm) or any(
        phrase in norm for phrase in ("متوفر", "موجود", "متاح", "خلصان")
    ):
        return "availability"
    if re.search(r"\b(menu|recommend|suggest|popular|featured)\b", norm) or any(
        phrase in norm for phrase in ("منيو", "اقترح", "اقتراح", "عندكم ايه", "الاكثر", "مميز")
    ):
        return "menu"
    if re.search(r"\b(hello|hi|hey)\b", norm) or any(
        phrase in norm for phrase in ("اهلا", "سلام", "مرحبا", "هلا", "ازيك")
    ):
        return "greeting"
    return "order"
