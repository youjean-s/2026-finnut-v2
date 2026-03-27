from __future__ import annotations
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np
import pandas as pd


# val.csv 의 고정 카테고리 컬럼명과 매핑
# key: 학습 feature 컬럼명, value: 실제 거래 category 값
CATEGORY_COLS = {
    "cat_spend_ratio_entertainment_30d": "entertainment",
    "cat_spend_ratio_gas_transport_30d": "gas_transport",
    "cat_spend_ratio_grocery_pos_30d":   "grocery_pos",
    "cat_spend_ratio_home_30d":          "home",
    "cat_spend_ratio_kids_pets_30d":     "kids_pets",
    "cat_spend_ratio_misc_net_30d":      "misc_net",
    "cat_spend_ratio_other_30d":         "other",
    "cat_spend_ratio_shopping_pos_30d":  "shopping_pos",
    "cat_spend_ratio_shopping_net_30d":  "shopping_net",
}


def _to_dt(x) -> datetime | None:
    if isinstance(x, datetime):
        return x
    try:
        return pd.to_datetime(x).to_pydatetime()
    except Exception:
        return None


def build_features_from_transactions(
    transactions: list[dict],
    asof: datetime | None = None
) -> dict:
    """
    FINNUT normalized transactions → ML feature dict.
    모든 컬럼이 val.csv (학습 feature) 와 일치하도록 맞춤.
    """
    if not transactions:
        return {}

    # 유효 tx 필터링
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
            "dt":       dt,
            "amt":      amt,
            "category": (tx.get("category") or "other").lower().strip(),
        })

    if not txs:
        return {}

    asof = asof or max(t["dt"] for t in txs)

    w7  = asof - timedelta(days=7)
    w30 = asof - timedelta(days=30)

    amt_7  = [t["amt"] for t in txs if t["dt"] >= w7]
    amt_30 = [t["amt"] for t in txs if t["dt"] >= w30]

    days_7  = list({t["dt"].date() for t in txs if t["dt"] >= w7})
    days_30 = list({t["dt"].date() for t in txs if t["dt"] >= w30})

    # ── spend features (7d) ──
    spend_sum_7d  = float(sum(amt_7))
    spend_mean_7d = float(np.mean(amt_7))  if amt_7  else 0.0
    spend_std_7d  = float(np.std(amt_7))   if len(amt_7) > 1 else 0.0
    spend_max_7d  = float(max(amt_7))      if amt_7  else 0.0
    day_count_7d  = float(len(days_7))

    # ── spend features (30d) ──
    spend_sum_30d  = float(sum(amt_30))
    spend_mean_30d = float(np.mean(amt_30)) if amt_30 else 0.0
    spend_std_30d  = float(np.std(amt_30))  if len(amt_30) > 1 else 0.0
    spend_max_30d  = float(max(amt_30))     if amt_30 else 0.0
    day_count_30d  = float(len(days_30))

    # ── category ratio (30d) ──
    cat_sum: dict[str, float] = defaultdict(float)
    for t in txs:
        if t["dt"] >= w30:
            cat_sum[t["category"]] += t["amt"]
    total_30 = spend_sum_30d if spend_sum_30d > 0 else 1.0

    cat_ratios = {}
    for col, cat_key in CATEGORY_COLS.items():
        cat_ratios[col] = cat_sum.get(cat_key, 0.0) / total_30

    unique_category_count_30d = float(len(set(
        t["category"] for t in txs if t["dt"] >= w30
    )))

    features = {
        # 7d
        "spend_sum_7d":   spend_sum_7d,
        "spend_mean_7d":  spend_mean_7d,
        "spend_std_7d":   spend_std_7d,
        "spend_max_7d":   spend_max_7d,
        "day_count_7d":   day_count_7d,
        # 30d
        "spend_sum_30d":  spend_sum_30d,
        "spend_mean_30d": spend_mean_30d,
        "spend_std_30d":  spend_std_30d,
        "spend_max_30d":  spend_max_30d,
        "day_count_30d":  day_count_30d,
        # category
        "unique_category_count_30d": unique_category_count_30d,
        **cat_ratios,
    }

    return features