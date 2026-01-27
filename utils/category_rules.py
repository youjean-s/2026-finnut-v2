import re

def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    # 지점/점/센터 같은 꼬리 제거(너무 공격적이면 1주차 후반에 조정)
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"(지점|점|센터|본점)$", "", s)
    return s

def categorize_store(store_name: str) -> str:
    """
    Map store names to spending categories using keyword rules.
    """
    store_n = _norm(store_name)

    rules = {
        "편의점": ["GS25", "CU", "세븐일레븐", "이마트24"],
        "카페": ["스타벅스", "이디야", "폴바셋", "커피"],
        "식비": ["맥도날드", "버거킹", "김밥", "식당", "한식"],
        "교통": ["지하철", "버스", "택시", "대중교통"],
        "쇼핑": ["무신사", "올리브영", "다이소", "백화점", "현대백화점"],
        "주거": ["관리비", "월세", "전기", "가스"],
        "뷰티": ["헤어", "네일", "미용"],
    }

    for category, keywords in rules.items():
        if any(_norm(k) in store_n for k in keywords):
            return category

    return "기타"

