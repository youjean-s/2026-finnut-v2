from datetime import datetime, timedelta


def get_beauty_persona_transactions():
    today = datetime.now().date()

    raw_rows = [
        (-36, "12:10", "학생식당", "other", 5500),
        (-35, "18:20", "GS25 이대점", "grocery_pos", 4200),
        (-34, "14:15", "올리브영 신촌점", "shopping_pos", 15000),
        (-33, "19:30", "메가커피", "other", 3500),
        (-32, "16:40", "올리브영 신촌점", "shopping_pos", 18000),
        (-31, "21:50", "네일온 신촌점", "shopping_pos", 38000),
        (-30, "13:25", "학생식당", "other", 5500),
        (-29, "18:10", "올리브영 신촌점", "shopping_pos", 17000),
        (-28, "12:30", "CU", "grocery_pos", 3800),
        (-27, "19:00", "올리브영 신촌점", "shopping_pos", 21000),
        (-26, "22:10", "올리브영 신촌점", "shopping_pos", 13000),
        (-26, "22:40", "올리브영 신촌점", "shopping_pos", 9500),   # 반복결제
        (-25, "15:00", "브러쉬헤어", "shopping_pos", 72000),
        (-24, "11:40", "맘스터치", "other", 7000),
        (-23, "18:30", "올리브영 신촌점", "shopping_pos", 19000),
        (-22, "13:10", "스타벅스", "other", 6000),
        (-21, "20:20", "올리브영 신촌점", "shopping_pos", 22000),
        (-20, "21:55", "네일온 신촌점", "shopping_pos", 40000),
        (-19, "14:10", "다이소", "home", 6000),
        (-18, "17:30", "올리브영 신촌점", "shopping_pos", 18500),
        (-17, "12:20", "학생식당", "other", 5500),
        (-16, "19:10", "올리브영 신촌점", "shopping_pos", 20000),
        (-15, "18:40", "브러쉬헤어", "shopping_pos", 80000),
        (-14, "13:00", "CU", "grocery_pos", 4000),
        (-13, "20:30", "올리브영 신촌점", "shopping_pos", 23000),
        (-12, "16:10", "올리브영 신촌점", "shopping_pos", 19500),
        (-11, "21:40", "네일온 신촌점", "shopping_pos", 45000),
        (-10, "11:30", "메가커피", "other", 3500),
        (-9,  "18:50", "올리브영 신촌점", "shopping_pos", 25000),
        (-8,  "20:10", "올리브영 신촌점", "shopping_pos", 27000),
        (-7,  "19:30", "올리브영 신촌점", "shopping_pos", 28000),

        # 최근 7일 급증 구간
        (-6,  "21:20", "올리브영 신촌점", "shopping_pos", 35000),
        (-5,  "18:40", "브러쉬헤어", "shopping_pos", 95000),
        (-4,  "22:15", "네일온 신촌점", "shopping_pos", 60000),
        (-3,  "15:30", "올리브영 신촌점", "shopping_pos", 42000),
        (-2,  "19:10", "올리브영 신촌점", "shopping_pos", 20000),
        (-1,  "22:00", "올리브영 신촌점", "shopping_pos", 30000),
        (0,   "17:00", "올리브영 신촌점", "shopping_pos", 25000),
    ]

    txs = []
    for day_offset, time_str, merchant, category, amount in raw_rows:
        date_obj = today + timedelta(days=day_offset)
        dt = datetime.strptime(f"{date_obj.isoformat()} {time_str}", "%Y-%m-%d %H:%M")

        txs.append({
            "merchant": merchant,
            "amount": amount,
            "category": category,
            "approved_at": dt.isoformat(),
            "timestamp": dt.isoformat(),
            "datetime": dt.isoformat(),
            "date": date_obj.isoformat(),
            "time": time_str,
        })

    return txs