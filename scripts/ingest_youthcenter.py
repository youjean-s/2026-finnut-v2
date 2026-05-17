"""
온통청년 청년정책 API → policies + policy_eligibility 테이블 수집 스크립트

[API 키 설정 방법 - 둘 중 하나]
  방법 A) .env 파일에 추가:
      YOUTHCENTER_API_KEY=발급받은키값

  방법 B) 이 파일 상단 API_KEY 변수에 직접 입력:
      API_KEY = "발급받은키값"

[실행]
    python scripts/ingest_youthcenter.py

[온통청년 API 실제 스펙]
    GET https://www.youthcenter.go.kr/go/ythip/getPlcy
    파라미터:
        apiKeyNm  : 인증키 (필수)
        pageNum   : 페이지 번호 (1부터)
        pageSize  : 페이지당 건수
        rtnType   : json
    응답: { resultCode, result: { pagging: { totCount }, youthPolicyList: [...] } }
"""

import os
import sys
import json
import math
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.db import get_conn, init_db, now_iso

load_dotenv(dotenv_path=".env")
API_KEY = os.getenv("YOUTHCENTER_API_KEY", "")

if not API_KEY:
    raise ValueError(
        "YOUTHCENTER_API_KEY가 없습니다.\n"
        "  방법 A) .env 파일에  YOUTHCENTER_API_KEY=키값  추가\n"
        "  방법 B) 이 스크립트 상단 API_KEY = '키값' 에 직접 입력"
    )

BASE_URL  = "https://www.youthcenter.go.kr/go/ythip/getPlcy"
PAGE_SIZE = 100
MAX_PAGES = 300
SLEEP_SEC = 0.3

LCLSF_TO_CATEGORY = {
    "일자리":         "employment",
    "주거":           "housing",
    "교육":           "education",
    "교육･직업훈련":  "education",
    "금융･복지･문화": "welfare",
    "복지문화":       "welfare",
    "참여권리":       "participation",
}


def _parse_date(s):
    if not s:
        return None
    s = str(s).strip().replace("-", "").replace(".", "").replace(" ", "")
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return None


def _build_status(row):
    se_cd = (row.get("aplyPrdSeCd") or "").strip()
    if se_cd == "0057002":
        return "진행중"
    if se_cd == "0057003":
        return "마감"

    aply_ymd = row.get("aplyYmd") or ""
    if "~" in aply_ymd:
        parts = aply_ymd.split("~")
        start = _parse_date(parts[0].strip())
        end   = _parse_date(parts[1].strip())
    else:
        start = _parse_date(row.get("bizPrdBgngYmd") or "")
        end   = _parse_date(row.get("bizPrdEndYmd") or "")

    if start and end:
        today = datetime.today().date()
        s = datetime.strptime(start, "%Y-%m-%d").date()
        e = datetime.strptime(end,   "%Y-%m-%d").date()
        if s <= today <= e:
            return "진행중"
        elif today < s:
            return "예정"
        else:
            return "마감"
    return "정보없음"


def _build_policy_key(row):
    plcy_no = (row.get("plcyNo") or "").strip()
    if plcy_no:
        return f"youthcenter:{plcy_no}"
    import hashlib
    base = f"{row.get('plcyNm', '')}|{row.get('sprvsnInstCdNm', '')}"
    return f"youthcenter:hash:{hashlib.sha1(base.encode()).hexdigest()}"


def _build_condition(row):
    parts = []
    try:
        min_int = int(row.get("sprtTrgtMinAge") or 0)
        max_int = int(row.get("sprtTrgtMaxAge") or 0)
        if min_int > 0 or max_int > 0:
            parts.append(f"연령: {min_int or '?'}~{max_int or '?'}세")
    except (ValueError, TypeError):
        pass
    add_cnd = (row.get("addAplyQlfcCndCn") or "").strip()
    if add_cnd and add_cnd not in ("해당없음", "-"):
        parts.append(f"신청자격: {add_cnd}")
    earn_etc = (row.get("earnEtcCn") or "").strip()
    if earn_etc and earn_etc not in ("해당없음", "-"):
        parts.append(f"소득조건: {earn_etc}")
    return "\n".join(parts)


