"""Deterministic confidentiality checks that run alongside the AI review."""

from __future__ import annotations

import re
from typing import Any

SECRET_PATTERNS = [
    (r"sk-ant-[A-Za-z0-9_-]{10,}", "an Anthropic API key"),
    (r"sk-[A-Za-z0-9]{20,}", "an API key"),
    (r"AKIA[0-9A-Z]{16}", "an AWS access key"),
    (r"ghp_[A-Za-z0-9]{30,}", "a GitHub token"),
    (r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", "a JWT"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "a private key"),
    (r"(?i)postgres(?:ql)?://[^\s'\"`]+:[^\s'\"`]+@", "a database URL with a password"),
    (r"(?i)(password|passwd|secret)\s*[:=]\s*['\"][^'\"]{6,}['\"]", "a hard-coded password"),
]
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"https?://[^\s)\"'<>`]+")
INTERNAL_RE = re.compile(r"(?i)\b(?:localhost:\d+|\d{1,3}(?:\.\d{1,3}){3}|[a-z0-9-]+\.(?:internal|local|corp)\b|[a-z0-9-]+\.run\.app)")


def scan(text: str, site_url: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for pattern, what in SECRET_PATTERNS:
        for m in re.finditer(pattern, text):
            findings.append({
                "severity": "high", "kind": "secret", "quote": m.group(0)[:60],
                "why": f"This looks like {what}.", "suggestion": "Remove it, and rotate it if it was ever real.",
            })
    for m in set(EMAIL_RE.findall(text)):
        findings.append({
            "severity": "medium", "kind": "personal", "quote": m,
            "why": "An email address in a public post.", "suggestion": "Remove it unless it's meant to be public.",
        })
    for m in set(INTERNAL_RE.findall(text)):
        findings.append({
            "severity": "medium", "kind": "confidential", "quote": m,
            "why": "An internal host, IP address or service URL.", "suggestion": "Replace it with a generic description.",
        })
    for url in sorted(set(URL_RE.findall(text))):
        if url.startswith(site_url):
            continue
        findings.append({
            "severity": "low", "kind": "unverified-link", "quote": url,
            "why": "External link written by the model.", "suggestion": "Open it and confirm it exists and says what the post claims.",
        })
    return findings
