"""
coaching_card.py
----------------
FHI + 소비 패턴 기반 3분 코칭카드 생성 (ChatGPT API)
"""

import os
import re
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


CATEGORY_LABELS = {
    "entertainment": "문화·여가",
    "gas_transport": "교통",
    "grocery_pos": "편의점·마트",
    "home": "생활용품",
    "kids_pets": "키즈·반려동물",
    "misc_net": "온라인 기타소비",
    "other": "식비·기타",
    "shopping_pos": "미용·오프라인 쇼핑",
    "shopping_net": "온라인 쇼핑",
}

CATEGORY_EXAMPLES = {
    "entertainment": "영화, 전시, 놀거리",
    "gas_transport": "택시, 교통비",
    "grocery_pos": "편의점, 마트, 간식, 생필품",
    "home": "다이소, 생활용품, 집에 필요한 물건",
    "kids_pets": "반려동물, 육아 관련 소비",
    "misc_net": "온라인 기타 결제",
    "other": "식비, 카페, 간식",
    "shopping_pos": "올리브영, 네일, 헤어, 화장품, 뷰티 소비",
    "shopping_net": "온라인 쇼핑, 장바구니 결제",
}

CARD_VARIATIONS = {
    "control": "지출을 잠깐 쉬어가게 하는 방향",
    "substitute": "비슷한 만족을 더 가볍게 채우는 방향",
    "checklist": "사기 전에 한 번 점검해보는 방향",
}


def generate_coaching_card(
    fhi: float,
    features: dict,
    impulsive_score: float = 0.0,
    spike_score: float = 0.0,
    variation: str = "control",
    banned_titles: list[str] | None = None,
    banned_keywords: list[str] | None = None,
) -> dict:
    """
    FHI + 소비 feature → ChatGPT API → 3분 코칭카드 생성
    """
    banned_titles = banned_titles or []
    banned_keywords = banned_keywords or []

    spend_sum_7d = features.get("spend_sum_7d", 0)
    spend_mean_30d = features.get("spend_mean_30d", 0)

    top_category_key = _get_top_category_key(features)
    top_category_label = CATEGORY_LABELS.get(top_category_key, "기타")
    top_category_example = CATEGORY_EXAMPLES.get(top_category_key, "관련 소비")
    top_category_ratio = _get_top_category_ratio(features)

    if fhi >= 80:
        grade = "양호 🟢"
    elif fhi >= 60:
        grade = "주의 🟡"
    else:
        grade = "위험 🔴"

    variation_guide = CARD_VARIATIONS.get(variation, CARD_VARIATIONS["control"])
    banned_titles_text = ", ".join(banned_titles) if banned_titles else "없음"
    banned_keywords_text = ", ".join(banned_keywords) if banned_keywords else "없음"

    status_summary = f"""
- 금융건강지수(FHI): {fhi}점 / 100점
- FHI 등급: {grade}
- 최근 7일 총 지출: {spend_sum_7d:,.0f}원
- 최근 30일 일평균 지출: {spend_mean_30d:,.0f}원
- 충동구매 점수: {impulsive_score:.2f} (0~1, 높을수록 위험)
- 소비 급증 점수: {spike_score:.2f}
- 주요 소비 카테고리 코드: {top_category_key}
- 주요 소비 카테고리 해석: {top_category_label}
- 주요 소비 예시: {top_category_example}
- 최근 30일 해당 카테고리 비중: {top_category_ratio:.1%}
""".strip()

    prompt = f"""
당신은 대학생의 생활비 습관을 부드럽게 코칭하는 친근한 금융 코치입니다.
아래 사용자의 소비 데이터를 보고 3분 코칭카드를 작성해주세요.

[사용자 소비 현황]
{status_summary}

[이번 카드의 방향]
- 이번 카드는 "{variation_guide}" 방향으로 작성하세요.
- 다른 카드와 겹치지 않도록 관점과 표현을 분명히 다르게 하세요.

[핵심 톤]
- 잔소리나 통제처럼 말하지 말고, 일상에서 가볍게 실천할 수 있는 제안처럼 써주세요.
- 너무 딱딱한 표현보다 말맛 있는 생활 코칭 문구를 선호합니다.
- 예시 톤:
  배달 대신 집밥
  편의점 간식 줄이기
  물 2L 마시기
  파우치 먼저 살펴보기
  올리브영 장바구니 쉬어가기
  지금 있는 제품부터 써보기

[중요 지시]
1. 안드로이드 앱에서 mission이 카드 상단의 가장 큰 문구로 보입니다.
2. mission은 짧고 부드러운 생활 코칭 문구로 작성하세요.
3. mission은 완전한 문장형 말투를 피하세요.
4. mission은 아래 같은 느낌으로 끝나면 좋습니다.
   - ~하기 / ~줄이기 / ~챙기기 / ~찾아보기 / ~미루기 / ~정리하기 / ~확인하기
   - ~마시기 / ~써보기 / ~쉬어가기 / ~살펴보기
5. "소비 통제하기", "지출 관리하기", "불필요한 소비 차단하기" 같은 딱딱한 표현은 피하세요.
6. coaching은 mission을 바로 설명하는 1~2문장으로 작성하세요.
7. title은 내부 구분용 짧은 제목입니다.
8. diagnosis는 소비 상태를 한 줄로 요약하세요.
9. 주요 소비 카테고리를 반드시 적극 반영하세요.
10. 주요 소비 카테고리가 "미용·오프라인 쇼핑"이면 진단/코칭/미션에
    화장품, 올리브영, 네일, 헤어, 파우치, 재고, 뷰티 소비 같은 표현을 자연스럽게 넣으세요.
11. 범용적인 절약 조언만 하지 말고, 사용자의 실제 과소비 영역에 맞춘 조언을 주세요.
12. 같은 표현 반복을 피하세요.
13. 아래 제목/표현은 피하세요.
   - 금지 제목: {banned_titles_text}
   - 금지 키워드: {banned_keywords_text}

[variation별 추가 규칙]
- control: 지금 당장 잠깐 쉬어갈 수 있는 행동
- substitute: 같은 욕구를 더 가볍게 채우는 행동
- checklist: 사기 전에 확인하거나 점검하는 행동

[출력 형식 - 반드시 아래 형식 그대로]
제목: (짧은 제목)
진단: (소비 상태 한 줄 요약)
코칭: (맞춤 조언 1~2문장)
미션: (짧고 부드러운 생활 코칭 문구)
""".strip()

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "당신은 대학생의 생활비 습관을 부드럽게 코칭하는 친근한 금융 코치입니다. "
                    "반드시 사용자의 주요 과소비 카테고리를 구체적으로 반영하세요. "
                    "특히 shopping_pos는 미용·오프라인 쇼핑으로 해석하고 "
                    "올리브영, 네일, 헤어, 화장품, 파우치, 재고 같은 표현을 적극 활용하세요. "
                    "mission은 카드 헤드라인처럼 짧고 말맛 있게 작성하세요."
                )
            },
            {"role": "user", "content": prompt}
        ],
        max_tokens=300,
        temperature=0.95,
    )

    raw = response.choices[0].message.content.strip()
    card = _parse_card(raw)

    card["title"] = _normalize_title(card.get("title", ""), variation, top_category_label)
    card["diagnosis"] = _normalize_diagnosis(card.get("diagnosis", ""), top_category_label)
    card["coaching"] = _normalize_coaching(card.get("coaching", ""), top_category_key)
    card["mission"] = _normalize_mission(card.get("mission", ""), top_category_key, variation)

    card["fhi"] = fhi
    card["grade"] = grade
    card["raw"] = raw
    return card


