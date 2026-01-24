import os
import sys
from datetime import datetime

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from utils.parser import parse_push_notification
from utils.category_rules import categorize_store
from utils.fhi_calculator import calculate_fhi_from_transactions


DEMO_CASES = [
    ("case1_normal_cafe",
     "카카오페이\n스타벅스\n2025-01-01 12:30\n5,000원"),
    ("case2_convenience_night",
     "[신한카드 승인] 5,800원\nGS25 이대점\n일시불 승인\n2024-11-21 23:10"),
    ("case3_shopping_mid",
     "[삼성카드 승인] 29,900원\n무신사\n2025-01-04 19:05"),
    ("case4_many_small_1",
     "[KB국민카드 승인] 9,000원\nCU\n2025-01-05 01:10"),
    ("case5_many_small_2",
     "[KB국민카드 승인] 8,000원\nGS25\n2025-01-05 02:10"),
]


def run():
    print("\n===== WEEK3 DEMO CASES =====\n")
    all_txs = []

    for name, text in DEMO_CASES:
        txs = parse_push_notification(text)
        if not txs:
            print(f"[FAIL] {name}: parse failed\n")
            continue

        tx = txs[0]
        cat = categorize_store(tx.get("merchant", ""))
        all_txs.extend(txs)

        print(f"--- {name} ---")
        print(f"source={tx.get('source')} pay={tx.get('payment_method')}")
        print(f"merchant={tx.get('merchant')} amount={tx.get('amount')} dt={tx.get('datetime')}")
        print(f"category={cat}\n")

    # 누적 기준으로 impulsive/spike/FHI가 변화하는 걸 보여주기
    result = calculate_fhi_from_transactions(all_txs)
    print("===== FINAL (accumulated) =====")
    print(f"FHI={result.get('fhi')}")
    print(f"impulsive_score={result.get('impulsive', {}).get('impulsive_score')}")
    print(f"spike_score={result.get('spike', {}).get('spike_score')}")
    print("\n=============================\n")


if __name__ == "__main__":
    run()
