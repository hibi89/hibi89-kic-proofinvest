# P191 Public Apple 2026 real model numeric fact gate

The real CPU SmolLM2 135M model receives only two manually transcribed publicly
reported FY2026 SEC Apple 10-K Item 8 numbers: CFO 145097 and net income
132175 in USD millions. The precomputed difference 12922 and the expected
GREATER classification are not sent. Actual constrained model JSON output
must classify CFO vs net income, provide the exact known primary-source ID,
and emit HUMAN_REVIEW_ONLY. The model runs at localhost 127.0.0.1:11435 in
disposable pinned Ollama CI with public 105 MB Apache-2.0 weights.

The independent Python validator strictly parses the actual model envelope,
requires done=true and positive eval_count, exact claim/citation/decision with
no extras, and recomputes the correct comparison from P190's real SEC public
financial-statement figures with Decimal. Incorrect and free-text answers
BLOCK; Guard HOLD, zero trades and no display of model prose are mandatory.
No owner originals, market records, secrets, SEC API or external model requests.

If the actual [model-e2e] CI is successful and the accepted factual claim
is observed, this is a distinct real-public-issuer model source-linked fact
precondition, not the earlier synthetic missing-data A/B/C focus. It does not
prove independently authenticated raw SEC originals, full source rights,
licensed NDX or peers, full A/B/C factual narration or public Production.
The old 51/100 overall remains unchanged until authentic functional evidence
exists and scoring can be supported without double counting.
