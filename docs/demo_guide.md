
# FINNUT Demo Guide (Rule-based Engine)

## 0) Prerequisites
- Run commands from repository root (where `main.py` exists)
- Python installed (3.10+ recommended)

## 1) Run Main Demo
```bash
python main.py
````

Expected output sections:

* received push text
* parsed result (merchant/amount/datetime)
* category + impulsive/spike + FHI

## 2) Run Test Scripts

### Week1 functional cases

```bash
python demo_pages/check_week1_cases.py
```

### Category regression

```bash
python demo_pages/check_category_rules.py
```

### Extreme input robustness

```bash
python demo_pages/check_extremes.py
```

## 3) How to Add New Push Message Format

1. Add a new parser function in `utils/parser.py` (e.g., `_parse_hyundai`)
2. Extend `_detect_source()` mapping
3. Add routing in `parse_push_notification()`
4. Add a test case in `demo_pages/check_week1_cases.py`

## 4) Sample Push Text (copy/paste)

### Shinhan

```
[신한카드 승인] 5,800원
GS25 이대점
일시불 승인
2024-11-21 23:10
```

### KakaoPay

```
카카오페이
스타벅스
2025-01-01 12:30
5,000원
```

```
::contentReference[oaicite:0]{index=0}
```
