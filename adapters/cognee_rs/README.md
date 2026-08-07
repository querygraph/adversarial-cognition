# Cognee Rust adapter

This entry runs the native `cognee-cli` from the official `topoteretes/cognee-rs`
repository. It is deliberately separate from the Python `cognee` adapter.

Build the CLI from the official `v0.2.0` checkout (the adapter was verified
against commit `038c5a9b0272af4185963b4d198bfb398f7c8ca9`), then configure the
benchmark command:

```sh
export COGNEE_RS_BIN=/path/to/cognee-cli
export MARCIANA_ADVERSARIAL_COGNEE_RS_CMD='adapters/cognee_rs/run.sh'
python run_benchmark.py --systems marciana,cognee-rs
```

From a checkout: `git checkout 038c5a9b0272af4185963b4d198bfb398f7c8ca9 &&
cargo build --release -p cognee-cli`.

The adapter uses a private `COGNEE_CONFIG_HOME` and data/system roots for each
run. It claims only native retrieval and persistence. Cognee's dataset name is
not an authorization boundary, so tenant and clearance cases remain explicitly
unsupported.
