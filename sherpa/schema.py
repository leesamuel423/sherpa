from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, Field


class Source(BaseModel):
    source_type: str
    title: str
    url: str
    retrieved_snippet: str = Field(
        ...,
        description=(
            "Verbatim excerpt from the retrieved context that supports the finding. "
            "Must be a direct substring of the fetched text."
        ),
    )


class Finding(BaseModel):
    claim: str = Field(..., description="A single factual assertion.")
    supporting_sources: list[Source] = Field(
        ...,
        min_length=1,
        description="At least one source with a verbatim snippet grounding the claim.",
    )
    confidence: float = Field(..., ge=0.0, le=1.0)


class AuditMetadata(BaseModel):
    passed: bool
    attempts: int
    errors: list[str] = Field(default_factory=list)
    wall_clock_seconds: float


class ResearchOutput(BaseModel):
    query: str
    summary: str = Field(..., max_length=1000)
    findings: list[Finding] = Field(..., min_length=1)
    sources_consulted: list[Source]
    audit: AuditMetadata


# --- Internal audit types (used by auditor.py and producer.py) ---


class AuditErrorType(str, Enum):
    SCHEMA = "schema"
    GROUNDING = "grounding"
    CONSISTENCY = "consistency"


@dataclass
class AuditError:
    error_type: AuditErrorType
    field_path: str
    message: str


@dataclass
class AuditResult:
    passed: bool
    errors: list[AuditError] = field(default_factory=list)


@dataclass
class RetrievedSource:
    source_type: str
    title: str
    url: str
    text: str
