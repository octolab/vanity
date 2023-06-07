---
code: null
id: I_kwDODBR9IM8AAAABeoNTmg
databaseId: 6350394266
number: 506
url: https://github.com/octomation/vanity/issues/506
title: "ci/cd: least privilege and no expression injection in workflows"
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
createdAt: 2026-11-12T13:03:38Z
updatedAt: 2026-11-12T13:03:38Z
lastEditedAt: null
closedAt: null
---

# ci/cd: least privilege and no expression injection in workflows

## Motivation

The build holds a token that reads every private repository of the
catalog and writes the `go-import` of every module. The promise provenance
asks for explicit versions of third-party code, minimal permissions and no
untrusted text in shell. Actions are already pinned to patch tags; the rest
is not kept. The promises are in the note "Обещания vanity" (Mindset); the first two assessments are the reports of 2026-11-10 and 2026-11-12.

## PoC

```bash
grep -L '^permissions:' .github/workflows/*.yml          # cleanup.caches, cleanup.runs
grep -n 'txt=\${{' .github/actions/notify/action.yml   # commit message and inputs.reason in run:
grep -n 'uses:' .github/workflows/*.yml | grep -vE '@v[0-9]+\.[0-9]+\.[0-9]+|\./'   # nothing today
```

## Scope

- Every workflow declares `permissions:` at the top level, and jobs widen
  them only where needed.
- `.github/actions/notify` passes the commit message, `inputs.reason` and
  other event text through `env:`, never as `${{ … }}` inside `run:`.
- External actions stay pinned to full patch tags `vX.Y.Z`; Dependabot keeps
  them current.

## Acceptance criteria

- [ ] `grep -L '^permissions:' .github/workflows/*.yml` prints nothing.
- [ ] A commit message with `$(…)` or quotes is shown verbatim in Slack and
      not executed.
- [ ] No external `uses:` without a patch tag.

## Out of scope

- Pinning by commit SHA: patch tags are the agreed compromise.
- The maintainer binary checksum: under [[issue-500]] the publisher does not
  use maintainer.
