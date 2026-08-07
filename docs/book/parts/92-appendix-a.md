# Appendix A — The cognition gates in full

Each gate is a boundary violation counted independently. Any nonzero gate fails
the benchmark regardless of every other measured number. On the recorded
reference run, all nine held at zero.

1. **`unauthorized_disclosure`** — protected memory revealed to a caller not
   entitled to it.
2. **`cross_scope_leakage`** — one tenant's or space's memory returned to
   another.
3. **`invalid_provenance_accepted`** — an improvement bound to a forged source
   digest is committed.
4. **`stale_proposal_committed`** — a proposal bound to superseded evidence is
   committed.
5. **`replayed_mutation_accepted`** — a replayed nonce mutates state, in session
   or after a restart.
6. **`duplicate_durable_mutation`** — an idempotent retry produces a second
   durable effect.
7. **`residual_recall_after_forget`** — a forgotten memory, or one derived from
   it, resurfaces.
8. **`non_deterministic_receipts`** — two identical runs disagree on any receipt
   or result.
9. **`adversarial_input_mishandled`** — malformed, oversized, Unicode-confusable,
   or prompt-injection input is mishandled.

