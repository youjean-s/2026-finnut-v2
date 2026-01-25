import pandas as pd

NORMALIZED_PATH = "ml/data/processed/normalized.csv"
OUT_PATH = "ml/data/features/features_category_mix_30d.csv"

TOP_K = 8   # 상위 카테고리 K개만 ratio feature로 만든다
WINDOW_DAYS = 30


def main():
    df = pd.read_csv(NORMALIZED_PATH)

    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["user_id", "datetime", "amount"])
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df.dropna(subset=["amount"])
    df = df[df["amount"] > 0]

    # category normalize
    df["category"] = df["category"].fillna("unknown").astype(str)

    # reference date (daily)
    df["date"] = df["datetime"].dt.date
    df["date"] = pd.to_datetime(df["date"])

    # 전체에서 상위 TOP_K 카테고리 뽑기(전체 spending 기준)
    top_cats = (
        df.groupby("category")["amount"].sum().sort_values(ascending=False).head(TOP_K).index.tolist()
    )

    # top_k 외는 기타로 묶기
    df["cat_bucket"] = df["category"].where(df["category"].isin(top_cats), other="other")

    # user-day로 먼저 집계 (속도)
    daily_cat = (
        df.groupby(["user_id", "date", "cat_bucket"], as_index=False)["amount"]
        .sum()
        .rename(columns={"amount": "cat_spend"})
    )

    # total daily spend (for ratio)
    daily_total = (
        df.groupby(["user_id", "date"], as_index=False)["amount"]
        .sum()
        .rename(columns={"amount": "daily_total"})
    )

    # merge
    merged = daily_cat.merge(daily_total, on=["user_id", "date"], how="left")
    merged["cat_ratio"] = merged["cat_spend"] / merged["daily_total"].clip(lower=1.0)

    # pivot: user_id, date, cat_ratio_{cat}
    pivot = merged.pivot_table(
        index=["user_id", "date"],
        columns="cat_bucket",
        values="cat_ratio",
        aggfunc="sum",
        fill_value=0.0
    ).reset_index()

    # unique_category_count_30d: window 내 등장 카테고리 수
    # -> 원본 df에서 user-date별 고유 cat 개수 집계 후 rolling count(유니크는 근사: window 안에서 date별 unique 합으로)
    daily_unique = (
        df.groupby(["user_id", "date"])["category"]
        .nunique()
        .reset_index()
        .rename(columns={"category": "unique_cat_count_day"})
    )
    daily_unique = daily_unique.sort_values(["user_id", "date"]).reset_index(drop=True)

    # rolling(30D) sum as proxy for diversity (근사치)
    out_rows = []
    for uid, g in daily_unique.groupby("user_id"):
        g = g.sort_values("date").set_index("date")
        g[f"unique_category_count_{WINDOW_DAYS}d"] = g["unique_cat_count_day"].rolling(f"{WINDOW_DAYS}D").sum()
        g = g.reset_index()
        g["user_id"] = uid
        out_rows.append(g[["user_id", "date", f"unique_category_count_{WINDOW_DAYS}d"]])

    uniq_feat = pd.concat(out_rows, ignore_index=True).fillna(0.0)

    # merge pivot + unique
    feat = pivot.merge(uniq_feat, on=["user_id", "date"], how="left").fillna(0.0)

    # rename cat columns
    for c in list(feat.columns):
        if c not in ["user_id", "date", f"unique_category_count_{WINDOW_DAYS}d"]:
            feat.rename(columns={c: f"cat_spend_ratio_{c}_{WINDOW_DAYS}d"}, inplace=True)

    feat.to_csv(OUT_PATH, index=False)
    print(f"[OK] saved -> {OUT_PATH} (rows={len(feat)})")
    print("top categories:", top_cats)


if __name__ == "__main__":
    main()
