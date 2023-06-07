---
code: null
id: I_kwDODBR9IM8AAAABeoNZ1g
databaseId: 6350395862
number: 507
url: https://github.com/octomation/vanity/issues/507
title: "docs: publish the contract for modules on go.octolab.org"
issueType: Task
labels:
  - "scope: docs"
  - "type: improvement"
assignees:
  - kamilsk
milestone: null
parent: null
issueFields: {}
state: OPEN
stateReason: null
duplicateOf: null
createdAt: 2026-11-12T13:03:43Z
updatedAt: 2026-11-12T13:04:07Z
lastEditedAt: 2026-11-12T13:04:07Z
closedAt: null
---

# docs: publish the contract for modules on go.octolab.org

## Motivation

vanity relies on promises of every project it serves: the module path
matches the vanity URL, releases are semver tags, and published tags are
never deleted or moved. None of it is written where a project can read it,
and octolab/config broke the last one: v0.0.1–v0.0.4 exist only in the Go
proxy, while 26 projects, including the templates go-tool and go-service,
still require them. Anyone who sets `GOPRIVATE=go.octolab.org` to reach the
private modules bypasses the proxy and fails. After [[issue-500]] the same
contract is what a project accepts when it publishes itself. The promises are in the note "Обещания vanity" (Mindset); the first two assessments are the reports of 2026-11-10 and 2026-11-12.

## PoC

```bash
curl -s https://proxy.golang.org/go.octolab.org/toolkit/config/@v/list
git ls-remote --tags https://github.com/octolab/config
gh api repos/octolab/cli/rulesets --jq length                     # 0
sha=$(gh api repos/octolab/cli/git/refs/tags/v0.6.4 --jq .object.sha)
gh api repos/octolab/cli/git/tags/$sha --jq .verification.verified   # true
```

## Scope

- A contract in the README of vanity (and later the publishing action):
  module path equals the vanity URL and no other project or template
  declares it; releases are annotated, signed tags `vX.Y.Z`; published tags
  are never deleted or moved.
- A tag ruleset on `refs/tags/v*` with "Restrict deletions" and "Restrict
  updates" in every repository where the plan allows it: public
  repositories on Free, all repositories of octopot (Team). In private
  repositories on Free the rule stays an agreement.
- The monthly assessment ([[issue-503]]) reports a
  repository without the ruleset or with unsigned new tags.

## Acceptance criteria

- [ ] The contract is in the README.
- [ ] Every eligible repository of the catalog has the tag ruleset.
- [ ] A list of repositories that cannot have it, with the reason.

## Out of scope

- Restoring the deleted tags of octolab/config: a decision of its own.
- Re-signing old tags.