def _build_source_meta(row):
    return {
        "plcyNo":         row.get("plcyNo"),
        "lclsfNm":        row.get("lclsfNm"),
        "mclsfNm":        row.get("mclsfNm"),
        "minAge":         row.get("sprtTrgtMinAge"),
        "maxAge":         row.get("sprtTrgtMaxAge"),
        "schoolCd":       row.get("schoolCd"),
        "jobCd":          row.get("jobCd"),
        "sbizCd":         row.get("sbizCd"),
        "earnCndSeCd":    row.get("earnCndSeCd"),
        "mrgSttsCd":      row.get("mrgSttsCd"),
        "aplyPrdSeCd":    row.get("aplyPrdSeCd"),
        "plcyKywdNm":     row.get("plcyKywdNm"),
        "sprvsnInstCdNm": row.get("sprvsnInstCdNm"),
        "zipCd":          row.get("zipCd"),
    }


def _convert_row(row, fetched_at):
    lclsf_nm   = (row.get("lclsfNm") or "").strip()
    category   = LCLSF_TO_CATEGORY.get(lclsf_nm, "youth")
    aply_ymd   = row.get("aplyYmd") or ""

    if "~" in aply_ymd:
        parts      = aply_ymd.split("~")
        start_date = _parse_date(parts[0].strip())
        end_date   = _parse_date(parts[1].strip())
    else:
        start_date = _parse_date(row.get("bizPrdBgngYmd") or "")
        end_date   = _parse_date(row.get("bizPrdEndYmd") or "")

    return {
        "policy_key":  _build_policy_key(row),
        "name":        (row.get("plcyNm") or "").strip(),
        "category":    category,
        "provider":    (row.get("sprvsnInstCdNm") or "").strip(),
        "period":      aply_ymd.strip(),
        "start_date":  start_date,
        "end_date":    end_date,
        "status":      _build_status(row),
        "link":        (row.get("aplyUrlAddr") or row.get("refUrlAddr1") or "").strip(),
        "condition":   _build_condition(row),
        "benefit":     (row.get("plcySprtCn") or row.get("plcyExplnCn") or "").strip(),
        "source":      "youthcenter",
        "source_id":   (row.get("plcyNo") or "").strip(),
        "fetched_at":  fetched_at,
        "source_meta": json.dumps(_build_source_meta(row), ensure_ascii=False),
        "raw_json":    json.dumps(row, ensure_ascii=False),
    }


def _build_eligibility(policy_id, row, ts):
    try:
        min_age = int(row.get("sprtTrgtMinAge") or 0) or None
        max_age = int(row.get("sprtTrgtMaxAge") or 0) or None
    except (ValueError, TypeError):
        min_age = max_age = None

    school_cd       = (row.get("schoolCd") or "")
    student_required = (1 if any(c in school_cd for c in ["0049002", "0049005"]) else None)

    keywords = []
    kwd_nm   = row.get("plcyKywdNm") or ""
    if kwd_nm:
        keywords += [k.strip() for k in kwd_nm.split(",") if k.strip()]
    mclsf_nm = (row.get("mclsfNm") or "").strip()
    if mclsf_nm and mclsf_nm not in keywords:
        keywords.append(mclsf_nm)

    earn_cd     = (row.get("earnCndSeCd") or "").strip()
    income_type = "연소득" if earn_cd == "0043002" else None

    return {
        "policy_id":           policy_id,
        "min_age":             min_age,
        "max_age":             max_age,
        "region":              "전국",
        "student_required":    student_required,
        "income_type":         income_type,
        "income_max_percent":  None,
        "income_max_quintile": None,
        "keywords_json":       json.dumps(keywords, ensure_ascii=False),
        "evidence_json":       json.dumps({
            "schoolCd":    row.get("schoolCd"),
            "jobCd":       row.get("jobCd"),
            "sbizCd":      row.get("sbizCd"),
            "earnCndSeCd": row.get("earnCndSeCd"),
        }, ensure_ascii=False),
        "updated_at": ts,
    }


