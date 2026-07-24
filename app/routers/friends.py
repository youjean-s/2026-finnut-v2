from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.db import get_conn, now_iso

router = APIRouter(tags=["friends"])


# ──────────────────────────────
# 요청/응답 모델
# ──────────────────────────────

class FriendRequestCreate(BaseModel):
    sender_id: int
    receiver_finnut_id: str  # finnut_id로 상대 지정


class FriendRequestAction(BaseModel):
    user_id: int  # 요청 수락/거절을 수행하는 본인 id (권한 체크용)


def _user_brief(r) -> Dict[str, Any]:
    return {
        "id": r["id"],
        "nickname": r["nickname"],
        "finnut_id": r["finnut_id"],
    }


def _friend_ids(conn, user_id: int) -> set:
    cur = conn.cursor()
    cur.execute("SELECT friend_id FROM friendships WHERE user_id = ?", (user_id,))
    return {row["friend_id"] for row in cur.fetchall()}


# ──────────────────────────────
# 검색
# ──────────────────────────────

@router.get("/users/search")
def search_user(finnut_id: str, requester_id: Optional[int] = None) -> Dict[str, Any]:
    """
    finnut_id 정확 일치 검색.
    requester_id를 넘기면 friend_status(친구/요청중/none/self)까지 계산해서 반환.
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, nickname, finnut_id FROM users WHERE finnut_id = ?", (finnut_id,))
    r = cur.fetchone()

    if not r:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")

    result = _user_brief(r)

    if requester_id is not None:
        if requester_id == r["id"]:
            result["friend_status"] = "self"
        else:
            if r["id"] in _friend_ids(conn, requester_id):
                result["friend_status"] = "friends"
            else:
                cur.execute("""
                    SELECT 1 FROM friend_requests
                    WHERE sender_id = ? AND receiver_id = ? AND status = 'pending'
                """, (requester_id, r["id"]))
                if cur.fetchone():
                    result["friend_status"] = "requested"
                else:
                    cur.execute("""
                        SELECT 1 FROM friend_requests
                        WHERE sender_id = ? AND receiver_id = ? AND status = 'pending'
                    """, (r["id"], requester_id))
                    result["friend_status"] = "incoming_request" if cur.fetchone() else "none"

            # 공통 친구 수
            mutual_count = len(_friend_ids(conn, requester_id) & _friend_ids(conn, r["id"]))
            result["mutual_friends_count"] = mutual_count

    conn.close()
    return result


# ──────────────────────────────
# 친구 요청 보내기
# ──────────────────────────────

@router.post("/friend-requests")
def send_friend_request(payload: FriendRequestCreate) -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE finnut_id = ?", (payload.receiver_finnut_id,))
    receiver = cur.fetchone()
    if not receiver:
        conn.close()
        raise HTTPException(status_code=404, detail="Receiver not found")

    receiver_id = receiver["id"]
    if receiver_id == payload.sender_id:
        conn.close()
        raise HTTPException(status_code=400, detail="Cannot add yourself")

    # 이미 친구인지 체크
    if receiver_id in _friend_ids(conn, payload.sender_id):
        conn.close()
        raise HTTPException(status_code=400, detail="Already friends")

    # 이미 pending 요청 있는지 체크 (내가 보낸 것도, 상대가 보낸 것도)
    cur.execute("""
        SELECT id FROM friend_requests
        WHERE ((sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?))
        AND status = 'pending'
    """, (payload.sender_id, receiver_id, receiver_id, payload.sender_id))
    if cur.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Request already pending")

    ts = now_iso()
    cur.execute("""
        INSERT INTO friend_requests (sender_id, receiver_id, status, created_at, updated_at)
        VALUES (?, ?, 'pending', ?, ?)
    """, (payload.sender_id, receiver_id, ts, ts))
    req_id = cur.lastrowid
    conn.commit()
    conn.close()

    return {"id": req_id, "status": "pending", "created_at": ts}


# ──────────────────────────────
# 받은 요청 목록
# ──────────────────────────────

@router.get("/friend-requests/received/{user_id}")
def get_received_requests(user_id: int) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT fr.id, fr.created_at, u.id as sender_user_id, u.nickname, u.finnut_id
        FROM friend_requests fr
        JOIN users u ON u.id = fr.sender_id
        WHERE fr.receiver_id = ? AND fr.status = 'pending'
        ORDER BY fr.created_at DESC
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()

    return [{
        "request_id": r["id"],
        "created_at": r["created_at"],
        "sender": {"id": r["sender_user_id"], "nickname": r["nickname"], "finnut_id": r["finnut_id"]},
    } for r in rows]


# ──────────────────────────────
# 요청 수락 / 거절
# ──────────────────────────────

@router.post("/friend-requests/{request_id}/accept")
def accept_friend_request(request_id: int, payload: FriendRequestAction) -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM friend_requests WHERE id = ?", (request_id,))
    req = cur.fetchone()
    if not req:
        conn.close()
        raise HTTPException(status_code=404, detail="Request not found")
    if req["receiver_id"] != payload.user_id:
        conn.close()
        raise HTTPException(status_code=403, detail="Not authorized to accept this request")
    if req["status"] != "pending":
        conn.close()
        raise HTTPException(status_code=400, detail=f"Request already {req['status']}")

    ts = now_iso()
    cur.execute("UPDATE friend_requests SET status='accepted', updated_at=? WHERE id=?", (ts, request_id))

    # 양방향 friendship insert
    cur.execute("""
        INSERT OR IGNORE INTO friendships (user_id, friend_id, created_at) VALUES (?, ?, ?)
    """, (req["sender_id"], req["receiver_id"], ts))
    cur.execute("""
        INSERT OR IGNORE INTO friendships (user_id, friend_id, created_at) VALUES (?, ?, ?)
    """, (req["receiver_id"], req["sender_id"], ts))

    conn.commit()
    conn.close()
    return {"id": request_id, "status": "accepted"}


@router.post("/friend-requests/{request_id}/reject")
def reject_friend_request(request_id: int, payload: FriendRequestAction) -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM friend_requests WHERE id = ?", (request_id,))
    req = cur.fetchone()
    if not req:
        conn.close()
        raise HTTPException(status_code=404, detail="Request not found")
    if req["receiver_id"] != payload.user_id:
        conn.close()
        raise HTTPException(status_code=403, detail="Not authorized to reject this request")
    if req["status"] != "pending":
        conn.close()
        raise HTTPException(status_code=400, detail=f"Request already {req['status']}")

    ts = now_iso()
    cur.execute("UPDATE friend_requests SET status='rejected', updated_at=? WHERE id=?", (ts, request_id))
    conn.commit()
    conn.close()
    return {"id": request_id, "status": "rejected"}


# ──────────────────────────────
# 친구 목록 / 공통 친구
# ──────────────────────────────

@router.get("/friends/mutual")
def get_mutual_friends(user_id: int, target_id: int) -> Dict[str, Any]:
    conn = get_conn()
    mutual_ids = _friend_ids(conn, user_id) & _friend_ids(conn, target_id)

    if not mutual_ids:
        conn.close()
        return {"count": 0, "friends": []}

    cur = conn.cursor()
    placeholders = ",".join("?" for _ in mutual_ids)
    cur.execute(f"SELECT id, nickname, finnut_id FROM users WHERE id IN ({placeholders})", tuple(mutual_ids))
    rows = cur.fetchall()
    conn.close()

    return {"count": len(rows), "friends": [_user_brief(r) for r in rows]}


@router.get("/friends/{user_id}")
def get_friends(user_id: int) -> List[Dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.id, u.nickname, u.finnut_id, f.created_at
        FROM friendships f
        JOIN users u ON u.id = f.friend_id
        WHERE f.user_id = ?
        ORDER BY f.created_at DESC
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()
    return [{"id": r["id"], "nickname": r["nickname"], "finnut_id": r["finnut_id"], "since": r["created_at"]} for r in rows]