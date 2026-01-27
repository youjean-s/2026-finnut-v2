"""
parser.py
Input: push notification text (str)
Output: list[dict] normalized transactions with keys:
  datetime, amount, merchant, category, source, payment_method, raw_text
"""

import re
from datetime import datetime


def _detect_source(text: str) -> str:
    t = text.lower()
    if "카카오페이" in text or "kakaopay" in t:
        return "kakaopay"
    if "신한" in text:
        return "shinhan"
    if "kb" in t or "국민" in text:
        return "kb"
    if "현대" in text:
        return "hyundai"
    if "삼성" in text:
        return "samsung"
    return "unknown"


def _normalize_tx(tx: dict, raw_text: str) -> dict:
    """
    Normalize parsed transaction dict to a fixed schema.
    """
    source = tx.get("source") or "unknown"
    pm = tx.get("payment_method") or "unknown"

    merchant = tx.get("merchant") or tx.get("store") or tx.get("place") or "알수없음"

    # amount는 무조건 float(+지출). 변환 실패하면 0.0
       # amount는 무조건 int(+지출). 변환 실패하면 0
    amt = tx.get("amount", 0)
    try:
        # int/float/str 모두 대응
        if isinstance(amt, str):
            s = amt.replace(",", "").replace("원", "").replace("₩", "").strip()
            amount = int(float(s)) if s else 0
        else:
            amount = int(float(amt))
    except Exception:
        amount = 0

    return {
        "datetime": tx.get("datetime"),   # parser에서 datetime으로 맞춰주고 있음
        "amount": amount,
        "merchant": merchant,
        "category": tx.get("category"),
        "source": source,
        "payment_method": pm,
        "raw_text": raw_text,
    }



def _parse_unknown(text: str) -> dict:
    # 기존 기본 파싱 로직을 unknown fallback으로 사용
    amount_pattern = r"([\d,]+)\s*원"
    amount_match = re.search(amount_pattern, text)
    amount = int(amount_match.group(1).replace(",", "")) if amount_match else 0

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    store = lines[1] if len(lines) >= 2 else "알수없음"

    datetime_pattern = r"(\d{4}-\d{2}-\d{2})\s*(\d{2}:\d{2})"
    dt_match = re.search(datetime_pattern, text)
    if dt_match:
        dt_str = f"{dt_match.group(1)} {dt_match.group(2)}"
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
    else:
        dt = datetime.now()

    return {"store": store, "amount": amount, "datetime": dt}


def _parse_shinhan(text: str) -> dict:
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # 1) amount: 어디 있든 "숫자원" 패턴으로 검색 (1줄째에 붙는 경우 대응)
    amount = 0
    m = re.search(r"([\d,]+)\s*원", text)
    if m:
        amount = int(m.group(1).replace(",", ""))

    # 2) datetime: 보통 마지막 줄에 있음 (없으면 현재시간)
    dt = datetime.now()
    mdt = re.search(r"(\d{4}-\d{2}-\d{2})\s*(\d{2}:\d{2})", text)
    if mdt:
        dt = datetime.strptime(f"{mdt.group(1)} {mdt.group(2)}", "%Y-%m-%d %H:%M")

    # 3) store/merchant: 보통 2번째 줄이 매장명
    store = "알수없음"
    if len(lines) >= 2:
        store = lines[1]
    else:
        # fallback: 그래도 없으면 unknown 로직 사용
        fallback = _parse_unknown(text)
        store = fallback.get("store", store)

    return {
        "store": store,
        "amount": amount,
        "datetime": dt,
        "payment_method": "card",  # 신한카드 푸시는 카드 결제로 간주
    }

def _parse_kakaopay(text: str) -> dict:
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # amount
    amount = 0
    m = re.search(r"([\d,]+)\s*원", text)
    if m:
        amount = int(m.group(1).replace(",", ""))

    # datetime (있는 경우만)
    dt = datetime.now()
    mdt = re.search(r"(\d{4}-\d{2}-\d{2})\s*(\d{2}:\d{2})", text)
    if mdt:
        dt = datetime.strptime(f"{mdt.group(1)} {mdt.group(2)}", "%Y-%m-%d %H:%M")

    # merchant: 보통 2번째 줄
    store = "알수없음"
    if len(lines) >= 2:
        store = lines[1]

    return {
        "store": store,
        "amount": amount,
        "datetime": dt,
        "payment_method": "wallet",  # 카카오페이는 지갑/간편결제로
    }


def _parse_kb(text: str) -> dict:
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # amount
    amount = 0
    m = re.search(r"([\d,]+)\s*원", text)
    if m:
        amount = int(m.group(1).replace(",", ""))

    # datetime
    dt = datetime.now()
    mdt = re.search(r"(\d{4}[./-]\d{2}[./-]\d{2})\s*(\d{2}:\d{2})", text)
    if mdt:
        date_str = mdt.group(1).replace(".", "-").replace("/", "-")
        dt = datetime.strptime(f"{date_str} {mdt.group(2)}", "%Y-%m-%d %H:%M")

    # merchant: 보통 2번째 줄이거나, "가맹점" 라벨 뒤에 올 수도 있어서 fallback
    store = "알수없음"
    if len(lines) >= 2:
        store = lines[1]
    # 라벨 패턴 fallback
    mstore = re.search(r"(가맹점|사용처)[:\s]*([^\n]+)", text)
    if mstore:
        store = mstore.group(2).strip()

    return {
        "store": store,
        "amount": amount,
        "datetime": dt,
        "payment_method": "card",
    }


def _parse_samsung(text: str) -> dict:
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # amount
    amount = 0
    m = re.search(r"([\d,]+)\s*원", text)
    if m:
        amount = int(m.group(1).replace(",", ""))

    # datetime (YYYY-MM-DD HH:MM 또는 YYYY.MM.DD HH:MM 등)
    dt = datetime.now()
    mdt = re.search(r"(\d{4}[./-]\d{2}[./-]\d{2})\s*(\d{2}:\d{2})", text)
    if mdt:
        date_str = mdt.group(1).replace(".", "-").replace("/", "-")
        dt = datetime.strptime(f"{date_str} {mdt.group(2)}", "%Y-%m-%d %H:%M")

    # merchant: 보통 2번째 줄 / 또는 "가맹점:" 라벨 뒤
    store = "알수없음"
    if len(lines) >= 2:
        store = lines[1]

    mstore = re.search(r"(가맹점|사용처)[:\s]*([^\n]+)", text)
    if mstore:
        store = mstore.group(2).strip()

    # 삼성페이면 wallet, 삼성카드면 card로(초간단 휴리스틱)
    payment_method = "wallet" if "삼성페이" in text else "card"

    return {
        "store": store,
        "amount": amount,
        "datetime": dt,
        "payment_method": payment_method,
    }



def parse_push_notification(text: str) -> list[dict]:
    try:
        source = _detect_source(text)

        if source == "shinhan":
            tx = _parse_shinhan(text)
        elif source == "kakaopay":
            tx = _parse_kakaopay(text)
        elif source == "kb":
            tx = _parse_kb(text)
        elif source == "samsung":
            tx = _parse_samsung(text)
        else:
            tx = _parse_unknown(text)

        if not tx:
            return []

        tx["source"] = source
        return [_normalize_tx(tx, raw_text=text)]

    except Exception as e:
        print("[ParserError]", e)
        return []
