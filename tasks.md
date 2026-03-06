# Work Breakdown: SnapSoft AI&ML Homework

## Summary

Build an event-driven AWS pipeline (Terraform + Lambda) that preprocesses second-hand car sales data from a landing S3 bucket into a curated S3 bucket, then train and evaluate an sklearn model in a Jupyter notebook that slightly underestimates car prices.

| #   | Task                                          | Depends on | Status  |
| --- | --------------------------------------------- | ---------- | ------- |
| 1   | Set up project repository and tooling         | None       | DONE    |
| 2   | Set up AWS account and credentials            | None       | DONE    |
| 3   | Explore and document the dataset              | None       | DONE    |
| 4   | Write the Lambda preprocessing script         | 3          | DONE    |
| 5   | Author the Terraform infrastructure           | 4          | DONE    |
| 6   | Deploy and validate the pipeline              | 2, 5       | DONE    |
| 7   | Build the ML training and evaluation notebook | 3, 6       | DONE    |
| 8   | Write the README and package deliverables     | 5, 6, 7    | DONE    |

## Tasks

### 1. Set up project repository and tooling

Initialize the git repo, folder structure, and confirm all local tools are working.

**Steps:**

1. Run `git init` in the project directory and create a `.gitignore` (Python, Terraform, Jupyter artifacts, `.terraform/`, `*.tfstate*`, `__pycache__/`, `.ipynb_checkpoints/`)
2. Create the folder structure: `terraform/`, `terraform/lambda/`, `notebook/`
3. Install Python 3.13 (`uv python install 3.13`) and pin it for the project. Verify local tooling: `python --version` (3.13.x), `terraform --version` (1.14.6), confirm `jupyter` is available
4. Create an initial commit with the repo skeleton and the sample CSV

**Acceptance criteria:**

- Git repo is initialized with a clean `.gitignore` covering all relevant artifacts
- Folder structure matches the planned layout
- Python, Terraform, and Jupyter are confirmed working locally

**Verification scenarios:**

- `git status` shows clean working tree after initial commit
- `terraform --version` returns 1.14.x
- `python --version` returns 3.13.x
- `jupyter --version` runs without error

**Depends on:** None

---

### 2. Set up AWS account and credentials

Create an AWS account (Free Tier), configure an IAM user for programmatic access, and set up the AWS CLI locally.

**Steps:**

