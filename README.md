# Second-Hand Car Price Estimation Pipeline

Event-driven AWS pipeline that preprocesses second-hand car sales data and trains an ML model to estimate selling prices.

## Architecture

```
┌──────────────┐   S3 Event (.csv)   ┌────────────────────┐   PutObject   ┌───────────────────┐
│  S3 Landing  │ ──────────────────> │  Lambda (Python)   │ ───────────>  │    S3 Curated     │
│    Bucket    │                     │  + Pandas layer    │               │      Bucket       │
└──────────────┘                     └────────────────────┘               └─────────┬─────────┘
                                                                                   │
                                                                            Read curated CSV
                                                                                   │
                                                                         ┌─────────▼─────────┐
                                                                         │  Jupyter Notebook  │
                                                                         │  (sklearn model)   │
                                                                         └────────────────────┘
```

The Lambda drops PII and non-ML columns (car_ID, CarName, ownername, owneremail, dealershipaddress, saledate, iban) and removes rows missing critical attributes (carbody, fueltype, drivewheel, Price). Rows with imputable missing values are kept.

## Prerequisites

- AWS account with CLI configured (`aws configure`)
- Terraform >= 1.14
- Python 3.13 with Jupyter (`pip install notebook scikit-learn pandas matplotlib`)

## Deploy

```bash
cd terraform
```

Create `terraform.tfvars`:

```hcl
bucket_prefix = "your-globally-unique-prefix"
```

`aws_region` defaults to `eu-central-1`. Override it in `terraform.tfvars` if needed.

```bash
terraform init
terraform plan
terraform apply
```

Terraform outputs the bucket names and Lambda function name after apply.

## Usage

Upload a CSV to the landing bucket to trigger preprocessing:

```bash
aws s3 cp your-data.csv s3://<bucket_prefix>-landing/
```

The cleaned file appears in the curated bucket:

```bash
aws s3 ls s3://<bucket_prefix>-curated/
aws s3 cp s3://<bucket_prefix>-curated/your-data.csv .
```

## Notebook

Open `notebook/training.ipynb` in Jupyter. It loads the curated CSV, performs feature engineering (median/mode imputation, one-hot encoding via sklearn Pipeline), trains a `GradientBoostingRegressor` with quantile loss, and evaluates on a held-out test set.

```bash
cd notebook
jupyter notebook training.ipynb
```

Update the data path in the first code cell if your curated CSV is somewhere else.

## Design decisions

The model uses `GradientBoostingRegressor` with `loss='quantile'` and `alpha=0.4` so it learns to underestimate rather than center predictions. Lowering alpha increases the bias toward lower estimates. Terraform state is local -- no remote backend needed for a homework submission.

## Teardown

```bash
cd terraform
terraform destroy
```

This removes all AWS resources (S3 buckets, Lambda, IAM role, event notification). Objects in the buckets must be deleted first -- Terraform will prompt if they're not empty.
