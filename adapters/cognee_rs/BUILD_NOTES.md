# Cognee Rust build notes

These notes record the failed native build attempts so the Cognee Rust team
can reproduce and fix them. No benchmark score was produced from these runs.

## Environment

- Host: Apple Silicon macOS (arm64)
- Docker builder: `rust:1.91-bookworm` (arm64)
- Source: `topoteretes/cognee-rs`
- Commit: `038c5a9b0272af4185963b4d198bfb398f7c8ca9`
- Command: `cargo build --release -p cognee-cli`

## Failures observed

### Host build

The host build reached the `cxx` crate and failed because the active macOS
toolchain could not find the C++ standard header:

```text
cxx.h:2:10: fatal error: 'algorithm' file not found
```

This indicates missing or misconfigured Xcode/Command Line Tools C++ headers.
Building in a Linux container avoids depending on the host SDK.

### Docker build

The Linux build initially failed because `protoc` was absent. After adding
`protobuf-compiler`, `lance-encoding` still failed while importing the well-
known protobuf definition:

```text
protoc failed: google/protobuf/empty.proto: File not found.
encodings_v2_0.proto:8:1: Import "google/protobuf/empty.proto" was not found or had errors.
```

The Debian package installs that file under `/usr/include/google/protobuf`.
The current benchmark Dockerfile supplies a wrapper that adds
`-I/usr/include` to the `protoc` invocation. If this remains insufficient,
the upstream build should pass an explicit protobuf include directory to the
`prost-build`/Lance code generation step (or use a vendored `protoc` bundle).

After the protobuf headers were supplied, the next native dependency failure
was `lbug`'s bundled CMake build:

```text
failed to execute command: No such file or directory
is `cmake` not installed?
```

The builder therefore also needs the `cmake` system package.

## Recommended upstream checks

1. Verify the build on both `linux/amd64` and `linux/arm64` with Rust 1.91.
2. Make the protobuf include path explicit instead of relying on the system
   `protoc` search path.
3. Document required packages (`build-essential`, `protobuf-compiler`) and
   the expected `PROTOC`/include configuration in the Rust CLI build docs.
4. Add a CI smoke job that builds `cognee-cli` from a clean container and runs
   `cognee-cli --help` before publishing a release artifact.
