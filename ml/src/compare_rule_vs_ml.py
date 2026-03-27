"""
compare_rule_vs_ml.py
---------------------
Rule-based FHI vs LightGBM FHI 비교 분석
- 전체 MAE/RMSE 비교
- 교수님 피드백: Rule이 실패하는 시나리오에서 ML이 더 잘 예측함을 보여줌

Usage:
    python ml/src/compare_rule_vs_ml.py
"""

import json
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import mean_absolute_error, mean_squared_error

# ── 경로 설정 ──────────────────────────────────────────────
VAL_PATH   = "ml/data/features/val.csv"
MODEL_PATH = "ml/artifacts/models/lgbm_fhi_v2_grid_best.txt"
REPORT_OUT = "ml/artifacts/reports/rule_vs_ml_report.json"

# make_labels.py 와 동일한 파라미터
ALPHA = 30.0

# Rule-based에서 제외할 non-feature 컬럼
NON_FEATURE_COLS = {"user_id", "date", "label_fhi"}


# ── 유틸 ───────────────────────────────────────────────────
def rule_predict(df: pd.DataFrame) -> np.ndarray:
    """make_labels.py 와 동일한 Rule-based FHI 계산."""
    base_7         = (df["spend_mean_30d"] * 7).clip(lower=1.0)
    spike_ratio    = ((df["spend_sum_7d"] - base_7) / base_7).fillna(0.0)
    positive_spike = spike_ratio.clip(lower=0.0)
    labels         = (100.0 - ALPHA * positive_spike).clip(0.0, 100.0)
    return labels.values


def get_feature_cols(df: pd.DataFrame) -> list:
    return [c for c in df.columns if c not in NON_FEATURE_COLS]


def rmse(y_true, y_pred):
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


# ── 시나리오 정의 ──────────────────────────────────────────
def label_scenarios(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rule-based가 실패하는 3가지 시나리오 레이블링.

    시나리오 1 – 고정 지출 과다 패널티
        : spend_sum_7d가 높지만 spend_std_30d가 낮음 (변동 없이 꾸준한 지출)
        Rule은 spike로 오해해서 FHI를 낮춤 → 실제론 건강한 소비

    시나리오 2 – 이벤트성 일시 급증
        : spend_max_7d가 spend_mean_30d 대비 매우 큼 (한 번의 큰 지출)
        Rule은 무조건 낮은 FHI → 평소 패턴은 정상

    시나리오 3 – 점진적 소비 증가 (Rule 미탐지)
        : spike_ratio 작지만 spend_std_30d가 높음
        Rule은 높은 점수 → 실제론 위험 신호
    """
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


# ── 메인 ───────────────────────────────────────────────────
def main():
    # 1. 데이터 로드
    print("[1/4] 데이터 로드 중...")
    df = pd.read_csv(VAL_PATH)
    print(f"      val rows: {len(df):,}")

    # 2. 모델 로드 & ML 예측
    print("[2/4] LightGBM 예측 중...")
    model     = lgb.Booster(model_file=MODEL_PATH)
    feat_cols = get_feature_cols(df)
    ml_pred   = model.predict(df[feat_cols])
    ml_pred   = np.clip(ml_pred, 0.0, 100.0)

    # 3. Rule 예측
    print("[3/4] Rule-based 예측 중...")
    rule_pred = rule_predict(df)
    y_true    = df["label_fhi"].values

    # ── 전체 성능 비교 ──
    rule_mae    = mean_absolute_error(y_true, rule_pred)
    ml_mae      = mean_absolute_error(y_true, ml_pred)
    rule_rmse   = rmse(y_true, rule_pred)
    ml_rmse_val = rmse(y_true, ml_pred)

    print("\n" + "="*50)
    print("  전체 성능 비교 (val set)")
    print("="*50)
    print(f"  {'':20s} {'MAE':>8}  {'RMSE':>8}")
    print(f"  {'Rule-based':20s} {rule_mae:>8.4f}  {rule_rmse:>8.4f}")
    print(f"  {'LightGBM':20s} {ml_mae:>8.4f}  {ml_rmse_val:>8.4f}")
    print(f"  {'MAE 개선량':20s} {rule_mae - ml_mae:>+8.4f}")
    print("="*50)

    # ── 시나리오별 비교 ──
    print("\n[4/4] 시나리오별 분석 중...")
    df["rule_pred"] = rule_pred
    df["ml_pred"]   = ml_pred
    df = label_scenarios(df)

    scenario_results = {}
    print("\n" + "="*65)
    print("  시나리오별 MAE 비교")
    print("="*65)
    print(f"  {'시나리오':30s} {'n':>7}  {'Rule MAE':>9}  {'ML MAE':>9}  {'ML 우위':>8}")
    print("-"*65)

    for sc in ["normal", "s1_fixed_expense", "s2_event_spike", "s3_gradual_increase"]:
        mask = df["scenario"] == sc
        n    = mask.sum()
        if n == 0:
            continue
        r_mae = mean_absolute_error(df.loc[mask, "label_fhi"], df.loc[mask, "rule_pred"])
        m_mae = mean_absolute_error(df.loc[mask, "label_fhi"], df.loc[mask, "ml_pred"])
        delta = r_mae - m_mae
        flag  = "✓ ML 우세" if delta > 0 else "  Rule 우세"
        print(f"  {sc:30s} {n:>7,}  {r_mae:>9.4f}  {m_mae:>9.4f}  {delta:>+7.4f} {flag}")
        scenario_results[sc] = {
            "n": int(n),
            "rule_mae": round(r_mae, 4),
            "ml_mae":   round(m_mae, 4),
            "delta_mae": round(delta, 4)
        }

    print("="*65)
    print("\n※ 시나리오 설명")
    print("  s1_fixed_expense    : Rule이 건강한 고정지출을 위험으로 오분류")
    print("  s2_event_spike      : Rule이 이벤트성 지출을 과도하게 패널티")
    print("  s3_gradual_increase : Rule이 점진적 위험 신호를 미탐지")

    # ── 결과 저장 ──
    report = {
        "overall": {
            "rule_mae":       round(rule_mae, 4),
            "rule_rmse":      round(rule_rmse, 4),
            "ml_mae":         round(ml_mae, 4),
            "ml_rmse":        round(ml_rmse_val, 4),
            "mae_improvement": round(rule_mae - ml_mae, 4)
        },
        "scenarios": scenario_results
    }
    with open(REPORT_OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n[완료] 결과 저장 → {REPORT_OUT}")


if __name__ == "__main__":
    main()