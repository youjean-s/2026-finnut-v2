from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.db import get_conn, now_iso

router = APIRouter(tags=["challenges"])

VALID_CATEGORIES = {"소비절약", "저축", "투자공부", "생활"}
ACORN_PER_CHECKIN = 5  # 인증 1회당 지급 도토리


# ──────────────────────────────
# 요청 모델
# ──────────────────────────────

class ChallengeCreate(BaseModel):
    title: str
    category: str
    description: Optional[str] = None
    period_days: int = 7
    created_by: Optional[int] = None


class JoinBody(BaseModel):
    user_id: int


class CheckinBody(BaseModel):
    user_id: int


# ──────────────────────────────
# 헬퍼
# ──────────────────────────────

def _today() -> str:
    return date.today().isoformat()


def _participant_count(conn, challenge_id: int) -> int:
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) c FROM challenge_participants WHERE challenge_id = ?", (challenge_id,))
    return cur.fetchone()["c"]


def _today_cert_rate(conn, challenge_id: int) -> float:
    total = _participant_count(conn, challenge_id)
    if total == 0:
        return 0.0
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(DISTINCT user_id) c FROM challenge_checkins
        WHERE challenge_id = ? AND checkin_date = ?
    """, (challenge_id, _today()))
    checked = cur.fetchone()["c"]
    return round(checked / total * 100, 1)


def _challenge_to_dict(conn, r) -> Dict[str, Any]:
    return {
        "id": r["id"],
        "title": r["title"],
        "category": r["category"],
        "description": r["description"],
        "period_days": r["period_days"],
        "participant_count": _participant_count(conn, r["id"]),
        "cert_rate": _today_cert_rate(conn, r["id"]),
        "created_at": r["created_at"],
    }


# ──────────────────────────────
# 목록 / 검색  (GET /challenges/{id}보다 먼저 매칭될 고정 경로 없음 -> id는 int라 충돌 없음)
# ──────────────────────────────

@router.get("/challenges")
def list_challenges(
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    period_days: Optional[int] = None,
    limit: int = 20,
    offset: int = 0,
) -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor()

    where = []
    params: List[Any] = []
    if keyword:
        where.append("title LIKE ?")
        params.append(f"%{keyword}%")
    if category and category != "전체":
        where.append("category = ?")
        params.append(category)
    if period_days:
        where.append("period_days = ?")
        params.append(period_days)

    where_clause = f"WHERE {' AND '.join(where)}" if where else ""
    cur.execute(f"SELECT COUNT(*) c FROM challenges {where_clause}", params)
    total = cur.fetchone()["c"]

    cur.execute(f"""
        SELECT * FROM challenges {where_clause}
        ORDER BY created_at DESC LIMIT ? OFFSET ?
    """, params + [limit, offset])
    rows = cur.fetchall()

    items = [_challenge_to_dict(conn, r) for r in rows]
    conn.close()
    return {"total_count": total, "limit": limit, "offset": offset, "items": items}


@router.post("/challenges")
def create_challenge(payload: ChallengeCreate) -> Dict[str, Any]:
    if payload.category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"category must be one of {VALID_CATEGORIES}")

    conn = get_conn()
    cur = conn.cursor()
    ts = now_iso()
    cur.execute("""
        INSERT INTO challenges (title, category, description, period_days, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (payload.title, payload.category, payload.description, payload.period_days, payload.created_by, ts))
    challenge_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": challenge_id, "created_at": ts}


@router.get("/challenges/{challenge_id}")
def get_challenge(challenge_id: int) -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM challenges WHERE id = ?", (challenge_id,))
    r = cur.fetchone()
    if not r:
        conn.close()
        raise HTTPException(status_code=404, detail="Challenge not found")
    result = _challenge_to_dict(conn, r)
    conn.close()
    return result


# ──────────────────────────────
# 참여
# ──────────────────────────────

@router.post("/challenges/{challenge_id}/join")
def join_challenge(challenge_id: int, payload: JoinBody) -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id FROM challenges WHERE id = ?", (challenge_id,))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Challenge not found")

    cur.execute("""
        SELECT id FROM challenge_participants WHERE challenge_id = ? AND user_id = ?
    """, (challenge_id, payload.user_id))
    if cur.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Already joined")

    ts = now_iso()
    cur.execute("""
        INSERT INTO challenge_participants (challenge_id, user_id, joined_at, acorn_score, current_streak)
        VALUES (?, ?, ?, 0, 0)
    """, (challenge_id, payload.user_id, ts))
    conn.commit()
    conn.close()
    return {"challenge_id": challenge_id, "user_id": payload.user_id, "joined_at": ts}


# ──────────────────────────────
# 오늘 인증하기
# ──────────────────────────────

