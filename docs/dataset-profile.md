# Dataset Profile: ml_sample_data_snapsoft.csv

## Overview

- **Rows:** 245
- **Columns:** 27
- **Target:** `Price` (float, no nulls)

## Column Classification

### Drop (PII / non-ML) — 7 columns

| Column | Reason |
|--------|--------|
| `car_ID` | Row identifier, no predictive value |
| `CarName` | Free-text, high cardinality, not usable without NLP |
| `ownername` | PII |
| `owneremail` | PII |
| `dealershipaddress` | PII, multi-line text |
| `saledate` | Transaction metadata, not a car attribute |
| `iban` | PII (financial) |

### Critical (drop row if missing) — 4 columns

| Column | Nulls | Reason |
|--------|-------|--------|
| `carbody` | 10 | Defines car category — cannot be reliably imputed |
| `fueltype` | 10 | Fundamentally changes car characteristics |
| `drivewheel` | 0 | Core mechanical attribute |
| `Price` | 0 | Target variable — row is useless without it |

### Imputable (keep row) — 16 columns

| Column | Type | Nulls (after critical drop) | Imputation strategy |
|--------|------|----------------------------|---------------------|
| `aspiration` | categorical | 0 | — |
| `doornumber` | categorical | 0 | — |
| `enginelocation` | categorical | 9 | Mode (`front`, 98% of values) |
| `color` | categorical | 0 | — |
| `cylindernumber` | numeric (float) | 8 | Median |
| `carlength` | numeric (float) | 4 | Median |
| `wheelbase` | numeric | 0 | — |
| `carwidth` | numeric | 0 | — |
| `carheight` | numeric | 0 | — |
| `curbweight` | numeric | 0 | — |
| `enginesize` | numeric | 0 | — |
| `compressionratio` | numeric | 0 | — |
| `horsepower` | numeric | 0 | — |
| `peakrpm` | numeric | 0 | — |
| `citympg` | numeric | 0 | — |
| `highwaympg` | numeric | 0 | — |

## Missing-Value Pattern

27 rows have at least one null. The nulls fall into two distinct patterns:

1. **Critical-missing rows (10):** car_IDs 40, 47, 62, 63, 133, 161, 194, 197, 227, 242. Always missing `fueltype` + `carbody` simultaneously, often also `CarName`, `carlength`, `horsepower`, `cylindernumber`. These are dropped.

2. **Imputable-missing rows (17):** isolated nulls in `enginelocation`, `cylindernumber`, or `carlength`. These rows are otherwise complete and are kept.

After dropping critical-null rows: **235 rows, 20 columns** (7 PII columns removed).

## Correlations with Price

| Feature | Pearson r |
|---------|-----------|
| `enginesize` | 0.87 |
| `curbweight` | 0.84 |
| `horsepower` | 0.80 |
| `carwidth` | 0.76 |
| `cylindernumber` | 0.71 |
| `carlength` | 0.66 |
| `wheelbase` | 0.55 |
| `carheight` | 0.11 |
| `compressionratio` | 0.08 |
| `peakrpm` | -0.11 |
| `citympg` | -0.67 |
| `highwaympg` | -0.69 |

## Key Observations

- `enginesize`, `curbweight`, and `horsepower` are the strongest linear predictors.
- `citympg` and `highwaympg` are strongly negatively correlated (larger/pricier cars consume more fuel).
- `color` has 15 values, roughly uniform — unlikely to be a strong predictor.
- `enginelocation` is 98% `front` — very low variance.
- `cylindernumber` is parsed as float due to nulls — treat as ordinal or categorical in modeling.
- Price range: 5,118 – 45,400 (median ~10,080, right-skewed).

## Decisions for Downstream Tasks

**Task 4 (Lambda preprocessing):**
- Drop 7 PII columns
- Drop rows where any of `carbody`, `fueltype`, `drivewheel`, `Price` is null
- Keep all other rows (imputation is deferred to the notebook)

**Task 7 (ML notebook):**
- Impute `enginelocation` with mode, `cylindernumber` and `carlength` with median
- Encode categoricals (one-hot or ordinal)
- Strong feature set for gradient boosting: engine/weight/power features dominate
