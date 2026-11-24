from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, Field, StringConstraints

MAX_CONTENT_CHARS = 2_000_000


def _reject_nul(value: str | None) -> str | None:
    if value is not None and "\x00" in value:
        raise ValueError("must not contain NUL characters")
    return value


# PostgreSQL can't store NUL in text, so it is refused here instead of failing as a 500
# (review finding M2). Attach to every free-text input: body fields, query and form values.
NoNul = AfterValidator(_reject_nul)

# Titles: surrounding whitespace is trimmed, and a blank title is rejected.
Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255), NoNul
]


def _reject_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be blank")
    return value


# Content is stored exactly as sent (whitespace can matter in legal text), but it can't be blank.
Content = Annotated[
    str, Field(min_length=1, max_length=MAX_CONTENT_CHARS), AfterValidator(_reject_blank), NoNul
]


class MessageResponse(BaseModel):
    message: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
