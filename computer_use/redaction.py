"""Conservative redaction for logs and persisted evidence."""

from __future__ import annotations

import os
import re
from typing import Any

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|password|authorization)(\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]+\b"),
]


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): "[REDACTED]" if re.fullmatch(
            r"(?i)(api[_-]?key|token|password|authorization)", str(k)
        ) else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if not isinstance(value, str):
        return value
    result = value
    for secret in filter(None, [os.getenv("OPENAI_API_KEY")]):
        result = result.replace(secret, "[REDACTED]")
    for pattern in SECRET_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result
