from __future__ import annotations
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd


def _to_dt(x) -> datetime | None:
    if isinstance(x, datetime):
        return x
    try:
        return pd.to_datetime(x).to_pydatetime()
    except Exception:
        return None


def build_features_from_transactions(transactions: list[dict], asof: datetime | None = None) -> dict:
    """
    Convert FINNUT normalized transactions -> feature dict for ML model.

    Expected tx keys: datetime, amount, merchant, category, payment_method, source
    Output keys should match (at least partially) training features.
    """

    if not transactions:
        return {}

    txs = []
    for tx in transactions:
        if not isinstance(tx, dict):
            continue
        dt = _to_dt(tx.get("datetime"))
        if dt is None:
            continue
        try:
            amt = float(tx.get("amount", 0))
        except Exception:
            continue
        if amt <= 0:
            continue
        txs.append({
            "dt": dt,
            "amt": amt,
            "category": (tx.get("category") or "unknown"),
        })

    if not txs:
        return {}

    asof = asof or max(t["dt"] for t in txs)

    # windows
    w7 = asof - timedelta(days=7)
    w30 = asof - timedelta(days=30)

    amt_7 = [t["amt"] for t in txs if t["dt"] >= w7]
    amt_30 = [t["amt"] for t in txs if t["dt"] >= w30]

    # category counts (30d)
    cat_30 = [t["category"] for t in txs if t["dt"] >= w30]
    unique_cat_30 = len(set(cat_30))

    # category mix ratio (30d)
    cat_sum = defaultdict(float)
    for t in txs:
        if t["dt"] >= w30:
            cat_sum[t["category"]] += t["amt"]
    total_30 = sum(cat_sum.values()) if cat_sum else 0.0

    # 기본 feature 세트 (너가 일단 features.csv에 있었던 형태로 최소 구성)
    features = {
        "spend_sum_7d": sum(amt_7),
        "spend_mean_30d": (sum(amt_30) / len(amt_30)) if amt_30 else 0.0,
        "tx_count_7d": float(len(amt_7)),
        "tx_count_30d": float(len(amt_30)),
        "unique_category_count_30d": float(unique_cat_30),
    }

    # (선택) 카테고리별 비중 feature: 카테고리명이 컬럼으로 쓰이던 방식이면 여기서 생성
    # 예: cat_ratio_편의점, cat_ratio_카페 ...
    for cat, s in cat_sum.items():
        key = f"cat_ratio_{cat}"
        features[key] = (s / total_30) if total_30 > 0 else 0.0

    return features
