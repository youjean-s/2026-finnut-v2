"""
app/services/mission_verifier.py
----------------------------------
미션 실행 검증 (사진 기반 / 거래내역 기반)
"""
import base64
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

from typing import Dict, Any, List

from app.db import get_conn


def verify_transactions(
    user_id: int,
    period_start: str,
    period_end: str,
    keywords: List[str],
) -> Dict[str, Any]:
    """
    기간 내 거래내역 중 keywords(배달앱 이름 등)와 매칭되는 가맹점명이 있는지 확인.
    매칭 0건 -> 미션 성공(약속을 지킴), 매칭 있음 -> 실패.
    """
    if not keywords:
        return {
            "success": False,
            "reason": "검증 키워드가 설정되지 않았습니다.",
            "matched_transactions": [],
        }

    conn = get_conn()
    cur = conn.cursor()

    like_clauses = " OR ".join(["merchant LIKE ?"] * len(keywords))
    params = [user_id, period_start, period_end] + [f"%{kw}%" for kw in keywords]

    cur.execute(
        f"""SELECT tx_datetime, merchant, amount FROM transactions
            WHERE user_id = ?
              AND tx_datetime >= ?
              AND tx_datetime <= ?
              AND ({like_clauses})
            ORDER BY tx_datetime""",
        params,
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return {
            "success": True,
            "reason": f"{period_start} ~ {period_end} 기간 동안 해당 가맹점 거래 내역이 없습니다.",
            "matched_transactions": [],
        }

    matched = [
        {"datetime": r["tx_datetime"], "merchant": r["merchant"], "amount": r["amount"]}
        for r in rows
    ]
    return {
        "success": False,
        "reason": f"{matched[0]['merchant']} 등 {len(matched)}건의 거래가 발견되었습니다.",
        "matched_transactions": matched,
    }

def verify_photo(photo_path: str, mission_text: str) -> Dict[str, Any]:
    """
    업로드된 사진이 미션 내용(mission_text)과 맞는지 Vision LLM으로 판별.
    """
    try:
        with open(photo_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")
    except FileNotFoundError:
        return {"success": False, "reason": "사진 파일을 찾을 수 없습니다.", "confidence": "low"}

    ext = os.path.splitext(photo_path)[1].lower().lstrip(".")
    mime = "jpeg" if ext in ("jpg", "jpeg") else ext or "jpeg"

    prompt = f"""
당신은 사용자가 금융 습관 미션을 실제로 실천했는지 사진으로 확인하는 검증관입니다.

[미션 내용]
{mission_text}

[작업]
사진을 보고 이 미션이 실제로 수행되었다고 볼 수 있는지 판단하세요.
너무 엄격하게 판단하지 말고, 상식적으로 미션과 관련 있어 보이면 성공으로 처리하세요.

[출력 형식 - 반드시 아래 형식 그대로]
판정: (성공 또는 실패)
이유: (한 줄 이유)
신뢰도: (높음, 보통, 낮음 중 하나)
""".strip()

    try:
        response = client.chat.completions.create(
            model="gpt-5.4-mini",
            messages=[
                {"role": "system", "content": "당신은 사진을 보고 미션 수행 여부를 판별하는 검증관입니다."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/{mime};base64,{image_b64}"},
                        },
                    ],
                },
            ],
            max_completion_tokens=200,
            temperature=0.2,
        )
        raw = response.choices[0].message.content.strip()
    except Exception as e:
        return {"success": False, "reason": f"검증 중 오류 발생: {e}", "confidence": "low"}

    return _parse_verification(raw)


def _parse_verification(raw: str) -> Dict[str, Any]:
    result = {"success": False, "reason": "", "confidence": "low"}
    for line in raw.splitlines():
        if line.startswith("판정:"):
            result["success"] = "성공" in line
        elif line.startswith("이유:"):
            result["reason"] = line.split(":", 1)[1].strip()
        elif line.startswith("신뢰도:"):
            conf = line.split(":", 1)[1].strip()
            result["confidence"] = {"높음": "high", "보통": "medium", "낮음": "low"}.get(conf, "low")
    return result    