def _get_top_category_key(features: dict) -> str:
    cat_features = {
        k.replace("cat_spend_ratio_", "").replace("_30d", ""): v
        for k, v in features.items()
        if k.startswith("cat_spend_ratio_")
    }
    if not cat_features:
        return "other"
    return max(cat_features, key=cat_features.get)


def _get_top_category_ratio(features: dict) -> float:
    cat_features = {
        k.replace("cat_spend_ratio_", "").replace("_30d", ""): v
        for k, v in features.items()
        if k.startswith("cat_spend_ratio_")
    }
    if not cat_features:
        return 0.0
    return float(max(cat_features.values()))


def _normalize_title(title: str, variation: str, top_category_label: str) -> str:
    title = (title or "").strip()
    if title:
        return title

    defaults = {
        "control": f"{top_category_label} 쉬어가기",
        "substitute": f"{top_category_label} 가볍게 바꾸기",
        "checklist": f"{top_category_label} 먼저 점검하기",
    }
    return defaults.get(variation, "소비 흐름 돌아보기")


def _normalize_diagnosis(diagnosis: str, top_category_label: str) -> str:
    diagnosis = (diagnosis or "").strip()
    if diagnosis:
        return diagnosis
    return f"최근 {top_category_label} 지출 비중이 높아졌어요."


