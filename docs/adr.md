# Architecture Decision Records

## ADR-0001: Use Python 3.13 everywhere

**Status:** Accepted | **Date:** 2026-03-05

AWS Lambda supports up to 3.13. Use the same version locally to eliminate mismatch risks. 3.14 is available locally but offers nothing needed for this project.

---

## ADR-0002: Local Terraform state

**Status:** Accepted | **Date:** 2026-03-05

Store state locally, no remote backend. This is a homework submission — remote state (S3 + DynamoDB) would be overengineering. State file excluded via `.gitignore`.

---

## ADR-0003: Gradient boosting with quantile loss for price underestimation

**Status:** Accepted | **Date:** 2026-03-05

Business wants slight underestimation. Use `GradientBoostingRegressor` with `loss='quantile'`, `alpha < 0.5` (~0.4). This bakes underestimation into the training objective — no post-processing hacks. Alpha is a direct tuning knob for the bias/accuracy trade-off.

---

## ADR-0004: Use scikit-learn with classic GradientBoostingRegressor

**Status:** Accepted | **Date:** 2026-03-05

**Context:** The homework requires an "sklearn compatible framework." We need a library and specific model class that supports asymmetric (quantile) loss for the underestimation requirement.

**Decision:** Use `scikit-learn` (v1.8) with `sklearn.ensemble.GradientBoostingRegressor`.

**Rationale:**

- sklearn is the de facto standard for tabular ML in Python and is explicitly called out in the assignment.
- The classic `GradientBoostingRegressor` supports `loss='quantile'` with a tunable `alpha` parameter — the mechanism for underestimation. `HistGradientBoostingRegressor` is faster and handles NaNs natively, but does not support quantile loss.
- XGBoost / LightGBM would also work, but add an external dependency for no gain on a 235-row dataset. Staying pure-sklearn keeps the dependency tree minimal.
- Deep learning frameworks (PyTorch, TensorFlow) are inappropriate — 235 rows of tabular data is a sweet spot for tree ensembles, not neural networks.

**Preprocessing approach:** `sklearn.pipeline.Pipeline` wrapping `ColumnTransformer` (median imputation for numerics, mode imputation + one-hot encoding for categoricals) ensures no data leakage between train and test sets.
