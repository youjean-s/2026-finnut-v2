from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Query, HTTPException
from app.db import get_conn

router = APIRouter(tags=["scholarships"])

ALLOWED_STATUS = {"진행중", "예정", "마감", "정보없음"}


@router.get("/scholarships")
def list_scholarships(
    q: Optional[str] = Query(default=None, description="검색어"),
    status: Optional[str] = Query(default=None, description="진행중/예정/마감"),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Dict[str, Any]:

    where = []
    params: List[Any] = []

    if q:
        keyword = f"%{q.strip()}%"
        where.append("(name LIKE ? OR type LIKE ? OR condition LIKE ? OR grant LIKE ?)")
        params += [keyword, keyword, keyword, keyword]

    if status:
        s = status.strip()
        if s in ALLOWED_STATUS:
            where.append("status = ?")
            params.append(s)

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(f"SELECT COUNT(*) FROM scholarships{where_sql}", params)
    total_count = cur.fetchone()[0]

    cur.execute(
        f"""
        SELECT
            id, name, type, period, start_date, end_date, status, link, condition, grant
        FROM scholarships
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
            "name": r[1],
            "type": r[2],
            "period": r[3],
            "start_date": r[4],
            "end_date": r[5],
            "status": r[6],
            "link": r[7],
            "condition": r[8],
            "grant": r[9],
        }
        for r in rows
    ]

    return {
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@router.get("/scholarships/{scholarship_id}")
def get_scholarship(scholarship_id: int):

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, name, type, period, start_date, end_date, status, link, condition, grant
        FROM scholarships
        WHERE id = ?
        """,
        (scholarship_id,),
    )

    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Scholarship not found")

    return {
        "id": row[0],
        "name": row[1],
        "type": row[2],
        "period": row[3],
        "start_date": row[4],
        "end_date": row[5],
        "status": row[6],
        "link": row[7],
        "condition": row[8],
        "grant": row[9],
    }