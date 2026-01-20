"""
fhi_calculator.py
Input: transactions (list[dict]) from parser normalized schema
Output: {"fhi": float, "impulsive": dict, "spike": dict}
"""


def calculate_fhi(impulsive: float, spike: float) -> float:
    """
    금융건강지수(FHI) = 100 - (충동구매*40 + 급증*30)
    """
    score = 100 - (impulsive * 40 + max(0, spike) * 30)
    return round(max(score, 0), 2)

from utils.impulsive_detector import detect_impulsive
from utils.spending_spike import detect_spending_spike

def calculate_fhi_from_transactions(transactions) -> dict:
    """
    transactions: list[dict] normalized by parser
    returns:
      {
        "fhi": float,
        "impulsive": {...},
        "spike": {...}
      }
    """
    # ✅ input guard
    if not transactions:
        return {
            "fhi": 0.0,
            "impulsive": {"impulsive_score": 0.0, "impulsive_flags": []},
            "spike": {"spike_score": 0.0, "spike_flags": []},
        }

    impulsive = detect_impulsive(transactions)
    spike = detect_spending_spike(transactions)

    imp_score = float(impulsive.get("impulsive_score", 0.0))
    spike_score = float(spike.get("spike_score", 0.0))

    fhi = calculate_fhi(imp_score, spike_score)

    return {"fhi": fhi, "impulsive": impulsive, "spike": spike}