1. Create an AWS account at aws.amazon.com (use Free Tier)
2. Sign in to the AWS Console, create an IAM user with programmatic access and attach the `AdministratorAccess` policy (homework scope — in production you'd use least privilege)
3. Generate access keys for the IAM user
4. Install the AWS CLI locally and run `aws configure` to set the access key, secret key, and default region (e.g., `eu-central-1`)
5. Verify connectivity by running `aws sts get-caller-identity`

**Acceptance criteria:**

- AWS CLI is configured and can authenticate against the AWS account
- `aws sts get-caller-identity` returns the IAM user's ARN

**Verification scenarios:**

- `aws sts get-caller-identity` — returns a valid JSON response with Account, UserId, and Arn
- `aws s3 ls` — runs without authentication errors (may return empty list)

**Validation scenarios:**

- Run `aws sts get-caller-identity` from the terminal — expect JSON with the correct account ID and IAM user ARN — Automation: full
- Run `aws s3 ls` — expect no error — Automation: full

**Depends on:** None

---

### 3. Explore and document the dataset

Analyze the CSV to make informed decisions about which columns to drop, which rows to remove, and which missing values to impute. Record these decisions so tasks 4 and 7 can reference them.

**Steps:**

1. Load `ml_sample_data_snapsoft.csv` in a scratch notebook or script; inspect shape, dtypes, and first/last rows
2. Identify PII / non-ML columns: `car_ID`, `CarName`, `ownername`, `owneremail`, `dealershipaddress`, `saledate`, `iban` — these have no predictive value for price or are privacy-sensitive
3. Profile each remaining column for missing values, outliers, and cardinality
4. Decide "critical" columns (rows missing these get dropped): `carbody`, `fueltype`, `drivewheel`, `Price` — these define the car's identity and the target variable
5. Decide "imputable" columns (rows missing these are kept): numeric columns like `horsepower`, `enginesize`, `peakrpm` etc. — can be imputed by median or group median
6. Document findings and decisions in `agent.md` or a section in the notebook

**Acceptance criteria:**

- Columns are classified into three groups: drop (PII/non-ML), critical (must-have), imputable
- Missing-value profile is known for each column
- Decisions are documented and referenced by later tasks

**Verification scenarios:**

- Load the CSV and count nulls per column — counts match the documented profile
- Confirm PII columns contain no predictive signal (e.g., `ownername` has no correlation with Price)
- Confirm critical columns, when missing, make the row unusable (e.g., a row with no `carbody` can't be categorized)

**Depends on:** None

---

### 4. Write the Lambda preprocessing script

Implement the Python function that reads a CSV from the landing S3 bucket, applies the preprocessing rules from task 3, and writes the cleaned CSV to the curated bucket.

**Steps:**

1. Create `terraform/lambda/preprocess.py` with a `lambda_handler(event, context)` function
2. Extract the source bucket and object key from the S3 event payload
3. Read the CSV into a Pandas DataFrame using `s3.get_object()`
4. Drop PII/non-ML columns (`car_ID`, `CarName`, `ownername`, `owneremail`, `dealershipaddress`, `saledate`, `iban`)
5. Drop rows where critical columns are null (`carbody`, `fueltype`, `drivewheel`, `Price`, and possibly others identified in task 3)
6. Write the cleaned DataFrame as CSV to the curated bucket (same filename) using `s3.put_object()`
7. Add basic logging (file processed, rows before/after, columns dropped) and error handling

**Acceptance criteria:**

- Lambda handler correctly parses S3 event, reads CSV, applies transformations, writes result
- PII columns are removed from output
- Rows missing critical attributes are removed; rows missing only imputable attributes are preserved
- Output CSV is written to the curated bucket with the same filename

**Verification scenarios:**

- Input CSV with all rows valid — output has same row count, PII columns removed
- Input CSV with rows missing `carbody` — those rows are absent from output
- Input CSV with rows missing `horsepower` only — those rows are preserved in output
- Input with a non-CSV file key — handler logs a warning / handles gracefully
- Empty CSV (header only) — output is a header-only CSV, no crash

**Validation scenarios:**

- Upload sample CSV to landing bucket via CLI, check curated bucket for output file, download and verify column list and row count — Automation: full
- Upload CSV with intentionally missing critical fields, verify those rows are dropped — Automation: full

**Depends on:** 3

---

### 5. Author the Terraform infrastructure

Define all AWS resources as Terraform code: S3 buckets, Lambda function with IAM role, S3 event notification, and the Pandas Lambda layer.

**Steps:**

1. Create `terraform/main.tf` with the AWS provider block (region parameterized via variable)
2. Define two S3 buckets: landing zone and curated zone (with sensible naming, e.g., prefixed with a variable for uniqueness)
3. Define the IAM role for the Lambda function with policies for S3 read (landing), S3 write (curated), and CloudWatch Logs
4. Define the Lambda function resource: Python 3.13 runtime, handler pointing to `preprocess.lambda_handler`, attach the IAM role, configure a Pandas layer (use the AWS SDK for Pandas managed layer ARN or a custom layer)
5. Define the S3 bucket notification on the landing bucket: trigger the Lambda on `s3:ObjectCreated:*` filtered to `.csv` suffix
6. Add the `aws_lambda_permission` to allow S3 to invoke the Lambda
7. Create `terraform/variables.tf` (region, bucket name prefix) and `terraform/outputs.tf` (bucket names, Lambda ARN)

**Acceptance criteria:**

- `terraform validate` passes with no errors
- `terraform plan` produces a plan creating: 2 S3 buckets, 1 Lambda function, 1 IAM role + policies, 1 S3 notification, 1 Lambda permission
- All resources are parameterized via variables where appropriate

**Verification scenarios:**

- `terraform validate` — passes
- `terraform plan` — shows expected resource count, no errors
- Changing the `region` variable — plan reflects the new region
- Changing the `bucket_prefix` variable — bucket names update accordingly

**Validation scenarios:**

- Run `terraform apply`, confirm all resources are created in the AWS Console — Automation: partial (apply is automated, console verification is visual)
- Upload a CSV to the landing bucket, verify Lambda execution in CloudWatch Logs — Automation: full

**Depends on:** 4

---

### 6. Deploy and validate the pipeline

Apply the Terraform config to AWS and run an end-to-end test with the sample CSV.

**Steps:**

1. Run `terraform init` in the `terraform/` directory
2. Run `terraform plan` and review the output
3. Run `terraform apply` and confirm
4. Upload `ml_sample_data_snapsoft.csv` to the landing bucket using `aws s3 cp`
5. Wait briefly, then check the curated bucket for the output file
6. Download the curated file and verify: PII columns removed, row count reflects dropped rows, all remaining rows are valid
7. Check CloudWatch Logs for the Lambda invocation — confirm it ran without errors

**Acceptance criteria:**

- All Terraform resources deploy successfully
- Uploading a CSV to the landing bucket triggers the Lambda and produces a cleaned CSV in the curated bucket
- Lambda logs show successful execution with row/column counts

**Verification scenarios:**

- Upload sample CSV — curated bucket contains a file with the same name
- Curated CSV has no PII columns
- Curated CSV has fewer or equal rows (depending on data quality)
- Lambda CloudWatch logs show processing summary without errors

**Validation scenarios:**

- Run `aws s3 cp ml_sample_data_snapsoft.csv s3://<landing-bucket>/`, wait 10s, run `aws s3 ls s3://<curated-bucket>/` — file appears — Automation: full
- Download curated file, diff column headers against expected list — Automation: full
- `aws logs tail /aws/lambda/<function-name> --since 1m` — shows success log entries — Automation: full

**Depends on:** 2, 5

---

### 7. Build the ML training and evaluation notebook

Create a Jupyter notebook that loads the curated data, performs feature engineering, trains a model biased toward underestimation, and evaluates it with appropriate metrics.

**Steps:**

1. Create `notebook/training.ipynb`; load the curated CSV from S3 (or local copy for development)
2. Perform brief EDA: distributions, correlations with Price, check for remaining nulls
3. Preprocess features: encode categoricals (one-hot or ordinal), impute missing numerics (median), scale if needed
4. Split data into train/test sets (e.g., 80/20)
5. Train a `GradientBoostingRegressor` (or `HistGradientBoostingRegressor`) with `loss='quantile'` and `alpha=0.4` (or similar) to bias predictions below actual price
6. Evaluate: MAE, RMSE, R², and a custom "underestimation rate" metric (% of predictions below actual). Visualize predicted vs. actual.
7. Briefly discuss model choice and the underestimation approach in markdown cells

**Acceptance criteria:**

- Notebook runs end-to-end without errors
- Model is trained and evaluated on held-out test data
- Predictions systematically lean toward underestimation (>50% of predictions are below actual price)
- Evaluation metrics and a predicted-vs-actual plot are included

**Verification scenarios:**

- Notebook executes from top to bottom without errors (Restart & Run All)
- Underestimation rate on test set is > 50% (ideally 60-70%)
- R² is positive and reasonable (> 0.7 for this dataset would be good)
- No data leakage: test set was not seen during training
- Imputation handles the same missing-value columns documented in task 3

**Validation scenarios:**

- Run all cells in Jupyter — final cell outputs metrics and plot — Automation: partial (execution is automated, plot quality is visual)
- Change alpha to 0.5 (symmetric) and re-run — underestimation rate should drop to ~50% — Automation: full

**Depends on:** 3, 6

---

### 8. Write the README and package deliverables

Document the project and create the final zip for submission.

**Steps:**

1. Write `README.md` covering: project overview, architecture diagram (text-based), prerequisites (AWS account, Terraform, Python, AWS CLI), step-by-step Terraform deployment instructions (`init`, `plan`, `apply`), how to trigger the pipeline, how to run the notebook, teardown instructions (`terraform destroy`)
2. Review all files for consistency: variable names match between Terraform and README, bucket names are parameterized, no hardcoded secrets
3. Run a final end-to-end test: destroy and re-deploy from scratch, upload CSV, verify curated output, run notebook
4. Create the zip: `terraform/` (all .tf files + `lambda/preprocess.py`), `notebook/training.ipynb`, `README.md`
5. Verify the zip contents match the deliverable list from the assignment

**Acceptance criteria:**

- README contains clear Terraform deployment instructions that a reviewer can follow
- Zip contains exactly: Terraform files, Lambda script, notebook, README
- No secrets, state files, or `.terraform/` directory in the zip

**Verification scenarios:**

- Unzip the archive — contents match the expected file list
- Follow README instructions on a clean terminal — commands are copy-pastable and correct
- No `.tfstate`, `.terraform/`, `__pycache__`, or `.ipynb_checkpoints/` in the zip

**Validation scenarios:**

- Extract zip to a temp directory, run `terraform init && terraform validate` inside `terraform/` — succeeds — Automation: full
- Grep the zip contents for AWS access keys or secrets — no matches — Automation: full

**Depends on:** 5, 6, 7
