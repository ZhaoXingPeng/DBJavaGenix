"""Helpers for preventing credentials from crossing logging and response boundaries."""

from __future__ import annotations

import re
from typing import Any, Iterable


_SENSITIVE_KEY_NAMES = {
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_key",
    "private_key",
    "authorization",
    "credential",
}
_SENSITIVE_KEY_PREFIXES = ("password_", "passwd_", "secret_", "authorization_", "credential_")
_SENSITIVE_KEY_SUFFIXES = (
    "_password",
    "_passwd",
    "_secret",
    "_token",
    "_api_key",
    "_apikey",
    "_access_key",
    "_private_key",
    "_authorization",
    "_credential",
)
_URL_PASSWORD_RE = re.compile(r"(?P<prefix>://[^/\s:@]+:)(?P<password>[^@/\s]+)(?P<suffix>@)")
_QUERY_SECRET_RE = re.compile(
    r"(?P<prefix>[?&](?:password|passwd|token|api[_-]?key|secret)=)(?P<value>[^&\s]+)",
    re.IGNORECASE,
)


def is_sensitive_key(key: object) -> bool:
    """Return whether a mapping key commonly identifies a secret value."""
    normalized = str(key).replace("-", "_").lower()
    return (
        normalized in _SENSITIVE_KEY_NAMES
        or normalized.startswith(_SENSITIVE_KEY_PREFIXES)
        or normalized.endswith(_SENSITIVE_KEY_SUFFIXES)
    )


def redact_sensitive_data(value: Any, replacement: str = "***") -> Any:
    """Recursively redact secret-looking mapping values without mutating input."""
    if isinstance(value, dict):
        return {
            key: replacement if is_sensitive_key(key) else redact_sensitive_data(item, replacement)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive_data(item, replacement) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive_data(item, replacement) for item in value)
    if isinstance(value, set):
        return {redact_sensitive_data(item, replacement) for item in value}
    if isinstance(value, str):
        return _redact_embedded_credentials(value, replacement)
    return value


def redact_sensitive_text(value: object, secrets: Iterable[object] = ()) -> str:
    """Replace known secret values in exception text before it is logged or returned."""
    text = str(value)
    for secret in secrets:
        if secret is None:
            continue
        candidate = str(secret)
        if candidate:
            text = text.replace(candidate, "***")
    return _redact_embedded_credentials(text, "***")


def _redact_embedded_credentials(value: str, replacement: str) -> str:
    """Mask credentials embedded in JDBC/HTTP URLs and query strings."""
    value = _URL_PASSWORD_RE.sub(r"\g<prefix>" + replacement + r"\g<suffix>", value)
    return _QUERY_SECRET_RE.sub(r"\g<prefix>" + replacement, value)
