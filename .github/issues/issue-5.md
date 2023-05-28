---
code: null
id: MDU6SXNzdWU0ODMyNDU2MTg=
databaseId: 483245618
number: 5
url: https://github.com/octomation/vanity/issues/5
title: "how to warmup godoc and vanity url"
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
createdAt: 2019-08-21T07:26:48Z
updatedAt: 2021-01-02T08:55:40Z
lastEditedAt: null
closedAt: 2021-01-02T08:55:40Z
---

# how to warmup godoc and vanity url

when new subpackage or package released

<!-- 2019-08-22T19:30Z https://github.com/octomation/vanity/issues/5#issuecomment-524044095
```bash
$ curl -H 'content-type: application/x-www-form-urlencoded' \
     --data 'path=go.octolab.org%2Ftoolkit%2Fcli' \
     'https://godoc.org/-/refresh'
```
-->

<!-- 2019-08-22T19:33Z https://github.com/octomation/vanity/issues/5#issuecomment-524045160
```bash
$ go list all | grep $(go list -m)
```
-->

<!-- 2019-08-22T19:34Z https://github.com/octomation/vanity/issues/5#issuecomment-524045545
```bash
$ curl --data-urlencode 'path=go.octolab.org/toolkit/cli' ...
```
-->

<!-- 2019-08-22T19:36Z https://github.com/octomation/vanity/issues/5#issuecomment-524046266
open question is: how to trim semantic path?

```bash
go list all | grep $(go list -m)
github.com/kamilsk/retry/v4
github.com/kamilsk/retry/v4/backoff
github.com/kamilsk/retry/v4/jitter
github.com/kamilsk/retry/v4/strategy
```
-->

<!-- 2021-01-02T08:55Z https://github.com/octomation/vanity/issues/5#issuecomment-753449249
moved to octomation/maintainer#4
-->
