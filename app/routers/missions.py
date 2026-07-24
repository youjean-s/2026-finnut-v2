"""
app/routers/missions.py
------------------------
코칭카드 미션 실행 로그 + 인증(사진/거래내역)
"""

import os
import uuid
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from app.db import get_conn, now_iso
from app.services.mission_verifier import verify_photo, verify_transactions

router = APIRouter(tags=["missions"])

VALID_CATEGORIES = {
    "convenience", "cafe", "food", "transport", "shopping",
    "housing", "entertainment", "subscription", "other"
}

# category(영문 코드) -> verification_type. 여기 없으면 기본값 'photo'
CATEGORY_TO_VERIFICATION = {
    "food": "transaction",  # 배달/식비 절제형 미션
}

# transaction 타입일 때 거래내역에서 매칭할 가맹점 키워드
CATEGORY_KEYWORDS = {
    "food": ["배달의민족", "배민", "요기요", "쿠팡이츠"],
}


def resolve_verification(category: str):
    v_type = CATEGORY_TO_VERIFICATION.get(category, "photo")
    keywords = CATEGORY_KEYWORDS.get(category)
    return v_type, keywords


UPLOAD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "uploads", "mission_photos"
)
UPLOAD_DIR = os.path.normpath(UPLOAD_DIR)
os.makedirs(UPLOAD_DIR, exist_ok=True)


class MissionCreate(BaseModel):
    user_id: int
    card_title: str
    card_mission: str
    category: str
    target_count: int = Field(ge=1, le=30)
    period_days: int = Field(default=7, ge=1, le=30)


def _row_to_dict(r) -> Dict[str, Any]:
    return {
        "id": r["id"],
        "user_id": r["user_id"],
        "card_title": r["card_title"],
        "card_mission": r["card_mission"],
        "category": r["category"],
        "target_count": r["target_count"],
        "current_count": r["current_count"],
        "period_start": r["period_start"],
        "period_end": r["period_end"],
        "status": r["status"],
        "verification_type": r["verification_type"],
        "verification_keywords": r["verification_keywords"],
        "created_at": r["created_at"],
    }


def _maybe_evaluate_transaction_mission(mission_row, cur) -> None:
    """
    transaction 타입 미션이 active 상태이고 기간이 끝났으면
    조회 시점에 자동으로 성공/실패를 확정짓는다 (lazy evaluation).
    mission_row는 sqlite3.Row, 커밋은 호출부에서 처리.
    """
    if mission_row["verification_type"] != "transaction":
        return
    if mission_row["status"] != "active":
        return
    if datetime.now().date().isoformat() <= mission_row["period_end"]:
        return

    keywords = json.loads(mission_row["verification_keywords"]) if mission_row["verification_keywords"] else []
    result = verify_transactions(
        user_id=mission_row["user_id"],
        period_start=mission_row["period_start"],
        period_end=mission_row["period_end"],
        keywords=keywords,
    )
    new_status = "completed" if result["success"] else "failed"
    cur.execute(
        "UPDATE mission_logs SET status = ? WHERE id = ?",
        (new_status, mission_row["id"]),
    )


