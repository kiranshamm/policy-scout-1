"""
Policy Detection Classifier
Rule-based engine that classifies webpage URLs and content into compliance policy categories.
"""

import re
from typing import Optional
from dataclasses import dataclass


@dataclass
class PolicyMatch:
    category: str
    confidence: float
    matched_rule: str


# ─── Policy Definitions ──────────────────────────────────────────────────────

POLICY_CATEGORIES = [
    "Privacy Policy",
    "Terms & Conditions",
    "Refund Policy",
    "Shipping Policy",
    "Contact Us",
    "About Us",
    "FAQ",
    "Cancellation Policy",
]

# URL slug keyword rules — (keywords, category, base_confidence)
URL_RULES = [
    # Privacy Policy
    (["privacy", "privacy-policy", "privacy_policy", "datenschutz", "gdpr", "data-policy", "privacidad"], "Privacy Policy", 0.95),
    # Terms & Conditions
    (["terms", "tos", "terms-of-service", "terms-and-conditions", "terms-of-use", "legal", "gebruiksvoorwaarden", "condiciones"], "Terms & Conditions", 0.95),
    # Refund Policy
    (["refund", "refunds", "return", "returns", "return-policy", "money-back", "reembolso"], "Refund Policy", 0.92),
    # Shipping Policy
    (["shipping", "delivery", "ship", "envio", "livraison", "versand", "shipping-policy", "delivery-policy"], "Shipping Policy", 0.92),
    # Contact Us
    (["contact", "contact-us", "contactus", "support", "help", "reach-us", "get-in-touch", "contacto"], "Contact Us", 0.90),
    # About Us
    (["about", "about-us", "aboutus", "our-story", "company", "who-we-are", "mission", "team", "sobre"], "About Us", 0.88),
    # FAQ
    (["faq", "faqs", "frequently-asked", "questions", "help-center", "knowledge-base"], "FAQ", 0.88),
    # Cancellation Policy
    (["cancellation", "cancel", "cancellation-policy", "cancel-order", "subscription-cancel"], "Cancellation Policy", 0.90),
]

# Page content keyword rules — (keywords, category)
CONTENT_RULES = [
    (["privacy policy", "personal data", "gdpr", "personal information we collect", "data protection", "cookie policy"], "Privacy Policy"),
    (["terms and conditions", "terms of service", "terms of use", "user agreement", "binding agreement"], "Terms & Conditions"),
    (["refund policy", "money back guarantee", "return policy", "eligible for a refund", "full refund"], "Refund Policy"),
    (["shipping policy", "delivery time", "shipping rates", "free shipping", "estimated delivery", "order fulfillment"], "Shipping Policy"),
    (["contact us", "get in touch", "send us a message", "our support team", "email us at"], "Contact Us"),
    (["about us", "our story", "our mission", "founded in", "who we are", "our team", "our company"], "About Us"),
    (["frequently asked questions", "faq", "common questions", "answers to your questions"], "FAQ"),
    (["cancellation policy", "cancel your subscription", "cancel your order", "how to cancel"], "Cancellation Policy"),
]


def _normalize_slug(url: str) -> str:
    """Extract and normalize the URL slug for keyword matching."""
    # Remove protocol and domain
    path = re.sub(r"^https?://[^/]+", "", url.lower())
    # Replace separators with spaces
    path = re.sub(r"[-_/.]", " ", path)
    return path.strip()


def classify_by_url(url: str) -> Optional[PolicyMatch]:
    """
    Classify a URL using slug keyword matching.
    Returns the best matching PolicyMatch or None.
    """
    slug = _normalize_slug(url)
    best_match: Optional[PolicyMatch] = None

    for keywords, category, base_confidence in URL_RULES:
        for keyword in keywords:
            norm_kw = keyword.replace("-", " ").replace("_", " ")
            if norm_kw in slug:
                confidence = base_confidence
                # Boost confidence if keyword is an exact path segment
                if f"/{keyword}" in url.lower() or url.lower().endswith(f"/{keyword}"):
                    confidence = min(1.0, confidence + 0.04)
                if best_match is None or confidence > best_match.confidence:
                    best_match = PolicyMatch(
                        category=category,
                        confidence=confidence,
                        matched_rule=f"url_keyword:{keyword}"
                    )

    return best_match


def classify_by_content(content: str) -> Optional[PolicyMatch]:
    """
    Classify a page by its text content using keyword matching.
    Returns the best matching PolicyMatch or None.
    """
    content_lower = content.lower()
    best_match: Optional[PolicyMatch] = None

    for keywords, category in CONTENT_RULES:
        score = 0
        matched_kw = None
        for keyword in keywords:
            if keyword in content_lower:
                score += 1
                if matched_kw is None:
                    matched_kw = keyword

        if score > 0:
            # Confidence based on how many keywords matched
            confidence = min(0.95, 0.6 + (score * 0.08))
            if best_match is None or confidence > best_match.confidence:
                best_match = PolicyMatch(
                    category=category,
                    confidence=confidence,
                    matched_rule=f"content_keyword:{matched_kw}"
                )

    return best_match


def classify_link(url: str, title: str = "", content: str = "") -> Optional[PolicyMatch]:
    """
    Classify a link using URL rules first, then fall back to content analysis.
    Returns the best PolicyMatch or None.
    """
    url_match = classify_by_url(url)
    content_match = None

    combined_text = f"{title} {content}"
    if combined_text.strip():
        content_match = classify_by_content(combined_text)

    # Prefer URL match if high confidence, otherwise blend
    if url_match and url_match.confidence >= 0.88:
        return url_match
    if content_match and url_match:
        # Use the higher confidence one, but keep both signals
        return url_match if url_match.confidence >= content_match.confidence else content_match
    return url_match or content_match


def build_compliance_results(classified_links: list[dict]) -> tuple[list[dict], float]:
    """
    Build the final compliance results table from all classified links.
    Returns (results_list, score_percentage).
    
    classified_links: [{"category": str, "url": str, "title": str, "confidence": float}]
    """
    # Pick best URL per category (highest confidence)
    best_per_category: dict[str, dict] = {}

    for item in classified_links:
        cat = item["category"]
        if cat not in best_per_category or item["confidence"] > best_per_category[cat]["confidence"]:
            best_per_category[cat] = item

    results = []
    found_count = 0

    for category in POLICY_CATEGORIES:
        if category in best_per_category:
            entry = best_per_category[category]
            results.append({
                "category": category,
                "status": "found",
                "url": entry["url"],
                "title": entry.get("title", ""),
                "confidence": entry["confidence"],
            })
            found_count += 1
        else:
            results.append({
                "category": category,
                "status": "missing",
                "url": None,
                "title": None,
                "confidence": 0.0,
            })

    score = (found_count / len(POLICY_CATEGORIES)) * 100
    return results, round(score, 1)
