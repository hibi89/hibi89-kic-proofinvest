# KUODRA — ML Evaluation Explanation Contract (P41)

Status 2026-10-31: deterministic interpreter and localhost-only optional Streamlit JSON uploader implemented; actual model training, model score reproduction, citation authentication and Gemini explanations are NOT implemented.

## Input: kuodra.ml-evaluation.v1

JSON is UTF-8, at most 65,536 bytes. For an EVALUATED record provide exactly:
- schema, status=EVALUATED, issuer_cik (10 numeric characters), as_of (YYYY-MM-DD), model_name, target
- evaluation object: split=WALK_FORWARD, train_end, test_start, test_end (ISO dates), train_rows and test_rows (positive integer counts), metric=MAE or RMSE, baseline_value and model_value (nonnegative finite decimal strings)
- features: 1 to 3 objects with name, method=PERMUTATION_IMPORTANCE or SHAP_ABSOLUTE_MEAN, importance (nonnegative decimal string), source_ids (existing IDs)
- sources: 1 to 12 objects with id, HTTPS url without credentials/query/fragment, published_at (ISO date), sha256 (64 lowercase hexadecimal characters).

For a declined model use only schema, status=NO_TRAIN or INSUFFICIENT_EVIDENCE, issuer_cik, as_of, reason_code. Missing evidence must NOT become a fabricated probability or model score.

## Processing and limits

Issuer CIK/as-of must match the currently entered local workspace fields. All test records must end by as-of, train_end must precede test_start, and source published_at must be <= as-of. Strict parse rejects duplicate JSON keys, NaN, oversized inputs, unknown fields, missing source IDs and wrong model/metric contracts. Output is a Korean deterministic summary of the reported baseline-vs-model error, model-attributed top factors, source IDs, URLs, dates, digests, sample counts and split ranges.

Every model-reported result states REPORTED_UNVERIFIED and model_verified=false, source_authenticated=false, ai_generated=false, trade_signal=false. Data truth, licensed use, actual source SHA, release vintages, true feature availability at each historical point, group leakage, model reproducibility and calibration remain separate gates. No LLM/API/network/trade or change to Decimal/Guard.

## Test

python -B -m unittest discover -s tests -p 'test_ml_explainability*.py' -v

9 targeted tests PASS, feature SHA 816996888b06637dd83b1b385d4a8939842d616a. GitHub Actions #41197719786 3/3 SUCCESS (Python, Windows SQLite, Chromium). Mock/synthetic inputs ONLY; this is not proof of trained model performance.
