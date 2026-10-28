"""News verification service for TruthLens.

Handles evidence-based verification of claims against external fact-check
and web-search APIs.

Verification statuses:
  - SUPPORTED: relevant evidence supports the claim
  - DEBUNKED: reliable evidence contradicts the claim
  - CONFLICTING_EVIDENCE: credible sources disagree or evidence is mixed
  - UNVERIFIED: evidence is insufficient, unavailable, or inconclusive

Rules:
  1. Do not label a claim DEBUNKED simply because no matching fact-check was found.
  2. Do not mark a claim SUPPORTED solely because a search result exists.
  3. Keep ML prediction separate from the verification status.
  4. Preserve actual source URLs and titles returned by the provider.
  5. Include publication dates, publishers, and relevant excerpts only when available.
  6. Do not fabricate citations, article titles, quotations, sources, or search results.
  7. Distinguish a failed API request from a successful search with zero results.
  8. Clearly disclose when a provider is unavailable or its rate limit is reached.
  9. If evidence cannot justify a conclusion, return UNVERIFIED with an explanation.
  10. Do not claim that all news on the internet was searched.
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# Provider configuration
GOOGLE_FACT_CHECK_API_KEY = os.environ.get("GOOGLE_FACT_CHECK_API_KEY")


class VerificationResult:
    """Result structure for a verification check."""

    def __init__(
        self,
        status: str,
        explanation: str,
        sources: List[Dict[str, Any]] = None,
    ):
        self.status = status
        self.explanation = explanation
        self.sources = sources or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.status,
            "explanation": self.explanation,
            "sources": self.sources,
        }


# Provider interface
class EvidenceProvider:
    """Abstract base class for evidence providers."""

    name = "base_provider"

    def search(self, claim: str) -> Tuple[int, List[Dict[str, Any]]]:
        """Search for evidence related to a claim.

        Returns:
            Tuple of (status_code, results_list).
            status_code: 200 = successful search with results,
            204 = successful search with zero results,
            other = API error.
        """
        raise NotImplementedError("Subclasses must implement this method")

    def close(self):
        """Clean up provider resources."""
        pass


class GoogleFactCheckProvider(EvidenceProvider):
    """Google Fact Check Tools API provider.

    Requires GOOGLE_FACT_CHECK_API_KEY environment variable.
    https://developers.google.com/fact-check/tools/overview
    """

    name = "google_fact_check"

    def __init__(self):
        self.api_key = GOOGLE_FACT_CHECK_API_KEY
        self.service_enabled = self.api_key is not None
        if not self.service_enabled:
            logger.warning(
                "Google Fact Check API key not configured; "
                "provider will report unavailable."
            )

    def search(self, claim: str) -> Tuple[int, List[Dict[str, Any]]]:
        """Search for fact-checks related to a claim.

        Returns:
            Tuple of (status_code, results_list).
            status_code:
                200 - successful search with fact-check results
                204 - successful search, no matching fact-checks found
                503 - provider unavailable (no API key or API error)
        """
        if not self.service_enabled:
            return 503, []

        # In a full implementation, would call:
        # https://factchecktools.googleapis.com/v1alpha1/claims:search
        # With the API key and claim query

        # For now, since we don't have a real API key, we report unavailable
        # but document the expected behavior.
        return 503, []


# Provider registry - can be extended with other permitted search providers
_provider_instance: Optional[EvidenceProvider] = None


def get_provider() -> EvidenceProvider:
    """Get the configured evidence provider instance.

    Returns:
        An EvidenceProvider subclass instance.
    """
    global _provider_instance
    if _provider_instance is None:
        provider_name = os.environ.get(
            "TRUTHLENS_EVIDENCE_PROVIDER", "google_fact_check"
        )
        if provider_name == "google_fact_check":
            _provider_instance = GoogleFactCheckProvider()
        else:
            logger.warning(
                f"Unknown evidence provider: {provider_name}; "
                "using default (unavailable) provider."
            )
            _provider_instance = GoogleFactCheckProvider()
    return _provider_instance


def verify_claim(
    claim: str,
) -> VerificationResult:
    """Verify a claim against available evidence providers.

    Implements conservative evidence evaluation:
    - Queries the configured external evidence provider
    - Evaluates retrieved evidence conservatively
    - Keeps ML prediction separate from verification status
    - Returns appropriate verification status

    Args:
        claim: The news claim or text to verify.

    Returns:
        VerificationResult with status, explanation, and sources.
    """
    provider = get_provider()
    sources = []

    # Query the evidence provider
    status_code, results = provider.search(claim)

    # Handle different provider responses
    if status_code == 503:
        # Provider unavailable (no API key, rate limit, or API error)
        return VerificationResult(
            status="unverified",
            explanation="External evidence provider is currently unavailable. "
            "The fact-check or web-search API is not configured or "
            "could not be reached. Insufficient evidence was available "
            "to evaluate this claim.",
            sources=[],
        )

    if status_code == 204:
        # Successful search but zero results
        # Rule 1: Do not label DEBUNKED simply because no matching fact-check was found
        return VerificationResult(
            status="unverified",
            explanation="No matching fact-checks or corroborating journalistic "
            "evidence was found for this claim. This does not mean the claim "
            "is false, only that no supporting evidence was found in the "
            "queried sources.",
            sources=[],
        )

    if status_code == 200:
        # Successful search with results
        for result in results:
            source_entry = {
                "title": result.get("title", "Untitled Corroborating Report"),
                "publisher": result.get("publisher", None),
                "date": result.get("date", None),
                "excerpt": result.get("excerpt", None),
                "url": result.get("url", None),
            }
            # Only add if we have meaningful data
            if source_entry["title"] and source_entry["title"] != "Untitled Corroborating Report":
                sources.append(source_entry)

        # Determine verification status based on sources
        if not sources:
            # No usable sources found in results
            return VerificationResult(
                status="unverified",
                explanation="The evidence search returned results, but none "
                " contained sufficient credible information to support or "
                "contradict the claim.",
                sources=[],
            )

        # Check for explicit debunking evidence
        has_debunked = any(
            s.get("publisher") and "debunk" in str(s.get("title", "")).lower()
            or s.get("excerpt") and "debunk" in str(s.get("excerpt", "")).lower()
            for s in sources
        )

        # Check for supporting evidence
        has_supported = any(
            s.get("publisher") and "support" in str(s.get("title", "")).lower()
            or s.get("excerpt") and "support" in str(s.get("excerpt", "")).lower()
            for s in sources
        )

        # Rule 2: Do not mark SUPPORTED solely because a search result exists
        # Rule 3: Keep ML prediction separate

        if has_debunked and not has_supported:
            status = "debunked"
            explanation = (
                "Reliable evidence contradicts this claim. "
                "Available fact-checks and journalistic investigations "
                "explicitly refute the assertion."
            )
        elif has_supported and not has_debunked:
            status = "supported"
            explanation = (
                "Relevant evidence supports this claim. "
                "Available fact-checks and journalistic reports "
                "corroborate the assertion."
            )
        elif has_debunked and has_supported:
            status = "conflicting_evidence"
            explanation = (
                "Credible sources disagree or evidence is materially mixed. "
                "Some sources support the claim while others contradict it. "
                "Further investigation may be needed to resolve the discrepancy."
            )
        else:
            # Has search results but cannot determine support/contradiction
            status = "unverified"
            explanation = (
                "Evidence from available sources is insufficient to reach "
                "a definitive conclusion. While some sources were found, "
                "they do not clearly support or contradict the claim."
            )

        return VerificationResult(
            status=status,
            explanation=explanation,
            sources=sources,
        )

    # Fallback for unexpected status codes
    return VerificationResult(
        status="unverified",
        explanation="Unable to evaluate claim due to an unexpected "
        "response from the evidence provider.",
        sources=[],
    )