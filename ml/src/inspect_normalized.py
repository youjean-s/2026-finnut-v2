import pandas as pd

NORMALIZED_PATH = "ml/data/processed/normalized.csv"

def main():
    df = pd.read_csv(NORMALIZED_PATH)

    print("== Basic Info ==")
    print("rows:", len(df))
    print("cols:", list(df.columns))

    # datetime parse + sort
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["datetime", "amount"])

    # amount numeric + positive
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df.dropna(subset=["amount"])
    df = df[df["amount"] > 0]

    df = df.sort_values("datetime").reset_index(drop=True)

    print("\n== After Cleaning ==")
    print("rows:", len(df))
    print("datetime min:", df["datetime"].min())
    print("datetime max:", df["datetime"].max())
    print("amount min:", df["amount"].min())
    print("amount max:", df["amount"].max())

    print("\n== Sample 5 rows ==")
    print(df[["datetime", "amount", "merchant", "category", "payment_method", "source"]].head(5))

    # save cleaned overwrite (선택: 덮어쓰기)
    df.to_csv(NORMALIZED_PATH, index=False)
    print(f"\n[OK] cleaned overwrite -> {NORMALIZED_PATH}")

if __name__ == "__main__":
    main()
