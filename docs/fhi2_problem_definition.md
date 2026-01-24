# FHI 2.0 Problem Definition (Draft)

## Goal
- Predict user's financial health signal from transaction history (spending patterns)
- Output should be explainable and consistent with FHI 1.0 rule engine

## Output Type (choose one)
### Option A) Regression (0~100)
- Output: continuous FHI score (0~100)
- Pros: fine-grained, aligns with current FHI 1.0
- Cons: label definition is hard without ground truth

### Option B) Classification (risk level 3-class)
- Output: {low, medium, high} risk
- Pros: easier communication, easier evaluation
- Cons: loses granularity, threshold tuning needed

## Initial Label Strategy (bootstrap)
- Use FHI 1.0 rule-based score as weak label for initial training
- Later: replace/adjust with feedback-based labels or expert rubric

## Inputs (minimum)
- Per transaction: datetime, amount, merchant/category, payment_method
- Window: last 30~90 days

## Success Criteria
- Stable performance on holdout set
- Explainability: top features driving score (feature importance/SHAP)
- Robustness: missing category/merchant cases handled
