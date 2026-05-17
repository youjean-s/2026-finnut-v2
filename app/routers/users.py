import json
from datetime import date
from typing import Optional, List, Any, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.db import get_conn, now_iso

router = APIRouter(tags=["users"])


# ── 학교 구분 ──
SCHOOL_TYPES = {"대학생", "대학원생", "기타"}


def _calc_age(birthdate_str: Optional[str]) -> Optional[int]:
    """생년월일(YYYY-MM-DD) → 만 나이 자동 계산"""
    if not birthdate_str:
        return None
    try:
        bd = date.fromisoformat(birthdate_str)
        today = date.today()
        age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
        return age
    except ValueError:
        return None


def _bool_to_int(v: Optional[bool]) -> Optional[int]:
    if v is None:
        return None
    return 1 if v else 0


class UserCreate(BaseModel):
    nickname: Optional[str] = None
    gender: Optional[str] = None          # "male" | "female" | "other"
    birthdate: Optional[str] = None       # "YYYY-MM-DD"
    income_level: Optional[int] = Field(default=None, ge=1, le=10)  # 소득분위 1~10
    region: Optional[str] = None
    school: Optional[str] = None          # "대학생" | "대학원생" | "기타"
    student: Optional[bool] = None
    keywords: List[str] = Field(default_factory=list)


class UserUpdate(BaseModel):
    nickname: Optional[str] = None
    gender: Optional[str] = None
    birthdate: Optional[str] = None
    income_level: Optional[int] = Field(default=None, ge=1, le=10)
    region: Optional[str] = None
    school: Optional[str] = None
    student: Optional[bool] = None
    keywords: Optional[List[str]] = None


def _row_to_dict(r) -> Dict[str, Any]:
    """DB row → API 응답 dict (나이 자동 계산 포함)"""
    return {
        "id": r["id"],
        "nickname": r["nickname"],
        "gender": r["gender"],
        "birthdate": r["birthdate"],
        "age": _calc_age(r["birthdate"]),   # 생년월일 기준 자동 계산
        "income_level": r["income_level"],
        "region": r["region"],
        "school": r["school"],
        "student": (None if r["student"] is None else bool(r["student"])),
        "keywords": json.loads(r["keywords_json"] or "[]"),
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
    }


# ──────────────────────────────
# 엔드포인트
# ──────────────────────────────

@router.post("/users")
def create_user(payload: UserCreate) -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor()
    ts = now_iso()

    cur.execute("""
        INSERT INTO users (
            nickname, gender, birthdate, income_level,
            region, school, student, keywords_json,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        payload.nickname,
        payload.gender,
        payload.birthdate,
        payload.income_level,
        payload.region,
        payload.school,
        _bool_to_int(payload.student),
        json.dumps(payload.keywords, ensure_ascii=False),
        ts,
        ts,
    ))
    user_id = cur.lastrowid
    conn.commit()
    conn.close()

    return {"id": user_id, "created_at": ts}


@router.get("/users/{user_id}")
def get_user(user_id: int) -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    r = cur.fetchone()
    conn.close()

    if not r:
        raise HTTPException(status_code=404, detail="User not found")

    return _row_to_dict(r)


@router.patch("/users/{user_id}")
def update_user(user_id: int, payload: UserUpdate) -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    r = cur.fetchone()
    if not r:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")

    ts = now_iso()

    # 값이 넘어오면 업데이트, 없으면 기존값 유지
    nickname     = payload.nickname      if payload.nickname      is not None else r["nickname"]
    gender       = payload.gender        if payload.gender        is not None else r["gender"]
    birthdate    = payload.birthdate     if payload.birthdate     is not None else r["birthdate"]
    income_level = payload.income_level  if payload.income_level  is not None else r["income_level"]
    region       = payload.region        if payload.region        is not None else r["region"]
    school       = payload.school        if payload.school        is not None else r["school"]
    student      = _bool_to_int(payload.student) if payload.student is not None else r["student"]
    keywords_json = (
        json.dumps(payload.keywords, ensure_ascii=False)
        if payload.keywords is not None
        else r["keywords_json"]
    )

    cur.execute("""
        UPDATE users
        SET nickname=?, gender=?, birthdate=?, income_level=?,
            region=?, school=?, student=?, keywords_json=?, updated_at=?
        WHERE id=?
    """, (nickname, gender, birthdate, income_level,
          region, school, student, keywords_json, ts, user_id))

    conn.commit()
    conn.close()

    # 수정된 유저 정보 전체 반환
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    updated = cur.fetchone()
    conn.close()

    return _row_to_dict(updated)