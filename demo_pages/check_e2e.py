import os
import sys

# 프로젝트 루트를 path에 추가 (demo_pages에서 utils import 되게)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from utils.parser import parse_push_notification
from utils.category_rules import categorize_store
from utils.fhi_calculator import calculate_fhi_from_transactions
from mock.push_emulator import get_random_push


def run(n: int = 20):
    ok = 0
    fail = 0

    for i in range(1, n + 1):
        push = get_random_push()
        txs = parse_push_notification(push)

        if not txs:
            print(f"[{i:02d}] PARSE_FAIL | push={push!r}")
            fail += 1
            continue

        # 첫 트랜잭션만 출력용으로 사용
        tx = txs[0]
        merchant = tx.get("merchant")
        amount = tx.get("amount")

        category = categorize_store(merchant or "")
        result = calculate_fhi_from_transactions(txs)

        fhi = result.get("fhi")
        imp = result.get("impulsive", {}).get("impulsive_score")
        spk = result.get("spike", {}).get("spike_score")

        # 최소 형태 검증
        if fhi is None or imp is None or spk is None:
            print(f"[{i:02d}] SHAPE_FAIL | result={result}")
            fail += 1
            continue

        print(f"[{i:02d}] OK | {merchant} | {amount} | {category} | imp={imp} spk={spk} fhi={fhi}")
        ok += 1

    print("\n===== SUMMARY =====")
    print(f"OK: {ok}")
    print(f"FAIL: {fail}")


if __name__ == "__main__":
    run(20)
