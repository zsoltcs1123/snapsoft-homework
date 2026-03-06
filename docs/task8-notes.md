# Task 8 — Interview Prep Notes

Personal reference for reasoning about the README and deliverable packaging.

---

## What's in the zip

| File | Purpose |
|---|---|
| `terraform/main.tf` | All AWS resources: 2 S3 buckets, IAM role, Lambda, S3 notification |
| `terraform/variables.tf` | `aws_region` (default eu-central-1), `bucket_prefix` (required) |
| `terraform/outputs.tf` | Bucket names and Lambda ARN for scripting |
| `terraform/lambda/preprocess.py` | Preprocessing logic: drop PII columns, drop rows missing critical attributes |
| `notebook/training.ipynb` | Model training and evaluation with quantile loss for underestimation |
| `README.md` | Deployment instructions, architecture overview, teardown |

Total: 6 files. Matches the assignment deliverable list exactly.

---

## What's excluded and why

| Excluded | Reason |
|---|---|
| `terraform.tfvars` | Contains a personal bucket prefix. Reviewer creates their own per README instructions. |
| `.terraform/`, `*.tfstate*`, `build/` | Terraform runtime artifacts — must not be shared |
| `exploration.ipynb` | Scratch EDA notebook, not a deliverable. Interview talking point only. |
| `ml_sample_data_snapsoft.csv` | Raw data provided separately by the company |
| `docs/`, `AGENTS.md`, `tasks.md` | Internal project management files |
| `pyproject.toml`, `uv.lock`, `.python-version` | Local dev tooling config |

---

## README structure rationale

The README is aimed at a technical reviewer who wants to deploy and verify quickly. Structure:

1. **One-paragraph overview** — establishes context without filler
2. **ASCII architecture diagram** — shows the full data flow at a glance. Chose ASCII over Mermaid because it renders in any text editor without a Markdown renderer.
3. **Prerequisites** — listed upfront so the reviewer knows what to install before starting
4. **Deploy / Usage / Teardown** — copy-pastable commands with placeholders. Terraform outputs are referenced so the reviewer can script the upload step.
5. **Design decisions** — brief (3 sentences) covering quantile loss choice and local state. Signals thoughtfulness without padding the submission with unsolicited docs.

---

## Why no `terraform.tfvars` in the zip?

S3 bucket names are globally unique. Shipping a hardcoded prefix would cause name collisions for the reviewer. The README instructs them to create `terraform.tfvars` with their own prefix. This is idiomatic Terraform — `.tfvars` files are commonly `.gitignore`d when they contain environment-specific values.

---

## Anticipated interview questions

**Q: Why didn't you include the data file?**
A: The assignment says the company provides the data separately and uploads it to the landing zone. Including it in the zip would imply the Lambda expects a specific file, when in reality it processes any `.csv` uploaded to the landing bucket.

**Q: What if I deploy to a different region?**
A: Override `aws_region` in `terraform.tfvars`. The only region-dependent resource is the Pandas Lambda layer ARN, which is interpolated from the variable. All other resources are region-agnostic.

**Q: Why no CI/CD pipeline?**
A: Out of scope for the assignment. In production you'd have a GitHub Actions or GitLab CI pipeline running `terraform plan` on PR and `terraform apply` on merge to main. The notebook would run as a scheduled job (e.g., SageMaker Pipeline or Airflow DAG).

**Q: Why local Terraform state?**
A: ADR-0002 — homework scope. Remote state (S3 + DynamoDB) is mandatory for teams but adds setup overhead with no benefit for a single-developer submission.
