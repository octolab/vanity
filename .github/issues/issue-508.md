---
code: null
id: I_kwDODBR9IM8AAAABgHsusA
databaseId: 6450523824
number: 508
url: https://github.com/octolab/vanity/issues/508
title: "ci/cd: no expression injection in the notify of module repositories"
issueType: Task
labels:
  - "type: improvement"
  - "scope: inventory"
assignees:
  - kamilsk
milestone: null
parent: null
issueFields: {}
state: OPEN
stateReason: null
duplicateOf: null
createdAt: 2026-11-17T17:40:31Z
updatedAt: 2026-11-17T17:40:31Z
lastEditedAt: null
closedAt: null
---

# ci/cd: no expression injection in the notify of module repositories

## Motivation

[[issue-506]] removed event text from shell in the workflows of vanity. The module
repositories that publish themselves keep their own `notify`: in 17 of them it puts
`github.event.head_commit.message` or `inputs.reason` into `run:` as `${{ … }}`, so a
commit message with `$(…)` or quotes runs in the job instead of being shown in Slack.

## PoC

```bash
grep -rn 'txt=\${{' .github/actions/notify/action.yml .github/workflows/*.yml   # in a module repository
```

Modules: octomation/go-module, go-service, go-tool, tuna, dotapps, optflow, secret,
tablo; octopot/fiddle, telemost, airseat, loop, beads, click; withsparkle/service;
tact-app/inbox, service.

## Acceptance criteria

- [ ] In each of the 17 repositories event text reaches shell only through `env:`.
- [ ] A commit message with `$(…)` or quotes is shown verbatim in Slack and not executed.

## Out of scope

- The workflows of vanity: done in [[issue-506]].
- Moving `notify` into a shared action.
