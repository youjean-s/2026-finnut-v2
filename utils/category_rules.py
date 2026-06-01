import re

def _norm(merchant: str) -> str:
    """가맹점명 정규화: 소문자 변환, 공백 제거, 지점 접미사 제거"""
    s = merchant.lower().strip()
    s = re.sub(r'\s+', '', s)
    s = re.sub(r'(지점|점|센터|마트|몰|샵|스토어)$', '', s)
    return s

CATEGORY_LABELS = {
    "convenience":   "편의점·다이소",
    "cafe":          "카페",
    "food":          "식비",
    "transport":     "교통",
    "shopping":      "쇼핑",
    "housing":       "주거·공과금",
    "entertainment": "문화·여가",
    "subscription":  "구독",
    "other":         "기타",
}

CATEGORY_KEYWORDS = {
    "convenience": [
        "gs25", "cu", "세븐일레븐", "7eleven", "미니스톱", "이마트24",
        "편의점", "다이소",
    ],
    "cafe": [
        "스타벅스", "starbucks", "이디야", "투썸플레이스", "twosome",
        "할리스", "폴바셋", "커피빈", "coffeebean", "메가커피", "컴포즈",
        "빽다방", "더벤티", "매머드커피", "카페베네", "카페", "cafe",
        "coffee", "커피", "블루보틀", "테라로사", "공차", "gongcha",
    ],
    "food": [
        "맥도날드", "mcdonalds", "버거킹", "롯데리아", "kfc", "노브랜드버거",
        "맘스터치", "서브웨이", "subway", "피자헛", "도미노", "파파존스",
        "bhc", "bbq", "교촌", "네네치킨", "굽네", "치킨",
        "한솥", "김밥천국", "본죽", "죠스떡볶이",
        "배달의민족", "배민", "요기요", "쿠팡이츠",
        "식당", "레스토랑", "밥집", "분식", "냉면", "삼겹살", "갈비",
        "음식", "도시락", "푸드",
    ],
    "transport": [
        "티머니", "tmoney", "교통카드", "지하철", "버스",
        "카카오택시", "uber", "우버", "타다", "쏘카", "그린카",
        "기차", "ktx", "srt", "코레일",
        "버스터미널", "공항버스", "주차", "파킹",
        "주유", "gs칼텍스", "sk주유소", "현대오일뱅크", "s-oil", "shell",
        "전기차충전", "충전소",
    ],
    "shopping": [
        # 온라인
        "쿠팡", "coupang", "네이버쇼핑", "11번가", "gmarket", "지마켓",
        "auction", "옥션", "위메프", "티몬", "인터파크",
        "무신사", "에이블리", "지그재그", "브랜디", "하이버",
        "아이허브", "iherb", "아마존", "amazon",
        # 오프라인
        "올리브영", "h&m", "zara", "유니클로", "uniqlo",
        "abc마트", "나이키", "nike", "아디다스", "adidas",
        "뉴발란스", "newbalance", "이케아", "ikea",
        # 뷰티
        "네일", "헤어", "화장품", "뷰티", "이니스프리", "아리따움",
        "토니모리", "더페이스샵", "missha", "미샤", "클리오", "롬앤",
        # 의류/잡화
        "의류", "패션", "신발", "가방", "액세서리",
    ],
    "housing": [
        "관리비", "월세", "전기요금", "한국전력", "kepco",
        "수도요금", "가스요금", "도시가스", "한국가스",
        "인터넷", "kt", "sk브로드밴드", "lg유플러스", "lgu+",
        "공과금", "전기", "수도", "난방", "임대",
    ],
    "entertainment": [
        "cgv", "메가박스", "롯데시네마", "영화",
        "공연", "전시", "갤러리", "미술관", "박물관",
        "steam", "스팀", "닌텐도", "nintendo", "게임",
        "노래방", "코인노래", "볼링", "pc방", "방탈출",
        "헬스", "피트니스", "gym", "수영", "스포츠",
        "독서실", "스터디카페",
        "놀이공원", "에버랜드", "롯데월드",
    ],
    "subscription": [
        "netflix", "넷플릭스", "youtube premium", "유튜브프리미엄",
        "spotify", "스포티파이", "apple music", "멜론", "지니뮤직",
        "wavve", "왓챠", "tving", "disney+", "디즈니플러스",
        "naver plus", "네이버플러스", "쿠팡플레이",
        "adobe", "microsoft", "ms365", "notion", "노션",
        "chatgpt", "claude", "copilot",
        "구독", "정기결제", "월정액",
    ],
}

def classify(merchant: str) -> str:
    norm = _norm(merchant)
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in norm:
                return category
    return "other"