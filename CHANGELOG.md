# Changelog

## Unreleased

- Extract MARCIANA-ADVERSARIAL-v1 from querygraph/marciana (`cbf3592`) into
  a standalone repository: the deterministic reference backend, the
  eighteen-case pinned corpus, hard-gate and category-metric evaluation,
  the comparative adapter protocol, the offline public-corpus inventory,
  the runner, and the full test suite.
- Make the external adapter timeout configurable through
  `MARCIANA_ADVERSARIAL_TIMEOUT_SECONDS` for slow local-model adapters.
