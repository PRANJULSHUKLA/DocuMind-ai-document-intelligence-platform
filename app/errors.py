"""Application error types shared by provider and HTTP boundaries."""


class GenerationUnavailableError(RuntimeError):
    """The configured generation providers exhausted their transient retries."""
