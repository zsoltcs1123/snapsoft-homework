# Task 7 — Interview Prep Notes

Personal reference for reasoning about every ML decision in the training notebook.

---

## Why gradient boosting for this problem?

Gradient boosting (specifically `GradientBoostingRegressor`) is the right tool here for four reasons:

1. **Tabular data, small dataset.** With 235 rows and ~19 features, we're squarely in the regime where tree-based ensembles dominate. Neural networks need thousands-to-millions of rows to outperform trees on tabular data. Linear models can work but struggle with non-linear relationships (e.g., a 6-cylinder engine doesn't cost exactly 1.5x a 4-cylinder).

2. **Mixed feature types.** We have both numeric (wheelbase, enginesize, horsepower) and categorical (fueltype, carbody, drivewheel) features. Trees handle these naturally after one-hot encoding. Linear models would need more careful feature engineering (interactions, polynomial terms).

3. **Native quantile loss support.** The classic `GradientBoostingRegressor` supports `loss='quantile'` — this is the mechanism for asymmetric prediction (underestimation). This is the single biggest reason for the model choice.

4. **No scaling required.** Trees split on thresholds, so they're invariant to feature scale. No need for StandardScaler or MinMaxScaler, which simplifies the pipeline.

### How gradient boosting works (simple version)

Gradient boosting builds an ensemble of decision trees sequentially. Each tree corrects the errors (residuals) of the previous trees. The "gradient" part means it uses gradient descent in function space — each new tree is fit to the negative gradient of the loss function.

With `n_estimators=200` and `max_depth=4`:
- 200 trees are built one at a time.
- Each tree is shallow (max 4 levels of splits), which prevents overfitting. A depth-4 tree can model interactions between up to 4 features.
- `learning_rate=0.1` shrinks each tree's contribution, requiring more trees but producing a more robust ensemble (regularization via shrinkage).

**If they ask "why not a deeper tree?":** Deeper trees memorize the training data faster. With only 188 training rows, depth 4 is conservative. You'd tune this with cross-validation in production.

**If they ask "why 200 trees?":** It's a sensible default. Too few = underfitting, too many = overfitting (though learning rate mitigates this). With 188 training rows, 200 shallow trees is plenty. In production you'd use early stopping on a validation set.

---

## GradientBoostingRegressor vs alternatives

| Algorithm | Pros | Cons | Verdict |
|-----------|------|------|---------|
| **GradientBoostingRegressor** (sklearn) | Native quantile loss, pure sklearn, well-documented | Slower than histogram-based variants, no native NaN handling | **Selected** |
| **HistGradientBoostingRegressor** (sklearn) | Fast (histogram binning), handles NaN natively | No `loss='quantile'` support in sklearn | Rejected — can't do quantile regression |
| **XGBoost** | Fast, regularized, supports quantile loss (`reg:quantileerror`) | External dependency, overkill for 235 rows | Would work but unnecessary complexity |
| **LightGBM** | Fastest training, supports quantile loss | External dependency, leaf-wise growth can overfit small data | Same as XGBoost |
| **Random Forest** | Simple, parallelizable | No native quantile loss (would need quantile forest extension), generally weaker than boosting | Rejected |
| **Linear Regression** | Interpretable, fast | Assumes linear relationships, no native quantile loss (would need QuantileRegressor) | Too restrictive for this data |
| **Neural Network** | Flexible | Needs much more data, expensive to tune, overkill | Rejected |

**Key takeaway:** `GradientBoostingRegressor` is the only sklearn model that combines (a) strong tabular performance with (b) native quantile loss support. That's why we chose it.

