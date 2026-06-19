# Team 이루리 | 대학(원)생의 생활비 부담 완화를 위한 소비습관 개선 및 장학·복지 정보 추천 어플리케이션: FINNUT

이 저장소는 이화여자대학교 졸업프로젝트 그로쓰 수업 (2026 Spring)을 위한
**팀 이루리(Iruri)**의 **초기 기획 및 핵심 기술 검증용** 레포지토리입니다.

---

## 📌 프로젝트에 대한 설명

FINNUT은 대학(원)생의 생활비 부담 완화를 위한 소비습관 개선 및 장학·복지 정보 추천 어플리케이션 입니다. 

| 구분 | 내용 |
| --- | --- |
| **프로젝트명** | 대학(원)생의 생활비 부담 완화를 위한 소비습관 개선 및 장학·복지 정보 추천 어플리케이션: FINNUT |
| **주제** | 청년층의 재정적 불안정 해소 및 금융 습관 개선 |
| **핵심 목표** | 1) AI 기반 FHI 엔진을 통한 위험 소비 패턴 진단 및 코칭  2) API 및 웹 크롤링을 통한 흩어진 청년 복지/장학금 정보 자동 매칭 |
| **상태** | 핵심 로직 구현 및 기술 검증 완료 (Rule-based FHI + LightGBM 예측, 정책 데이터 수집/매칭) |

### 팀 구성

| 역할 | 담당 팀원 | 주요 기여 내용 |
| :--- | :--- | :--- |
| **PM & AI/Backend** | **송유진** | FHI 엔진(파싱, 충동/급증 지수) 및 LightGBM 예측 파이프라인 설계·구현, 프로젝트 총괄 |
| **Backend/DB** | **임슬민** | 한국장학재단 API 연동 및 데이터 수집 파이프라인(DB 적재) 구현 |
| **Frontend/Backend** | **정서진** | 복지/장학금 정책 매칭 로직 개발 및 Android 클라이언트 구성 |

### 기술 스택

| 영역 | 주요 기술/패키지 | 활용 목적 |
| :--- | :--- | :--- |
| **Backend** | **FastAPI**, **uvicorn** | FHI 분석, 정책/장학금 매칭 API 서버 |
| **AI/ML** | **LightGBM** | FHI 하락 예측(7일 후 예상 FHI) 및 이상 소비 패턴 탐지를 위한 ML 모델 학습 |
| **코칭/NLG** | **ChatGPT API (gpt-4o-mini)** | FHI 진단 결과 기반, 사용자 맞춤형 코칭 카드 생성 |
| **데이터 처리** | **Python (pandas, re, datetime)** | 카드 알림 텍스트 파싱 및 FHI 지표 계산 |
| **정보 수집** | **공공데이터 API (한국장학재단, 온통청년)** & **웹 크롤러** | 장학금 및 청년 복지/금융사 혜택 정보 통합 확보 |
| **DB** | **SQLite** | 장학금/정책/사용자 데이터 저장 |
| **모바일 클라이언트** | **Kotlin / Jetpack Compose**, **Room DB** | 온디바이스 데이터 저장 및 UI |

---

## 💻 Source code에 대한 설명

