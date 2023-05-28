---
code: null
id: MDU6SXNzdWU0ODE5NzE5NTI=
databaseId: 481971952
number: 1
url: https://github.com/octomation/vanity/issues/1
title: "automate build based on yaml"
issueType: null
labels: []
assignees:
  - kamilsk
milestone: null
parent: null
issueFields: {}
state: CLOSED
stateReason: COMPLETED
duplicateOf: null
createdAt: 2019-08-18T09:13:43Z
updatedAt: 2020-03-28T08:34:06Z
lastEditedAt: 2020-03-27T20:22:45Z
closedAt: 2020-03-28T08:34:06Z
---

# automate build based on yaml

- [x] define the structure
```yaml
sources:
- pkg: go.octolab.org
  go-import: { vcs: git, path: https://github.com/octolab/pkg}
  go-source: { path: https://github.com/octolab/pkg, file: https://github.com/octolab/pkg/tree/master{/dir} line: https://github.com/octolab/pkg/tree/master{/dir}/{file}#L{line}}
- ...
```
- [x] implement builder
