# Task 5 — Interview Prep Notes

Personal reference for reasoning about the Terraform infrastructure decisions.

---

## Why a single `main.tf`?

The entire infrastructure is ~9 resources. Splitting into `iam.tf`, `s3.tf`, `lambda.tf` adds file-juggling overhead with no readability benefit at this scale. In production with 30+ resources across multiple services, you'd split by concern.

---

## Resource-by-resource reasoning

| Resource | Why |
|---|---|
| `aws_s3_bucket` x 2 | Landing and curated zones are separate buckets, not prefixes in one bucket. This gives independent access policies, lifecycle rules, and event configurations. |
| `aws_iam_role` + inline policy | Inline policy keeps the IAM definition co-located with the resource it serves. For a single-purpose Lambda, there's no reuse argument for a managed policy. |
| `aws_lambda_function` | Python 3.13, 256 MB memory, 60s timeout. Memory is sized for Pandas cold-start overhead (the layer itself is ~60 MB). Timeout is generous for a 491-row CSV but cheap insurance. |
| `aws_lambda_permission` | Required for S3 to invoke Lambda cross-service. Without it, the notification silently fails. |
| `aws_s3_bucket_notification` | Filtered to `.csv` suffix so non-CSV uploads don't trigger the Lambda. `depends_on` the permission to avoid a race condition during apply. |
| `data "archive_file"` | Zips `lambda/` directory at plan time. `source_code_hash` ensures Terraform detects code changes and redeploys. |

---

## Why the AWS-managed Pandas layer?

AWS publishes a managed layer (`AWSSDKPandas-Python313`) under account `336392948345`. Benefits:

- Zero build/upload effort — just reference the ARN.
- Maintained by AWS — security patches handled upstream.
- Includes pyarrow and other data dependencies.

Trade-off: the layer is ~60 MB and includes more than just Pandas (awswrangler, pyarrow). A custom slim layer with only Pandas would reduce cold-start time by ~200-300 ms. Not worth optimizing for a homework project, but worth mentioning.

The ARN is region-dependent, so it's interpolated from `var.aws_region` rather than hardcoded.

---

## IAM: least privilege within homework scope

The Lambda role grants:

- `s3:GetObject` scoped to the landing bucket only
- `s3:PutObject` scoped to the curated bucket only
- CloudWatch Logs permissions (broad `arn:aws:logs:*:*:*` — acceptable for homework; in production you'd scope to the specific log group)

The assume-role policy restricts to `lambda.amazonaws.com` — no other service can assume this role.

**If they ask "why not use AWSLambdaBasicExecutionRole?":** That's a managed policy that grants CloudWatch Logs access. Using it means one fewer inline statement, but you then need a separate `aws_iam_role_policy_attachment`. For a single Lambda with a simple policy, inline is more readable and self-contained.

---

## What's deliberately missing (and why)

| Missing feature | Why omitted | What you'd add in production |
|---|---|---|
| S3 bucket versioning | Unnecessary complexity for demo data | `aws_s3_bucket_versioning` — enables rollback and audit trail |
| S3 encryption (SSE-S3 / KMS) | Default encryption is now on by default for new S3 buckets (since Jan 2023) | Explicit KMS key for cross-account access or compliance |
| S3 lifecycle rules | Dataset is tiny, no retention concern | Expire old objects, transition to Glacier |
| S3 public access block | New buckets are private by default (since April 2023) | Explicit `aws_s3_bucket_public_access_block` for defense-in-depth |
| Remote state backend | ADR-0002 — local state is sufficient for homework | S3 + DynamoDB for team collaboration and state locking |
| Lambda VPC config | Lambda only talks to S3 (public endpoint) | VPC + NAT if the Lambda needed to reach private resources |
| Lambda dead-letter queue | Failures are visible in CloudWatch | SQS DLQ for retry and alerting |
| Lambda reserved concurrency | No traffic concern | Prevent runaway invocations from consuming account-level concurrency |
| CloudWatch alarms | Manual log inspection is fine for demo | Alarm on error rate, duration, throttles |

---

## Variables design

- `aws_region` defaults to `eu-central-1` — a sensible European region. Parameterized so the reviewer can deploy anywhere.
- `bucket_prefix` has no default — forces the deployer to pick a globally unique prefix. This avoids bucket name collisions without resorting to random suffixes.

**If they ask "why not use `random_id` for bucket names?":** Random names are hard to reference in scripts and documentation. A human-chosen prefix is more practical for a demo. In a CI/CD pipeline you'd typically use the environment name or account ID as the prefix.

---

## `archive_file` vs. external build step

The `archive_file` data source zips the `lambda/` directory at plan/apply time. This works because the Lambda has no pip dependencies — everything comes from the managed Pandas layer.

If the Lambda needed custom pip packages, you'd need a `null_resource` with a `local-exec` provisioner to run `pip install -t` into a build directory before zipping. Or use a container-based Lambda.

---

## Anticipated interview questions

**Q: Why not use SAM or CDK?**
A: The assignment specifically asks for Terraform `.tf` files. SAM is AWS-only and abstracts away the underlying resources. CDK generates CloudFormation, not Terraform. Both are valid in practice, but Terraform is more portable and explicit.

**Q: What happens if the Lambda fails?**
A: The S3 event notification is asynchronous — S3 retries twice with backoff. After 3 failures, the event is dropped (or sent to a DLQ if configured). CloudWatch Logs capture the error. For this homework, that's sufficient.

**Q: What if someone uploads a 1 GB CSV?**
A: The Lambda has 256 MB memory and 60s timeout — it would fail. For large files, you'd use Step Functions to orchestrate chunked processing, or switch to Glue/EMR. The preprocessing logic in `preprocess.py` is stateless, so it could run anywhere.

**Q: Why separate landing and curated buckets instead of prefixes?**
A: Separate buckets give you independent IAM policies (the Lambda can read landing but not write to it), independent event notifications, and clearer cost attribution. Prefixes in one bucket would work but blur these boundaries.
