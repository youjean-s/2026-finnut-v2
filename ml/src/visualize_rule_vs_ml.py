"""
visualize_rule_vs_ml.py
-----------------------
Rule-based vs LightGBM FHI 비교 시각화

Usage:
    python ml/src/visualize_rule_vs_ml.py
"""

import numpy as np
import pandas as pd
import lightgbm as lgb
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import rcParams

# 한글 폰트 설정
rcParams['font.family'] = 'Malgun Gothic'
rcParams['axes.unicode_minus'] = False

VAL_PATH   = "ml/data/features/val.csv"
MODEL_PATH = "ml/artifacts/models/lgbm_fhi_v2_grid_best.txt"
OUT_DIR    = "ml/artifacts/reports/"

ALPHA = 30.0
NON_FEATURE_COLS = {"user_id", "date", "label_fhi"}


def rule_predict(df):
    base_7         = (df["spend_mean_30d"] * 7).clip(lower=1.0)
    spike_ratio    = ((df["spend_sum_7d"] - base_7) / base_7).fillna(0.0)
    positive_spike = spike_ratio.clip(lower=0.0)
    return (100.0 - ALPHA * positive_spike).clip(0.0, 100.0).values


def label_scenarios(df):
    df = df.copy()
    base_7      = (df["spend_mean_30d"] * 7).clip(lower=1.0)
    spike_ratio = ((df["spend_sum_7d"] - base_7) / base_7).fillna(0.0)
    std_ratio   = (df["spend_std_30d"] / df["spend_mean_30d"].clip(lower=1.0)).fillna(0.0)
    max_ratio   = (df["spend_max_7d"]  / df["spend_mean_30d"].clip(lower=1.0)).fillna(0.0)

    s1 = (spike_ratio > 0.1) & (std_ratio < 0.3)
    s2 = (max_ratio > 3.0) & (~s1)
    s3 = (spike_ratio.abs() < 0.1) & (std_ratio > 0.5) & (~s1) & (~s2)

    df["scenario"] = "normal"
    df.loc[s1, "scenario"] = "s1_fixed_expense"
    df.loc[s2, "scenario"] = "s2_event_spike"
    df.loc[s3, "scenario"] = "s3_gradual_increase"
    return df


