from pydantic import BaseModel


class SubmissionAccepted(BaseModel):
    token: str
    status: str
    status_url: str


class SubmissionStatus(BaseModel):
    token: str
    status: str
    record_count: int
    completed_operations: int
    failed_operations: int
    created_at: int | None = None
    started_at: int | None = None
    finished_at: int | None = None
    updated_at: int | None = None
    failure_code: str | None = None
    failure_message: str | None = None


class SubmissionJournalEntry(BaseModel):
    sequence: int
    outcome: str
    action: str | None = None
    pid: str | None = None
    local_id: str | None = None
    record_type: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: int | None = None


class SubmissionJournalPage(BaseModel):
    entries: list[SubmissionJournalEntry]
    next_after: int | None = None
