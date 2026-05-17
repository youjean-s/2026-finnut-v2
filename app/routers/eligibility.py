import json
from typing import Optional, List, Any, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.db import get_conn, now_iso

router = APIRouter(tags=["eligibility"])

class EligibilityUpsert(BaseModel):
    min_age: Optional[int] = Field(default=None, ge=0, le=120)
    max_age: Optional[int] = Field(default=None, ge=0, le=120)
    region: Optional[str] = None                 # "전국"/"서울"/...
    student_required: Optional[bool] = None

    income_type: Optional[str] = None            # "median" or "quintile" or None
    income_max_percent: Optional[int] = Field(default=None, ge=0, le=999)
    income_max_quintile: Optional[int] = Field(default=None, ge=0, le=99)

    keywords: List[str] = Field(default_factory=list)
    evidence: Dict[str, Any] = Field(default_factory=dict)  # 근거 문장/출처 저장용

def _bool_to_int(v: Optional[bool]) -> Optional[int]:
    if v is None:
        return None
    return 1 if v else 0

@router.get("/policies/{policy_id}/eligibility")
def get_eligibility(policy_id: int) -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM policy_eligibility WHERE policy_id = ?", (policy_id,))
    r = cur.fetchone()
    conn.close()

    if not r:
        raise HTTPException(status_code=404, detail="Eligibility not found")

    return {
        "policy_id": r["policy_id"],
        "min_age": r["min_age"],
        "max_age": r["max_age"],
        "region": r["region"],
        "student_required": (None if r["student_required"] is None else bool(r["student_required"])),
        "income_type": r["income_type"],
        "income_max_percent": r["income_max_percent"],
        "income_max_quintile": r["income_max_quintile"],
        "keywords": json.loads(r["keywords_json"] or "[]"),
        "evidence": json.loads(r["evidence_json"] or "{}"),
        "updated_at": r["updated_at"],
    }

@router.put("/policies/{policy_id}/eligibility")
def upsert_eligibility(policy_id: int, payload: EligibilityUpsert) -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor()

    # 정책 존재 확인
    cur.execute("SELECT id FROM policies WHERE id = ?", (policy_id,))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Policy not found")

    ts = now_iso()

    cur.execute("""
        INSERT INTO policy_eligibility
        (policy_id, min_age, max_age, region, student_required,
         income_type, income_max_percent, income_max_quintile,
         keywords_json, evidence_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(policy_id)
        DO UPDATE SET
            min_age=excluded.min_age,
            max_age=excluded.max_age,
            region=excluded.region,
            student_required=excluded.student_required,
            income_type=excluded.income_type,
            income_max_percent=excluded.income_max_percent,
            income_max_quintile=excluded.income_max_quintile,
            keywords_json=excluded.keywords_json,
            evidence_json=excluded.evidence_json,
            updated_at=excluded.updated_at;
    """, (
        policy_id,
        payload.min_age,
        payload.max_age,
        payload.region,
        _bool_to_int(payload.student_required),
        payload.income_type,
        payload.income_max_percent,
        payload.income_max_quintile,
        json.dumps(payload.keywords, ensure_ascii=False),
        json.dumps(payload.evidence, ensure_ascii=False),
        ts,
    ))

    conn.commit()
    conn.close()
    return {"policy_id": policy_id, "updated_at": ts}