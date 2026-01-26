from turtle import mode
from ml.ml_runtime.feature_builder import build_features_from_transactions
from ml.ml_runtime.model_loader import FHIModel
from ml.ml_runtime.feature_builder import build_features_from_transactions
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

def calculate_fhi_from_transactions(transactions, mode: str = "rule", model: FHIModel | None = None) -> dict:
    """
    transactions: list[dict] normalized by parser
    returns:
      {
        "fhi": float,
        "impulsive": {...},
        "spike": {...}
      }
    """
    # input guard
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

    # clamp (rule inputs)
    imp_score = max(0.0, min(1.0, imp_score))
    spike_score = max(0.0, spike_score)

    # mode switch
    if mode == "ml":
        # 모델 없으면 기본 로드
        model = model or FHIModel()

        # (Step3에서 더 정교하게 만들지만, 지금은 최소 feature만 넣어서 동작 확인)
        # 최소한 spend_mean_30d 같은 feature들이 없으면 0으로 들어감.
        features = build_features_from_transactions(transactions)
        fhi = float(model.predict_one(features))

        # clamp to 0~100
        fhi = max(0.0, min(100.0, fhi))
    else:
        fhi = calculate_fhi(imp_score, spike_score)

    return {"fhi": round(float(fhi), 2), "impulsive": impulsive, "spike": spike, "mode": mode}


def compare_rule_vs_ml(transactions) -> dict:
    """
    Returns both rule-based and ML-based FHI results for the same transactions.
    """
    rule_res = calculate_fhi_from_transactions(transactions, mode="rule")
    ml_res = calculate_fhi_from_transactions(transactions, mode="ml")

    return {
        "rule": rule_res,
        "ml": ml_res,
        "delta": round(float(ml_res["fhi"]) - float(rule_res["fhi"]), 2),
    }