| 폴더/파일 | 설명 |
| :--- | :--- |
| **app/** | FastAPI 백엔드 — 진입점(`main.py`), DB 초기화(`db.py`), 라우터(`routers/`) |
| ┗ `app/routers/fhi.py` | 금융건강지수(FHI) 진단 및 7일 예상 FHI 예측 API |
| ┗ `app/routers/scholarships.py`, `policies.py`, `eligibility.py` | 장학금·정책 조회 및 자격요건 매칭 API |
| ┗ `app/routers/recommendations.py`, `user_recommendations.py` | 사용자 맞춤 추천 API |
| ┗ `app/routers/users.py` | Kakao 소셜 로그인, 사용자 프로필 등록 API |
| **utils/** | FHI 엔진 핵심 로직 — 푸시 알림 파서, FHI 계산기, 충동소비 탐지기, 카테고리 분류 규칙 |
| **ml/** | LightGBM 학습/추론 파이프라인 — `src/`(학습·튜닝 스크립트), `ml_runtime/`(서비스용 feature builder·model loader), `artifacts/`(학습된 모델, 성능 리포트) |
| **scripts/** | 한국장학재단·온통청년 API 연동 및 DB 적재/마이그레이션 스크립트 |
| **mock/** | 푸시 알림 Mock 데이터 에뮬레이터 |
| **demo_pages/** | 정책 매칭, 푸시 파싱 등 핵심 기능 시연 및 테스트 스크립트 |
| **docs/** | 프로젝트 기획, 팀 규칙(`GroundRule.md`), 기술 문서 |
| **data/** | 장학금/정책 DB 파일(`kosaf_scholarships.db`) |
| **requirements.txt** | 프로젝트 환경 설정을 위한 필수 라이브러리 목록 |

### 주요 API

| 분류 | 라우터 |
| :--- | :--- |
| 금융건강지수(FHI) | `app/routers/fhi.py` — 현재 FHI 진단, 7일 예상 FHI 예측 |
| 장학금/정책 매칭 | `app/routers/scholarships.py`, `policies.py`, `eligibility.py`, `recommendations.py`, `user_recommendations.py` |
| 사용자 | `app/routers/users.py` — Kakao 소셜 로그인, 프로필 등록 |

---

## 🔨 How to Build

본 프로젝트는 별도의 컴파일 과정이 없는 Python 기반 서비스이며, "빌드"는 **FHI 예측용 LightGBM 모델 학습**을 의미합니다.

학습된 모델은 이미 `ml/artifacts/models/`에 포함되어 있어 **재학습 없이 바로 사용 가능**합니다. 모델을 처음부터 다시 빌드하고 싶다면 아래 순서로 실행합니다.

```bash
# 1. 피처 엔지니어링
python ml/src/feature_engineering.py

# 2. 라벨 생성
python ml/src/make_labels.py

# 3. 학습/검증 데이터 분리
python ml/src/split_train_val.py

# 4. 베이스라인 모델 학습
python ml/src/train_lgbm_baseline.py

# 5. 하이퍼파라미터 튜닝 (선택)
python ml/src/tune_lgbm_grid.py
```

학습 결과는 `ml/artifacts/reports/`(성능 리포트, feature importance)와 `ml/artifacts/models/`(모델 파일)에 저장됩니다.

---

## ⚙️ How to Install

### 1. 저장소 클론

```bash
git clone https://github.com/youjean-s/2025-fall-iruri-start.git
cd 2025-fall-iruri-start
```

### 2. 가상환경 생성 및 활성화

```bash
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

> Python 3.10 이상 권장

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4. 환경변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 아래 값을 채워주세요.

```env
OPENAI_API_KEY=발급받은_OpenAI_API_키
KOSAF_API_KEY=발급받은_한국장학재단_API_키
```

### 5. 백엔드 서버 실행

```bash
uvicorn app.main:app --reload
```

실행 후 `http://localhost:8000/health` 에서 정상 동작 여부를 확인할 수 있습니다.
DB(`data/kosaf_scholarships.db`)는 이미 저장소에 포함되어 있어 별도 초기화 없이 바로 사용 가능합니다.

---

## ✅ How to Test

핵심 로직(FHI 계산, 카테고리 분류, 푸시 알림 파싱 등)은 `demo_pages/`의 스크립트로 개별 검증합니다.

```bash
# 주차별 케이스 검증
python demo_pages/check_week1_cases.py

# 카테고리 분류 규칙 검증
python demo_pages/check_category_rules.py

# 극단값(이상치) 처리 검증
python demo_pages/check_extremes.py

# Rule-based FHI vs ML 예측 FHI 비교 검증
python demo_pages/check_rule_vs_ml.py

# 전체 파이프라인(E2E) 검증
python demo_pages/check_e2e.py
```

API 서버가 실행 중인 상태에서는 FastAPI 자동 문서(`http://localhost:8000/docs`)를 통해 각 엔드포인트를 직접 호출하며 동작을 확인할 수 있습니다.

---

## 🤝 Ground Rule

팀 규칙은 **`docs/GroundRule.md`**에 정리되어 있습니다.