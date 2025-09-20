"""Custom exceptions used by the AION service clients."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class APIError(RuntimeError):
    """Represents an error returned by an external API service."""

    service: str
    message: str
    status: Optional[int] = None

    def __post_init__(self) -> None:
        status_text = f" (status: {self.status})" if self.status is not None else ""
        super().__init__(f"{self.service} API error: {self.message}{status_text}")
