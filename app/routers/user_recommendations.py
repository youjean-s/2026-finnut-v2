import json
from datetime import date
from typing import List, Optional, Dict, Any, Tuple
from fastapi import APIRouter, Query, HTTPException
from app.db import get_conn

router = APIRouter(tags=["recommendations"])

ALLOWED_STATUS = {"진행중", "예정", "마감", "정보없음"}

def _norm(s: Optional[str]) -> str:
    return (s or "").strip()

def _calc_age(birthdate_str: Optional[str]) -> Optional[int]:
    if not birthdate_str:
        return None
    try:
        birth = date.fromisoformat(birthdate_str)
        today = date.today()
        return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    except:
        return None

def _find_snippet(text: str, keyword: str, window: int) -> Optional[str]:
    if not text or not keyword:
        return None
    idx = text.find(keyword)
    if idx == -1:
        return None
    start = max(0, idx - window)
    end = min(len(text), idx + len(keyword) + window)
    snippet = text[start:end].replace("\n", " ").strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet

def _collect_snippets(policy: Dict[str, Any], keywords: List[str], window: int) -> List[Dict[str, str]]:
    name = _norm(policy.get("name"))
    provider = _norm(policy.get("provider"))
    condition = _norm(policy.get("condition"))
    benefit = _norm(policy.get("benefit"))

    sources: List[Tuple[str, str]] = [
        ("name", name),
        ("condition", condition),
        ("benefit", benefit),
        ("provider", provider),
    ]

    out: List[Dict[str, str]] = []
    for kw in keywords:
        k = _norm(kw)
        if not k:
            continue
        for source_name, text in sources:
            snip = _find_snippet(text, k, window)
            if snip:
                out.append({"keyword": k, "source": source_name, "snippet": snip})
                break
        if len(out) >= 6:
            break
    return out

def _score(policy: Dict[str, Any], user: Dict[str, Any], keywords: List[str]) -> Tuple[int, List[str]]:
    score = 0
    reasons: List[str] = []

    status = _norm(policy.get("status"))
    if status == "진행중":
        score += 30
        reasons.append("현재 신청 가능(진행중)")
    elif status == "예정":
        score += 10
        reasons.append("곧 신청 시작(예정)")
    elif status == "마감":
        score -= 50
        reasons.append("현재 마감")

    blob = " ".join([
        _norm(policy.get("name")),
        _norm(policy.get("provider")),
        _norm(policy.get("condition")),
        _norm(policy.get("benefit")),
    ])
    for k in keywords:
        k = _norm(k)
        if not k:
            continue
        if k in _norm(policy.get("name")):
            score += 10
            reasons.append(f"키워드 '{k}'가 정책명에 포함")
        elif k in blob:
            score += 5
            reasons.append(f"키워드 '{k}'가 조건/혜택/기관에 포함")
    
    # 특정 대상 제한 정책 페널티
    restricted_keywords = ["북한이탈주민", "탈북", "다문화", "장애인", "한부모"]
    blob_text = " ".join([
        _norm(policy.get("name")),
        _norm(policy.get("condition")),
    ])
    for rk in restricted_keywords:
        if rk in blob_text:
            score -= 100
            reasons.append(f"대상 제한({rk}) → 제외")
            break

    # provider 지역 완전 제외
    # provider 지역 완전 제외
# provider 지역 완전 제외
    if user.get("region"):
        provider = _norm(policy.get("provider"))
        name = _norm(policy.get("name"))
        condition = _norm(policy.get("condition"))
        blob_region = f"{provider} {name} {condition}"

        if blob_region:
            user_region = user.get("region", "")

            sido_list = [
                "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
                "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"
            ]
            sigungu_list = [
                "수원", "성남", "고양", "용인", "부천", "안산", "안양", "남양주",
                "화성", "의정부", "평택", "시흥", "파주", "김포", "광명",
                "군포", "이천", "오산", "하남", "의왕", "양평", "여주", "동두천",
                "과천", "구리", "포천", "양주", "가평", "연천", "안성", "의성",
                "인제", "영월", "광양", "충남", "도립"
            ]

            for region_kw in sido_list + sigungu_list:
                if region_kw in blob_region:
                    if region_kw not in user_region:
                        score -= 100
                        reasons.append(f"지역 불일치({region_kw}) → 제외")
                    break

    return score, reasons[:6]

@router.get("/users/{user_id}/recommendations")
def recommend_for_user(
    user_id: int,
    top_n: int = Query(default=10, ge=1, le=50),
    exclude_closed: bool = True,
    include_snippets: bool = True,
    snippet_window: int = Query(default=40, ge=10, le=120),
    keyword: List[str] = Query(default_factory=list, description="추가 검색 키워드(여러 개 가능)"),
) -> Dict[str, Any]:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    u = cur.fetchone()
    if not u:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")

    user = {
        "id": u["id"],
        "age": _calc_age(u["birthdate"]),
        "student": (None if u["student"] is None else bool(u["student"])),
        "region": u["region"],
        "keywords": json.loads(u["keywords_json"] or "[]"),
    }

    keywords = []
    for k in (user["keywords"] + keyword):
        k = _norm(k)
        if k and k not in keywords:
            keywords.append(k)

    if user["student"] is True:
        for t in ["대학생", "재학생", "학부", "대학원", "학생"]:
            if t not in keywords:
                keywords.append(t)
    if user["age"] is not None and 19 <= user["age"] <= 34:
        for t in ["청년", "청년층"]:
            if t not in keywords:
                keywords.append(t)

    where = []
    params: List[Any] = []

    if exclude_closed:
        where.append("(p.status IS NULL OR p.status != '마감')")

    if user["region"]:
        where.append("(e.region IS NULL OR e.region='전국' OR e.region=?)")
        params.append(user["region"])

    if user["age"] is not None:
        where.append("(e.min_age IS NULL OR e.min_age <= ?)")
        where.append("(e.max_age IS NULL OR e.max_age >= ?)")
        params += [user["age"], user["age"]]

    if user["student"] is not None:
        where.append("(e.student_required IS NULL OR e.student_required = ?)")
        params.append(1 if user["student"] else 0)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    cur.execute(f"""
        SELECT
            p.id, p.policy_key, p.name, p.category, p.provider,
            p.period, p.start_date, p.end_date, p.status,
            p.link, p.condition, p.benefit,
            p.source, p.source_id, p.fetched_at
        FROM policies p
        LEFT JOIN policy_eligibility e ON e.policy_id = p.id
        {where_sql}
        ORDER BY
            CASE p.status
                WHEN '진행중' THEN 1
                WHEN '예정' THEN 2
                WHEN '마감' THEN 3
                ELSE 4
            END,
            p.start_date DESC,
            p.id DESC
        LIMIT 800
    """, params)

    rows = cur.fetchall()
    conn.close()

    items: List[Dict[str, Any]] = []
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

        sc, reasons = _score(p, user, keywords)
        p["score"] = sc
        p["reasons"] = reasons

        if include_snippets:
            p["snippets"] = _collect_snippets(p, keywords, snippet_window)
        else:
            p["snippets"] = []

        items.append(p)

    items.sort(key=lambda x: x["score"], reverse=True)
    top = [p for p in items if p["score"] > -20][:top_n]

    return {
        "user": user,
        "top_n": top_n,
        "returned": len(top),
        "exclude_closed": exclude_closed,
        "include_snippets": include_snippets,
        "items": top,
    }