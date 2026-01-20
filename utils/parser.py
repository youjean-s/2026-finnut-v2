"""
parser.py
Input: push notification text (str)
Output: list[dict] normalized transactions with keys:
  datetime, amount, merchant, category, source, payment_method, raw_text
"""

import re
from datetime import datetime


def _normalize_tx(tx: dict, raw_text: str) -> dict:
    """
    Normalize parsed transaction dict to a fixed schema.
    """
    return {
        "datetime": tx.get("datetime"),
        "amount": float(tx.get("amount", 0)),
        "merchant": tx.get("merchant") or tx.get("store") or tx.get("place"),
        "category": tx.get("category"),
        "source": tx.get("source"),                 # 아직 없으면 None
        "payment_method": tx.get("payment_method"), # 아직 없으면 None
        "raw_text": raw_text,
    }


def parse_push_notification(text: str) -> list[dict]:
    """
    Parse various card/KakaoPay/Pay-style payment push notifications.

    Returns:
        list[dict] of normalized transactions (empty list if nothing parsed)
    """
    try:
        # 금액 추출
        amount_pattern = r"([\d,]+)\s*원"
        amount_match = re.search(amount_pattern, text)
        amount = int(amount_match.group(1).replace(",", "")) if amount_match else 0

        # 가맹점명 추출 (두 번째 줄)
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        store = lines[1] if len(lines) >= 2 else "알수없음"

        # 날짜/시간 추출
        datetime_pattern = r"(\d{4}-\d{2}-\d{2})\s*(\d{2}:\d{2})"
        dt_match = re.search(datetime_pattern, text)
        if dt_match:
            dt_str = f"{dt_match.group(1)} {dt_match.group(2)}"
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        else:
            dt = datetime.now()

        tx = {"store": store, "amount": amount, "datetime": dt}
        return [_normalize_tx(tx, raw_text=text)]

    except Exception as e:
        print("[ParserError]", e)
        return []
   
