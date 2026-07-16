from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db import init_db
from app.routers.scholarships import router as scholarships_router
from app.routers.policies import router as policies_router
from app.routers.recommendations import router as recommendations_router
from app.routers.users import router as users_router
from app.routers.eligibility import router as eligibility_router
from app.routers.user_recommendations import router as user_recommendations_router
from app.routers.fhi import router as fhi_router
from app.routers.missions import router as missions_router
from app.routers.transactions import router as transactions_router   # 추가
app = FastAPI(
    title="FINNUT Backend",
    description="장학금/청년정책 추천 + 금융건강지수(FHI) 분석 통합 API",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 서버 시작 시 DB 초기화 (테이블 생성 + 마이그레이션)
init_db()


@app.get("/health")
def health_check():
    return {"status": "ok"}


# 정책/장학금 관련
app.include_router(scholarships_router)
app.include_router(policies_router)
app.include_router(recommendations_router)
app.include_router(users_router)
app.include_router(eligibility_router)
app.include_router(user_recommendations_router)

# FHI 분석
app.include_router(fhi_router)
app.include_router(missions_router)
app.include_router(transactions_router)