def _normalize_coaching(coaching: str, top_category_key: str) -> str:
    coaching = (coaching or "").strip()
    if coaching:
        return coaching

    fallback_map = {
        "shopping_pos": "올리브영, 네일, 헤어처럼 미용 관련 결제가 이어지면 생활비 부담이 은근히 커질 수 있어요. 새로 사기 전에 지금 있는 제품과 예약 내역을 먼저 살펴보면 훨씬 가볍게 조절할 수 있어요.",
        "shopping_net": "온라인 쇼핑은 바로 결제하지 않고 한 번 쉬어가기만 해도 지출 흐름이 달라질 수 있어요. 장바구니에 담아둔 뒤 다시 고르는 습관이 도움이 돼요.",
        "grocery_pos": "편의점과 마트의 작은 결제도 자주 반복되면 꽤 크게 쌓여요. 필요한 것부터 먼저 고르면 부담을 덜 수 있어요.",
        "other": "반복되는 생활 소비는 작은 습관 변화만으로도 흐름이 달라질 수 있어요. 오늘 필요한 지출과 미뤄도 되는 지출을 가볍게 나눠보세요.",
        "home": "생활용품은 필요와 충동이 섞이기 쉬워요. 이미 있는 물건을 먼저 점검하면 중복 구매를 줄이기 쉬워져요.",
    }
    return fallback_map.get(
        top_category_key,
        "최근 소비 흐름을 한 번만 돌아봐도 지출 패턴이 훨씬 선명하게 보일 수 있어요."
    )


def _normalize_mission(mission: str, top_category_key: str, variation: str) -> str:
    mission = (mission or "").strip()

    mission = re.sub(r"^(오늘의\s*)?미션[:：]?\s*", "", mission).strip()
    mission = re.sub(r"^(오늘은|오늘)\s*", "", mission).strip()

    bad_patterns = [
        r"해보세요\.?$",
        r"보세요\.?$",
        r"세요\.?$",
        r"해요\.?$",
        r"도전해보세요\.?$",
    ]
    for pattern in bad_patterns:
        mission = re.sub(pattern, "", mission).strip()

    mission = mission.rstrip(".! ")

    if not mission:
        return _default_mission(top_category_key, variation)

    good_suffixes = [
        "하기", "줄이기", "챙기기", "찾아보기",
        "미루기", "정리하기", "확인하기", "점검하기",
        "마시기", "써보기", "쉬어가기", "살펴보기",
        "남기기", "비우기", "고르기"
    ]
    if any(mission.endswith(suffix) for suffix in good_suffixes):
        return mission

    if mission.endswith("기"):
        return mission

    return mission + "하기"


def _default_mission(top_category_key: str, variation: str) -> str:
    default_map = {
        ("shopping_pos", "control"): "올리브영 장바구니 쉬어가기",
        ("shopping_pos", "substitute"): "지금 있는 제품부터 써보기",
        ("shopping_pos", "checklist"): "파우치 먼저 살펴보기",

        ("shopping_net", "control"): "장바구니 하루 쉬어가기",
        ("shopping_net", "substitute"): "찜한 상품 다시 고르기",
        ("shopping_net", "checklist"): "장바구니 목록 정리하기",

        ("grocery_pos", "control"): "편의점 간식 줄이기",
        ("grocery_pos", "substitute"): "집에 있는 간식 먼저 먹기",
        ("grocery_pos", "checklist"): "사기 전 목록 먼저 보기",

        ("other", "control"): "배달 대신 집밥",
        ("other", "substitute"): "물 2L 마시기",
        ("other", "checklist"): "오늘 지출 가볍게 적어보기",

        ("home", "control"): "생활용품 쇼핑 쉬어가기",
        ("home", "substitute"): "집에 있는 물건 먼저 쓰기",
        ("home", "checklist"): "서랍 속 재고 먼저 보기",
    }
    return default_map.get((top_category_key, variation), "오늘 소비 가볍게 돌아보기")


def _parse_card(raw: str) -> dict:
    result = {"title": "", "diagnosis": "", "coaching": "", "mission": ""}
    mapping = {
        "제목": "title",
        "진단": "diagnosis",
        "코칭": "coaching",
        "미션": "mission",
    }

    for line in raw.splitlines():
        line = line.strip()
        for ko, en in mapping.items():
            if line.startswith(f"{ko}:"):
                result[en] = line.split(":", 1)[1].strip()

    return result


def print_card(card: dict):
    print(card)


if __name__ == "__main__":
    from mock.push_emulator import get_random_push
    from utils.parser import parse_push_notification
    from utils.category_rules import categorize_store
    from utils.fhi_calculator import calculate_fhi_from_transactions
    from ml.ml_runtime.feature_builder import build_features_from_transactions

    push = get_random_push()
    txs = parse_push_notification(push)
    for tx in txs:
        tx["category"] = categorize_store(tx.get("merchant", ""))

    result = calculate_fhi_from_transactions(txs, mode="ml")
    features = build_features_from_transactions(txs)

    card = generate_coaching_card(
        fhi=result["fhi"],
        features=features,
        impulsive_score=result["impulsive"].get("impulsive_score", 0.0),
        spike_score=result["spike"].get("spike_score", 0.0),
        variation="control",
    )
    print_card(card)