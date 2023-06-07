---
code: null
id: I_kwDODBR9IM8AAAABeoNLcQ
databaseId: 6350392177
number: 504
url: https://github.com/octomation/vanity/issues/504
title: "ci/cd: verify the live site after each deploy"
issueType: Task
labels:
  - "scope: inventory"
  - "type: improvement"
assignees:
  - kamilsk
milestone: null
parent: null
issueFields: {}
state: OPEN
stateReason: null
duplicateOf: null
createdAt: 2026-11-12T13:03:30Z
updatedAt: 2026-11-12T13:04:04Z
lastEditedAt: 2026-11-12T13:04:04Z
closedAt: null
---

# ci/cd: verify the live site after each deploy

## Motivation

CD reports success when GitHub Pages accepts the artifact, not when
go.octolab.org serves the new catalog. The promise delivery asks for both:
the live site is built from `main`, and it is checked after the deploy.
The secret that reads the private submodules expires silently, and the
check before checkout only tests that it is not empty. The promises are in the note "Обещания vanity" (Mindset); the first two assessments are the reports of 2026-11-10 and 2026-11-12.

## PoC

```bash
sed -n '/deploy:/,$p' .github/workflows/cd.urls.yml   # deploy, then notify; no check
sed -n '/Check submodule credentials/,/fi/p' .github/workflows/cd.urls.yml
```

## Scope

- A job after `deploy` that runs `bin/verify.py --url https://go.octolab.org`
  against the modules of the commit and fails the run if they differ;
  propagation delay of Pages is retried, not ignored.
- The credentials check proves read access to one private submodule
  instead of a non-empty value, and names the secret in the error.

## Acceptance criteria

- [ ] A deploy whose pages differ from `.gitmodules` fails the run.
- [ ] A run with an expired or revoked secret fails at the credentials step
      with a clear message, before checkout.
- [ ] A normal deploy passes within the retry budget.

## Out of scope

- Replacing the secret: [[issue-500]].
- Scheduled checks between deploys: [[issue-503]].