@router.post("/missions/create")
def create_mission(body: MissionCreate) -> Dict[str, Any]:
    """코칭카드의 미션을 '수락'해서 실행 로그 대상으로 저장"""
    if body.category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"category는 {VALID_CATEGORIES} 중 하나여야 합니다.")

    verification_type, verification_keywords = resolve_verification(body.category)

    today = datetime.now().date()
    period_start = today.isoformat()
    period_end = (today + timedelta(days=body.period_days - 1)).isoformat()

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO mission_logs
           (user_id, card_title, card_mission, category, target_count,
            current_count, period_start, period_end, status,
            verification_type, verification_keywords, created_at)
           VALUES (?, ?, ?, ?, ?, 0, ?, ?, 'active', ?, ?, ?)""",
        (body.user_id, body.card_title, body.card_mission, body.category,
         body.target_count, period_start, period_end,
         verification_type, json.dumps(verification_keywords) if verification_keywords else None,
         now_iso()),
    )
    mission_id = cur.lastrowid
    conn.commit()

    cur.execute("SELECT * FROM mission_logs WHERE id = ?", (mission_id,))
    row = cur.fetchone()
    conn.close()
    return _row_to_dict(row)


@router.post("/missions/{mission_id}/executions")
async def add_execution(
    mission_id: int,
    photo: UploadFile = File(...),
    note: Optional[str] = Form(default=None),
) -> Dict[str, Any]:
    """사진 업로드 → Vision LLM 검증 → 통과 시에만 카운트 증가 (photo 타입 미션 전용)"""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM mission_logs WHERE id = ?", (mission_id,))
    mission = cur.fetchone()
    if mission is None:
        conn.close()
        raise HTTPException(status_code=404, detail="미션을 찾을 수 없습니다.")

    if mission["verification_type"] == "transaction":
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="이 미션은 사진 인증 대상이 아닙니다. 거래내역 기준으로 기간 종료 시 자동 확인됩니다.",
        )

    if mission["status"] != "active":
        conn.close()
        raise HTTPException(status_code=400, detail="이미 종료된 미션입니다.")

    if datetime.now().date().isoformat() > mission["period_end"]:
        cur.execute("UPDATE mission_logs SET status = 'failed' WHERE id = ?", (mission_id,))
        conn.commit()
        conn.close()
        raise HTTPException(status_code=400, detail="미션 기간이 만료되었습니다.")

    ext = os.path.splitext(photo.filename or "")[1] or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(await photo.read())

    verification = verify_photo(filepath, mission["card_mission"])

    cur.execute(
        """INSERT INTO mission_executions
           (mission_log_id, photo_path, note, executed_at, verified, verification_reason, confidence)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            mission_id, filepath, note, now_iso(),
            1 if verification["success"] else 0,
            verification.get("reason"),
            verification.get("confidence"),
        ),
    )
    execution_id = cur.lastrowid

    if verification["success"]:
        new_count = mission["current_count"] + 1
        new_status = "completed" if new_count >= mission["target_count"] else "active"
        cur.execute(
            "UPDATE mission_logs SET current_count = ?, status = ? WHERE id = ?",
            (new_count, new_status, mission_id),
        )
    conn.commit()

    cur.execute("SELECT * FROM mission_logs WHERE id = ?", (mission_id,))
    row = cur.fetchone()
    conn.close()

    result = _row_to_dict(row)
    result["execution"] = {
        "id": execution_id,
        "verified": verification["success"],
        "verification_reason": verification.get("reason"),
        "confidence": verification.get("confidence"),
    }
    return result


@router.post("/missions/{mission_id}/executions/{execution_id}/override")
def override_execution(mission_id: int, execution_id: int) -> Dict[str, Any]:
    """사진 검증 실패(fail) 건을 사용자가 수동으로 성공 처리"""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM mission_executions WHERE id = ? AND mission_log_id = ?",
        (execution_id, mission_id),
    )
    execution = cur.fetchone()
    if execution is None:
        conn.close()
        raise HTTPException(status_code=404, detail="실행 기록을 찾을 수 없습니다.")

    if execution["verified"] == 1:
        conn.close()
        raise HTTPException(status_code=400, detail="이미 인증된 기록입니다.")

    cur.execute("SELECT * FROM mission_logs WHERE id = ?", (mission_id,))
    mission = cur.fetchone()
    if mission is None:
        conn.close()
        raise HTTPException(status_code=404, detail="미션을 찾을 수 없습니다.")
    if mission["status"] != "active":
        conn.close()
        raise HTTPException(status_code=400, detail="이미 종료된 미션입니다.")

    cur.execute(
        """UPDATE mission_executions
           SET verified = 1, verification_reason = ?, confidence = 'override'
           WHERE id = ?""",
        (f"(수동 확인) {execution['verification_reason'] or ''}".strip(), execution_id),
    )

    new_count = mission["current_count"] + 1
    new_status = "completed" if new_count >= mission["target_count"] else "active"
    cur.execute(
        "UPDATE mission_logs SET current_count = ?, status = ? WHERE id = ?",
        (new_count, new_status, mission_id),
    )
    conn.commit()

    cur.execute("SELECT * FROM mission_logs WHERE id = ?", (mission_id,))
    row = cur.fetchone()
    conn.close()
    return _row_to_dict(row)


@router.get("/missions/{mission_id}")
def get_mission(mission_id: int) -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM mission_logs WHERE id = ?", (mission_id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="미션을 찾을 수 없습니다.")

    _maybe_evaluate_transaction_mission(row, cur)
    conn.commit()

    cur.execute("SELECT * FROM mission_logs WHERE id = ?", (mission_id,))
    row = cur.fetchone()
    conn.close()
    return _row_to_dict(row)


@router.get("/missions/user/{user_id}")
def list_user_missions(user_id: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM mission_logs WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
    )
    rows = cur.fetchall()

    for row in rows:
        _maybe_evaluate_transaction_mission(row, cur)
    conn.commit()

    if status:
        cur.execute(
            "SELECT * FROM mission_logs WHERE user_id = ? AND status = ? ORDER BY created_at DESC",
            (user_id, status),
        )
    else:
        cur.execute(
            "SELECT * FROM mission_logs WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
        )
    rows = cur.fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]