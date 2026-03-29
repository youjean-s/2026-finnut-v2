from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import random

from mock.push_emulator import get_random_push
from utils.parser import parse_push_notification
from utils.category_rules import categorize_store
from utils.fhi_calculator import calculate_fhi_from_transactions
from ml.ml_runtime.feature_builder import build_features_from_transactions
from ml.src.coaching_card import generate_coaching_card

app = FastAPI()

# fallback 카드 목록
FALLBACK_CARDS = [
    {
        "title": "텀블러 챙기기",
        "diagnosis": "카페 지출을 조금만 줄여도 차이가 생겨요.",
        "coaching": "오늘은 음료를 사기 전에 집에서 물이나 커피를 챙겨보세요.",
        "mission": "오늘 카페 음료 1회 참기"
    },
    {
        "title": "간식 쉬어가기",
        "diagnosis": "소액 지출이 반복되면 생각보다 크게 쌓여요.",
        "coaching": "편의점 간식을 바로 사기보다 집에 있는 음식부터 확인해보세요.",
        "mission": "오늘 편의점 방문 1번 줄이기"
    },
    {
        "title": "배달 대신 한 끼",
        "diagnosis": "식비가 새는 순간은 생각보다 자주 와요.",
        "coaching": "배달 대신 간단한 집밥이나 학교 식당을 선택해보면 부담이 줄어요.",
        "mission": "오늘 한 끼는 배달 대신 다른 선택하기"
    },
    {
        "title": "이동비 아끼기",
        "diagnosis": "짧은 거리 이동도 쌓이면 부담이 돼요.",
        "coaching": "가까운 거리는 걷거나 자전거를 타면 지출도 줄고 기분도 환기돼요.",
        "mission": "오늘 1회는 걸어서 이동하기"
    },
    {
        "title": "오늘 지출 멈춤",
        "diagnosis": "지출 흐름을 잠깐 끊는 것만으로도 조절감이 생겨요.",
        "coaching": "오늘은 꼭 필요한 것 외에는 결제하지 않는 하루를 만들어보세요.",
        "mission": "오늘 충동 결제 0회 도전"
    },
]

class RefreshRequest(BaseModel):
    fhi: float
    features: dict
    impulsive_score: float = 0.0
    spike_score: float = 0.0
    current_titles: List[str] = []

def build_demo_transactions():
    push = get_random_push()
    txs = parse_push_notification(push)

    # 혹시 단건/문자 파싱 결과가 1개뿐이어도 동작은 하게 둠
    for tx in txs:
        tx["category"] = categorize_store(tx.get("merchant", ""))

    return txs

def safe_generate_card(fhi, features, impulsive_score, spike_score, current_titles=None):
    current_titles = current_titles or []
    try:
        card = generate_coaching_card(
            fhi=fhi,
            features=features,
            impulsive_score=impulsive_score,
            spike_score=spike_score,
        )
        if not card.get("title"):
            raise ValueError("빈 카드 생성")
        return card
    except Exception:
        candidates = [c for c in FALLBACK_CARDS if c["title"] not in current_titles]
        if not candidates:
            candidates = FALLBACK_CARDS
        card = random.choice(candidates).copy()
        card["fhi"] = fhi
        card["grade"] = "양호 🟢" if fhi >= 80 else "주의 🟡" if fhi >= 60 else "위험 🔴"
        card["raw"] = "fallback"
        return card

@app.get("/")
def root():
    return {"message": "FINNUT demo API running"}

@app.post("/demo/home")
def demo_home():
    txs = build_demo_transactions()

    result = calculate_fhi_from_transactions(txs, mode="ml")
    features = build_features_from_transactions(txs)

    fhi = result["fhi"]
    impulsive_score = result["impulsive"].get("impulsive_score", 0.0)
    spike_score = result["spike"].get("spike_score", 0.0)

    cards = []
    current_titles = []
    for _ in range(3):
        card = safe_generate_card(
            fhi=fhi,
            features=features,
            impulsive_score=impulsive_score,
            spike_score=spike_score,
            current_titles=current_titles
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
    card = safe_generate_card(
        fhi=req.fhi,
        features=req.features,
        impulsive_score=req.impulsive_score,
        spike_score=req.spike_score,
        current_titles=req.current_titles
    )
    return card 