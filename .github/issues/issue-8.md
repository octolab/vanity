---
code: null
id: MDU6SXNzdWU5ODM3NTc3NTM=
databaseId: 983757753
number: 8
url: https://github.com/octomation/vanity/issues/8
title: "cd/cd: automation based on submodules"
issueType: null
labels:
  - "type: feature"
  - "scope: inventory"
  - "impact: high"
  - "effort: medium"
assignees:
  - kamilsk
milestone: null
parent: null
issueFields: {}
state: CLOSED
stateReason: COMPLETED
duplicateOf: null
createdAt: 2021-08-31T11:33:48Z
updatedAt: 2023-08-03T17:57:18Z
lastEditedAt: null
closedAt: 2023-08-03T17:57:18Z
---

# cd/cd: automation based on submodules

algorithm:
- move all HTML into /docs
- add go modules as submodules
- build HTML recursively walk all submodules

<!-- 2023-04-17T15:01Z https://github.com/octomation/vanity/issues/8#issuecomment-1511538351
Useful

- https://pkg.go.dev/about#adding-a-package
```
$ curl -v https://proxy.golang.org/go.octolab.org/template/module/@v/v1.0.0.info

$ go mod init test
$ GOPROXY=https://proxy.golang.org GO111MODULE=on go get go.octolab.org/template/module@v1.0.0
```
- https://github.com/golang/go/issues/38848#issuecomment-669941421
-->

<!-- 2023-04-17T16:51Z https://github.com/octomation/vanity/issues/8#issuecomment-1511736227
blocked by octomation/maintainer/issues/134
-->

<!-- 2023-07-09T06:40Z https://github.com/octomation/vanity/issues/8#issuecomment-1627623866
prefix: `go list -m`
import.url: `gh repo view --json url`
import.source.dir: `gh repo view --json url`/tree/`gh repo view --json defaultBranchRef`{/dir}
vcs: git
packages: `go list ./...`
tags: `gh repo view --json repositoryTopics`
-->
