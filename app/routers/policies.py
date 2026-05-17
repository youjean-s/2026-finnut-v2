from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Query, HTTPException
from app.db import get_conn

router = APIRouter(tags=["policies"])

# category는 일단 자유롭게 두고, status만 제한(오타 방지)
ALLOWED_STATUS = {"진행중", "예정", "마감", "정보없음"}


@router.get("/policies")
def list_policies(
    q: Optional[str] = Query(default=None, description="검색어 (name/provider/condition/benefit)"),
    category: Optional[str] = Query(default=None, description="scholarship/housing/employment/subsidy ..."),
    status: Optional[str] = Query(default=None, description="진행중/예정/마감/정보없음"),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Dict[str, Any]:

    where = []
    params: List[Any] = []

    if q:
        kw = f"%{q.strip()}%"
        where.append("(name LIKE ? OR provider LIKE ? OR condition LIKE ? OR benefit LIKE ?)")
        params += [kw, kw, kw, kw]

    if category:
        where.append("category = ?")
        params.append(category.strip())

    if status:
        s = status.strip()
        if s in ALLOWED_STATUS:
            where.append("status = ?")
            params.append(s)

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    conn = get_conn()
    cur = conn.cursor()

    # total_count
    cur.execute(f"SELECT COUNT(*) FROM policies{where_sql}", params)
    total_count = cur.fetchone()[0]

    # items
    cur.execute(
        f"""
        SELECT
            id, policy_key, name, category, provider,
            period, start_date, end_date, status,
            link, condition, benefit,
            source, source_id, fetched_at
        FROM policies
        {where_sql}
        ORDER BY
            CASE status
                WHEN '진행중' THEN 1
                WHEN '예정' THEN 2
                WHEN '마감' THEN 3
                ELSE 4
            END,
            start_date DESC,
            id DESC
        LIMIT ? OFFSET ?
        """,
        params + [limit, offset],
    )

    rows = cur.fetchall()
    conn.close()

    items = [
        {
            "id": r[0],
            "policy_key": r[1],
            "name": r[2],
            "category": r[3],
            "provider": r[4],
            "period": r[5],
            "start_date": r[6],
            "end_date": r[7],
            "status": r[8],
            "link": r[9],
            "condition": r[10],
            "benefit": r[11],
            "source": r[12],
            "source_id": r[13],
            "fetched_at": r[14],
        }
        for r in rows
    ]

    return {
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@router.get("/policies/{policy_id}")
def get_policy(policy_id: int) -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            id, policy_key, name, category, provider,
            period, start_date, end_date, status,
            link, condition, benefit,
            source, source_id, fetched_at,
            raw_json
        FROM policies
        WHERE id = ?
        """,
        (policy_id,),
    )

    r = cur.fetchone()
    conn.close()

    if not r:
        raise HTTPException(status_code=404, detail="Policy not found")

    return {
        "id": r[0],
        "policy_key": r[1],
        "name": r[2],
        "category": r[3],
        "provider": r[4],
        "period": r[5],
        "start_date": r[6],
        "end_date": r[7],
        "status": r[8],
        "link": r[9],
        "condition": r[10],
        "benefit": r[11],
        "source": r[12],
        "source_id": r[13],
        "fetched_at": r[14],
        "raw_json": r[15],
    }