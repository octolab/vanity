---
code: null
id: I_kwDODBR9IM8AAAABeR_aRg
databaseId: 6327097926
number: 499
url: https://github.com/octomation/vanity/issues/499
title: "security: reconsider how private modules are published"
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
createdAt: 2026-11-11T11:06:13Z
updatedAt: 2026-11-11T11:06:13Z
lastEditedAt: null
closedAt: null
---

# security: reconsider how private modules are published

## Motivation

The repository is public, and go.octolab.org publishes a page for every package
of every registered module. For the 11 private modules (octopot/airseat, beads,
click, loop; octomation/optflow, secret, tablo; tact-app/inbox, service, github,
trello) this discloses more than their existence:

- `.gitmodules` names their repositories, and gitlinks pin their commits;
- the site lists their package tree, e.g. `toolset/airseat/internal/command/demo`,
  over 120 pages in total, with links to their default branch;
- Dependabot pull requests that bump a private submodule may quote its commit
  titles in this public repository (not checked).

Package pages exist for `go get` in GOPATH mode and for the redirect to
pkg.go.dev, which never shows private modules. In module mode `go get` of a
subpackage queries every prefix of the path and accepts a 404 as "no module
here": a page for the module root is enough (checked with go1.27.3 against a
server that answers only for the root).

## Scope

Decide what vanity publishes for a private module and make the build and
`bin/verify.py` follow that decision: the generated pages, the data read from
GitHub for them, and the Dependabot configuration for private submodules.

## Acceptance criteria

- [ ] The policy for private modules is written down in README: what is
      published and why.
- [ ] `go get` of a subpackage of a private module works over
      `GOPROXY=direct` for someone with access, with the new build.
- [ ] `make verify` checks the private modules against the policy instead of
      requiring pages they no longer have.
- [ ] Nothing on go.octolab.org discloses more about a private module than the
      policy allows.

## Out of scope

- Moving private modules out of vanity or to another domain.
- Rewriting the history of this repository to remove `.gitmodules` entries.
- The expired `DEPENDABOT_TOKEN` that blocks delivery now.
