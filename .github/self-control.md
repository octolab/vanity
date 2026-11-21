# Self-control

Open checks that outlive a working session: things to look at later, decisions
that are waiting, and follow-ups that still need an issue. Each item says when
to look, what proves it and what to do if it fails. An item is removed once it
is proven or moved into an issue.

## Close the promises pass of 2026-11-10

The pass is delivered: the commit series is in `main`, `cd.urls.yml` publishes
the pages, and `bin/verify-live.sh --packages` checks discovery against the
live site.

- [ ] **Record the promises of vanity** next to the pass report, so the next
  pass starts from them. Proven when the promise notes are saved and nothing
  of the pass is left unsaved.
- [ ] **Close the open thread of the pass** about module path conflicts. Its
  questions are answered; the decisions are in the pass report.

## Kept on purpose

Decided during the pass, not open work. Revisit only with a new pass:
tablo is declared in two repositories; dotapps, telemost, go-markdown and
go-yaml keep template paths; 14 projects stay on `github.com/kamilsk/…`; the
history of `octolab/protocol` diverges from its tags; tags without the `v`
prefix; the archived breakit.
