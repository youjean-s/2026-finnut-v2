import pandas as pd

NORMALIZED_PATH = "ml/data/processed/normalized.csv"
OUT_PATH = "ml/data/features/features_category_mix_30d.csv"

WINDOW_DAYS = 30

# 고정 카테고리 (새 카테고리 기준)
FIXED_CATS = [
    "convenience",
    "cafe",
    "food",
    "transport",
    "shopping",
    "housing",
    "entertainment",
    "subscription",
    # "other"는 나머지 전부 편입되므로 별도 지정 불필요
]


def main():
    df = pd.read_csv(NORMALIZED_PATH)

    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["user_id", "datetime", "amount"])
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df.dropna(subset=["amount"])
    df = df[df["amount"] > 0]

    df["category"] = df["category"].fillna("other").astype(str)

    # reference date (daily)
    df["date"] = df["datetime"].dt.date
    df["date"] = pd.to_datetime(df["date"])

    # 고정 카테고리 외 → other로 편입
    df["cat_bucket"] = df["category"].where(df["category"].isin(FIXED_CATS), other="other")

    # user-day로 집계
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

    # pivot
    pivot = merged.pivot_table(
        index=["user_id", "date"],
        columns="cat_bucket",
        values="cat_ratio",
        aggfunc="sum",
        fill_value=0.0
    ).reset_index()

    # 누락된 카테고리 컬럼 보정 (데이터에 없는 카테고리는 0으로 채움)
    all_cats = FIXED_CATS + ["other"]
    for cat in all_cats:
        if cat not in pivot.columns:
            pivot[cat] = 0.0

    # unique_category_count_30d
    daily_unique = (
        df.groupby(["user_id", "date"])["category"]
        .nunique()
        .reset_index()
        .rename(columns={"category": "unique_cat_count_day"})
    )
    daily_unique = daily_unique.sort_values(["user_id", "date"]).reset_index(drop=True)

    out_rows = []
    for uid, g in daily_unique.groupby("user_id"):
        g = g.sort_values("date").set_index("date")
        g[f"unique_category_count_{WINDOW_DAYS}d"] = (
            g["unique_cat_count_day"].rolling(f"{WINDOW_DAYS}D").sum()
        )
        g = g.reset_index()
        g["user_id"] = uid
        out_rows.append(g[["user_id", "date", f"unique_category_count_{WINDOW_DAYS}d"]])

    uniq_feat = pd.concat(out_rows, ignore_index=True).fillna(0.0)

    # merge pivot + unique
    feat = pivot.merge(uniq_feat, on=["user_id", "date"], how="left").fillna(0.0)

    # rename cat columns → cat_spend_ratio_{cat}_30d
    for c in all_cats:
        if c in feat.columns:
            feat.rename(columns={c: f"cat_spend_ratio_{c}_{WINDOW_DAYS}d"}, inplace=True)

    feat.to_csv(OUT_PATH, index=False)
    print(f"[OK] saved -> {OUT_PATH} (rows={len(feat)})")
    print("fixed categories:", all_cats)


if __name__ == "__main__":
    main()