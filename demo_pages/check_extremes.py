import os
import sys
from datetime import datetime, timedelta

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from utils.impulsive_detector import detect_impulsive
from utils.spending_spike import detect_spending_spike
from utils.fhi_calculator import calculate_fhi_from_transactions


def run():
    now = datetime.now()

    cases = [
        {
            "name": "empty_list",
            "txs": [],
        },
        {
            "name": "bad_amounts",
            "txs": [
                {"datetime": now, "amount": "abc", "merchant": "X"},
                {"datetime": now, "amount": -100, "merchant": "Y"},
                {"datetime": now, "amount": 5000, "merchant": "Z"},
            ],
        },
        {
            "name": "night_spend",
            "txs": [
                {"datetime": now.replace(hour=23, minute=10), "amount": 5800, "merchant": "GS25"},
            ],
        },
        {
            "name": "many_small",
            "txs": [
                {"datetime": now - timedelta(hours=3), "amount": 9000, "merchant": "A"},
                {"datetime": now - timedelta(hours=2), "amount": 8000, "merchant": "B"},
                {"datetime": now - timedelta(hours=1), "amount": 7000, "merchant": "C"},
            ],
        },
    ]

    for c in cases:
        name = c["name"]
        txs = c["txs"]

        imp = detect_impulsive(txs)
        spk = detect_spending_spike(txs)
        fhi = calculate_fhi_from_transactions(txs)

        # 기본 shape 검증
        assert isinstance(imp, dict) and "impulsive_score" in imp and "impulsive_flags" in imp
        assert isinstance(spk, dict) and "spike_score" in spk and "spike_flags" in spk
        assert isinstance(fhi, dict) and "fhi" in fhi and "impulsive" in fhi and "spike" in fhi

        # 점수 범위(정책)
        imp_score = float(imp.get("impulsive_score", 0.0))
        assert 0.0 <= imp_score <= 1.0

        print(f"[OK] {name} | imp={imp_score} spk={spk.get('spike_score')} fhi={fhi.get('fhi')}")

    print("\nEXTREMES TEST PASS")


if __name__ == "__main__":
    run()
