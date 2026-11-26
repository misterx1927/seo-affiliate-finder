"""Validate analysis against the page text before storing any model output."""
from dataclasses import dataclass
import re
from urllib.parse import urlsplit

class AnalysisError(ValueError):
    pass

@dataclass(frozen=True)
class Analysis:
    relevance: str
    brands: tuple[str, ...]
    contact: str | None
    evidence: str


def _contains_complete_name(source: str, name: str) -> bool:
    """Require a whole name, not just letters embedded in another word.

    This checks only textual presence, not whether the name is a casino.
    Whitespace and case have already been normalized by the caller.
    """
    normalized = " ".join(name.casefold().split())
    start = 0
    while (index := source.find(normalized, start)) != -1:
        end = index + len(normalized)
        left = index == 0 or not (normalized[0].isalnum() and source[index - 1].isalnum())
        right = end == len(source) or not (normalized[-1].isalnum() and source[end].isalnum())
        if left and right:
            return True
        start = index + 1
    return False


def _usable_contact(value: str) -> bool:
    """Accept a concrete endpoint, not a page label such as 'Contact us'."""
    value = value.strip()
    if re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", value):
        return True
    try:
        parts = urlsplit(value)
        if parts.scheme in {"http", "https"} and parts.hostname and not any(c.isspace() for c in value):
            return True
    except ValueError:
        pass
    # Require normal phone punctuation or a leading '+', avoiding plain IDs.
    digits = sum(c.isdigit() for c in value)
    return (7 <= digits <= 15 and bool(re.fullmatch(r"[+()\d .-]+", value))
            and (value.startswith('+') or any(c in value for c in ' ()-')))


def _contains_complete_email(source: str, value: str) -> bool:
    """Reject an email fabricated from the middle of a longer address."""
    name = value.strip().casefold()
    preceding = r"[a-z0-9.!#$%&'*+/=?^_`{|}~@-]"
    following = r"[a-z0-9!#$%&'*+/=?^_`{|}~@-]|\.[a-z0-9]"
    return re.search(rf"(?<!{preceding}){re.escape(name)}(?!{following})", source) is not None

def validate_analysis(payload: object, page_text: str) -> Analysis:
    if not isinstance(payload, dict) or not isinstance(page_text, str):
        raise AnalysisError("Invalid analysis or source text")
    if set(payload) != {"relevance", "brands", "contact", "evidence"}:
        raise AnalysisError("Unexpected analysis fields")
    relevance, brands = payload["relevance"], payload["brands"]
    contact, evidence = payload["contact"], payload["evidence"]
    if not isinstance(relevance, str) or relevance not in {"yes", "no", "needs_review"}:
        raise AnalysisError("Invalid relevance")
    if not isinstance(brands, list) or len(brands) > 100 or any(not isinstance(b, str) or not b.strip() or len(b) > 100 for b in brands):
        raise AnalysisError("Invalid brands")
    if contact is not None and (not isinstance(contact, str) or not contact.strip() or len(contact) > 300):
        raise AnalysisError("Invalid contact")
    if not isinstance(evidence, str) or not evidence.strip() or len(evidence) > 500:
        raise AnalysisError("Invalid evidence")
    source = " ".join(page_text.casefold().split())
    contains = lambda value: " ".join(value.casefold().split()) in source
    if not contains(evidence):
        raise AnalysisError("Evidence quote not found in the supplied page text")
    # Provider markdown contains link destinations that are not visible page
    # copy. A domain inside a URL is not evidence that a casino is mentioned.
    # Keep link labels and prose; this remains a presence check, not semantic proof.
    brand_source = re.sub(r"(?i)\b(?:https?://|www\.)[^\s<>\"')\]]+", " ", source)
    if any(not _contains_complete_name(brand_source, b) for b in brands):
        raise AnalysisError("One or more reported brands were not found as complete names outside URLs in the supplied page text")
    if contact and not contains(contact):
        raise AnalysisError("Reported contact was not found in the supplied page text")
    if contact and "@" in contact and not _contains_complete_email(source, contact):
        raise AnalysisError("Reported email was not found as a complete address")
    # Labels and anti-bot placeholders are not actionable contact endpoints.
    if contact and not _usable_contact(contact):
        contact = None
    # Models can emit the same name with different capitalization or spacing,
    # including a space between a numeral and a letter (21Casino / 21 Casino).
    # Do not remove spaces between words or between digits: those can identify
    # genuinely different brands.
    # Keep the first spelling rather than displaying duplicate brands.
    unique_brands = []
    seen = set()
    for brand in brands:
        name = " ".join(brand.split())
        key = re.sub(r'(?<=\d)\s+(?=[^\W\d_])|(?<=[^\W\d_])\s+(?=\d)', '', name.casefold())
        if key not in seen:
            seen.add(key)
            unique_brands.append(name)
    return Analysis(relevance, tuple(unique_brands), contact, evidence)
