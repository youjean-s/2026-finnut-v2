import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from utils.category_rules import categorize_store


CASES = [
    ("GS25 이대점", "편의점"),
    ("gs25이대점", "편의점"),
    ("CU", "편의점"),
    ("스타벅스 강남점", "카페"),
    ("이디야커피 이화점", "카페"),
    ("올리브영 강남점", "쇼핑"),
    ("무신사", "쇼핑"),
    ("다이소", "쇼핑"),
    ("버거킹", "식비"),
    ("맥도날드", "식비"),
]


def run():
    ok = 0
    fail = 0

    for store, expect in CASES:
        got = categorize_store(store)
        if got != expect:
            print(f"[FAIL] {store}: got={got}, expect={expect}")
            fail += 1
        else:
            print(f"[OK] {store}: {got}")
            ok += 1

    print("\n===== CATEGORY TEST SUMMARY =====")
    print(f"OK: {ok}")
    print(f"FAIL: {fail}")


if __name__ == "__main__":
    run()
