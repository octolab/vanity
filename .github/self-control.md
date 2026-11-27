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

## Watch

- [ ] **On the first Nextra release after 4.6.1** (shuding/nextra#4990): move
  the `nextra-theme-docs` override in `docs/package.json` to zod 4.6.6 or
  later, or drop it, and drop the katex and minimatch overrides its ranges
  cover. Proven when `npm audit` is clean and `make` verifies every page.

## Checks by occasion

Not open work: what to check each time the occasion comes.

### After a push to main or a release of a module

- [ ] **The delivery is green.** `gh run list -L 5`: Continuous delivery
  passed Gating, Building, Deploying and Verifying the live site.
- [ ] **The live site is whole.** `python3 bin/pages.py doctor` prints only
  `ok`. If a card shows another version than the entry, the smoke test names
  it; nothing to edit by hand, rerun the delivery.
- [ ] **A new module is noticed.** `python3 bin/catalog.py cards` warns of a
  public module without a card: add its card as AGENTS.md says.

### After Dependabot fails or a security alert opens

A security update of a transitive dependency of `docs/` fails with
`security_update_not_possible` when its parent pins an older range.

- [ ] **Lift it with `overrides`** in `docs/package.json`, then `npm install`
  in `docs/`, `npm audit`, `make` and `make test`. Proven when `npm ls <name>`
  shows the patched version and `make` verifies every page.
- [ ] **Keep an override no longer than needed.** On each update of `nextra`,
  drop the overrides its own ranges now cover and check again.

Overrides in place:

| Package | Override | Why |
| --- | --- | --- |
| katex | `^0.18.2` | GHSA ranges below 0.18.2; nextra and mermaid ask for 0.16 |
| minimatch | `^11.0.1` | ReDoS ranges below 11.0.1; nextra → ts-morph asks for 10 |
| zod | `4.1.12` under `nextra-theme-docs` | **kept vulnerable on purpose**: newer zod breaks Nextra 4.6.1 (shuding/nextra#5036; `expected nonoptional` while prerendering). zod validates our own theme config at build time only; the alert (GHSA-mrhx-c7xc-m3w5) is dismissed as a tolerable risk, as in octomation/maintainer |
