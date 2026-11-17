---
code: null
id: I_kwDODBR9IM8AAAABeoNPjw
databaseId: 6350393231
number: 505
url: https://github.com/octolab/vanity/issues/505
title: "build: verify go-source and redirects, not only go-import"
issueType: Task
labels:
  - "type: improvement"
  - "scope: code"
assignees:
  - kamilsk
milestone: null
parent: null
issueFields: {}
state: CLOSED
stateReason: COMPLETED
duplicateOf: null
createdAt: 2026-11-12T13:03:34Z
updatedAt: 2026-11-17T17:46:37Z
lastEditedAt: 2026-11-17T17:45:41Z
closedAt: 2026-11-17T17:46:36Z
---

# build: verify go-source and redirects, not only go-import

## Motivation

`bin/verify.py` compares only the `go-import` meta with `.gitmodules`. The
`go-source` meta (the branch in the dir and file templates) and the
redirect to the documentation are not checked, although
`bin/lib/core/check.bash` says they are. The promise integrity asks that all
three match. The promises are in the note "Обещания vanity" (Mindset); the first two assessments are the reports of 2026-11-10 and 2026-11-12.

## PoC

```bash
grep -n 'go-source' bin/verify.py                 # nothing
grep -n 'go-source' bin/lib/core/check.bash       # the claim
curl -s 'https://go.octolab.org/toolkit/cli?go-get=1' | grep -E 'go-source|refresh'
```

## Scope

- `verify.py` checks, for every module root and every package page, locally
  and with `--url`: `go-import`, `go-source` (repository and default branch),
  and the redirect target.
- An unknown path under go.octolab.org answers 404, so `go get` of a
  missing package fails fast.
- A changed `url` of an existing module in a diff is reported, so that a
  path never moves to another repository without a decision.

## Acceptance criteria

- [x] A page with a wrong branch in `go-source` fails `make verify`.
- [x] A page with a wrong redirect fails `make verify`.
- [x] The comment in `check.bash` matches what is checked.

## Out of scope

- What private modules publish: [[issue-499]].

<!-- 2026-11-17T18:40Z https://github.com/octolab/vanity/issues/505#issuecomment-6956079420
Done with the self-publishing rollout (#500).

- `bin/verify.py` checks `go-import`, `go-source` and the redirect of every module root and package page, locally and with `--url`; an unknown path must answer 404.
- `test_wrong_branch` and `test_wrong_redirect` in `bin/tests/test_catalog.py` fail on a wrong branch and a wrong redirect; the suite is green.
- `bin/lib/core/check.bash` names the same three checks.
- `bin/verify-live.sh --packages` on 2026-11-17: 385 packages verified over HTTPS.
-->
