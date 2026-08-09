# Vendor notes

A system's vendor may attach a short note to its rows on
[adversari.al/cognition](https://adversari.al/cognition) — design intent behind
declined or failed cases, corrections of *interpretation* (never of recorded
outcomes), and a link to a longer document.

## How to submit

1. Copy `TEMPLATE.md` to `vendor-notes/<system>.md`, where `<system>` is your
   system's id exactly as it appears in the results table (`mem0`, `graphiti`,
   `cognee`, `cognee-rs`, `akka-fluree`, `letta`, …). The site's *Vendor
   notes* popup links you to a prefilled GitHub editor for this file.
2. Keep the note a **short summary — at most 100 words of body text**. Put the
   full story in a longer document: either add
   `vendor-notes/details/<system>.md` in the same PR, or link an external doc
   you host. The `details:` field is required.
3. Open a PR titled `vendor-notes: <system> — <subject>` touching only your
   note (and, optionally, your details file).
4. Leave `verified: false`. A maintainer verifies that you represent the
   vendor (organization membership or a company-domain email), flips
   `verified: true`, and merges. Only verified notes render on the site; the
   git history is the provenance.

## Updating your note

Notes are living documents — update them the same way they were created:

1. Edit `vendor-notes/<system>.md` in a PR (the site's popup links straight to
   the GitHub editor for your file). Update the `date:` field to the day of
   the edit — the validator requires it to change when the body changes, and
   the site shows it as "last updated".
2. Titles for update PRs: `vendor-notes: <system> — update: <what changed>`.
3. Leave `verified:` exactly as it is; it is not yours to set either way.
   **A maintainer re-verifies the submitter on every merge that touches a
   note** — an existing `verified: true` never carries over to an edit by
   itself, so an update from an unverified account will be flipped to
   `verified: false` (unpublishing the note) rather than inheriting trust.
4. The full history of every note — who changed what, when, and which
   maintainer merged it — is the git log. Nothing is ever silently replaced.

## Rules

- The published numbers may not be restated differently than the run; a note
  interprets, it does not re-score.
- One file per system per benchmark family. Address multiple result versions
  with the `versions:` list rather than separate files.
- `scripts/check_vendor_notes.py` validates every note in CI: frontmatter
  schema, a known system id, the 100-word cap, the required `details:` link,
  and `verified: false` on submission.
