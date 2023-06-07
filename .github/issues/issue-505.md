---
code: null
id: I_kwDODBR9IM8AAAABeoNPjw
databaseId: 6350393231
number: 505
url: https://github.com/octomation/vanity/issues/505
title: "build: verify go-source and redirects, not only go-import"
issueType: Task
labels:
  - "scope: code"
  - "type: improvement"
assignees:
  - kamilsk
milestone: null
parent: null
issueFields: {}
state: OPEN
stateReason: null
duplicateOf: null
createdAt: 2026-11-12T13:03:34Z
updatedAt: 2026-11-12T13:03:34Z
lastEditedAt: null
closedAt: null
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

- [ ] A page with a wrong branch in `go-source` fails `make verify`.
- [ ] A page with a wrong redirect fails `make verify`.
- [ ] The comment in `check.bash` matches what is checked.

## Out of scope

- What private modules publish: [[issue-499]].
