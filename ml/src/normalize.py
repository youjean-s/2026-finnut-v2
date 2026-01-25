import os
import pandas as pd

# FINNUT normalized schema:
# datetime, amount, merchant, category, payment_method, source

def normalize_raw_dataset(input_csv: str, output_csv: str, source_name: str) -> None:
    df = pd.read_csv(input_csv)

   # Candidate A: kartik2112/fraud_detection (credit card transactions)
    if source_name == "kaggle_fraud_detection":
        # expected columns:
        # cc_num, trans_date_trans_time, merchant, category, amt
        out = pd.DataFrame({
        "user_id": df["cc_num"].astype(str),  # ✅ 여기로 와야 함
        "datetime": pd.to_datetime(df["trans_date_trans_time"], errors="coerce"),
        "amount": pd.to_numeric(df["amt"], errors="coerce"),
        "merchant": df["merchant"].astype(str),
        "category": df["category"].astype(str),
        "payment_method": "card",
        "source": source_name,
    })


    # Candidate B: retail transactional dataset (example)
    elif source_name == "kaggle_retail_tx":
        # expected columns:
        # datetime, amount, merchant, category, payment_method, source
        out = pd.DataFrame({
            "datetime": pd.to_datetime(dt, errors="coerce"),
            "amount": pd.to_numeric(df.get("amount", df.get("total_amount")), errors="coerce"),
            "merchant": df.get("product_brand", df.get("product_type", "")).astype(str),
            "category": df.get("product_category", "").astype(str),
            "payment_method": df.get("payment_method", "unknown").astype(str),
            "source": source_name,
        })
    else:
        raise ValueError(f"Unknown source_name: {source_name}")

    # basic cleaning
    out = out.dropna(subset=["datetime", "amount"])
    out = out[out["amount"] > 0]
    out.to_csv(output_csv, index=False)
    print(f"[OK] normalized saved -> {output_csv} (rows={len(out)})")


if __name__ == "__main__":
    # Example usage:
    # python ml/src/normalize.py
    raw = "ml/data/raw/transactions.csv"
    out = "ml/data/processed/normalized.csv"
    normalize_raw_dataset(raw, out, source_name="kaggle_fraud_detection")
