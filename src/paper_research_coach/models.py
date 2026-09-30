from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def uid() -> str:
    return uuid4().hex


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(default_factory=uid, pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    revision: int = 0
    created_at: str = Field(default_factory=now)
    updated_at: str = Field(default_factory=now)
    archived: bool = False


class Paper(Record):
    title: str = Field(min_length=1, max_length=2000)
    authors: str = ""
    publication: str = ""
    year: str = ""
    doi: str = ""
    url: str = ""
    source_path: str = ""
    source_version: str = ""
    page_count: int = 0
    access_scope: Literal["full", "abstract", "excerpt", "metadata"] = "metadata"
    paper_type: str = "empirical"
    goal: str = ""
    status: Literal["queued", "reading", "paused", "done"] = "queued"
    comparison: dict[str, str] = Field(default_factory=dict)
    zotero_key: str = ""
    zotero_attachment: str = ""
    zotero_server: str = ""
    zotero_collection: str = ""


class Anchor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paper_id: str
    source_version: str = ""
    page_index: int | None = Field(default=None, ge=0)
    page_label: str = ""
    section: str = ""
    figure: str = ""
    quote: str = ""
    # Unrotated PDF user-space points: x0, y0, x1, y1. Origin bottom-left.
    rects: list[tuple[float, float, float, float]] = Field(default_factory=list)
    status: Literal["verified", "inferred", "unresolved", "stale"] = "unresolved"

    @model_validator(mode="after")
    def check_geometry(self):
        if self.rects and self.page_index is None:
            raise ValueError("Region anchors require a page index")
        for x0, y0, x1, y1 in self.rects:
            import math

            if (
                not all(math.isfinite(x) for x in (x0, y0, x1, y1))
                or x1 <= x0
                or y1 <= y0
            ):
                raise ValueError("Invalid PDF rectangle")
        return self


class Note(Record):
    paper_id: str
    author: Literal["user", "assistant", "external"] = "user"
    provenance: Literal["USER", "PAPER", "EXTERNAL", "INFERENCE", "IDEA"] = "USER"
    content: str = Field(min_length=1, max_length=200000)
    anchor: Anchor | None = None
    links: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    discussed: bool = False
    read_only: bool = False
    annotation_type: str = "highlight"
    color: str = "#ffda75"

    @model_validator(mode="after")
    def authorship(self):
        if self.anchor and self.anchor.paper_id != self.paper_id:
            raise ValueError("Anchor must belong to this paper")
        if self.author == "user" and self.provenance != "USER":
            raise ValueError("Learner-authored words must use USER provenance")
        if self.author != "user" and self.provenance == "USER":
            raise ValueError("Only learner-authored words can use USER provenance")
        return self


class ReadingStep(BaseModel):
    step: Literal["orient", "insight", "model", "method", "evidence", "synthesis", "transfer", "recall"]
    evidence: str = Field(min_length=1, max_length=6000)
    page_index: int = Field(ge=0)
    finished_at: str = Field(default_factory=now)


class ReadingFlow(BaseModel):
    status: Literal["not_started", "active", "completed"] = "not_started"
    source_version: str = ""
    started_at: str = ""
    completed: list[ReadingStep] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def ordered(self):
        keys = ["orient", "insight", "model", "method", "evidence", "synthesis", "transfer", "recall"]
        if [s.step for s in self.completed] != keys[:len(self.completed)]:
            raise ValueError("Reading steps must follow the paper's route")
        if (self.status == "completed") != (len(self.completed) == 8):
            raise ValueError("A reading round ends after all eight steps")
        if self.status == "not_started" and self.completed:
            raise ValueError("An unstarted route cannot have completed steps")
        return self


class LearningEvidence(BaseModel):
    conversation_id: str
    message_id: str
    answer_quote: str = Field(min_length=8, max_length=2000)
    assistance: Literal["model", "guided", "prompt-only", "independent"]
    judgment: Literal["supported", "partial", "revise"]
    criterion: str = Field(min_length=8, max_length=2000)
    feedback: str = Field(min_length=8, max_length=4000)
    anchor: Anchor
    recorded_at: str = Field(default_factory=now)


class Session(Record):
    paper_id: str
    goal: str = ""
    stage: Literal[
        "orient",
        "insight",
        "model",
        "method",
        "evidence",
        "synthesis",
        "transfer",
        "recall",
        "talk",
    ] = "orient"
    depth: Literal["skim", "understand", "reconstruct"] = "understand"
    cursor: Anchor | None = None
    pending_question: str = ""
    next_action: str = ""
    established: list[str] = Field(default_factory=list)
    support: dict[str, Literal["model", "guided", "prompt-only", "independent"]] = (
        Field(default_factory=dict)
    )
    note_consent: bool = False
    learning_consent: bool = False
    support_evidence: dict[Literal["contribution", "mechanism", "evidence", "test", "comparison"], LearningEvidence] = Field(default_factory=dict)
    reading_flow: ReadingFlow = Field(default_factory=ReadingFlow)


class Relation(Record):
    paper_id: str
    target_id: str
    relation: Literal["prior", "extends", "alternative", "challenges", "reproduces"] = (
        "prior"
    )
    evidence: str = ""
    source_url: str = ""
    verified: bool = False


class Idea(Record):
    paper_id: str
    title: str
    observation: str = ""
    hypothesis: str = ""
    alternative: str = ""
    baseline: str = ""
    minimal_test: str = ""
    negative_outcome: str = ""
    literature_question: str = ""
    status: Literal["seed", "checking", "testable", "reframe", "killed"] = "seed"


class Review(Record):
    paper_id: str
    prompt: str
    anchor: Anchor | None = None
    due_at: str = Field(default_factory=now)
    interval_index: int = Field(default=0, ge=0)
    intervals: list[int] = Field(default_factory=lambda: [1, 3, 7, 14], min_length=1)
    attempts: list[dict] = Field(default_factory=list)

    @field_validator("due_at")
    @classmethod
    def valid_due_date(cls, value):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("Review date requires a timezone")
        return dt.astimezone(timezone.utc).isoformat()

    @model_validator(mode="after")
    def intervals_positive(self):
        if any(x < 1 or x > 3650 for x in self.intervals):
            raise ValueError("Review intervals must be 1–3650 days")
        return self


class SyncState(BaseModel):
    server_id: str = ""
    collection: str = ""
    enabled: bool = False
    poll_seconds: int = Field(default=5, ge=3, le=3600)
    last_success: str = ""
    state: str = "disconnected"
    message: str = ""


MODELS = {
    "paper": Paper,
    "note": Note,
    "session": Session,
    "relation": Relation,
    "idea": Idea,
    "review": Review,
}


class Mutation(BaseModel):
    kind: Literal["paper", "note", "session", "relation", "idea", "review"]
    data: dict
    expected_revision: int = Field(default=0, ge=0)


class Commit(BaseModel):
    operation_id: str = Field(default_factory=uid, min_length=1, max_length=120)
    mutations: list[Mutation] = Field(min_length=1, max_length=100)
