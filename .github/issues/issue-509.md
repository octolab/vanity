---
code: null
id: I_kwDODBR9IM8AAAABgHs0nA
databaseId: 6450525340
number: 509
url: https://github.com/octolab/vanity/issues/509
title: "ci/cd: move the tap publication of maintainer and indexit out of the release job"
issueType: Task
labels:
  - "type: improvement"
  - "scope: code"
assignees:
  - kamilsk
milestone: null
parent: null
issueFields: {}
state: OPEN
stateReason: null
duplicateOf: null
createdAt: 2026-11-17T17:40:36Z
updatedAt: 2026-11-17T17:40:36Z
lastEditedAt: null
closedAt: null
---

# ci/cd: move the tap publication of maintainer and indexit out of the release job

## Motivation

[[issue-500]] asked that in octomation/maintainer and octopot/indexit the release, the tap,
the skill and vanity each be a call of its own action, so that `cd.yml` reads as a list of
publications. Today `skill` (octomation/skills-action) and `vanity`
(octomation/vanity-action) are jobs of their own. The tap is not: the `release` job mints
the Releaser token and runs goreleaser, which builds the release and writes the formula to
octolab/homebrew-tap in one step.

## PoC

```bash
gh api repos/octomation/maintainer/contents/.github/workflows/cd.yml --jq .content | base64 -d | grep -n 'uses:\|create-github-app-token'
gh api repos/octopot/indexit/contents/.github/workflows/cd.yml --jq .content | base64 -d | grep -n 'uses:\|create-github-app-token'
```

## Acceptance criteria

- [ ] In maintainer and indexit `cd.yml` the tap publication is a job of its own that can
      be re-run alone; the `release` job needs no Releaser token.
- [ ] A release of each still publishes the GitHub release, the tap formula, the skill
      and the vanity entry.

## Out of scope

- Tags in octolab/homebrew-tap: octolab/homebrew-tap#10.
- The `skill` and `vanity` jobs: already separate.
