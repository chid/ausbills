class AusBillsError(Exception):
    """Base exception for ausbills failures."""


class SourceBlockedError(AusBillsError):
    """Raised when a source returns a WAF, bot check, or browser-only challenge."""


class SourceUnavailableError(AusBillsError):
    """Raised when a source cannot be reached or returns an unusable response."""


class ParseError(AusBillsError):
    """Raised when a source response does not match the expected structure."""
