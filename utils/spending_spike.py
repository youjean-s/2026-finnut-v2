"""
spending_spike.py
Input: transactions (list[dict]) from parser normalized schema
Output: {"spike_score": float, "spike_flags": list}
"""

class SpendingSpikeDetector:
    """
    최근 7일 평균 vs 이전 30일 평균 비교
    """

    def __init__(self):
        self.daily_history = []  # 금액 목록

    def compute_spike(self, amount: int) -> float:
        self.daily_history.append(amount)

        if len(self.daily_history) < 10:
            return 0.0  # 데이터 부족 → 급증 판단 못함

        recent7 = self.daily_history[-7:]
        prev30 = self.daily_history[-37:-7] if len(self.daily_history) >= 37 else self.daily_history[:-7]

        if not prev30:
            return 0.0

        avg_recent = sum(recent7) / len(recent7)
        avg_prev = sum(prev30) / len(prev30)

        if avg_prev == 0:
            return 0.0

        spike_ratio = (avg_recent - avg_prev) / avg_prev
        return round(spike_ratio, 2)

def detect_spending_spike(transactions, detector: "SpendingSpikeDetector" = None) -> dict:
    """
    transactions: list[dict] (parser normalized schema)
      expected keys: datetime, amount, merchant, ...
    returns:
      {"spike_score": float, "spike_flags": list}
    """
    # ✅ Input guard
    if not transactions:
        return {"spike_score": 0.0, "spike_flags": []}
    if isinstance(transactions, dict):
        transactions = [transactions]
    transactions = [tx for tx in transactions if isinstance(tx, dict)]
    if not transactions:
        return {"spike_score": 0.0, "spike_flags": []}

    detector = detector or SpendingSpikeDetector()

    scores = []
    for tx in transactions:
        amt = tx.get("amount", 0)
        try:
            amt_int = int(amt)
        except Exception:
            continue

        s = detector.compute_spike(amt_int)
        scores.append(s)

    # 0주차 정책: 여러 건이면 최근 값(마지막)을 spike_score로 사용
    spike_score = scores[-1] if scores else 0.0

    # flag는 일단 “급증”으로 볼 만한 임계치만 표시(임계치는 1주차에 튜닝)
    spike_flags = []
    if spike_score >= 0.5:  # 예: 50% 이상 증가
        spike_flags.append({"reason": "spike_ratio>=0.5", "score": spike_score})

    return {"spike_score": spike_score, "spike_flags": spike_flags}
