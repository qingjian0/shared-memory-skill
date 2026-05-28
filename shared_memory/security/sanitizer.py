from __future__ import annotations

import re
import logging

logger = logging.getLogger(__name__)

# Patterns to redact (spec section 13)
_SECRET_PATTERNS = [
    (r''sk-[a-zA-Z0-9]{20,60}'', ''[REDACTED_API_KEY]''),
    (r''Bearer\s+[a-zA-Z0-9\-_\.]+'', ''Bearer [REDACTED]''),
    (r''''(?:password|passwd|pwd|secret|token|credential)['']\s*[:=]\s*[''\"][^''\"]+[''\"]'''',
     '''\1: \'[REDACTED]\''''),
    (r''[A-Za-z0-9+/]{40,}={0,2}'', ''[REDACTED_BASE64]''),
    (r''\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b'', ''[IP_REDACTED]''),
    (r''[0-9a-fA-F]{64}'', ''[REDACTED_HASH]''),
]


def sanitize(content: str) -> str:
    """Auto-redact sensitive data before storage."""
    original_len = len(content)
    for pattern, replacement in _SECRET_PATTERNS:
        content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
    if len(content) != original_len:
        logger.debug("Sanitized content (%d chars removed)", original_len - len(content))
    return content


def has_sensitive_data(content: str) -> bool:
    """Check if content contains potential sensitive data."""
    for pattern, _ in _SECRET_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            return True
    return False
