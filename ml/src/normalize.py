import os
import pandas as pd

# Kaggle fraud_detection 원본 category → FINNUT 새 카테고리 매핑
KAGGLE_CATEGORY_MAP = {
    # convenience (편의점·다이소)
    "grocery_pos":        "convenience",

    # food (식비)
    "food_dining":        "food",
    "food_grocery_net":   "food",

    # cafe (카페)
    # Kaggle 데이터엔 cafe 분리 없으므로 food_dining 일부는 food로 통합
    # 카페 분리가 필요하면 merchant 기반으로 category_rules.py 사용 권장

    # transport (교통)
    "gas_transport":      "transport",

    # shopping (쇼핑)
    "shopping_pos":       "shopping",
    "shopping_net":       "shopping",
    "personal_care":      "shopping",   # 뷰티 통합

    # housing (주거·공과금)
    "home":               "housing",
    "kids_pets":          "housing",    # 삭제 카테고리 → housing으로 편입

    # entertainment (문화·여가)
    "entertainment":      "entertainment",
    "travel":             "entertainment",

    # subscription (구독)
    "misc_net":           "subscription",

    # other (기타)
    "misc_pos":           "other",
    "health_fitness":     "other",
}

def normalize_raw_dataset(input_csv: str, output_csv: str, source_name: str) -> None:
    df = pd.read_csv(input_csv)

    # Candidate A: kartik2112/fraud_detection (credit card transactions)
    if source_name == "kaggle_fraud_detection":
        out = pd.DataFrame({
            "user_id":         df["cc_num"].astype(str),
            "datetime":        pd.to_datetime(df["trans_date_trans_time"], errors="coerce"),
            "amount":          pd.to_numeric(df["amt"], errors="coerce"),
            "merchant":        df["merchant"].astype(str),
            "category":        df["category"].astype(str).map(KAGGLE_CATEGORY_MAP).fillna("other"),
            "payment_method":  "card",
            "source":          source_name,
        })

    # Candidate B: retail transactional dataset
    elif source_name == "kaggle_retail_tx":
        dt = pd.to_datetime(
            df.get("datetime", df.get("date", "")), errors="coerce"
        )
        out = pd.DataFrame({
            "datetime":        dt,
            "amount":          pd.to_numeric(df.get("amount", df.get("total_amount")), errors="coerce"),
            "merchant":        df.get("product_brand", df.get("product_type", "")).astype(str),
            "category":        df.get("product_category", "").astype(str).map(KAGGLE_CATEGORY_MAP).fillna("other"),
            "payment_method":  df.get("payment_method", "unknown").astype(str),
            "source":          source_name,
        })
    else:
        raise ValueError(f"Unknown source_name: {source_name}")

    # basic cleaning
    out = out.dropna(subset=["datetime", "amount"])
    out = out[out["amount"] > 0]
    out.to_csv(output_csv, index=False)
    print(f"[OK] normalized saved -> {output_csv} (rows={len(out)})")


if __name__ == "__main__":
    raw = "ml/data/raw/transactions.csv"
    out = "ml/data/processed/normalized.csv"
    normalize_raw_dataset(raw, out, source_name="kaggle_fraud_detection")