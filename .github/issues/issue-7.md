---
code: null
id: MDU6SXNzdWU3ODM1OTY1MzM=
databaseId: 783596533
number: 7
url: https://github.com/octomation/vanity/issues/7
title: "some modules return 404"
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
createdAt: 2021-01-11T18:22:54Z
updatedAt: 2021-01-11T21:06:27Z
lastEditedAt: null
closedAt: 2021-01-11T21:06:27Z
---

# some modules return 404

e.g. `curl -I https://go.octolab.org/toolkit/cli/?go-get=1`

```
HTTP/2 404 
content-type: text/html; charset=utf-8
```

<!-- 2021-01-11T18:23Z https://github.com/octomation/vanity/issues/7#issuecomment-758136057
it's happening because `maintainer` didn't generate index.html for a module without go files: https://github.com/octomation/vanity/tree/master/toolkit/cli
-->

<!-- 2021-01-11T19:14Z https://github.com/octomation/vanity/issues/7#issuecomment-758164111
```
go get go.octolab.org/toolkit/cli: unrecognized import path "go.octolab.org/toolkit/cli": reading https://go.octolab.org/toolkit/cli?go-get=1: 404 Not Found
make: *** [deps-update] Error 1
```
-->
