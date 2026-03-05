# Task 6 — Interview Prep Notes

Personal reference for reasoning about deployment and pipeline validation.

---

## Deployment summary

| Step | Command | Result |
|---|---|---|
| Init | `terraform init` | Providers reused from lock file (aws 5.100.0, archive 2.7.1) |
| Plan | `terraform plan` | 7 resources to create, 0 to change, 0 to destroy |
| Apply | `terraform apply -auto-approve` | All 7 resources created in ~37s |

Resources created: 2 S3 buckets, 1 IAM role, 1 IAM role policy, 1 Lambda function, 1 Lambda permission, 1 S3 bucket notification.

The `bucket_prefix` variable is set to `snapsoft-hw-zcsikos` via `terraform.tfvars`.

---

## End-to-end validation results

| Check | Expected | Actual | Status |
|---|---|---|---|
| Curated file appears in bucket | File exists after upload | Appeared within ~5s | PASS |
| PII columns removed | 7 columns absent | All 7 absent | PASS |
| Column count | 27 - 7 = 20 | 20 | PASS |
| Rows with missing critical cols dropped | Some rows removed | 245 -> 235 (10 dropped) | PASS |
| No nulls in critical columns | 0 nulls in carbody, fueltype, drivewheel, Price | 0 across all four | PASS |
| Lambda logs show success | No errors in CloudWatch | Clean execution, info-level logs only | PASS |

---

## Lambda performance observations

| Metric | Value |
|---|---|
| Cold start (init duration) | 2,879 ms |
| Processing duration | 604 ms |
| Billed duration | 3,484 ms |
| Max memory used | 199 MB / 256 MB |

The cold start is dominated by the AWSSDKPandas layer (~60 MB uncompressed). For a 245-row CSV this is fine. Memory headroom is ~57 MB — sufficient for this dataset but would need bumping for files >10k rows.

---

## Why `-auto-approve`?

Used for convenience in a homework context. In production you'd run `terraform plan -out=tfplan` followed by `terraform apply tfplan` to guarantee the applied plan matches what was reviewed. The `-auto-approve` flag skips the interactive confirmation prompt — acceptable here because we reviewed the plan output in the previous step.

---

## Why `terraform.tfvars` instead of `-var`?

A `.tfvars` file avoids repeating `-var bucket_prefix=...` on every command. It contains no secrets (just a naming prefix) so it's safe to commit. For sensitive values you'd use environment variables (`TF_VAR_*`) or a `.tfvars` file excluded from version control.

---

## Anticipated interview questions

**Q: How do you know the Lambda actually ran vs. the file just being copied?**
A: CloudWatch Logs show the full execution trace: INIT_START, the Lambda's info logs (`Dropped 10 rows`, `Processed ... 245 rows -> 235 rows`), and the REPORT line with duration and memory. The curated file is also smaller (23 KB vs 56 KB) and has fewer columns and rows — confirming transformation happened.

**Q: What if the Lambda fails silently?**
A: S3 event notifications to Lambda are asynchronous. If the Lambda throws an exception, S3 retries twice with exponential backoff. After 3 failures the event is discarded (unless a dead-letter queue is configured). The `logger.exception` call in the handler ensures failures are visible in CloudWatch. For production, you'd add a CloudWatch alarm on the Lambda error metric and an SQS DLQ.

**Q: How would you validate this in CI/CD?**
A: Run `terraform plan` in CI and fail the build if the plan has unexpected changes. For the end-to-end test: upload a known test CSV, poll the curated bucket for output, then run assertions on the output file (column list, row count, null checks). The validation script I ran locally could be wrapped in a pytest fixture.

**Q: What's the cold start cost in production?**
A: ~2.9s for the first invocation. Subsequent invocations reuse the warm container and take ~600ms. If latency matters, you'd use provisioned concurrency (keeps N containers warm). For a batch ETL pipeline triggered by file uploads, cold start latency is irrelevant — the user doesn't wait synchronously.
