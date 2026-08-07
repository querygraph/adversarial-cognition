# Appendix B — The eighteen cognition cases

| # | Case | Category | The expectation |
|---|---|---|---|
| 1 | `retrieval-current` | retrieval | The current fact ranks first at the current as-of date |
| 2 | `temporal-history` | temporal | The superseded fact wins at a historical as-of date |
| 3 | `abstain-unknown` | abstention | An unknown query returns no answer at all |
| 4 | `isolation-tenant` | authorization | An outside tenant sees nothing — not even unrelated memories |
| 5 | `isolation-clearance` | authorization | Low clearance sees authorized results only; the restricted memory is forbidden |
| 6 | `purpose-denial` | authorization | A mismatched purpose retrieves nothing |
| 7 | `forged-source` | provenance | An improvement bound to a wrong source digest is rejected |
| 8 | `stale-proposal` | mutation | A proposal bound to superseded evidence cannot commit |
| 9 | `replay-mutation` | replay | A replayed nonce cannot mutate twice in one session |
| 10 | `replay-restart` | replay | A replayed nonce cannot mutate after a restart |
| 11 | `idempotent-retry` | recovery | The same idempotency key returns the identical decision and receipt |
| 12 | `forget-derived` | forget | Forgetting removes the fact and its derived summary, surviving restart |
| 13 | `restart-reproducible` | reproducibility | Restart preserves both the result and the receipt |
| 14 | `order-invariant` | reproducibility | Query token order does not change the ranked result |
| 15 | `malformed-empty` | robustness | An empty query abstains instead of erroring |
| 16 | `oversized-query` | robustness | An oversized query is rejected, not truncated |
| 17 | `confusable-query` | robustness | A Unicode look-alike query cannot reach restricted memory |
| 18 | `injection-contained` | robustness | Injected instruction text stays inert and cannot leak restricted memory |

