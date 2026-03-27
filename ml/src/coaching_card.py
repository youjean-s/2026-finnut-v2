"""
coaching_card.py
----------------
FHI + 소비 패턴 기반 3분 코칭카드 생성 (ChatGPT API)

Usage:
    python ml/src/coaching_card.py
"""

import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def generate_coaching_card(
    fhi: float,
    features: dict,
    impulsive_score: float = 0.0,
    spike_score: float = 0.0,
) -> dict:
    """
    FHI + 소비 feature → ChatGPT API → 3분 코칭카드 생성

    Returns:
        {
            "title": str,
            "diagnosis": str,
            "coaching": str,
            "mission": str,
            "fhi": float
        }
    """

    # ── 소비 상태 요약 텍스트 생성 ──
    spend_sum_7d   = features.get("spend_sum_7d", 0)
    spend_mean_30d = features.get("spend_mean_30d", 0)
    top_category   = _get_top_category(features)

    status_summary = f"""
- 금융건강지수(FHI): {fhi}점 / 100점
- 최근 7일 총 지출: {spend_sum_7d:,.0f}원
- 최근 30일 일평균 지출: {spend_mean_30d:,.0f}원
- 충동구매 점수: {impulsive_score:.2f} (0~1, 높을수록 위험)
- 소비 급증 점수: {spike_score:.2f}
- 주요 소비 카테고리: {top_category}
""".strip()

    # ── FHI 등급 ──
    if fhi >= 80:
        grade = "양호 🟢"
    elif fhi >= 60:
        grade = "주의 🟡"
    else:
        grade = "위험 🔴"

    # ── 프롬프트 ──
    prompt = f"""
당신은 대학생 전용 금융 코치입니다.
아래 사용자의 소비 데이터를 보고 **3분 코칭카드**를 작성해주세요.

[사용자 소비 현황]
{status_summary}
FHI 등급: {grade}

[작성 규칙]
1. 친근하고 따뜻한 말투 (딱딱하지 않게)
2. 대학생이 바로 실천할 수 있는 구체적인 행동 미션 1가지
3. 절대 위협적이거나 부정적이지 않게
4. 전체 분량 150자 이내

[출력 형식 - 반드시 아래 형식 그대로]
제목: (한 줄 제목)
진단: (소비 상태 한 줄 요약)
코칭: (맞춤 조언 2~3문장)
미션: (오늘 당장 할 수 있는 행동 1가지)
""".strip()

    # ── API 호출 ──
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "당신은 대학생 재정 관리를 돕는 친근한 금융 코치입니다."},
            {"role": "user",   "content": prompt}
        ],
        max_tokens=300,
        temperature=0.7,
    )

    raw = response.choices[0].message.content.strip()

    # ── 파싱 ──
    card = _parse_card(raw)
    card["fhi"]   = fhi
    card["grade"] = grade
    card["raw"]   = raw
    return card


def _get_top_category(features: dict) -> str:
    """cat_spend_ratio_* 중 가장 높은 카테고리 반환."""
    cat_features = {
        k.replace("cat_spend_ratio_", "").replace("_30d", ""): v
        for k, v in features.items()
        if k.startswith("cat_spend_ratio_")
    }
    if not cat_features:
        return "기타"
    return max(cat_features, key=cat_features.get)


def _parse_card(raw: str) -> dict:
    """ChatGPT 응답 텍스트 → dict 파싱."""
    result = {"title": "", "diagnosis": "", "coaching": "", "mission": ""}
    mapping = {
        "제목": "title",
        "진단": "diagnosis",
        "코칭": "coaching",
        "미션": "mission",
    }
    for line in raw.splitlines():
        for ko, en in mapping.items():
            if line.startswith(f"{ko}:"):
                result[en] = line.split(":", 1)[1].strip()
    return result


def print_card(card: dict):
    print("\n" + "="*50)
    print(f"  🥜 FINNUT 3분 코칭카드  |  FHI {card['fhi']}점 {card['grade']}")
    print("="*50)
    print(f"  📌 {card['title']}")
    print(f"  📊 진단: {card['diagnosis']}")
    print(f"  💬 코칭: {card['coaching']}")
    print(f"  ✅ 오늘의 미션: {card['mission']}")
    print("="*50)


# ── 단독 실행 테스트 ──
if __name__ == "__main__":
    # main.py 파이프라인과 연결 테스트
    from mock.push_emulator import get_random_push
    from utils.parser import parse_push_notification
    from utils.category_rules import categorize_store
    from utils.fhi_calculator import calculate_fhi_from_transactions
    from ml.ml_runtime.feature_builder import build_features_from_transactions

    push = get_random_push()
    txs  = parse_push_notification(push)
    for tx in txs:
        tx["category"] = categorize_store(tx.get("merchant", ""))

    result   = calculate_fhi_from_transactions(txs, mode="ml")
    features = build_features_from_transactions(txs)

    card = generate_coaching_card(
        fhi             = result["fhi"],
        features        = features,
        impulsive_score = result["impulsive"].get("impulsive_score", 0.0),
        spike_score     = result["spike"].get("spike_score", 0.0),
    )
    print_card(card)