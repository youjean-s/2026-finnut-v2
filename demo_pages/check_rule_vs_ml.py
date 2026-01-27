import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from utils.parser import parse_push_notification
from utils.fhi_calculator import calculate_fhi_from_transactions


CASES = [
    {
        "name": "baseline_mix",
        "texts": [
            "[신한카드 승인] 5,800원\nGS25 이대점\n일시불 승인\n2024-11-21 23:10",
            "카카오페이\n스타벅스\n2025-01-01 12:30\n5,000원",
            "승인\n무신사\n2025-01-02 18:10\n32,000원",
        ],
    },
    {
        "name": "small_many",
        "texts": [
            "[신한카드 승인] 1,200원\nCU 이대점\n일시불 승인\n2025-01-04 00:10",
            "[신한카드 승인] 3,300원\n이디야커피\n일시불 승인\n2025-01-04 10:02",
            "[신한카드 승인] 2,200원\nGS25-대치점\n일시불 승인\n2025-01-04 11:59",
        ],
    },
]


def run():
    ok = 0
    fail = 0

    for case in CASES:
        name = case["name"]
        txs = []
        for text in case["texts"]:
            txs.extend(parse_push_notification(text))

        if not txs:
            print(f"[FAIL] {name}: no transactions parsed")
            fail += 1
            continue

        # rule
        rule_result = calculate_fhi_from_transactions(txs, mode="rule")
        # ml
        ml_result = calculate_fhi_from_transactions(txs, mode="ml")

        if "fhi" not in rule_result or "fhi" not in ml_result:
            print(f"[FAIL] {name}: bad result shape rule={rule_result}, ml={ml_result}")
            fail += 1
            continue

        diff = ml_result["fhi"] - rule_result["fhi"]
        print(f"[OK] {name} | rule_fhi={rule_result['fhi']} | ml_fhi={ml_result['fhi']} | diff={diff:+.2f}")
        ok += 1

    print("\n===== RULE vs ML SUMMARY =====")
    print(f"OK: {ok}")
    print(f"FAIL: {fail}")


if __name__ == "__main__":
    run()
