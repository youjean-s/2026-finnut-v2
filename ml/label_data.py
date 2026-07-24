"""
ml/label_data.py
------------------
ml/data_generator.py 로 만든 합성 거래 데이터에 ideal_fhi() 라벨(label_fhi)을 붙이는 스크립트.

[입력 형식 확인 결과]
ideal_fhi(df) (ml/src/compare_rule_vs_ml_v2.py)가 실제로 요구하는 건 "카테고리별 월 합계"도
"개별 거래"도 아니라, 유저 단위 rolling-window 집계 feature다:
    spend_mean_30d, spend_sum_7d, spend_std_30d, spend_max_7d
즉 data_generator의 개별 거래 리스트(tx_datetime/amount/merchant/category)를 바로 넣을 수 없고,
아래 변환이 필요하다:
    1) data_generator 거래 -> ml_runtime.feature_builder.build_features_from_transactions()로
       유저 x 기준일(asof) 단위 7일/30일 rolling feature 생성 (val.csv와 동일 스키마,
       카테고리 비율(cat_spend_ratio_*_30d)까지 이 함수가 같이 만들어준다)
    2) 그 feature DataFrame에 ideal_fhi(df)를 적용해 label_fhi 컬럼 추가

[중요 - 미래 데이터 누수 방지]
build_features_from_transactions()는 dt >= (asof - window) 하한만 체크하고 dt <= asof 상한을
체크하지 않는다. 유저의 전체 기간 거래를 통째로 넘기면 아직 오지 않은 미래 달의 거래까지
7일/30일 윈도우에 새어 들어가 spend_sum_7d가 비정상적으로 커지고 label_fhi가 0에 수렴하는
문제가 실제로 있었다 (원인 분석: 30명x3개월 생성 후 1~2월 라벨이 전부 0에 가깝게 나와서
유저 1/2를 직접 찍어봤더니, 미래 달 거래가 새어 들어가서 spend_sum_7d가 실제 7일치의
10~30배로 부풀어 있었음). 그래서 generate_labeled_features()는 매달 asof를 넘기기 전에
반드시 그 시점 이하(dt <= asof)로 직접 잘라서 넘긴다.

[asof 다중 체크포인트 - 근거 태깅]
처음엔 매달 말일 하루만 asof로 썼는데, rent 결제일(월 25일 근처)이 "말일 기준 최근 7일 창"에
거의 항상 걸려서 렌트 내는 유저가 매달 습관적으로 저점을 받는 부작용이 있었다. asof를
말일 하나가 아니라 주 단위 다중 체크포인트(7/14/21일 + 월말)로 늘리면, 한 달 안에서도
"고정비 결제 직후 주" 외의 시점들이 같이 잡혀서 이 쏠림이 완화되는지 확인하려는 것.
ASOF_CHECKPOINT_SOURCE에 근거를 태깅한다 (CATEGORY_WEIGHT_SOURCE와 동일한 방식):
- rank_basis  : 실사용자가 월말 딱 한 번이 아니라 한 달 중 여러 시점에 확인한다는 방향성
- value_basis : 정확히 7/14/21일 + 월말이라는 간격 자체

[KNOWN LIMITATION - 월말 체크포인트 편향]
4개 체크포인트(7/14/21일 + 월말) 중 "월말" 체크포인트는 고정 rent 결제일(23~27일, 자세한
근거는 data_generator.py의 TIMING_PATTERN_SOURCE["rent_billing_day"] 참고)과 구조적으로
겹친다. rent를 내는 유저(off_campus/dorm)는 월말 체크포인트에서 거의 매번 "최근 7일 급증"으로
잡혀 label_fhi가 낮게 나오고, 이게 전체 저점(label_fhi<10) 비율(30명x3개월x4시점=360행 중
26%)의 일부를 구성한다 - 즉 이 26%는 전부 "진짜 위험 신호"가 아니라 일부가 체크포인트 설계
아티팩트다. 30명x3개월x1체크포인트(월말만) 실험에서는 저점 비율이 52%까지 올라갔던 것과
비교하면, 체크포인트를 늘린 게 완화 효과는 있었지만 완전히 없애지는 못했다.

해결 타임라인 (3단계):
  1) 지금은 여기 문서화만 하고 다음 단계(LightGBM 재학습)로 넘어간다. 코드 수정 없음.
  2) LightGBM 재학습 결과에서 이 편향이 실질적 영향을 준다는 신호가 보이면(예: housing_type이
     off_campus/dorm인 행에서만 오차가 특정 방향으로 치우치는 등) 그때 재검토한다.
  3) 최종적으로 실사용자 데이터(10명)를 확보하면, 실제 사용자들이 앱을 확인하는 시점 분포를
     보고 체크포인트 설계(현재 7/14/21일+월말)를 재조정한다. ASOF_CHECKPOINT_SOURCE의
     value_basis: ASSUMED 항목이 이때 우선 보정 대상이다.

[rule_predict 관련 - 중요]
rule_predict()는 ideal_fhi()와 같은 파일(ml/src/compare_rule_vs_ml_v2.py)에 있지만,
이 스크립트는 ideal_fhi 함수 하나만 import한다. rule_predict()는 이 스크립트 어디에서도
호출/사용하지 않는다 (grep으로 재확인: rule_predict()는 ml/src/compare_rule_vs_ml.py,
compare_rule_vs_ml_v2.py, visualize_rule_vs_ml.py 세 곳의 자체 main()/스크립트 본문에서만
호출되고, 그 외에는 정의조차 없음 - 이 라벨링 파이프라인과는 무관).
label_fhi는 오직 ideal_fhi()의 출력이다.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd

from ml.data_generator import StudentSpendingGenerator, _add_months
from ml.ml_runtime.feature_builder import build_features_from_transactions
# rule_predict는 절대 import하지 않는다 (아래에서도 호출하지 않음).
from ml.src.compare_rule_vs_ml_v2 import ideal_fhi

FEATURES_OUT = "ml/data/features/synthetic_labeled.csv"

# asof 다중 체크포인트 근거 태깅 (CATEGORY_WEIGHT_SOURCE / TIMING_PATTERN_SOURCE와 동일한 방식).
ASOF_CHECKPOINT_SOURCE: Dict[str, dict] = {
    "weekly_checkpoints": {
        "checkpoint_days": [7, 14, 21, "month_end"],
        "rank_basis": "SOURCED_PARTIAL",
        "value_basis": "ASSUMED",
        "note": (
            "실사용자가 월말 한 번이 아니라 한 달 중 여러 시점에 앱을 열어 FHI를 확인한다는 "
            "방향성은 타당해서 SOURCED_PARTIAL. 정확히 7/14/21일 + 월말이라는 간격 자체는 "
            "FINNUT이 임의로 설정한 값으로 ASSUMED."
        ),
        "citation": [],
    },
}


def _to_feature_builder_input(tx: dict) -> dict:
    """data_generator 출력 스키마(tx_datetime) -> build_features_from_transactions 입력 스키마(datetime)."""
    return {"datetime": tx["tx_datetime"], "amount": tx["amount"], "category": tx["category"]}


def _month_checkpoint_days(start_date: datetime, month_index: int) -> List[int]:
    """month_index번째 달의 체크포인트 일자 목록: 7/14/21일 + 그 달의 마지막 날."""
    month_start = _add_months(start_date, month_index)
    next_month_start = _add_months(start_date, month_index + 1)
    days_in_month = (next_month_start - month_start).days
    return [7, 14, 21, days_in_month]


def _checkpoint_asof(start_date: datetime, month_index: int, day_number: int) -> datetime:
    """month_index번째 달의 day_number일 마지막 순간(23:59:59)을 기준일(asof)로 반환."""
    month_start = _add_months(start_date, month_index)
    return month_start + timedelta(days=day_number) - timedelta(seconds=1)


def generate_labeled_features(
    n_users: int, n_months: int, seed: Optional[int] = None, start_date: Optional[datetime] = None
) -> pd.DataFrame:
    """
    1) StudentSpendingGenerator로 유저별 개별 거래 생성
    2) 매달 4개 체크포인트(7/14/21일 + 월말)를 각각 기준일(asof)로 삼아
       build_features_from_transactions() 호출
       -> 유저 x 월 x 체크포인트 단위 rolling feature row 생성
    """
    generator = StudentSpendingGenerator(seed=seed)
    start_date = start_date or datetime(2026, 1, 1)

    rows: List[dict] = []
    for user_id in range(1, n_users + 1):
        profile = generator.generate_profile(user_id)
        user_txs: List[dict] = []
        for m in range(n_months):
            month_start = _add_months(start_date, m)
            user_txs.extend(generator.generate_month(profile, month_start))

        # build_features_from_transactions()는 dt >= (asof - window)만 필터링하고
        # dt <= asof 상한 체크가 없다. 그래서 전체 기간 거래를 통째로 넘기면 아직 오지
        # 않은 미래 달의 거래까지 7일/30일 윈도우에 새어 들어간다. 넘기기 전에 직접
        # asof 이하로 잘라서 이 누수를 막는다.
        feature_input_all = [_to_feature_builder_input(tx) for tx in user_txs]

        for m in range(n_months):
            for day_number in _month_checkpoint_days(start_date, m):
                asof = _checkpoint_asof(start_date, m, day_number)
                feature_input = [
                    tx for tx in feature_input_all
                    if datetime.fromisoformat(tx["datetime"]) <= asof
                ]
                feats = build_features_from_transactions(feature_input, asof=asof)
                if not feats:
                    continue
                feats["user_id"] = user_id
                feats["date"] = asof.date().isoformat()
                feats["housing_type"] = profile.housing_type  # 참고용 컬럼, 학습 feature는 아님
                rows.append(feats)

    return pd.DataFrame(rows)


def label_with_ideal_fhi(df: pd.DataFrame) -> pd.DataFrame:
    """ideal_fhi()로 label_fhi 컬럼을 붙인다. rule_predict()는 호출하지 않는다."""
    df = df.copy()
    df["label_fhi"] = ideal_fhi(df)
    return df


def main():
    print("[1/2] 합성 거래 생성 + rolling feature 변환 중 (개별 거래 -> 유저x월 단위 feature)...")
    df = generate_labeled_features(n_users=30, n_months=3, seed=42)
    print(f"      feature rows: {len(df)}")

    print("[2/2] ideal_fhi()로 라벨링 중... (rule_predict는 사용하지 않음)")
    labeled = label_with_ideal_fhi(df)

    os.makedirs(os.path.dirname(FEATURES_OUT), exist_ok=True)
    labeled.to_csv(FEATURES_OUT, index=False)
    print(f"[완료] {len(labeled)} rows -> {FEATURES_OUT}")
    print(
        f"label_fhi: 평균={labeled['label_fhi'].mean():.2f}, "
        f"최소={labeled['label_fhi'].min():.2f}, 최대={labeled['label_fhi'].max():.2f}"
    )


if __name__ == "__main__":
    main()
