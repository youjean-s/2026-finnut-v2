from utils.parser import parse_push_notification
from utils.category_rules import categorize_store
from utils.fhi_calculator import calculate_fhi_from_transactions
from mock.push_emulator import get_random_push


def main():
    print("\n================ FINNUT 기술 데모 ================\n")

    # 1. 푸시 알림 랜덤 생성
    push = get_random_push()
    print("수신한 푸시 알림:\n")
    print(push)
    print("--------------------------------------------------")

    # 2. 파싱 (✅ 이제 list[dict] 반환)
    txs = parse_push_notification(push)
    tx = txs[0] if txs else None
    if not tx:
        print("\n파싱 실패/해당없음\n")
        print("\n==================================================\n")
        return

    store = tx.get("merchant", "알수없음")
    amount = tx.get("amount", 0)
    dt = tx.get("datetime")

    print("\n 파싱 결과")
    print(f"- 가맹점명: {store}")
    print(f"- 금액: {amount}원")
    print(f"- 시간: {dt.strftime('%Y-%m-%d %H:%M') if dt else '알수없음'}")

    # 3. 카테고리 분류
    category = categorize_store(store)

    # 4~6. 충동/급증/FHI 계산 (✅ 통합 함수 사용)
    result = calculate_fhi_from_transactions(txs)
    impulsive_score = result["impulsive"]["impulsive_score"]
    spike_score = result["spike"]["spike_score"]
    fhi = result["fhi"]

    print("\n 소비 분석")
    print(f"- 카테고리: {category}")
    print(f"- 충동구매 점수: {impulsive_score}")
    print(f"- 급증 감지: {spike_score}")

    print("\n FHI")
    print(f"- 이번 소비 반영 후 FHI: {fhi}점")
    print("\n==================================================\n")


if __name__ == "__main__":
    main()
