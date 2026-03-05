# Task 3 — Interview Prep Notes

Personal reference for reasoning about the dataset exploration decisions.

---

## Why three column groups?

The homework says: delete columns that can't be used for training, delete rows missing significant attributes, keep rows with imputable attributes. This maps naturally to three groups:

1. **Drop columns** — columns that are structurally unusable for ML regardless of data quality.
2. **Critical columns** — columns where a missing value makes the entire row unusable.
3. **Imputable columns** — columns where a missing value can be filled in from the rest of the data.

Alternative: you could also have a fourth "low-value" group (columns that are present but contribute almost nothing, like `color` or `enginelocation`). I chose to keep them because dropping features should be a model-selection decision, not a preprocessing decision. The Lambda just cleans; the notebook decides what to use.

---

## Why these specific PII / non-ML columns?

| Column | Reasoning |
|--------|-----------|
| `car_ID` | Synthetic row identifier. Including it would cause data leakage — the model would memorize IDs. |
| `CarName` | Free text, high cardinality (196 unique values for 245 rows). You'd need NLP to extract signal. Out of scope for this task. |
| `ownername`, `owneremail`, `iban` | PII. No relationship to car price. Also a GDPR concern — this data shouldn't flow into a model at all. |
| `dealershipaddress` | PII (contains full street address). In theory, location could affect price, but this is unstructured multi-line text. Would need geocoding + regional features — out of scope. |
| `saledate` | Transaction timestamp. Could be useful for time-based features (depreciation, market trends), but with only 245 rows spanning 2015-2022, there's not enough data for temporal modeling. |

**If they ask "would you ever use CarName?":** Yes, in a production system you'd parse it into make/model and use those as categorical features. Here, `carbody`, `fueltype`, etc. already capture the car's characteristics, so the marginal value is low.

**If they ask "would you ever use saledate?":** With a larger dataset, absolutely — car prices depreciate over time. With 245 rows over 7 years, the signal would be noisy and the model couldn't learn a reliable time trend.

---

## Why these critical columns?

The key question: "what makes a column critical vs imputable?"

A column is **critical** if:
- Missing it makes the row semantically incomplete (you don't know what kind of car this is)
- It cannot be reliably imputed from other columns
- It defines a fundamental category that affects all other attributes

| Column | Why critical |
|--------|-------------|
| `carbody` | Defines the car's physical form (sedan, hatchback, wagon...). A car without a body type is unclassifiable. You can't infer it from weight or engine size alone — a heavy sedan and a heavy wagon are different things. |
| `fueltype` | Gas vs diesel fundamentally changes the car's economics and engineering. Imputing it randomly would introduce systematic bias. |
| `drivewheel` | fwd/rwd/4wd changes handling, maintenance, and price. (In practice, 0 rows are missing this — but it's still logically critical.) |
| `Price` | The target variable. You can't train on a row without a label. |

**If they ask "why not make `enginelocation` critical?":** It's 98% `front` and only 4 rows are `rear`. The mode imputation is almost certainly correct. Also, the 9 rows missing it all have `carbody` and `fueltype` present, so they're otherwise high-quality rows — dropping them would waste good data.

**If they ask "why not make `horsepower` critical?":** It's a continuous numeric variable with a well-defined distribution. Median imputation is a standard, defensible approach. Also, after dropping the critical-null rows, `horsepower` has zero remaining nulls — so it's moot for the Lambda, and if it did have nulls, the notebook could handle it.

---

## Missing-value strategy

**Two-stage approach:**
1. Lambda (task 4): drops rows where critical columns are null. No imputation — keep preprocessing simple and deterministic.
2. Notebook (task 7): imputes remaining nulls before training.

**Why not impute in the Lambda?** Because imputation strategy depends on model choice. Median imputation is fine for gradient boosting but you might want different strategies for linear models. The Lambda should be a generic data cleaning step; the notebook owns the ML-specific decisions.

**Why median imputation?** For numeric columns, median is robust to outliers (unlike mean) and doesn't require distributional assumptions. For `enginelocation`, mode imputation is appropriate because one value (`front`) dominates at 98%.

**When would you use group-median?** If you had enough data, you'd impute `cylindernumber` by median within the same `carbody` group (sedans tend to have different cylinder counts than hatchbacks). With only 8 missing values across 235 rows, the global median is fine.

**Trade-off:** Simple imputation can reduce variance in the imputed features, slightly flattening their effect on the model. With only 21 total nulls remaining across 235 rows (~0.6% of cells), the impact is negligible.

---

## What the correlations tell us

**Top predictors:** `enginesize` (r=0.87), `curbweight` (r=0.84), `horsepower` (r=0.80). These are all measures of "how big and powerful is the car" — makes intuitive sense for price.

**Negative correlations:** `highwaympg` (r=-0.69), `citympg` (r=-0.67). Bigger, pricier cars consume more fuel. This is the flip side of the engine/weight correlation.

**Near-zero:** `carheight` (r=0.11), `compressionratio` (r=0.08), `peakrpm` (r=-0.11). These contribute little linear signal — but tree-based models can still find interactions.

**Why this matters for task 7:** Gradient boosting trees handle correlated features well (they don't need decorrelation like linear models). The strong linear correlations suggest even a simple model should get decent R². The asymmetry requirement (underestimation) is a separate concern handled by quantile loss.

---

## Anticipated interview questions

**Q: Why not just drop all rows with any null?**
A: That would lose 27 rows (11% of data). 17 of those have just one or two missing values in non-critical columns. With a small dataset of 245 rows, preserving data is important. The cost of imputing a few isolated values is much lower than the cost of losing 17 training examples.

**Q: Why not drop `color`? It probably doesn't affect price.**
A: Probably not, but it costs nothing to keep it. Tree-based models naturally ignore irrelevant features by not splitting on them. Dropping it preemptively would be making an assumption without evidence. If we were doing feature selection, we'd let the model decide.

**Q: Why not impute `carbody` using the car name or other features?**
A: The 10 rows missing `carbody` are also missing `fueltype`, `CarName`, and several other columns simultaneously. They're systematically incomplete — likely data entry failures. Even if you could guess `carbody`, you'd still be missing `fueltype`. Better to drop them cleanly.

**Q: The dataset is only 245 rows. Is that enough for ML?**
A: It's small but workable for tabular data with gradient boosting. We have ~20 features and 235 clean rows. Tree-based models are sample-efficient for tabular data. The risk is overfitting — we mitigate this with train/test split and monitoring R²/MAE on held-out data. I wouldn't claim production-grade accuracy, but it's sufficient to demonstrate the approach.

**Q: How would this change at scale?**
A: With more data: (1) you'd add automated schema validation before the Lambda, (2) you'd use group-based imputation instead of global median, (3) you'd consider parsing `CarName` into make/model features, (4) you'd add data drift monitoring to catch changes in the distribution, (5) you'd move from single-file CSV to partitioned Parquet in S3 for query efficiency.

---

## What I'd do differently in production

1. **Schema validation:** Validate incoming CSVs against a schema (column names, types, allowed values) before processing. Reject malformed files.
2. **Data quality metrics:** Log null rates, row counts, and value distributions per batch. Alert on anomalies.
3. **Versioned preprocessing:** Pin the column lists and imputation parameters (not hardcoded in a Lambda, but in a config file or parameter store).
4. **Audit trail:** Keep the original rows that were dropped, with a reason code, for compliance and debugging.
5. **Testing:** Unit tests for the Lambda with edge cases (empty file, all-null rows, schema changes). Integration tests for the full pipeline.
