"""
compare_rule_vs_ml_v2.py
------------------------
Rule-based FHI vs LightGBM FHI 비교 분석 (v2)

핵심 관점 변경:
- label_fhi = Rule 공식으로 만든 값이므로 Rule MAE는 항상 0
- 따라서 "정답 대비 오차" 비교가 아닌,
  "Rule이 과도하게 낮은/높은 점수를 주는 시나리오에서
   ML은 얼마나 다른 판단을 하는가"를 보여줌
- ideal_fhi를 별도 정의해서 셋을 비교

Usage:
    python ml/src/compare_rule_vs_ml_v2.py
"""

import json
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import mean_absolute_error

VAL_PATH   = "ml/data/features/val.csv"
MODEL_PATH = "ml/artifacts/models/lgbm_fhi_v2_grid_best.txt"
REPORT_OUT = "ml/artifacts/reports/rule_vs_ml_v2_report.json"

ALPHA = 30.0
NON_FEATURE_COLS = {"user_id", "date", "label_fhi"}


def rule_predict(df):
    base_7         = (df["spend_mean_30d"] * 7).clip(lower=1.0)
    spike_ratio    = ((df["spend_sum_7d"] - base_7) / base_7).fillna(0.0)
    positive_spike = spike_ratio.clip(lower=0.0)
    return (100.0 - ALPHA * positive_spike).clip(0.0, 100.0).values


def ideal_fhi(df):
    """
    Rule보다 정교한 '이상적 FHI' 정의:
    spike가 있어도 std가 낮으면(= 고정지출) 패널티 완화
    spike가 있어도 max만 크고 나머지 작으면(= 단발성) 패널티 완화
    점진적 증가(std 높음)는 추가 패널티

    이 값이 사람이 납득할 수 있는 "더 합리적인 FHI"
    """
    base_7      = (df["spend_mean_30d"] * 7).clip(lower=1.0)
    spike_ratio = ((df["spend_sum_7d"] - base_7) / base_7).fillna(0.0).clip(lower=0.0)
    std_ratio   = (df["spend_std_30d"] / df["spend_mean_30d"].clip(lower=1.0)).fillna(0.0)
    max_ratio   = (df["spend_max_7d"]  / df["spend_mean_30d"].clip(lower=1.0)).fillna(0.0)

    # 고정지출 완화: std 낮으면 spike 패널티 50% 감면
    fixed_discount = np.where(std_ratio < 0.3, 0.5, 1.0)

    # 단발성 완화: max가 크고 std도 낮으면 추가 감면
    event_discount = np.where((max_ratio > 3.0) & (std_ratio < 0.5), 0.6, 1.0)

    # 점진적 증가 추가 패널티
    gradual_penalty = np.where(
        (spike_ratio < 0.1) & (std_ratio > 0.5),
        5.0, 0.0
    )

    effective_spike = spike_ratio * fixed_discount * event_discount
    ideal = (100.0 - ALPHA * effective_spike - gradual_penalty).clip(0.0, 100.0)
    return ideal.values


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
    print("[1/4] 데이터 로드 중...")
    df = pd.read_csv(VAL_PATH)
    print(f"      val rows: {len(df):,}")

    print("[2/4] LightGBM 예측 중...")
    model     = lgb.Booster(model_file=MODEL_PATH)
    feat_cols = [c for c in df.columns if c not in NON_FEATURE_COLS]
    ml_pred   = np.clip(model.predict(df[feat_cols]), 0.0, 100.0)

    print("[3/4] Rule / Ideal FHI 계산 중...")
    df["rule_fhi"]  = rule_predict(df)
    df["ml_fhi"]    = ml_pred
    df["ideal_fhi"] = ideal_fhi(df)
    df = label_scenarios(df)

    # ── 전체: Rule vs ML vs Ideal 평균 비교 ──
    print("\n" + "="*55)
    print("  전체 평균 FHI 비교 (val set)")
    print("="*55)
    print(f"  Rule FHI  평균: {df['rule_fhi'].mean():.2f}")
    print(f"  ML FHI    평균: {df['ml_fhi'].mean():.2f}")
    print(f"  Ideal FHI 평균: {df['ideal_fhi'].mean():.2f}")

    # Ideal 기준 MAE
    rule_mae  = mean_absolute_error(df["ideal_fhi"], df["rule_fhi"])
    ml_mae    = mean_absolute_error(df["ideal_fhi"], df["ml_fhi"])
    print(f"\n  [Ideal 기준 MAE]")
    print(f"  Rule-based MAE : {rule_mae:.4f}")
    print(f"  LightGBM  MAE  : {ml_mae:.4f}")
    print(f"  ML 개선량      : {rule_mae - ml_mae:+.4f}")
    print("="*55)

    # ── 시나리오별 비교 ──
    print("\n[4/4] 시나리오별 분석...")
    print("\n" + "="*75)
    print("  시나리오별 평균 FHI & Ideal 기준 MAE")
    print("="*75)
    print(f"  {'시나리오':28s} {'n':>7}  {'Rule':>7}  {'ML':>7}  {'Ideal':>7}  {'R-MAE':>7}  {'ML-MAE':>7}")
    print("-"*75)

    scenario_results = {}
    for sc in ["normal", "s1_fixed_expense", "s2_event_spike", "s3_gradual_increase"]:
        mask = df["scenario"] == sc
        n    = mask.sum()
        if n == 0:
            continue
        sub      = df[mask]
        r_mean   = sub["rule_fhi"].mean()
        m_mean   = sub["ml_fhi"].mean()
        i_mean   = sub["ideal_fhi"].mean()
        r_mae    = mean_absolute_error(sub["ideal_fhi"], sub["rule_fhi"])
        m_mae    = mean_absolute_error(sub["ideal_fhi"], sub["ml_fhi"])
        flag     = "✓ ML 우세" if r_mae > m_mae else "  Rule 우세"
        print(f"  {sc:28s} {n:>7,}  {r_mean:>7.2f}  {m_mean:>7.2f}  {i_mean:>7.2f}  {r_mae:>7.4f}  {m_mae:>7.4f}  {flag}")
        scenario_results[sc] = {
            "n": int(n),
            "rule_fhi_mean":  round(r_mean, 2),
            "ml_fhi_mean":    round(m_mean, 2),
            "ideal_fhi_mean": round(i_mean, 2),
            "rule_mae_vs_ideal": round(r_mae, 4),
            "ml_mae_vs_ideal":   round(m_mae, 4),
            "ml_wins": bool(r_mae > m_mae)
        }

    print("="*75)
    print("\n※ 시나리오 설명")
    print("  s1_fixed_expense    : spike 있지만 변동 낮음 → Rule이 건강한 고정지출을 위험으로 오분류")
    print("  s2_event_spike      : 단발성 큰 지출 → Rule이 이벤트성 지출을 과도하게 패널티")
    print("  s3_gradual_increase : spike 없지만 변동 높음 → Rule이 점진적 위험 신호 미탐지")

    # ── 저장 ──
    report = {
        "overall": {
            "rule_mae_vs_ideal": round(rule_mae, 4),
            "ml_mae_vs_ideal":   round(ml_mae, 4),
            "mae_improvement":   round(rule_mae - ml_mae, 4)
        },
        "scenarios": scenario_results
    }
    with open(REPORT_OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n[완료] 결과 저장 → {REPORT_OUT}")


if __name__ == "__main__":
    main()