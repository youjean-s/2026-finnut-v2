from datetime import datetime, timedelta
from typing import Optional

class ImpulsiveDetector:
    """
    충동 소비 지표 계산:
    - 야간 소비(21~02)
    - 24시간 내 2회 이상 소비
    - 소액다건(1만원 이하 3회 이상)
    """

    def __init__(self):
        self.history = []  # (datetime, amount)

    def compute_score(self, current_dt: datetime, amount: int) -> float:
        self.history.append((current_dt, amount))

        # 규칙 1: 야간 소비
        hour = current_dt.hour
        night_flag = (hour >= 21 or hour <= 2)
        night_score = 1.0 if night_flag else 0.0

        # 규칙 2: 24시간내 2회 이상
        recent = [t for t, a in self.history if current_dt - t <= timedelta(hours=24)]
        freq_score = 1.0 if len(recent) >= 2 else 0.0

        # 규칙 3: 소액다건
        small = [a for t, a in self.history if a <= 10000]
        small_score = 1.0 if len(small) >= 3 else 0.0

        # 가중합
        impulsive_score = round(
            0.4 * freq_score +
            0.3 * night_score +
            0.3 * small_score,
            2
        )

        return impulsive_score


def detect_impulsive(transactions, detector: Optional["ImpulsiveDetector"] = None) -> dict:
    """
    transactions: list[dict] (parser normalized schema)
      expected keys: datetime, amount, merchant, ...
    returns:
      {"impulsive_score": float, "impulsive_flags": list}
    """
    # ✅ Input guard
    if not transactions:
        return {"impulsive_score": 0.0, "impulsive_flags": []}
    if isinstance(transactions, dict):
        transactions = [transactions]
    transactions = [tx for tx in transactions if isinstance(tx, dict)]
    if not transactions:
        return {"impulsive_score": 0.0, "impulsive_flags": []}

    detector = detector or ImpulsiveDetector()

    scores = []
    flags = []

    for tx in transactions:
        dt = tx.get("datetime")
        amt = tx.get("amount", 0)

        if not isinstance(dt, datetime):
            continue
        try:
            amt_int = int(amt)
        except Exception:
            continue

        s = detector.compute_score(dt, amt_int)
        scores.append(s)

        if s >= 0.7:
            flags.append({
                "datetime": dt,
                "amount": amt_int,
                "merchant": tx.get("merchant"),
                "score": s
            })

    final_score = round(sum(scores) / len(scores), 2) if scores else 0.0
    return {"impulsive_score": final_score, "impulsive_flags": flags}