@router.post("/challenges/{challenge_id}/checkin")
def checkin_challenge(challenge_id: int, payload: CheckinBody) -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT * FROM challenge_participants WHERE challenge_id = ? AND user_id = ?
    """, (challenge_id, payload.user_id))
    participant = cur.fetchone()
    if not participant:
        conn.close()
        raise HTTPException(status_code=400, detail="Not a participant of this challenge")

    today = _today()
    if participant["last_checkin_date"] == today:
        conn.close()
        raise HTTPException(status_code=400, detail="Already checked in today")

    ts = now_iso()
    cur.execute("""
        INSERT INTO challenge_checkins (challenge_id, user_id, checkin_date, created_at)
        VALUES (?, ?, ?, ?)
    """, (challenge_id, payload.user_id, today, ts))

    # 연속 인증 여부 계산 (어제 인증했으면 streak+1, 아니면 1로 리셋)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    new_streak = (participant["current_streak"] + 1) if participant["last_checkin_date"] == yesterday else 1

    new_score = participant["acorn_score"] + ACORN_PER_CHECKIN
    cur.execute("""
        UPDATE challenge_participants
        SET acorn_score = ?, current_streak = ?, last_checkin_date = ?
        WHERE id = ?
    """, (new_score, new_streak, today, participant["id"]))

    # 도토리는 재화 개념 -> 유저 전역 잔액에도 반영
    cur.execute("""
        UPDATE users SET acorn_balance = COALESCE(acorn_balance, 0) + ? WHERE id = ?
    """, (ACORN_PER_CHECKIN, payload.user_id))

    conn.commit()
    conn.close()
    return {"challenge_id": challenge_id, "user_id": payload.user_id, "acorn_score": new_score, "current_streak": new_streak}


# ──────────────────────────────
# 챌린지 방 (진행현황 그리드 + 실시간 랭킹)
# ──────────────────────────────

@router.get("/challenges/{challenge_id}/room")
def get_challenge_room(challenge_id: int, user_id: int) -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM challenges WHERE id = ?", (challenge_id,))
    challenge = cur.fetchone()
    if not challenge:
        conn.close()
        raise HTTPException(status_code=404, detail="Challenge not found")

    cur.execute("""
        SELECT * FROM challenge_participants WHERE challenge_id = ? AND user_id = ?
    """, (challenge_id, user_id))
    me = cur.fetchone()
    if not me:
        conn.close()
        raise HTTPException(status_code=400, detail="Not a participant of this challenge")

    period_days = challenge["period_days"]
    joined_date = datetime.fromisoformat(me["joined_at"]).date()

    # 내 인증 기록 불러오기
    cur.execute("""
        SELECT checkin_date FROM challenge_checkins WHERE challenge_id = ? AND user_id = ?
    """, (challenge_id, user_id))
    checked_dates = {row["checkin_date"] for row in cur.fetchall()}

    today = date.today()
    progress = []
    for i in range(period_days):
        day = joined_date + timedelta(days=i)
        if day > today:
            status = "locked"          # 아직 오지 않은 날
        elif day.isoformat() in checked_dates:
            status = "done"            # 인증 완료
        elif day == today:
            status = "today"           # 오늘, 아직 미인증
        else:
            status = "missed"          # 지나갔는데 인증 안 함
        progress.append({"day": i + 1, "date": day.isoformat(), "status": status})

    d_day = max(period_days - (today - joined_date).days, 0)

    # 실시간 랭킹
    cur.execute("""
        SELECT cp.user_id, cp.acorn_score, u.nickname, u.finnut_id
        FROM challenge_participants cp
        JOIN users u ON u.id = cp.user_id
        WHERE cp.challenge_id = ?
        ORDER BY cp.acorn_score DESC, cp.joined_at ASC
    """, (challenge_id,))
    ranking = [{
        "rank": idx + 1,
        "user_id": row["user_id"],
        "nickname": row["nickname"],
        "finnut_id": row["finnut_id"],
        "acorn_score": row["acorn_score"],
        "is_me": row["user_id"] == user_id,
    } for idx, row in enumerate(cur.fetchall())]

    conn.close()

    return {
        "challenge": {
            "id": challenge["id"],
            "title": challenge["title"],
            "category": challenge["category"],
            "description": challenge["description"],
            "period_days": period_days,
        },
        "d_day": d_day,
        "my_progress": progress,
        "checked_today": today.isoformat() in checked_dates,
        "ranking": ranking,
    }


# ──────────────────────────────
# 내가 참여중인 챌린지 목록 (홈/챌린지 탭 상단용)
# ──────────────────────────────

@router.get("/users/{user_id}/challenges")
def get_my_challenges(user_id: int) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.*, cp.joined_at, cp.acorn_score, cp.current_streak, cp.last_checkin_date
        FROM challenge_participants cp
        JOIN challenges c ON c.id = cp.challenge_id
        WHERE cp.user_id = ?
        ORDER BY cp.joined_at DESC
    """, (user_id,))
    rows = cur.fetchall()

    today = date.today()
    items = []
    for r in rows:
        joined_date = datetime.fromisoformat(r["joined_at"]).date()
        elapsed = (today - joined_date).days
        d_day = max(r["period_days"] - elapsed, 0)
        progress_pct = round(min(r["current_streak"] / r["period_days"], 1.0) * 100, 1)

        # 이 챌린지 안에서 내 순위 계산
        cur.execute("""
            SELECT user_id FROM challenge_participants
            WHERE challenge_id = ?
            ORDER BY acorn_score DESC, joined_at ASC
        """, (r["id"],))
        ordered_ids = [row["user_id"] for row in cur.fetchall()]
        my_rank = ordered_ids.index(user_id) + 1 if user_id in ordered_ids else None

        items.append({
            "id": r["id"],
            "title": r["title"],
            "category": r["category"],
            "period_days": r["period_days"],
            "d_day": d_day,
            "current_streak": r["current_streak"],
            "acorn_score": r["acorn_score"],
            "progress_pct": progress_pct,
            "checked_today": r["last_checkin_date"] == today.isoformat(),
            "participant_count": len(ordered_ids),
            "my_rank": my_rank,
        })
    conn.close()
    return items