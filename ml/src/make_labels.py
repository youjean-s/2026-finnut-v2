import pandas as pd

IN_PATH = "ml/data/features/features.csv"
OUT_PATH = "ml/data/features/features_labeled.csv"

def clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))

def main():
    df = pd.read_csv(IN_PATH)

    # label = rule-based proxy (no ground truth)
    # 간단 proxy:
    # - spend_trend: spend_sum_7d vs spend_sum_30d (ratio)
    # - night/small/repeat 같은 건 아직 features에 없으니 우선 spend 패턴 기반으로만 시작
    # label_fhi = 100 - (alpha * positive_spike)
    # positive_spike = max(0, (spend_sum_7d - spend_mean_30d*7) / (spend_mean_30d*7))
    alpha = 30.0  # penalty scale (tunable)

    # ensure needed columns exist
    required = ["spend_sum_7d", "spend_mean_30d"]
    for c in required:
        if c not in df.columns:
            raise ValueError(f"Missing column: {c}")

    base_7 = (df["spend_mean_30d"] * 7).clip(lower=1.0)
    spike_ratio = (df["spend_sum_7d"] - base_7) / base_7
    spike_ratio = spike_ratio.fillna(0.0)

    positive_spike = spike_ratio.clip(lower=0.0)

    label = 100.0 - alpha * positive_spike
    df["label_fhi"] = label.apply(lambda x: clamp(float(x), 0.0, 100.0))

    df.to_csv(OUT_PATH, index=False)
    print(f"[OK] saved -> {OUT_PATH} (rows={len(df)})")
    print("label_fhi stats:", df["label_fhi"].describe())

if __name__ == "__main__":
    main()
