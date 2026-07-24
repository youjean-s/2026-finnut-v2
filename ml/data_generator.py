"""
ml/data_generator.py
---------------------
대학생 소비 데이터 합성 생성기 (하이브리드 방식, 1차 초안 - 구조/태깅 검토용)

- 거래 "금액 분포/빈도"(AMOUNT_DISTRIBUTION_BY_CATEGORY): ml/src/normalize.py 의
  kaggle_fraud_detection(Sparkov 생성 신용카드 거래 데이터셋) 카테고리별 금액 스케일/분포 형태를
  참고해 로그정규분포 파라미터로 근사. 실제 normalized.csv가 로컬에 있으면 카테고리별
  통계를 재적합(refit)하는 것을 권장 (현재는 "형태/스케일 참고" 수준).
- 카테고리 "비중"(CATEGORY_WEIGHT_SOURCE): 순위(rank_basis)와 정확한 수치(value_basis)를
  분리해서 SOURCED / SOURCED_PARTIAL / ASSUMED로 각각 태깅.
- 최종 카테고리 9종은 utils/category_rules.py 와 동일하게 유지.

다음 단계(라벨링)는 이 구조 확인 후 진행.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Literal, Optional

from utils.category_rules import CATEGORY_KEYWORDS

FINAL_CATEGORIES: List[str] = [
    "convenience", "cafe", "food", "transport",
    "shopping", "housing", "entertainment", "subscription", "other",
]

SourceTag = Literal["SOURCED", "SOURCED_PARTIAL", "ASSUMED"]


# ---------------------------------------------------------------------------
# 1) 카테고리 비중 근거 태깅
#    - rank_basis  : "식비 > 교통/주거 > 통신/문화생활" 이라는 상대적 순위의 근거 수준
#    - value_basis : weight에 들어간 구체적인 숫자(%) 자체의 근거 수준
#    - weight 값은 전부 합이 1.0이 되도록 맞춘 초기값이며, 실제 조정은 언제든 가능.
# ---------------------------------------------------------------------------
CATEGORY_WEIGHT_SOURCE: Dict[str, dict] = {
    "food": {
        "weight": 0.28,
        "rank_basis": "SOURCED",
        "value_basis": "ASSUMED",
        "note": (
            "대학생 지출 1순위가 식비라는 순위는 알바몬/잡코리아 대학생 생활비 설문 및 "
            "통계청 1인가구 소비지출 통계에서 반복적으로 확인됨. "
            "다만 정확한 비중(%)은 조사마다 편차가 커서, 그럴듯한 범위(대략 25~35%) 내에서 "
            "FINNUT이 임의로 하나의 값을 고정."
        ),
        "citation": ["알바몬 대학생 생활비 설문", "잡코리아 대학생 생활비 설문", "통계청 1인가구 소비지출 통계"],
    },
    "transport": {
        "weight": 0.12,
        "rank_basis": "SOURCED",
        "value_basis": "ASSUMED",
        "note": (
            "식비 다음으로 교통/주거가 상위권이라는 순위는 위 설문·통계에서 근거를 찾을 수 있음. "
            "교통과 주거 사이의 정확한 비중 배분은 FINNUT이 임의로 고정."
        ),
        "citation": ["알바몬 대학생 생활비 설문", "통계청 1인가구 소비지출 통계"],
    },
    "housing": {
        "weight": 0.19,
        "rank_basis": "SOURCED",
        "value_basis": "ASSUMED",
        "note": (
            "교통과 함께 2순위 그룹이라는 순위는 SOURCED. 정확한 비중 값 자체는 ASSUMED. "
            "자취/기숙사/본가 분기 로직은 별도 필드(housing_split_basis) 참고."
        ),
        "citation": ["알바몬 대학생 생활비 설문", "통계청 1인가구 소비지출 통계"],
        "housing_split_basis": "SOURCED_PARTIAL",
        "housing_split_note": (
            "자취생 주거비 부담이 기숙사/본가생보다 크다는 방향성은 통계청 1인가구 통계를 참고했으나, "
            "실제 분기 확률과 배수(off_campus/dorm/home 가중치 조정값)는 FINNUT이 자체 설계."
        ),
    },
    "entertainment": {
        "weight": 0.09,
        "rank_basis": "SOURCED",
        "value_basis": "ASSUMED",
        "note": (
            "통신/문화생활이 가장 낮은 순위 그룹이라는 순위는 SOURCED. "
            "문화생활(entertainment)에 배분한 정확한 비중 값은 ASSUMED."
        ),
        "citation": ["통계청 1인가구 소비지출 통계"],
    },
    "cafe": {
        "weight": 0.08,
        "rank_basis": "ASSUMED",
        "value_basis": "ASSUMED",
        "note": "카페 지출만 별도로 추적하는 특화 통계 자료가 없어 FINNUT이 자체 설계.",
        "citation": [],
    },
    "convenience": {
        "weight": 0.07,
        "rank_basis": "ASSUMED",
        "value_basis": "ASSUMED",
        "note": "편의점 지출 특화 통계 없음. FINNUT 자체 설계.",
        "citation": [],
    },
    "shopping": {
        "weight": 0.09,
        "rank_basis": "ASSUMED",
        "value_basis": "ASSUMED",
        "note": "쇼핑 지출 특화 통계 없음. FINNUT 자체 설계.",
        "citation": [],
    },
    "subscription": {
        "weight": 0.04,
        "rank_basis": "ASSUMED",
        "value_basis": "ASSUMED",
        "note": "구독 지출 특화 통계 없음. FINNUT 자체 설계.",
        "citation": [],
    },
    "other": {
        "weight": 0.04,
        "rank_basis": "ASSUMED",
        "value_basis": "ASSUMED",
        "note": "위 8개 카테고리에 속하지 않는 잔여 지출. 특화 통계 없음. FINNUT 자체 설계.",
        "citation": [],
    },
}

assert set(CATEGORY_WEIGHT_SOURCE.keys()) == set(FINAL_CATEGORIES), "카테고리 9종 불일치"
assert abs(sum(v["weight"] for v in CATEGORY_WEIGHT_SOURCE.values()) - 1.0) < 1e-9, "weight 합이 1.0이 아님"


# ---------------------------------------------------------------------------
# 2) 카테고리별 금액 분포/빈도 (Sparkov 계열 데이터셋 참고, 로그정규분포로 근사)
#    log_mu_sigma: ln(amount) ~ Normal(mu, sigma)
#    monthly_freq_range: 유저 1명 기준 월 거래 건수 범위 (min, max)
# ---------------------------------------------------------------------------
# housing은 rent/utility 두 하위 유형(HOUSING_SUBTYPE_DISTRIBUTION)으로 따로 관리하므로
# 여기엔 없음. 출력 category는 그대로 "housing" 하나로 합쳐서 나간다.
AMOUNT_DISTRIBUTION_BY_CATEGORY: Dict[str, dict] = {
    "convenience":   {"log_mu_sigma": (8.52, 0.40), "monthly_freq_range": (8, 15)},
    "cafe":          {"log_mu_sigma": (8.61, 0.35), "monthly_freq_range": (10, 20)},
    "food":          {"log_mu_sigma": (9.10, 0.50), "monthly_freq_range": (20, 35)},
    "transport":     {"log_mu_sigma": (7.31, 0.60), "monthly_freq_range": (15, 30)},
    "shopping":      {"log_mu_sigma": (10.46, 0.80), "monthly_freq_range": (3, 8)},
    "entertainment": {"log_mu_sigma": (9.60, 0.60), "monthly_freq_range": (2, 6)},
    "subscription":  {"log_mu_sigma": (9.20, 0.30), "monthly_freq_range": (2, 5)},
    "other":         {"log_mu_sigma": (9.20, 0.70), "monthly_freq_range": (1, 4)},
}

# 생성한 merchant가 utils/category_rules.categorize_store()로 되짚었을 때도 같은 카테고리로
# 분류되도록, 기존에 쓰는 카테고리 키워드 풀을 merchant 후보로 재사용.
# "other"는 categorize_store()의 기본값(어떤 키워드에도 안 걸릴 때)이라 CATEGORY_KEYWORDS에
# 항목이 없으므로, 의도적으로 다른 카테고리 키워드와 안 겹치는 잡화성 이름을 따로 채움.
# "housing"은 rent/utility 각자의 merchant 목록을 따로 쓰므로 여기서 빼고 아래에서 채운다.
MERCHANT_NAMES_BY_CATEGORY: Dict[str, List[str]] = {
    k: v for k, v in CATEGORY_KEYWORDS.items() if k != "housing"
}
MERCHANT_NAMES_BY_CATEGORY["other"] = ["문구점", "복사집", "동전세탁방", "코인세탁", "출력", "기타잡화"]

HousingType = Literal["off_campus", "dorm", "home"]

# 자취/기숙사/본가 분기 확률. 방향성(자취 > 기숙사, 자취 > 본가 주거비 부담)은 SOURCED_PARTIAL,
# 구체적 확률은 FINNUT 자체 설계.
HOUSING_TYPE_PROFILE: Dict[HousingType, dict] = {
    "off_campus": {"probability": 0.45},
    "dorm":       {"probability": 0.25},
    "home":       {"probability": 0.30},
}

# rent 금액대를 off_campus/dorm 간에 차등화한 근거 태깅 (CATEGORY_WEIGHT_SOURCE와 동일한 방식).
# - rank_basis  : "자취가 기숙사보다 비싸다 / 기숙사는 정액제라 변동폭이 작다"는 방향성의 근거 수준
# - value_basis : 실제로 넣은 금액대(만원 단위)와 변동폭(sigma) 자체의 근거 수준
# home은 항목 자체가 없음 = rent 미발생 (기존과 동일).
HOUSING_RENT_TIER_SOURCE: Dict[str, dict] = {
    "off_campus": {
        "log_mu_sigma": (13.10, 0.10),
        "amount_clip": (400_000, 600_000),
        "rank_basis": "SOURCED",
        "value_basis": "ASSUMED",
        "note": (
            "자취가 기숙사보다 주거비 부담이 크다는 방향성은 통계청 1인가구 소비지출 통계 등에서 "
            "근거를 찾을 수 있어 SOURCED. 정확한 금액대(40~60만원)는 FINNUT이 임의로 설정한 값으로 ASSUMED."
        ),
        "citation": ["통계청 1인가구 소비지출 통계"],
    },
    "dorm": {
        "log_mu_sigma": (12.49, 0.06),
        "amount_clip": (200_000, 350_000),
        "rank_basis": "SOURCED",
        "value_basis": "ASSUMED",
        "note": (
            "기숙사비가 자취보다 저렴하고, 정액제 특성상 변동폭이 작다는 방향성은 일반적으로 "
            "알려진 사실이라 SOURCED. 정확한 금액대(20~35만원)와 낮은 변동폭(sigma) 값 자체는 "
            "FINNUT이 임의로 설정한 값으로 ASSUMED."
        ),
        "citation": ["통계청 1인가구 소비지출 통계"],
    },
}

# housing 내부 하위 유형. 최종 출력 category는 "housing"으로 합치지만, 내부적으로는
# rent(고정 대액, 자취/기숙사만 발생 + 유형별 금액대 차등)와 utility(변동 소액, 전체 발생,
# 유형 무관 동일 분포)를 별도 분포로 생성한다.
HOUSING_SUBTYPE_DISTRIBUTION: Dict[str, dict] = {
    "rent": {
        "monthly_freq": 1,
        "merchant_names": ["월세", "임대"],
        # off_campus/dorm만 키로 존재 -> home은 자동으로 rent 미발생
        "by_housing_type": HOUSING_RENT_TIER_SOURCE,
    },
    "utility": {
        "log_mu_sigma": (10.82, 0.45),
        "amount_clip": (10_000, 150_000),
        "monthly_freq_range": (3, 6),
        "eligible_housing_types": ("off_campus", "dorm", "home"),
        "merchant_names": [m for m in CATEGORY_KEYWORDS["housing"] if m not in ("월세", "임대")],
    },
}

# rent/utility 결제일 근거 태깅 (CATEGORY_WEIGHT_SOURCE와 동일한 방식).
# - rank_basis  : "월세/공과금은 매월 정해진 날짜에 결제된다"는 방향성의 근거 수준
# - value_basis : 실제로 넣은 기준일(day)과 변동폭(jitter_days) 자체의 근거 수준
# 균등난수(0~27일)로 뽑던 기존 방식 대신, 고정 결제일 ± jitter로 day_offset을 뽑는다.
TIMING_PATTERN_SOURCE: Dict[str, dict] = {
    "rent_billing_day": {
        "target_day": 25,      # 매월 25일
        "jitter_days": 2,      # ±2일
        "rank_basis": "SOURCED",
        "value_basis": "ASSUMED",
        "note": (
            "월세 등 주거 고정비가 매월 정해진 날짜(자동이체/약정일)에 결제된다는 방향성은 "
            "일반적으로 알려진 사실이라 SOURCED. 구체적으로 25일을 기준일로 잡고 ±2일의 "
            "변동폭을 준 것은 FINNUT이 임의로 설정한 값으로 ASSUMED."
        ),
        "citation": [],
    },
    "utility_billing_day": {
        "target_day": 5,       # 매월 5일
        "jitter_days": 3,      # ±3일
        "rank_basis": "SOURCED",
        "value_basis": "ASSUMED",
        "note": (
            "공과금(전기/가스/수도/인터넷 등)도 매월 정해진 청구/자동이체일에 결제된다는 방향성은 "
            "일반적으로 알려진 사실이라 SOURCED. 구체적으로 5일을 기준일로 잡고 ±3일의 "
            "변동폭을 준 것은 FINNUT이 임의로 설정한 값으로 ASSUMED."
        ),
        "citation": [],
    },
}


@dataclass
class StudentProfile:
    user_id: int
    housing_type: HousingType


class StudentSpendingGenerator:
    """카테고리 비중(CATEGORY_WEIGHT_SOURCE) + 금액 분포(AMOUNT_DISTRIBUTION_BY_CATEGORY)를
    합쳐 유저별 월간 거래를 만드는 생성기. 라벨링(FHI 라벨 부착)은 다음 단계에서 별도로 붙임."""

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def generate_profile(self, user_id: int) -> StudentProfile:
        housing_type = self.rng.choices(
            population=list(HOUSING_TYPE_PROFILE.keys()),
            weights=[v["probability"] for v in HOUSING_TYPE_PROFILE.values()],
            k=1,
        )[0]
        return StudentProfile(user_id=user_id, housing_type=housing_type)

    def _draw_amount(self, category: str) -> float:
        mu, sigma = AMOUNT_DISTRIBUTION_BY_CATEGORY[category]["log_mu_sigma"]
        amount = self.rng.lognormvariate(mu, sigma)
        return round(amount / 100) * 100  # 100원 단위 반올림

    def _monthly_transaction_count(self, category: str) -> int:
        lo, hi = AMOUNT_DISTRIBUTION_BY_CATEGORY[category]["monthly_freq_range"]
        return self.rng.randint(lo, hi)

    def _draw_clipped_lognormal(self, log_mu_sigma, amount_clip) -> float:
        mu, sigma = log_mu_sigma
        lo, hi = amount_clip
        amount = self.rng.lognormvariate(mu, sigma)
        amount = min(max(amount, lo), hi)
        return round(amount / 100) * 100

    def _pick_billing_day_offset(self, target_day: int, jitter_days: int) -> int:
        """target_day(1-based) ± jitter_days 범위에서 결제일을 골라 0-based day_offset으로 반환."""
        target_offset = target_day - 1
        lo = max(0, target_offset - jitter_days)
        hi = min(27, target_offset + jitter_days)
        return self.rng.randint(lo, hi)

    def _make_tx(
        self, user_id: int, month_start: datetime, category: str, amount: float, merchant: str,
        day_offset: Optional[int] = None,
    ) -> dict:
        if day_offset is None:
            day_offset = self.rng.randint(0, 27)
        seconds_offset = self.rng.randint(0, 86_399)
        tx_dt = month_start + timedelta(days=day_offset, seconds=seconds_offset)
        return {
            "user_id": user_id,
            "tx_datetime": tx_dt.isoformat(timespec="seconds"),
            "amount": amount,
            "merchant": merchant,
            "category": category,
        }

    def _generate_housing_transactions(self, profile: StudentProfile, month_start: datetime) -> List[dict]:
        """rent(고정 대액, housing_type별 금액대 차등)/utility(변동 소액, 유형 무관 동일 분포)를
        따로 뽑아 만들되, 출력 category는 "housing"으로 통일."""
        transactions: List[dict] = []

        rent_config = HOUSING_SUBTYPE_DISTRIBUTION["rent"]
        rent_params = rent_config["by_housing_type"].get(profile.housing_type)
        if rent_params is not None:
            rent_timing = TIMING_PATTERN_SOURCE["rent_billing_day"]
            for _ in range(rent_config["monthly_freq"]):
                amount = self._draw_clipped_lognormal(rent_params["log_mu_sigma"], rent_params["amount_clip"])
                merchant = self.rng.choice(rent_config["merchant_names"])
                day_offset = self._pick_billing_day_offset(rent_timing["target_day"], rent_timing["jitter_days"])
                transactions.append(
                    self._make_tx(profile.user_id, month_start, "housing", amount, merchant, day_offset)
                )

        utility_config = HOUSING_SUBTYPE_DISTRIBUTION["utility"]
        if profile.housing_type in utility_config["eligible_housing_types"]:
            utility_timing = TIMING_PATTERN_SOURCE["utility_billing_day"]
            n_tx = self.rng.randint(*utility_config["monthly_freq_range"])
            for _ in range(n_tx):
                amount = self._draw_clipped_lognormal(utility_config["log_mu_sigma"], utility_config["amount_clip"])
                merchant = self.rng.choice(utility_config["merchant_names"])
                day_offset = self._pick_billing_day_offset(
                    utility_timing["target_day"], utility_timing["jitter_days"]
                )
                transactions.append(
                    self._make_tx(profile.user_id, month_start, "housing", amount, merchant, day_offset)
                )

        return transactions

    def generate_month(self, profile: StudentProfile, month_start: datetime) -> List[dict]:
        transactions: List[dict] = []
        for category in FINAL_CATEGORIES:
            if category == "housing":
                transactions.extend(self._generate_housing_transactions(profile, month_start))
                continue
            n_tx = self._monthly_transaction_count(category)
            for _ in range(n_tx):
                amount = self._draw_amount(category)
                merchant = self.rng.choice(MERCHANT_NAMES_BY_CATEGORY[category])
                transactions.append(self._make_tx(profile.user_id, month_start, category, amount, merchant))
        transactions.sort(key=lambda t: t["tx_datetime"])
        return transactions

    def generate(self, n_users: int, n_months: int, start_date: Optional[datetime] = None) -> List[dict]:
        start_date = start_date or datetime(2026, 1, 1)
        all_transactions: List[dict] = []
        for user_id in range(1, n_users + 1):
            profile = self.generate_profile(user_id)
            for m in range(n_months):
                month_start = _add_months(start_date, m)
                all_transactions.extend(self.generate_month(profile, month_start))
        return all_transactions


def _add_months(dt: datetime, months: int) -> datetime:
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    return dt.replace(year=year, month=month, day=1)


if __name__ == "__main__":
    print("=== CATEGORY_WEIGHT_SOURCE ===")
    for cat, info in CATEGORY_WEIGHT_SOURCE.items():
        print(f"- {cat}: weight={info['weight']:.2f}, rank={info['rank_basis']}, value={info['value_basis']}")

    print("\n=== 샘플 생성 (2 users x 1 month) ===")
    generator = StudentSpendingGenerator(seed=42)
    sample = generator.generate(n_users=2, n_months=1)
    print(f"총 거래 건수: {len(sample)}")
    for row in sample[:5]:
        print(row)
