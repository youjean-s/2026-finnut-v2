# FINNUT Rule-based Pipeline Flow

## End-to-End Flow
push text (str)
↓
utils.parser.parse_push_notification(text)
→ returns: list[tx] (normalized schema)
tx = {datetime, amount, merchant, category?, source, payment_method, raw_text}
↓
utils.category_rules.categorize_store(tx.merchant)
→ returns: category (str)
↓
utils.impulsive_detector.detect_impulsive(txs)
→ returns: {impulsive_score, impulsive_flags}
↓
utils.spending_spike.detect_spending_spike(txs)
→ returns: {spike_score, spike_flags}
↓
utils.fhi_calculator.calculate_fhi_from_transactions(txs)
→ returns: {fhi, impulsive, spike}


## Normalization Contract (must-haves)
- parser output must always be list[dict]
- dict keys: datetime, amount, merchant, source, payment_method, raw_text
- amount: float, spend is positive
- source: one of {shinhan, kakaopay, kb, samsung, unknown}
- payment_method: one of {card, wallet, unknown}

## Test Entry Points
- E2E random demo: `python main.py`
- Week1 cases: `python demo_pages/check_week1_cases.py`
- Category regression: `python demo_pages/check_category_rules.py`
- Extremes: `python demo_pages/check_extremes.py`
