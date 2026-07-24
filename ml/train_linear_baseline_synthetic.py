"""
ml/train_linear_baseline_synthetic.py
----------------------------------------
ml/train_lgbm_synthetic.py와 동일한 train/held_in/held_out(Set A) split로 선형회귀
(LinearRegression) baseline을 학습한다. LightGBM과 나중에 "baseline 대비 개선폭"을
비교하기 위한 준비 단계.

rule_predict()는 이 스크립트 어디에서도 import/호출하지 않는다 - 타겟은 오직 label_fhi
(= ideal_fhi()의 출력)이다.
"""
import os
import json

import joblib
from sklearn.linear_model import LinearRegression

from ml.train_lgbm_synthetic import (
    TRAIN_PATH, HELD_IN_PATH, HELD_OUT_PATH, _split_xy, _metrics,
)
import pandas as pd

MODEL_OUT = "ml/artifacts/models/linear_fhi_synthetic.joblib"
REPORT_OUT = "ml/artifacts/reports/synthetic_linear_report.json"


def main():
    train = pd.read_csv(TRAIN_PATH)
    held_in = pd.read_csv(HELD_IN_PATH)
    held_out = pd.read_csv(HELD_OUT_PATH)

    X_train, y_train = _split_xy(train)
    X_held_in, y_held_in = _split_xy(held_in)
    X_held_out, y_held_out = _split_xy(held_out)

    model = LinearRegression()
    model.fit(X_train, y_train)

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
    joblib.dump(model, MODEL_OUT)

    with open(REPORT_OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n[OK] Linear regression baseline trained on synthetic data (rule_predict 미사용)")
    print(f"  held_in      MAE={report['held_in']['mae']:.3f}  RMSE={report['held_in']['rmse']:.3f}")
    print(f"  held_out(A)  MAE={report['held_out_setA']['mae']:.3f}  RMSE={report['held_out_setA']['rmse']:.3f}")
    print(f"model  -> {MODEL_OUT}")
    print(f"report -> {REPORT_OUT}")


if __name__ == "__main__":
    main()
