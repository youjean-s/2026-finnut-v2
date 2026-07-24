"""
ml/train_lgbm_synthetic.py
----------------------------
ml/split_synthetic_data.py로 나눈 train/held_in/held_out(Set A)로 LightGBM 회귀 모델을
학습한다. 타겟은 label_fhi(= ideal_fhi()의 출력)뿐이다.

rule_predict()는 이 스크립트 어디에서도 import/호출하지 않는다 (ml/label_data.py와 동일한
원칙 - label_fhi 자체가 rule_predict와 무관하게 ideal_fhi()로만 만들어졌으므로, 학습도
그 라벨만 타겟으로 한다).
"""
import os
import json

import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import mean_absolute_error, mean_squared_error

TRAIN_PATH = "ml/data/features/synthetic_train.csv"
HELD_IN_PATH = "ml/data/features/synthetic_held_in.csv"
HELD_OUT_PATH = "ml/data/features/synthetic_held_out_setA.csv"

MODEL_OUT = "ml/artifacts/models/lgbm_fhi_synthetic.txt"
REPORT_OUT = "ml/artifacts/reports/synthetic_lgbm_report.json"
FI_OUT = "ml/artifacts/reports/synthetic_lgbm_feature_importance.csv"

TARGET = "label_fhi"
# housing_type은 label_data.py가 참고용으로 붙인 컬럼이라 feature에서 제외.
NON_FEATURE_COLS = ["user_id", "date", "label_fhi", "housing_type"]


def _split_xy(df: pd.DataFrame):
    y = df[TARGET].astype(float)
    X = df.drop(columns=[c for c in NON_FEATURE_COLS if c in df.columns])
    X = X.apply(pd.to_numeric, errors="coerce").fillna(0.0)
    return X, y


def _metrics(y_true, y_pred) -> dict:
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
    }


def main():
    train = pd.read_csv(TRAIN_PATH)
    held_in = pd.read_csv(HELD_IN_PATH)
    held_out = pd.read_csv(HELD_OUT_PATH)

    X_train, y_train = _split_xy(train)
    X_held_in, y_held_in = _split_xy(held_in)
    X_held_out, y_held_out = _split_xy(held_out)

    model = lgb.LGBMRegressor(
        n_estimators=600,
        learning_rate=0.05,
        num_leaves=63,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_held_in, y_held_in)],
        eval_metric="l1",
        callbacks=[lgb.log_evaluation(period=50)],
    )

    held_in_pred = model.predict(X_held_in)
    held_out_pred = model.predict(X_held_out)

    report = {
        "n_train_rows": int(len(X_train)),
        "n_held_in_rows": int(len(X_held_in)),
        "n_held_out_rows": int(len(X_held_out)),
        "n_features": int(X_train.shape[1]),
        "held_in": _metrics(y_held_in, held_in_pred),
        "held_out_setA": _metrics(y_held_out, held_out_pred),
    }

    os.makedirs(os.path.dirname(MODEL_OUT), exist_ok=True)
    os.makedirs(os.path.dirname(REPORT_OUT), exist_ok=True)
    model.booster_.save_model(MODEL_OUT)

    fi = pd.DataFrame({
        "feature": X_train.columns,
        "importance": model.booster_.feature_importance(importance_type="gain"),
    }).sort_values("importance", ascending=False)
    fi.to_csv(FI_OUT, index=False)

    with open(REPORT_OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n[OK] LightGBM trained on synthetic data (rule_predict 미사용, label_fhi만 타겟)")
    print(f"  held_in      MAE={report['held_in']['mae']:.3f}  RMSE={report['held_in']['rmse']:.3f}")
    print(f"  held_out(A)  MAE={report['held_out_setA']['mae']:.3f}  RMSE={report['held_out_setA']['rmse']:.3f}")
    print(f"model  -> {MODEL_OUT}")
    print(f"report -> {REPORT_OUT}")
    print(f"feature importance -> {FI_OUT}")


if __name__ == "__main__":
    main()
