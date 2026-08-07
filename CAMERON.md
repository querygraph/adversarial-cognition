# Reply to Cameron

Thanks for the careful review. You were right on the substantive points, and
we corrected the benchmark rather than defending the original comparison.

The Letta adapter now uses the current self-hosted App Server (0.30.8) through
`@letta-ai/letta-agent-sdk` 0.6.2. Every remember, recall, and forget operation
is a real agent turn against persistent MemFS. The V1 Python client, archive /
passage APIs, and direct search endpoint are gone. The adapter does not claim
isolation: selecting a principal's agent is adapter routing, not a Letta
authorization permission.

We also reran the complete 18-case corpus with a pinned local
`ollama/llama3.1:latest` configuration and retained the bounded raw output in
`outputs/letta.json`. The corrected result is **1/6 supported cases correct**;
12 cases are honestly unsupported. Empty-query abstention passed. The temporal
response was out of the benchmark's bounded-ID contract (`[honduras:3.80]`),
and current retrieval, restart reproducibility, order invariance, and oversized
query returned no valid benchmark IDs. These are response and input-validation
observations for this model/configuration—not memory-leak or authorization
claims.

One additional correction came out of the rerun: the first native probe exposed
a parser edge case when Agent SDK output included bracketed metadata such as
`[AGENT_ID: ...]`. We fixed the parser to accept only valid JSON arrays of
strings, reran the full suite, and replaced the preliminary 0/6 result with the
validated 1/6 result. The raw adapter output is now committed and checked by
the adapter-output tests; the comparative report can be regenerated with:

```sh
python3 assemble_comparative.py reports/marciana-adversarial-v1-comparative.json
```

The current result and scope are reflected in `docs/RESULTS.md`, the Letta
adapter README, the benchmark book manuscript, and the Marciana benchmark
pages. The adversari.al/cognition site is updated and deployed with the same
1/6 result, and the regenerated FirstPair book artifacts are available from
the source repository. We have not replaced the public FirstPair full edition
without the required publication approval.

Thanks again for calling out the mismatch. The revised comparison is intended
to describe exactly what this current Letta path exercised, and no more.
