# AGENTS.md

## Goal

Solve the SnapSoft Solution Architect homework: build an AWS-based, event-driven pipeline that preprocesses second-hand car sales data and trains an ML model to estimate selling prices.

The homework is described in the file `homework.md`.
The dataset file is found at `ml_sample_data_snapsoft.csv` (491 rows + header).

## About the User

- 10+ years software development experience.
- Strong general architecture/engineering skills.
- Gaps: AWS (experienced with Azure), Python ML ecosystem (sklearn, pandas in ML context).
- Applying for a **Solution Architect** position — deliverables must be professional, well-reasoned, but not overengineered.

## Architecture at a Glance

- **Landing zone S3 bucket** → S3 event notification → **Lambda** (Python + Pandas layer) → **Curated zone S3 bucket**.
- Notebook reads from curated zone, trains & evaluates model locally.

## Workflow

- Tasks are described in the file `tasks.md` with status tracking.
- The user will ask you to plan or execute a task.
- Definition of done:
  - the task is implemented according to the description
  - all acceptance criteria are met
  - all verification scenarios are met
  - an accompanying note is created in `docs` explaining the decisions and the implementation so the user can reason about it in an interview setting

## Deliverables (zip)

1. **Terraform files** — IaC defining the full AWS architecture.
2. **Python Lambda script** — preprocessing logic (drop PII/non-ML columns, drop rows missing critical attributes, keep imputable rows).
3. **Jupyter Notebook** — load curated data, train an sklearn-compatible model, evaluate it. Model should slightly underestimate price (business preference).
4. **README** — terraform deployment instructions.

## Key Decisions / Assumptions

- Terraform uses AWS provider; state stored locally (no remote backend — homework scope).
- Python 3.13 everywhere (Lambda runtime + local dev). Latest version supported by AWS Lambda.
- Terraform: 1.14.6.
- Pandas via AWS-managed AWSSDKPandas layer (or a slim custom layer if needed).
- Model choice: gradient boosted trees (e.g., `sklearn.ensemble.GradientBoostingRegressor` or `HistGradientBoostingRegressor`) — good accuracy for tabular data, native sklearn, tunable for asymmetric loss.
- Underestimation bias: use asymmetric loss or post-hoc quantile adjustment.
- No remote ML infra (SageMaker etc.) — notebook-only training per the assignment.
