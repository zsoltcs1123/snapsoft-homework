# Task 4 — Interview Prep Notes

Personal reference for reasoning about the Lambda preprocessing implementation.

---

## Why this code structure?

The handler follows **SLAP** (Single Level of Abstraction Principle). `lambda_handler` reads as a flat sequence of high-level steps — parse, guard, read, transform, write, respond. Each step delegates to a named function one level below. No inline plumbing in the handler.

This matters because:
- A reviewer can understand the full pipeline in 10 seconds by reading `lambda_handler` alone.
- Each helper is independently testable and replaceable.
- The I/O layer (`read_csv_from_s3`, `write_csv_to_s3`) is cleanly separated from the transformation layer (`preprocess`, `drop_non_ml_columns`, `drop_incomplete_rows`). If you wanted to unit-test `preprocess`, you'd just pass it a DataFrame — no mocking required.

---

## Why no imputation in the Lambda?

Imputation is a model-dependent decision. Median imputation works for gradient boosting but you'd want different strategies for linear models (e.g., indicator variables for missingness). The Lambda's job is deterministic cleaning — remove what's structurally unusable. The notebook owns ML-specific choices.

This is also a separation-of-concerns argument: the Lambda is a data engineering component, the notebook is a data science component. They should be independently changeable.

---

## Why environment variable for the curated bucket?

The Lambda needs to know where to write, but the bucket name is defined in Terraform. Hardcoding it creates a coupling between the Python code and the Terraform config. An environment variable (set by Terraform via the Lambda's `environment` block) keeps them loosely coupled.

The variable is validated at module load time — if it's missing, the Lambda fails on cold start with a clear `RuntimeError` rather than a confusing `KeyError` buried in the handler during the first invocation.

---

## Error handling philosophy

**Strategy:** catch everything at the top of `lambda_handler`, log the full traceback, re-raise.

**Why re-raise?** S3-triggered Lambdas are invoked asynchronously. If the function raises, Lambda retries twice (configurable). If we swallowed the error, it would silently succeed from Lambda's perspective and never retry. Re-raising preserves the retry contract.

**Why `logger.exception()`?** It captures the full stack trace into CloudWatch. Without it, an unhandled exception still shows up in CloudWatch, but the log format is less structured and harder to filter.

**Why `errors="ignore"` on column drop?** Defensive programming. If someone uploads a CSV that's already been cleaned (no PII columns), the Lambda shouldn't crash. It just skips the columns that aren't there.

**Why filter critical columns to those present?** Same reasoning — `dropna(subset=...)` throws `KeyError` if a listed column doesn't exist in the DataFrame. By filtering to `[c for c in CRITICAL_COLUMNS if c in df.columns]`, we handle edge cases like partial CSVs without crashing.

---

## Why skip non-CSV files instead of erroring?

The S3 notification is filtered to `.csv` suffix in Terraform (Task 5), so in practice only CSVs should trigger the Lambda. The `.csv` check in the handler is a defense-in-depth measure — if someone misconfigures the filter or triggers the Lambda manually with a non-CSV event, it logs a warning and returns cleanly instead of crashing on `pd.read_csv`.

---

## Why `unquote_plus` on the object key?

S3 event notifications URL-encode the object key. Spaces become `+`, special characters become `%XX`. If you don't decode, you'll call `s3.get_object()` with the wrong key and get a `NoSuchKey` error. `unquote_plus` handles both `+` and `%XX` encoding.

---

## Anticipated interview questions

**Q: Why not use S3 Select to filter the CSV server-side?**
A: S3 Select can push down row/column filtering to S3, avoiding downloading the full file. For 245 rows it's unnecessary. At scale (millions of rows), it would reduce Lambda memory and execution time. The trade-off is more complex query syntax and less flexibility for transformations.

**Q: Why pandas and not just the csv module?**
A: Pandas handles multiline quoted fields (the `dealershipaddress` column contains newlines), null detection, and column operations in one line. The stdlib `csv` module would require manual null handling and column indexing. The trade-off is Lambda cold start time (~2s for pandas) — acceptable for an event-driven batch process, but you'd avoid it for latency-sensitive APIs.

**Q: What happens if two files are uploaded simultaneously?**
A: Each upload triggers a separate Lambda invocation. They run independently and write to different keys in the curated bucket (same filename). No contention. If they had the same filename, the last write wins — but that's a data pipeline design issue, not a Lambda issue.

**Q: What if the CSV is very large?**
A: The Lambda reads the entire file into memory. With the default 128 MB memory and pandas overhead, you'd hit limits around 10-20 MB CSV files. Solutions: increase Lambda memory (up to 10 GB), use streaming/chunked reads, or switch to AWS Glue for large-scale ETL. For this homework's 245-row file, it's a non-issue.

**Q: Why not write Parquet instead of CSV?**
A: Parquet is better for analytics (columnar, compressed, typed). For this homework, CSV keeps things simple and the notebook can read it directly. In production, I'd write Parquet to the curated zone — it's smaller, faster to read, and preserves column types.

---

## What I'd do differently in production

1. **Schema validation:** Validate column names, types, and allowed values against a schema before processing. Reject or quarantine malformed files.
2. **Dead-letter queue:** Configure a DLQ on the Lambda so permanently failed events don't get silently dropped after retries.
3. **Metrics:** Emit custom CloudWatch metrics (rows processed, rows dropped, processing time) for monitoring dashboards.
4. **Idempotency:** Write to a key that includes a processing timestamp or hash to avoid overwriting if the same file is reprocessed.
5. **Testing:** Unit tests for `preprocess()` with pytest (no mocking needed thanks to I/O separation). Integration tests with moto or localstack for the full S3 round-trip.
6. **Output format:** Parquet instead of CSV for type safety and compression.
