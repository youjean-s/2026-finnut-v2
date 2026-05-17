from pydantic import BaseModel
from typing import Optional


class ScholarshipOut(BaseModel):
    id: int
    policy_key: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    period: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[str] = None
    link: Optional[str] = None
    condition: Optional[str] = None
    grant: Optional[str] = None
    source_uddi: Optional[str] = None
    fetched_at: Optional[str] = None


class ScholarshipDetailOut(ScholarshipOut):
    raw_json: Optional[str] = None
