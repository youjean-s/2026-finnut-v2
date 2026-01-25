import pandas as pd

NORMALIZED_PATH = "ml/data/processed/normalized.csv"
FEATURES_OUT = "ml/data/features/features_basic.csv"

WINDOWS = [7, 30]  # days


def main():
    df = pd.read_csv(NORMALIZED_PATH)

    # parse datetime
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["user_id", "datetime", "amount"])
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df.dropna(subset=["amount"])
    df = df[df["amount"] > 0]

    # date bucket (daily)
    df["date"] = df["datetime"].dt.date

    # daily spend per user (reduce size)
    daily = (
        df.groupby(["user_id", "date"], as_index=False)["amount"]
        .sum()
        .rename(columns={"amount": "daily_spend"})
    )

    # per user rolling features
    daily["date"] = pd.to_datetime(daily["date"])
    daily = daily.sort_values(["user_id", "date"]).reset_index(drop=True)

    rows = []
    for uid, g in daily.groupby("user_id"):
        g = g.sort_values("date").reset_index(drop=True)
        g = g.set_index("date")

        for w in WINDOWS:
            # rolling window sum/mean/std/max/count on daily_spend
            roll = g["daily_spend"].rolling(f"{w}D")

            g[f"spend_sum_{w}d"] = roll.sum()
            g[f"spend_mean_{w}d"] = roll.mean()
            g[f"spend_std_{w}d"] = roll.std().fillna(0.0)
            g[f"spend_max_{w}d"] = roll.max()
            g[f"day_count_{w}d"] = roll.count()

        # keep final daily feature rows
        g = g.reset_index()
        g["user_id"] = uid
        rows.append(g)

    feat = pd.concat(rows, ignore_index=True)

    # select output columns
    keep_cols = ["user_id", "date"] + [c for c in feat.columns if c.startswith(("spend_", "day_count_"))]
    feat = feat[keep_cols].dropna()

    feat.to_csv(FEATURES_OUT, index=False)
    print(f"[OK] saved -> {FEATURES_OUT} (rows={len(feat)})")
    print("columns:", feat.columns.tolist()[:20])


if __name__ == "__main__":
    main()
