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