def _fetch_page(page_index, display):
    resp = requests.get(
        BASE_URL,
        params={
            "apiKeyNm": API_KEY,
            "pageNum":  page_index,
            "pageSize": display,
            "rtnType":  "json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data   = resp.json()
    result = data.get("result", {})
    total  = result.get("pagging", {}).get("totCount", 0)
    items  = result.get("youthPolicyList", [])
    return {"totalCount": total, "youthPolicyList": items}


def _save_policies(policies, rows_map, ts):
    conn = get_conn()
    cur  = conn.cursor()

    for p in policies:
        cur.execute("""
            INSERT INTO policies
            (policy_key, name, category, provider, period, start_date, end_date,
             status, link, condition, benefit, source, source_id, fetched_at,
             source_meta, raw_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(policy_key) DO UPDATE SET
                name=excluded.name, category=excluded.category,
                provider=excluded.provider, period=excluded.period,
                start_date=excluded.start_date, end_date=excluded.end_date,
                status=excluded.status, link=excluded.link,
                condition=excluded.condition, benefit=excluded.benefit,
                source=excluded.source, source_id=excluded.source_id,
                fetched_at=excluded.fetched_at,
                source_meta=excluded.source_meta, raw_json=excluded.raw_json;
        """, (
            p["policy_key"], p["name"],       p["category"],  p["provider"],
            p["period"],     p["start_date"], p["end_date"],  p["status"],
            p["link"],       p["condition"],  p["benefit"],
            p["source"],     p["source_id"],  p["fetched_at"],
            p["source_meta"], p["raw_json"],
        ))

        cur.execute("SELECT id FROM policies WHERE policy_key=?", (p["policy_key"],))
        row_id = cur.fetchone()
        if row_id:
            elig = _build_eligibility(row_id[0], rows_map.get(p["policy_key"], {}), ts)
            cur.execute("""
                INSERT INTO policy_eligibility
                (policy_id, min_age, max_age, region, student_required,
                 income_type, income_max_percent, income_max_quintile,
                 keywords_json, evidence_json, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(policy_id) DO UPDATE SET
                    min_age=excluded.min_age, max_age=excluded.max_age,
                    region=excluded.region, student_required=excluded.student_required,
                    income_type=excluded.income_type,
                    income_max_percent=excluded.income_max_percent,
                    income_max_quintile=excluded.income_max_quintile,
                    keywords_json=excluded.keywords_json,
                    evidence_json=excluded.evidence_json,
                    updated_at=excluded.updated_at;
            """, (
                elig["policy_id"], elig["min_age"], elig["max_age"],
                elig["region"], elig["student_required"], elig["income_type"],
                elig["income_max_percent"], elig["income_max_quintile"],
                elig["keywords_json"], elig["evidence_json"], elig["updated_at"],
            ))

    conn.commit()
    conn.close()


def run():
    print("=== FINNUT 온통청년 정책 수집 시작 ===")
    init_db()
    fetched_at  = now_iso()
    total_saved = 0

    print("[1/2] 전체 건수 확인 중...")
    try:
        first = _fetch_page(1, PAGE_SIZE)
    except Exception as e:
        print(f"❌ API 호출 실패: {e}")
        return

    total_count = int(first.get("totalCount") or 0)
    items_first = first.get("youthPolicyList") or []
    print(f"  → 총 {total_count}건")

    if total_count == 0:
        print("수집할 데이터가 없습니다.")
        return

    total_pages = min(math.ceil(total_count / PAGE_SIZE), MAX_PAGES)
    print(f"[2/2] {total_pages}페이지 수집 시작...")

    for page in range(1, total_pages + 1):
        try:
            if page == 1:
                items = items_first
            else:
                time.sleep(SLEEP_SEC)
                data  = _fetch_page(page, PAGE_SIZE)
                items = data.get("youthPolicyList") or []

            if not items:
                print(f"  페이지 {page}: 데이터 없음, 종료")
                break

            policies = []
            rows_map = {}
            for row in items:
                p = _convert_row(row, fetched_at)
                policies.append(p)
                rows_map[p["policy_key"]] = row

            _save_policies(policies, rows_map, fetched_at)
            total_saved += len(policies)
            print(f"  페이지 {page}/{total_pages}: {len(policies)}건 저장 (누계 {total_saved}건)")

        except Exception as e:
            print(f"  ⚠️ 페이지 {page} 실패: {e}")
            continue

    print(f"\n=== 완료! 총 {total_saved}건 수집 → policies + policy_eligibility 저장 ===")


if __name__ == "__main__":
    run()
