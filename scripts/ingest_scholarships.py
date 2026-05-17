import os
import json
import hashlib
import requests
from dotenv import load_dotenv
from datetime import datetime
from app.db import get_conn, init_db, now_iso

# ============================
# 환경변수 로드
# ============================
load_dotenv(dotenv_path=".env")
SERVICE_KEY = os.getenv("SERVICE_KEY")

if not SERVICE_KEY:
    raise ValueError("ERROR: .env 파일에 SERVICE_KEY가 없습니다!")

# ============================
# 설정
# ============================
BASE_URL = "https://api.odcloud.kr/api/15028252/v1"

# 월별 UDDI 엔드포인트 목록
KOSAF_UDDIS = [
    "uddi:f8a232e7-c6ce-47c0-b9ef-e4d6aa58ff3f", #2026-04-24 업데이트
]

# ============================
# 날짜 파싱
# ============================
def parse_date(date_str: str):
    if not date_str or date_str == "-":
        return None

    s = str(date_str).replace(".", "-").replace("/", "-").strip()
    parts = s.split("-")
    if len(parts) == 3:
        y, m, d = parts
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    return None


# ============================
# 기간/상태 계산
# ============================
def build_period_and_status(row):
    start_raw = row.get("모집시작일", "")
    end_raw = row.get("모집종료일", "")

    start = parse_date(start_raw)
    end = parse_date(end_raw)

    today = datetime.today().date()

    if start and end:
        s = datetime.strptime(start, "%Y-%m-%d").date()
        e = datetime.strptime(end, "%Y-%m-%d").date()

        if s <= today <= e:
            status = "진행중"
        elif today < s:
            status = "예정"
        else:
            status = "마감"
    else:
        status = "정보없음"

    return {
        "period": f"{start or start_raw} ~ {end or end_raw}",
        "start": start,
        "end": end,
        "status": status
    }


# ============================
# 신청 자격(조건) 생성
# ============================
def build_condition(row):
    fields = [
        ("신청대상", row.get("신청대상")),
        ("지원대상", row.get("지원대상")),
        ("성적기준", row.get("성적기준 상세내용")),
        ("소득기준", row.get("소득기준 상세내용")),
        ("특정자격", row.get("특정자격 상세내용")),
        ("지역거주", row.get("지역거주여부 상세내용")),
        ("자격제한", row.get("자격제한 상세내용")),
    ]

    lines = []
    for label, value in fields:
        if value and str(value).strip() and value != "-":
            lines.append(f"{label}: {str(value).strip()}")

    return "\n".join(dict.fromkeys(lines))


# ============================
# 지원내용(benefit) 생성
# ============================
def build_benefit(row):
    fields = [
        row.get("지원내역 상세내용"),
        row.get("지원내역"),
        row.get("지원금액"),
        row.get("장학금액"),
        row.get("급여"),
    ]

    for f in fields:
        if f and str(f).strip() and f != "-":
            return str(f).strip()

    return ""


# ============================
# policy_key 생성 (안정적 UNIQUE)
# ============================
def build_policy_key(name: str, provider: str, link: str):
    base = f"{name}|{provider}|{link}".strip()
    h = hashlib.sha1(base.encode("utf-8")).hexdigest()
    return f"odcloud-kosaf:{h}"


# ============================
# API 호출
# ============================
def fetch_api(uddi, page=1, perPage=1500):
    url = f"{BASE_URL}/{uddi}"
    params = {
        "page": page,
        "perPage": perPage,
        "serviceKey": SERVICE_KEY
    }

    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()

    return r.json().get("data", [])


# ============================
# rows -> policies items
# ============================
def convert_to_policies(rows, source_uddi: str, fetched_at: str):
    out = []

    for row in rows:
        period_data = build_period_and_status(row)

        name = row.get("상품명") or ""
        provider = row.get("운영기관명", "") or ""
        link = row.get("홈페이지 주소", "") or ""

        out.append({
            "policy_key": build_policy_key(name, provider, link),
            "name": name,
            "category": "scholarship",
            "provider": provider,
            "period": period_data["period"],
            "start_date": period_data["start"],
            "end_date": period_data["end"],
            "status": period_data["status"],
            "link": link,
            "condition": build_condition(row),
            "benefit": build_benefit(row),
            "source": "odcloud-kosaf",
            "source_id": source_uddi,
            "fetched_at": fetched_at,
            "raw_json": json.dumps(row, ensure_ascii=False)
        })

    return out


# ============================
# DB 저장 (policies upsert)
# ============================
def save_to_db(policies):
    conn = get_conn()
    cur = conn.cursor()

    for p in policies:
        cur.execute("""
            INSERT INTO policies
            (policy_key, name, category, provider, period, start_date, end_date, status, link,
             condition, benefit, source, source_id, fetched_at, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(policy_key)
            DO UPDATE SET
                name = excluded.name,
                category = excluded.category,
                provider = excluded.provider,
                period = excluded.period,
                start_date = excluded.start_date,
                end_date = excluded.end_date,
                status = excluded.status,
                link = excluded.link,
                condition = excluded.condition,
                benefit = excluded.benefit,
                source = excluded.source,
                source_id = excluded.source_id,
                fetched_at = excluded.fetched_at,
                raw_json = excluded.raw_json;
        """, (
            p["policy_key"],
            p["name"],
            p["category"],
            p["provider"],
            p["period"],
            p["start_date"],
            p["end_date"],
            p["status"],
            p["link"],
            p["condition"],
            p["benefit"],
            p["source"],
            p["source_id"],
            p["fetched_at"],
            p["raw_json"]
        ))

    conn.commit()
    conn.close()


# ============================
# 실행
# ============================
def run():
    print("=== FINNUT 장학금 데이터 수집 시작 (-> policies) ===")
    init_db()

    fetched_at = now_iso()
    total = 0

    for uddi in KOSAF_UDDIS:
        try:
            print(f"[UDDI] {uddi} 수집 중...")
            rows = fetch_api(uddi)
            print(f" → {len(rows)}건 수집")

            policies = convert_to_policies(rows, source_uddi=uddi, fetched_at=fetched_at)
            save_to_db(policies)

            total += len(policies)

        except Exception as e:
            print(f"⚠️ {uddi} 실패:", e)
            continue

    print(f"=== 완료! 총 {total}건 처리됨 (policies 저장) ===")


if __name__ == "__main__":
    run()