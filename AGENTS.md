# AGENTS.md

## Goal

Solve the SnapSoft Solution Architect homework: build an AWS-based, event-driven pipeline that preprocesses second-hand car sales data and trains an ML model to estimate selling prices.
The homework is described in the file `homework.md`.

## About the User

- 10+ years software development experience.
- Strong general architecture/engineering skills.
- Gaps: AWS (experienced with Azure), Python ML ecosystem (sklearn, pandas in ML context).
- Applying for a **Solution Architect** position — deliverables must be professional, well-reasoned, but not overengineered.

## Deliverables (zip)

1. **Terraform files** — IaC defining the full AWS architecture.
2. **Python Lambda script** — preprocessing logic (drop PII/non-ML columns, drop rows missing critical attributes, keep imputable rows).
3. **Jupyter Notebook** — load curated data, train an sklearn-compatible model, evaluate it. Model should slightly underestimate price (business preference).
4. **README** — terraform deployment instructions.

## Architecture at a Glance

- **Landing zone S3 bucket** → S3 event notification → **Lambda** (Python + Pandas layer) → **Curated zone S3 bucket**.
- Notebook reads from curated zone, trains & evaluates model locally.

## Dataset

File: `ml_sample_data_snapsoft.csv` (491 rows + header).

Columns: `car_ID, CarName, ownername, owneremail, dealershipaddress, saledate, iban, fueltype, aspiration, doornumber, carbody, drivewheel, enginelocation, wheelbase, color, carlength, carwidth, carheight, curbweight, cylindernumber, enginesize, compressionratio, horsepower, peakrpm, citympg, highwaympg, Price`

Target: `Price`.

Columns to drop (PII / non-ML): `car_ID, CarName, ownername, owneremail, dealershipaddress, saledate, iban`.

## Key Decisions / Assumptions

- Terraform uses AWS provider; state stored locally (no remote backend — homework scope).
- Python 3.13 everywhere (Lambda runtime + local dev). Latest version supported by AWS Lambda.
- Terraform: 1.14.6.
- Pandas via AWS-managed AWSSDKPandas layer (or a slim custom layer if needed).
- Model choice: gradient boosted trees (e.g., `sklearn.ensemble.GradientBoostingRegressor` or `HistGradientBoostingRegressor`) — good accuracy for tabular data, native sklearn, tunable for asymmetric loss.
- Underestimation bias: use asymmetric loss or post-hoc quantile adjustment.
- No remote ML infra (SageMaker etc.) — notebook-only training per the assignment.

## Repo Structure (planned)

```
snapsoft-homework/
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── lambda/
│       └── preprocess.py
├── notebook/
│   └── training.ipynb
├── ml_sample_data_snapsoft.csv
├── README.md
└── agent.md
```
