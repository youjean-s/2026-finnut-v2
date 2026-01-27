# Week8 통합 테스트 체크리스트 (재현 커맨드)

## 1) 파서/카테고리/예외 케이스 테스트
```bash
python demo_pages/check_week1_cases.py
python demo_pages/check_category_rules.py
python demo_pages/check_extremes.py
````

## 2) Rule vs ML 비교 테스트

```bash
python demo_pages/check_rule_vs_ml.py
```

## 3) 메인 파이프라인 데모 실행 (push → parse → category → FHI)

```bash
python main.py
```