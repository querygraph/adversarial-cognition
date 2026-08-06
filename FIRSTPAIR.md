# FirstPair Library Contract

slug: adversarial-cognition
shelf: querygraph
default_edition: full

The *Adversarial Cognition* manuscript and book assets are owned by this
repository. FirstPair provides the shared build, artifact verification, reader
routes, and catalog delivery. The canonical shared workflow is
`~/src/firstpair/publishing/PUBLISH.md` and
`~/src/firstpair/publishing/UNIFIED_BOOK_BUILD_GOAL.md`.

## Source contract

- Book root: `docs/book/`
- Manuscript: `docs/book/manuscript.md`
- Metadata: `docs/book/metadata.yaml`
- Cover source: `docs/book/cover.md`
- Cover asset: `docs/book/cover/adversarial-cognition-cover.png`
- Headboard asset: `docs/book/cover/adversarial-cognition-headboard.png`
- Stable stem: `adversarial-cognition`
- Build configuration: `book.build.json`
- Publish-complete outputs: `docs/book/dist/`

The source repository owns the cover, headboard, and manuscript; no public
catalog or Blob metadata is edited from this repository during a local build.

## Safe workflow

```sh
git status --short --branch
~/src/firstpair/publishing/scripts/build-library-book.sh \
  --repo-root "$PWD" --edition full
```

Before an outward publication, this repository and FirstPair must both be
clean, pushed, and pass the canonical Git preflight. Full-edition publication
requires explicit user confirmation.
