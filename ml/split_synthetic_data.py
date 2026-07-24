"""
ml/split_synthetic_data.py
----------------------------
ml/label_data.py로 만든 synthetic_labeled.csv를 유저 단위로 train / held_in /
held_out(Set A) 3개로 나눈다.

유저 단위로 나누는 이유: 같은 유저의 여러 체크포인트(월 x 4시점) row는 서로 강하게
상관돼 있어서, row 단위로 무작위 split하면 train과 검증 세트에 같은 유저가 동시에
들어가는 leak이 생긴다 (ml/src/split_train_val.py와 동일한 원칙, user_id 기준 split).

- held_in  : 학습 중 튜닝/모니터링용 (LightGBM eval_set으로 사용)
- held_out : 학습에 전혀 관여하지 않는 최종 확인용 세트. 이번 합성 데이터 실험에서는
             "Set A"라고 부른다 - 나중에 실사용자 데이터가 들어오면 별도 held-out을
             추가로 만들 것이므로 지금 것과 구분해두는 용도.
"""
import numpy as np
import pandas as pd

IN_PATH = "ml/data/features/synthetic_labeled.csv"
TRAIN_OUT = "ml/data/features/synthetic_train.csv"
HELD_IN_OUT = "ml/data/features/synthetic_held_in.csv"
HELD_OUT_OUT = "ml/data/features/synthetic_held_out_setA.csv"

TRAIN_RATIO = 0.7
HELD_IN_RATIO = 0.15
# 나머지(1 - TRAIN_RATIO - HELD_IN_RATIO)가 held_out(Set A)
SEED = 42


def main():
    df = pd.read_csv(IN_PATH)
    if "user_id" not in df.columns or "label_fhi" not in df.columns:
        raise ValueError("synthetic_labeled.csv에 user_id / label_fhi 컬럼이 없음")

    users = df["user_id"].unique()
    rng = np.random.default_rng(SEED)
    rng.shuffle(users)

    n_train = int(len(users) * TRAIN_RATIO)
    n_held_in = int(len(users) * HELD_IN_RATIO)

    train_users = set(users[:n_train])
    held_in_users = set(users[n_train:n_train + n_held_in])
    held_out_users = set(users[n_train + n_held_in:])

    train = df[df["user_id"].isin(train_users)].copy()
    held_in = df[df["user_id"].isin(held_in_users)].copy()
    held_out = df[df["user_id"].isin(held_out_users)].copy()

    # leak check: 세 세트 간 유저 겹침이 없어야 함
    assert not (train_users & held_in_users), "train/held_in 유저 겹침"
    assert not (train_users & held_out_users), "train/held_out 유저 겹침"
    assert not (held_in_users & held_out_users), "held_in/held_out 유저 겹침"

    train.to_csv(TRAIN_OUT, index=False)
    held_in.to_csv(HELD_IN_OUT, index=False)
    held_out.to_csv(HELD_OUT_OUT, index=False)

    print(f"[OK] train           rows={len(train):3d} users={len(train_users):2d} -> {TRAIN_OUT}")
    print(f"[OK] held_in         rows={len(held_in):3d} users={len(held_in_users):2d} -> {HELD_IN_OUT}")
    print(f"[OK] held_out(Set A) rows={len(held_out):3d} users={len(held_out_users):2d} -> {HELD_OUT_OUT}")


if __name__ == "__main__":
    main()
