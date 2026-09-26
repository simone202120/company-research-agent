"""Domain exceptions raised by the research workflow."""


class ResearchError(Exception):
    """Base class for every error raised by the research workflow."""


class InvalidLLMOutputError(ResearchError):
    """The LLM returned output that does not match the expected schema."""


class ResearchNotFoundError(ResearchError):
    """No research exists for the given thread id."""


class InvalidResearchStateError(ResearchError):
    """The requested action is not allowed in the current research status."""