**If they ask "why not `QuantileRegressor` (sklearn's linear quantile regression)?":** It fits a linear model to the specified quantile. With non-linear price relationships (engine size vs price isn't linear), a linear quantile model would underperform. You'd need polynomial features or kernel tricks to match a tree's flexibility — at that point you're reinventing gradient boosting poorly.

---

## Quantile regression explained

### Standard regression vs quantile regression

Standard regression (e.g., `loss='squared_error'`) minimizes the mean squared error — it predicts the **mean** of the conditional distribution P(Price | features). The mean is the "middle" in terms of squared distance.

Quantile regression minimizes the **pinball loss** (also called quantile loss) — it predicts a specific **quantile** of the conditional distribution. The quantile is controlled by `alpha`.

### The pinball loss function

For a prediction ŷ and actual value y:

```
L(y, ŷ) = alpha * max(y - ŷ, 0) + (1 - alpha) * max(ŷ - y, 0)
```

Breaking this down:
- If ŷ **underestimates** (y > ŷ): penalty = `alpha * (y - ŷ)`
- If ŷ **overestimates** (ŷ > y): penalty = `(1 - alpha) * (ŷ - y)`

With `alpha = 0.4`:
- Under-prediction penalty factor: **0.4**
- Over-prediction penalty factor: **0.6**

Over-predictions are penalized 1.5x more than under-predictions. The model learns to avoid over-predicting, so it systematically leans low.

### Why alpha = 0.4?

- `alpha = 0.5`: symmetric — median regression. ~50% underestimation.
- `alpha = 0.4`: ~60% underestimation. "Slight" bias as requested.
- `alpha = 0.3`: ~70% underestimation. Aggressive — too much accuracy loss.
- `alpha = 0.1`: ~90% underestimation. Extreme — predictions become useless.

We chose 0.4 because:
1. It produces 55-65% underestimation — clearly biased but not extreme.
2. The accuracy hit is small (R² dropped from ~0.95 at alpha=0.5 to ~0.94 at alpha=0.4).
3. The business said "slightly" underestimate — 0.4 is the mildest meaningful asymmetry below 0.5.

**If they ask "how do you tune alpha?":** Plot alpha vs (underestimation rate, MAE, R²) on the test set. Pick the alpha that gives acceptable underestimation (e.g., 60%) with the least accuracy loss. With more data, you'd use cross-validation.

**If they ask "why not just multiply predictions by 0.95?":** A fixed multiplier (post-hoc scaling) is crude — it under-predicts by the same proportion at all price levels. Quantile regression naturally adapts the bias to the local price distribution. A $5,000 car and a $40,000 car get different absolute adjustments.

---

## The sklearn Pipeline pattern

### What it is

A `Pipeline` chains preprocessing steps and a model into a single object:

```python
Pipeline([
    ("preprocessor", ColumnTransformer([...])),
    ("regressor", GradientBoostingRegressor(...)),
])
```

When you call `pipeline.fit(X_train, y_train)`:
1. The `ColumnTransformer` calls `fit_transform` on `X_train` — it learns imputation values and encoding categories from the training data, then transforms it.
2. The transformed data is passed to `GradientBoostingRegressor.fit()`.

When you call `pipeline.predict(X_test)`:
1. The `ColumnTransformer` calls `transform` (not fit_transform!) on `X_test` — it uses the values learned during training.
2. The transformed data is passed to `GradientBoostingRegressor.predict()`.

### Why this prevents data leakage

Data leakage means the model sees information from the test set during training. Common sources:

- **Imputation leakage:** If you compute the median of a column on the full dataset (train + test) and then use it to fill nulls, the imputed training values contain information from the test set. In a Pipeline, `SimpleImputer` computes medians only on the training split.
- **Encoding leakage:** If you fit `OneHotEncoder` on the full dataset, the model knows all possible category values (including any that appear only in the test set). In a Pipeline, the encoder only sees training categories.

For this dataset the leakage risk is small (235 rows, few nulls), but the Pipeline pattern is the correct practice and it costs nothing to implement.

### ColumnTransformer

Applies different transformations to different columns:

```python
ColumnTransformer([
    ("num", numeric_pipeline, numeric_column_list),
    ("cat", categorical_pipeline, categorical_column_list),
])
```

- Numeric columns → `SimpleImputer(strategy="median")`
- Categorical columns → `SimpleImputer(strategy="most_frequent")` → `OneHotEncoder(handle_unknown="ignore")`

The `handle_unknown="ignore"` on OneHotEncoder means that if the test set contains a category not seen in training, it gets encoded as all-zeros (rather than throwing an error). This is defensive coding for production scenarios.

**If they ask "why not OrdinalEncoder?":** One-hot encoding treats each category as independent — `sedan` is not "more" than `hatchback`. Ordinal encoding imposes an arbitrary numeric order, which tree models might split on incorrectly. One-hot is safer for nominal categoricals. The downside is more features (one per category), but with only ~40 total one-hot columns and 188 training rows, it's fine.

---

## Feature engineering decisions

### Why no feature selection?

We pass all 19 features (7 categorical, 12 numeric) to the model. No features are dropped.

Reasons:
1. **Trees do implicit feature selection.** If `carheight` has no predictive power, the model simply never splits on it. Including it costs almost nothing.
2. **Small feature set.** 19 raw features expand to ~40 after one-hot encoding. With 188 training rows, the ratio is ~5:1 rows-to-features, which is workable for gradient boosting.
3. **Premature feature selection can hurt.** Dropping a feature based on low linear correlation (e.g., `compressionratio` has r=0.08 with Price) ignores non-linear effects and interactions. Let the model decide.

**If they ask "when would you do feature selection?":** When the feature set is much larger relative to the training data (e.g., 1000 features, 200 rows). Techniques: L1 regularization (Lasso), mutual information, recursive feature elimination, or model-based importance. For 19 features and 235 rows, it's unnecessary.

### Why median imputation (not mean)?

Median is robust to outliers. If `horsepower` has a few extreme values (e.g., sports cars with 300+ HP), the mean would be pulled toward those outliers, imputing unrealistic values for economy cars. The median stays at the typical value.

For this dataset there are only 21 nulls across 235 rows (~0.6% of cells), so the imputation strategy barely matters. Median is the defensible default.

### Why mode imputation for categoricals?

`enginelocation` is 98% `front`. Imputing with the most frequent value is almost certainly correct. The 9 rows missing it are otherwise complete — we'd lose them if we dropped instead of imputing.

### Why no feature scaling?

Tree-based models split on value thresholds, not distances. Whether `wheelbase` ranges from 86-120 or 0-1 doesn't change the split point's quality. Scaling adds complexity with zero benefit for trees. (You'd need scaling for linear models, SVMs, KNN, or neural networks.)

---

## Evaluation metrics: what they mean

### MAE (Mean Absolute Error): ~1,597

On average, predictions are off by about $1,597. This is the most interpretable metric — "our model is typically within $1,600 of the real price." For a dataset where prices range from ~$5,000 to ~$45,000, this is roughly 3-8% relative error.

### RMSE (Root Mean Squared Error): ~2,398

Similar to MAE but penalizes large errors more (because of the squaring). RMSE > MAE means some predictions have large errors (common when the model struggles with high-priced outliers). The gap (RMSE/MAE ≈ 1.5) suggests moderate error variance.

### R² (Coefficient of Determination): ~0.94

94% of the variance in Price is explained by the model. This is very good — means the features strongly predict price. R² = 1.0 would be a perfect model. R² < 0 would mean the model is worse than predicting the mean.

For context: R² ≈ 0.94 on a 47-sample test set with quantile loss (which sacrifices some accuracy for underestimation) is a strong result. A symmetric model (alpha=0.5) would likely get R² ≈ 0.95+.

### Underestimation rate: ~55%

55% of test predictions are below the actual price. This confirms the quantile loss is working as intended — the model is biased toward underestimation. With alpha=0.4 we expect 55-65% empirically (the theoretical target is 60%, but with only 47 test samples the variance is high).

### Predicted vs Actual plot

- Points below the red `y = x` line are underestimations (good — the majority should be here).
- Points above the line are overestimations.
- Tight clustering around the line means good accuracy.
- Systematic deviation at high prices might indicate the model struggles with expensive/rare cars.

### Residual distribution

- The histogram should be left-skewed (more negative residuals = more underestimations).
- The center of mass should be slightly below zero.
- A wide spread indicates high prediction variance.

---

## Train/test split details

### Why 80/20?

With 235 rows:
- Train: 188 rows — enough for gradient boosting to learn
- Test: 47 rows — enough for a rough estimate of generalization

**If they ask "why not 70/30?":** With only 235 rows, every training example matters. 80/20 balances having enough training data against having enough test data. 70/30 would give 165/70 — fewer training examples hurts model quality more than extra test examples help evaluation stability.

### Why `random_state=42`?

Reproducibility. The same split is produced every time the notebook runs. Without it, re-running the notebook could give different metrics — confusing for a demo.

### Why not cross-validation?

With 47 test samples, our metric estimates have high variance. 5-fold CV would give 5 estimates (each on ~47 samples) that you could average for lower variance. But:
- CV is harder to explain in a notebook (multiple folds, averaging scores).
- The purpose here is to demonstrate the approach, not to squeeze out optimal metrics.
- With 235 rows and 5 folds, each fold trains on 188 and tests on 47 — the same ratio as our single split.

In production, you'd use repeated stratified k-fold CV and report confidence intervals.

### Why not stratified split?

`train_test_split` does random splitting, not stratified. Stratified splitting (e.g., by price quartile) would ensure each quartile is equally represented in train and test. With a continuous target like Price, sklearn's `train_test_split` doesn't do this by default. You could bin the target and use `StratifiedShuffleSplit`, but with 235 rows the random split is unlikely to be significantly imbalanced.

---

## The two-stage preprocessing approach

### Lambda (task 4): drop columns and invalid rows

- Removes 7 PII/non-ML columns.
- Drops rows where critical columns (carbody, fueltype, drivewheel, Price) are null. 245 → 235 rows.
- No imputation — keeps preprocessing simple and deterministic.

### Notebook (task 7): impute and encode

- Imputes remaining nulls (median for numerics, mode for categoricals).
- One-hot encodes categoricals.
- All within a Pipeline fitted only on training data.

**Why split preprocessing across Lambda and notebook?** The Lambda is a data-cleaning step that runs in production on every uploaded CSV. It should be simple and deterministic — no ML-specific logic. The notebook owns imputation strategy because that depends on model choice (median imputation is fine for trees but suboptimal for linear models).

---

## Hyperparameter choices

| Parameter | Value | Why |
|-----------|-------|-----|
| `loss` | `'quantile'` | Asymmetric loss for underestimation — the core requirement |
| `alpha` | `0.4` | 40th percentile → ~60% underestimation. Mildest meaningful asymmetry below 0.5 |
| `n_estimators` | `200` | Enough capacity for 188 training rows. Default is 100; we use more because learning rate is 0.1 |
| `max_depth` | `4` | Shallow trees prevent overfitting. Allows up to 4-way feature interactions |
| `learning_rate` | `0.1` | Standard conservative choice. Lower = needs more trees but less overfitting |
| `random_state` | `42` | Reproducibility |

**If they ask "how would you tune these?":** GridSearchCV or RandomizedSearchCV over a parameter grid. For this problem:
- `alpha`: [0.3, 0.35, 0.4, 0.45]
- `n_estimators`: [100, 200, 300]
- `max_depth`: [3, 4, 5]
- `learning_rate`: [0.05, 0.1, 0.2]

Use a custom scoring function that combines R² and underestimation rate. In practice, you'd also add `min_samples_leaf` and `subsample` to the grid.

---

## Anticipated interview questions

**Q: Why not XGBoost or LightGBM?**
A: Both would work fine and likely give slightly better accuracy. But sklearn's `GradientBoostingRegressor` is sufficient for 235 rows, keeps the dependency tree pure-sklearn (as the assignment suggests), and natively supports quantile loss. Adding XGBoost for this dataset size is like using a forklift to move a chair.

**Q: How would you deploy this model to production?**
A: Train the model in a SageMaker Training Job (or a Step Functions pipeline), serialize with `joblib.dump()`, deploy to a SageMaker Endpoint or a Lambda behind API Gateway. The sklearn Pipeline serializes the full preprocessing + model, so the endpoint accepts raw features. Add a monitoring layer (SageMaker Model Monitor or custom CloudWatch metrics) to detect data drift and model degradation.

**Q: How would you retrain when new data arrives?**
A: Set up a scheduled retraining pipeline (e.g., weekly via Step Functions or Airflow). Compare new model's metrics against the current production model on a held-out validation set. Auto-promote if metrics improve, alert if they degrade. Store model artifacts in S3 with versioning.

**Q: What would you change with 10x or 100x more data?**
A: (1) Switch to `HistGradientBoostingRegressor` for faster training — or XGBoost/LightGBM with native quantile support. (2) Use k-fold CV for more robust evaluation. (3) Add hyperparameter tuning (Bayesian optimization). (4) Consider feature engineering: parse CarName into make/model, add time-based features from saledate, regional features from dealership location. (5) Move from CSV to Parquet for faster I/O. (6) Consider a two-model approach: one for point estimation, one for quantile.

**Q: Why is the underestimation rate 55% and not exactly 60%?**
A: Two reasons. (1) Finite sample size — with only 47 test samples, there's inherent variance. The true population underestimation rate is closer to 60%, but we'd need hundreds of test samples to converge. (2) Gradient boosting is an approximation — it minimizes the quantile loss over the training set using trees with limited depth, so the converged prediction isn't the exact 40th percentile, just an approximation of it.

**Q: Could the model overfit with only 188 training rows?**
A: It's a risk. We mitigate it with conservative hyperparameters (max_depth=4, learning_rate=0.1). The R² of ~0.94 on the test set (vs likely higher on training) is a healthy sign — if we were badly overfitting, test R² would be much lower than training R². In production, you'd monitor the train/test gap and use early stopping.

**Q: Why is MAE not the primary metric?**
A: For an asymmetric model, MAE is harder to interpret because it treats under- and over-predictions equally. The combination of R² (overall fit quality) and underestimation rate (asymmetry check) tells a more complete story. MAE is still useful as a "typical error magnitude" for business stakeholders.

**Q: What if the business wants to control the underestimation amount differently for different price ranges?**
A: Quantile regression gives a uniform quantile across the whole distribution. For price-range-specific control, you'd either: (1) train separate models per price segment, (2) use a conditional quantile regression approach, or (3) post-process predictions with a price-dependent adjustment curve. Option 1 is simplest but needs enough data per segment.

---

## What I'd do differently in production

1. **Cross-validation:** Replace the single train/test split with repeated k-fold CV to get confidence intervals on all metrics.
2. **Hyperparameter tuning:** GridSearchCV or Optuna with a custom scorer combining R² and underestimation rate.
3. **Feature engineering:** Parse CarName → make + model, extract age from saledate, geocode dealership for regional features.
4. **Model comparison:** Train multiple algorithms (GBR, XGBoost, LightGBM, linear quantile) and compare on the same CV folds.
5. **Monitoring:** Track prediction drift, feature drift, and actual-vs-predicted distributions in production.
6. **Explainability:** Add SHAP values to explain individual predictions ("this car is priced low because of high mileage and old age").
