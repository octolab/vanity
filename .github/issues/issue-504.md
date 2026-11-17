---
code: null
id: I_kwDODBR9IM8AAAABeoNLcQ
databaseId: 6350392177
number: 504
url: https://github.com/octolab/vanity/issues/504
title: "ci/cd: verify the live site after each deploy"
issueType: Task
labels:
  - "type: improvement"
  - "scope: inventory"
assignees:
  - kamilsk
milestone: null
parent: null
issueFields: {}
state: CLOSED
stateReason: COMPLETED
duplicateOf: null
createdAt: 2026-11-12T13:03:30Z
updatedAt: 2026-11-17T17:46:33Z
lastEditedAt: 2026-11-17T17:45:38Z
closedAt: 2026-11-17T17:46:33Z
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

- [x] A deploy whose pages differ from `.gitmodules` fails the run.
- [x] ~~A run with an expired or revoked secret fails at the credentials step
      with a clear message, before checkout.~~ Obsolete: CD reads no other repository and holds no such secret.
- [x] A normal deploy passes within the retry budget.

## Out of scope

- Replacing the secret: [[issue-500]].
- Scheduled checks between deploys: [[issue-503]].

<!-- 2026-11-17T18:40Z https://github.com/octolab/vanity/issues/504#issuecomment-6956078386
Done with the self-publishing rollout (#500).

- The job "Verifying the live site" of `cd.urls.yml` runs `bin/verify.py --url https://go.octolab.org` against the entries of the deployed commit; the entries replaced `.gitmodules`.
- A normal deploy passes within the retries: run 44110991840 on 8959eac is green; a 503 on one package passed on the second attempt.
- The credentials criterion is obsolete: vanity no longer checks out module code, and its workflows reference no secret but `SLACK_WEBHOOK`. `DEPENDABOT_TOKEN` was deleted from octomation on 2026-11-17.
-->
