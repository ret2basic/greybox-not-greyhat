from __future__ import annotations


class InferForgeError(Exception):
    """Expected user-facing failure."""


class ConfigurationError(InferForgeError):
    """The source or configuration contract is invalid."""


class ArtifactError(InferForgeError):
    """Required artifacts are missing, stale, or malformed."""


class TriageError(InferForgeError):
    """A finding lifecycle transition is invalid."""
