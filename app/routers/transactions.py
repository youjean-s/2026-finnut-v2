"""
app/routers/transactions.py
----------------------------
Android Room DB → 백엔드 거래내역 동기화
"""

from datetime import datetime
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import get_conn, now_iso

router = APIRouter(tags=["transactions"])


class TransactionItem(BaseModel):
    datetime: str            # ISO datetime, parser.py 스키마 그대로
    amount: int
    merchant: str
    category: Optional[str] = None
    source: Optional[str] = None
    payment_method: Optional[str] = None
    raw_text: Optional[str] = None


class SyncRequest(BaseModel):
    user_id: int
    transactions: List[TransactionItem]


@router.post("/transactions/sync")
def sync_transactions(body: SyncRequest) -> Dict[str, Any]:
    """Android에서 파싱된 거래내역을 백엔드로 동기화 (중복은 무시)"""
    if not body.transactions:
        raise HTTPException(status_code=400, detail="transactions가 비어 있습니다.")

    conn = get_conn()
    cur = conn.cursor()
    synced_at = now_iso()

    inserted = 0
    for tx in body.transactions:
        cur.execute(
            """INSERT OR IGNORE INTO transactions
               (user_id, tx_datetime, amount, merchant, category, source,
                payment_method, raw_text, synced_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (body.user_id, tx.datetime, tx.amount, tx.merchant, tx.category,
             tx.source, tx.payment_method, tx.raw_text, synced_at),
        )
        if cur.rowcount > 0:
            inserted += 1

    conn.commit()
    conn.close()

    return {
        "received": len(body.transactions),
        "inserted": inserted,
        "duplicates_ignored": len(body.transactions) - inserted,
        "synced_at": synced_at,
    }