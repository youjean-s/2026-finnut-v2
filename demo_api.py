from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import random

from utils.fhi_calculator import calculate_fhi_from_transactions
from ml.ml_runtime.feature_builder import build_features_from_transactions
from ml.src.coaching_card import generate_coaching_card
from demo_pages.demo_persona_data import get_beauty_persona_transactions

app = FastAPI()

FALLBACK_CARDS = [
    {
        "title": "올리브영 장바구니 쉬어가기",
        "diagnosis": "최근 미용 소비 비중이 높아졌어요.",
        "coaching": "올리브영과 뷰티 지출이 반복되면 생활비 부담이 커질 수 있어요. 필요한 품목만 남기고 한 번 쉬어가보세요.",
        "mission": "올리브영 장바구니 쉬어가기"
    },
    {
        "title": "이번 주 결제 템포 늦추기",
        "diagnosis": "최근 지출 속도가 조금 빨라졌어요.",
        "coaching": "짧은 기간에 결제가 몰리면 작은 소비도 크게 느껴질 수 있어요. 급하게 사기 전 한 번만 템포를 늦춰보세요.",
        "mission": "이번 주 결제 템포 늦추기"
    },
    {
        "title": "편의점 간식 줄이기",
        "diagnosis": "작은 생활 소비도 은근히 쌓일 수 있어요.",
        "coaching": "편의점이나 간식처럼 가벼운 결제도 반복되면 생활비 흐름이 무거워질 수 있어요. 집에 있는 간식부터 먼저 챙겨보세요.",
        "mission": "편의점 간식 줄이기"
    },
]

class RefreshRequest(BaseModel):
    fhi: float
    features: dict
    impulsive_score: float = 0.0
    spike_score: float = 0.0
    current_titles: List[str] = []


def build_demo_transactions():
    return get_beauty_persona_transactions()


def pick_fallback_card(fhi, current_titles=None, focus="top_category"):
    current_titles = current_titles or []

    focus_keywords = {
        "top_category": ["올리브영", "파우치", "제품", "미용"],
        "behavior_pattern": ["결제", "템포", "하루", "속도"],
        "secondary_habit": ["편의점", "간식", "물", "집밥"],
    }

    candidates = [c for c in FALLBACK_CARDS if c["title"] not in current_titles]
    if not candidates:
        candidates = FALLBACK_CARDS[:]

    preferred = focus_keywords.get(focus, [])
    filtered = [
        c for c in candidates
        if any(keyword in c["title"] or keyword in c["mission"] for keyword in preferred)
    ]
    if filtered:
        candidates = filtered

    card = random.choice(candidates).copy()
    card["fhi"] = fhi
    card["grade"] = "양호 🟢" if fhi >= 80 else "주의 🟡" if fhi >= 60 else "위험 🔴"
    card["raw"] = "fallback"
    return card


def safe_generate_card(
    fhi,
    features,
    impulsive_score,
    spike_score,
    current_titles=None,
    variation="control",
    focus="top_category",
):
    current_titles = current_titles or []

    banned_keywords = []
    if focus == "top_category":
        banned_keywords = ["편의점", "간식", "배달"]
    elif focus == "behavior_pattern":
        banned_keywords = ["올리브영 장바구니", "파우치", "화장대"]
    elif focus == "secondary_habit":
        banned_keywords = ["올리브영", "네일", "헤어", "결제 템포"]

    try:
        card = generate_coaching_card(
            fhi=fhi,
            features=features,
            impulsive_score=impulsive_score,
            spike_score=spike_score,
            variation=variation,
            focus=focus,
            banned_titles=current_titles,
            banned_keywords=banned_keywords,
        )
        if not card.get("title"):
            raise ValueError("빈 카드 생성")
        return card
    except Exception:
        return pick_fallback_card(
            fhi=fhi,
            current_titles=current_titles,
            focus=focus,
        )


@app.get("/")
def root():
    return {"message": "FINNUT demo API running"}


@app.get("/demo/home")
def demo_home():
    txs = build_demo_transactions()

    result = calculate_fhi_from_transactions(txs, mode="ml")
    features = build_features_from_transactions(txs)

    fhi = result["fhi"]
    impulsive_score = result["impulsive"].get("impulsive_score", 0.0)
    spike_score = result["spike"].get("spike_score", 0.0)

    card_plans = [
        {"variation": "control", "focus": "top_category"},
        {"variation": "checklist", "focus": "behavior_pattern"},
        {"variation": "substitute", "focus": "secondary_habit"},
    ]

    cards = []
    current_titles = []

    for plan in card_plans:
        card = safe_generate_card(
            fhi=fhi,
            features=features,
            impulsive_score=impulsive_score,
            spike_score=spike_score,
            current_titles=current_titles,
            variation=plan["variation"],
            focus=plan["focus"],
        )
        current_titles.append(card["title"])
        cards.append(card)

    return {
        "fhi": fhi,
        "grade": "양호 🟢" if fhi >= 80 else "주의 🟡" if fhi >= 60 else "위험 🔴",
        "impulsive_score": impulsive_score,
        "spike_score": spike_score,
        "features": features,
        "cards": cards
    }


@app.post("/demo/refresh-card")
def refresh_card(req: RefreshRequest):
    card_plans = [
        {"variation": "control", "focus": "top_category"},
        {"variation": "checklist", "focus": "behavior_pattern"},
        {"variation": "substitute", "focus": "secondary_habit"},
    ]
    plan = random.choice(card_plans)

    card = safe_generate_card(
        fhi=req.fhi,
        features=req.features,
        impulsive_score=req.impulsive_score,
        spike_score=req.spike_score,
        current_titles=req.current_titles,
        variation=plan["variation"],
        focus=plan["focus"],
    )
    return card