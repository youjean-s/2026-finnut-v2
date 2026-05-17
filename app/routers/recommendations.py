from typing import List, Optional, Dict, Any, Tuple
from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.db import get_conn

router = APIRouter(tags=["recommendations"])

ALLOWED_STATUS = {"진행중", "예정", "마감", "정보없음"}


class RecommendationRequest(BaseModel):
    age: Optional[int] = Field(default=None, ge=0, le=120)
    student: Optional[bool] = None
    region: Optional[str] = None  # "서울", "경기", "전국" 등 (텍스트 매칭)
    category_preference: Optional[str] = None  # scholarship/housing/employment/subsidy
    keywords: List[str] = Field(default_factory=list)  # ["학자금", "주거", "취업"] 등
    top_n: int = Field(default=10, ge=1, le=50)

    # ✅ (A) 마감 제외 옵션
    exclude_closed: bool = Field(default=True, description="true면 status='마감' 정책 제외")

    # ✅ (B) 근거문장 하이라이트 옵션
    include_snippets: bool = Field(default=True, description="true면 조건/혜택에서 키워드 근거 snippet 포함")
    snippet_window: int = Field(default=40, ge=10, le=120, description="snippet 앞뒤 문자 수")


def _norm(s: Optional[str]) -> str:
    return (s or "").strip()


def _all_keywords(req: RecommendationRequest) -> List[str]:
    kws: List[str] = []
    # 사용자 키워드
    for k in req.keywords:
        k = _norm(k)
        if k:
            kws.append(k)

    # region도 사실상 키워드로 취급
    if req.region:
        kws.append(_norm(req.region))

    # student이면 학생 관련 토큰도 근거 탐색에 포함
    if req.student is True:
        kws += ["대학생", "재학생", "학부", "대학원", "학생"]

    # age가 청년 범위면 '청년'도 근거 탐색에 포함
    if req.age is not None and 19 <= req.age <= 34:
        kws += ["청년", "청년층"]

    # 중복 제거(순서 유지)
    out: List[str] = []
    seen = set()
    for k in kws:
        if k and k not in seen:
            out.append(k)
            seen.add(k)
    return out


def _find_snippet(text: str, keyword: str, window: int) -> Optional[str]:
    if not text or not keyword:
        return None
    idx = text.find(keyword)
    if idx == -1:
        return None
    start = max(0, idx - window)
    end = min(len(text), idx + len(keyword) + window)
    snippet = text[start:end].replace("\n", " ").strip()
    # 보기 좋게 앞뒤 생략 표기
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet


def _collect_snippets(policy: Dict[str, Any], req: RecommendationRequest) -> List[Dict[str, str]]:
    if not req.include_snippets:
        return []

    condition = _norm(policy.get("condition"))
    benefit = _norm(policy.get("benefit"))
    name = _norm(policy.get("name"))
    provider = _norm(policy.get("provider"))

    window = req.snippet_window
    kws = _all_keywords(req)

    snippets: List[Dict[str, str]] = []
    # 우선순위: name -> condition -> benefit -> provider
    sources: List[Tuple[str, str]] = [
        ("name", name),
        ("condition", condition),
        ("benefit", benefit),
        ("provider", provider),
    ]

    for kw in kws:
        for source_name, text in sources:
            snip = _find_snippet(text, kw, window)
            if snip:
                snippets.append({"keyword": kw, "source": source_name, "snippet": snip})
                break  # 같은 kw는 한 번만

        if len(snippets) >= 6:  # 너무 길어지지 않게 제한
            break

    return snippets


def _score_policy(p: Dict[str, Any], req: RecommendationRequest) -> Dict[str, Any]:
    name = _norm(p.get("name"))
    category = _norm(p.get("category"))
    provider = _norm(p.get("provider"))
    status = _norm(p.get("status"))
    condition = _norm(p.get("condition"))
    benefit = _norm(p.get("benefit"))

    blob = " ".join([name, category, provider, status, condition, benefit])

    score = 0
    reasons: List[str] = []

    # 상태 기반
    if status == "진행중":
        score += 30
        reasons.append("현재 신청 가능(진행중)")
    elif status == "예정":
        score += 10
        reasons.append("곧 신청 시작(예정)")
    elif status == "마감":
        score -= 50
        reasons.append("현재 마감")
    else:
        score += 0

    # 카테고리 선호
    if req.category_preference and category == req.category_preference.strip():
        score += 40
        reasons.append(f"선호 카테고리 일치({category})")

    # 지역(텍스트 매칭)
    if req.region:
        r = req.region.strip()
        if r and (r in blob or ("전국" in blob)):
            score += 15
            reasons.append(f"지역 관련 키워드 매칭({r}/전국)")

    # 학생 여부(텍스트 매칭)
    if req.student is True:
        student_tokens = ["대학생", "재학생", "학부", "대학원", "학생"]
        if any(t in blob for t in student_tokens):
            score += 20
            reasons.append("대학생/학생 대상 키워드 매칭")

    # 나이 기반(아주 단순: '청년' 키워드)
    if req.age is not None:
        if 19 <= req.age <= 34 and ("청년" in blob or "청년층" in blob):
            score += 10
            reasons.append("청년 대상 키워드 매칭")

    # 사용자 키워드 매칭
    for kw in req.keywords:
        k = _norm(kw)
        if not k:
            continue
        if k in name:
            score += 10
            reasons.append(f"키워드 '{k}'가 정책명에 포함")
        elif k in blob:
            score += 5
            reasons.append(f"키워드 '{k}'가 조건/혜택/기관에 포함")

    return {
        "score": score,
        "reasons": reasons[:6],
    }


@router.post("/recommendations")
def recommend(req: RecommendationRequest) -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor()

    # 후보군 제한(최대 800) + status 우선 정렬
    cur.execute(
        """
        SELECT
            id, policy_key, name, category, provider,
            period, start_date, end_date, status,
            link, condition, benefit,
            source, source_id, fetched_at
        FROM policies
        ORDER BY
            CASE status
                WHEN '진행중' THEN 1
                WHEN '예정' THEN 2
                WHEN '마감' THEN 3
                ELSE 4
            END,
            start_date DESC,
            id DESC
        LIMIT 800
        """
    )
    rows = cur.fetchall()
    conn.close()

    candidates: List[Dict[str, Any]] = []

    for r in rows:
        p = {
            "id": r[0],
            "policy_key": r[1],
            "name": r[2],
            "category": r[3],
            "provider": r[4],
            "period": r[5],
            "start_date": r[6],
            "end_date": r[7],
            "status": r[8],
            "link": r[9],
            "condition": r[10],
            "benefit": r[11],
            "source": r[12],
            "source_id": r[13],
            "fetched_at": r[14],
        }

        status = _norm(p.get("status"))
        if req.exclude_closed and status == "마감":
            continue  # ✅ (A) 마감 제외

        sc = _score_policy(p, req)
        p["score"] = sc["score"]
        p["reasons"] = sc["reasons"]

        # ✅ (B) 근거 snippet
        p["snippets"] = _collect_snippets(p, req)

        candidates.append(p)

    candidates.sort(key=lambda x: x["score"], reverse=True)

    # 너무 낮은 점수는 컷(마감 제외여도 품질용)
    top = [p for p in candidates if p["score"] > -20][: req.top_n]

    return {
        "top_n": req.top_n,
        "returned": len(top),
        "exclude_closed": req.exclude_closed,
        "include_snippets": req.include_snippets,
        "items": top,
    }