def main():
    # ── 데이터 준비 ──
    df        = pd.read_csv(VAL_PATH)
    model     = lgb.Booster(model_file=MODEL_PATH)
    feat_cols = [c for c in df.columns if c not in NON_FEATURE_COLS]

    df["rule_fhi"] = rule_predict(df)
    df["ml_fhi"]   = np.clip(model.predict(df[feat_cols]), 0.0, 100.0)
    df             = label_scenarios(df)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Rule-based vs LightGBM FHI 비교 분석", fontsize=16, fontweight="bold", y=1.01)

    colors = {"rule_fhi": "#E07B39", "ml_fhi": "#4A90D9"}

    # ── 그래프 1: 시나리오별 평균 FHI 비교 (Bar chart) ──
    ax1 = axes[0, 0]
    sc_labels = {
        "normal":             "일반",
        "s1_fixed_expense":   "고정지출\n(S1)",
        "s2_event_spike":     "이벤트성\n급증 (S2)",
        "s3_gradual_increase":"점진적\n증가 (S3)"
    }
    sc_order = ["normal", "s1_fixed_expense", "s2_event_spike", "s3_gradual_increase"]
    sc_order = [s for s in sc_order if (df["scenario"] == s).sum() > 0]

    x      = np.arange(len(sc_order))
    width  = 0.35
    rule_means = [df[df["scenario"] == s]["rule_fhi"].mean() for s in sc_order]
    ml_means   = [df[df["scenario"] == s]["ml_fhi"].mean()   for s in sc_order]

    bars1 = ax1.bar(x - width/2, rule_means, width, label="Rule-based", color=colors["rule_fhi"], alpha=0.85)
    bars2 = ax1.bar(x + width/2, ml_means,   width, label="LightGBM",   color=colors["ml_fhi"],   alpha=0.85)

    for bar in bars1:
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                 f"{bar.get_height():.1f}", ha="center", va="bottom", fontsize=8)
    for bar in bars2:
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                 f"{bar.get_height():.1f}", ha="center", va="bottom", fontsize=8)

    ax1.set_xticks(x)
    ax1.set_xticklabels([sc_labels[s] for s in sc_order], fontsize=9)
    ax1.set_ylim(80, 105)
    ax1.set_ylabel("평균 FHI 점수")
    ax1.set_title("① 시나리오별 평균 FHI 비교")
    ax1.legend()
    ax1.grid(axis="y", linestyle="--", alpha=0.4)

    # ── 그래프 2: FHI 분포 비교 (Histogram) ──
    ax2 = axes[0, 1]
    ax2.hist(df["rule_fhi"], bins=50, alpha=0.6, color=colors["rule_fhi"], label="Rule-based", density=True)
    ax2.hist(df["ml_fhi"],   bins=50, alpha=0.6, color=colors["ml_fhi"],   label="LightGBM",   density=True)
    ax2.axvline(df["rule_fhi"].mean(), color=colors["rule_fhi"], linestyle="--", linewidth=1.5,
                label=f"Rule 평균 {df['rule_fhi'].mean():.1f}")
    ax2.axvline(df["ml_fhi"].mean(),   color=colors["ml_fhi"],   linestyle="--", linewidth=1.5,
                label=f"ML 평균 {df['ml_fhi'].mean():.1f}")
    ax2.set_xlabel("FHI 점수")
    ax2.set_ylabel("밀도")
    ax2.set_title("② 전체 FHI 점수 분포")
    ax2.legend(fontsize=8)
    ax2.grid(linestyle="--", alpha=0.4)

    # ── 그래프 3: Rule이 과도하게 낮은 케이스 (S2 이벤트성 급증) ──
    ax3 = axes[1, 0]
    s2_df = df[df["scenario"] == "s2_event_spike"].copy()

    if len(s2_df) > 0:
        # Rule FHI - ML FHI 차이: 양수면 Rule이 더 낮게 줌
        s2_df["diff"] = s2_df["rule_fhi"] - s2_df["ml_fhi"]
        s2_sample = s2_df.sample(min(500, len(s2_df)), random_state=42)

        sc = ax3.scatter(
            s2_sample["spend_max_7d"] / s2_sample["spend_mean_30d"].clip(lower=1),
            s2_sample["diff"],
            c=s2_sample["diff"],
            cmap="RdYlGn", alpha=0.5, s=15
        )
        plt.colorbar(sc, ax=ax3, label="Rule - ML FHI 차이")
        ax3.axhline(0, color="black", linestyle="--", linewidth=1)
        ax3.set_xlabel("단발 지출 크기 (max_7d / mean_30d)")
        ax3.set_ylabel("Rule FHI - ML FHI")
        ax3.set_title("③ 이벤트성 급증 시나리오\nRule이 낮게 줄수록 위 (+), ML이 낮게 줄수록 아래 (-)")
        ax3.grid(linestyle="--", alpha=0.4)
    else:
        ax3.text(0.5, 0.5, "S2 데이터 없음", ha="center", va="center", transform=ax3.transAxes)
        ax3.set_title("③ 이벤트성 급증 시나리오")

    # ── 그래프 4: Feature Importance (Rule vs ML 사용 변수 비교) ──
    ax4 = axes[1, 1]
    try:
        fi = pd.read_csv("ml/artifacts/reports/feature_importance.csv")
        fi = fi.sort_values("importance", ascending=False).head(10)

        # Rule이 쓰는 변수 강조
        rule_vars = {"spend_sum_7d", "spend_mean_30d"}
        bar_colors = ["#E07B39" if f in rule_vars else "#4A90D9" for f in fi["feature"]]

        ax4.barh(fi["feature"][::-1], fi["importance"][::-1] / 1e6, color=bar_colors[::-1], alpha=0.85)
        ax4.set_xlabel("Feature Importance (×10⁶)")
        ax4.set_title("④ LightGBM Feature Importance\n(주황=Rule도 사용, 파랑=ML만 사용)")

        rule_patch = mpatches.Patch(color="#E07B39", label="Rule-based도 사용하는 변수")
        ml_patch   = mpatches.Patch(color="#4A90D9", label="ML만 추가 학습한 변수")
        ax4.legend(handles=[rule_patch, ml_patch], fontsize=8)
        ax4.grid(axis="x", linestyle="--", alpha=0.4)
    except Exception as e:
        ax4.text(0.5, 0.5, f"FI 로드 실패\n{e}", ha="center", va="center", transform=ax4.transAxes)

    plt.tight_layout()
    out_path = OUT_DIR + "rule_vs_ml_visualization.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"[완료] 저장 → {out_path}")
    plt.show()


if __name__ == "__main__":
    main()