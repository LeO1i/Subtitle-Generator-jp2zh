class SubtitleError(Exception):
    """Base error for subtitle generation."""


class ASRError(SubtitleError):
    """ASR processing failed."""


class TranslationError(SubtitleError):
    """Machine translation failed."""


class BurnError(SubtitleError):
    """Subtitle burn-in failed."""


class ConfigError(SubtitleError):
    """Invalid pipeline configuration."""
