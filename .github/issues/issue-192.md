---
code: null
id: I_kwDODBR9IM5trff3
databaseId: 1840117751
number: 192
url: https://github.com/octomation/vanity/issues/192
title: "perf: avoid downloading deps"
issueType: null
labels:
  - "type: improvement"
  - "scope: inventory"
  - "impact: medium"
  - "effort: medium"
assignees:
  - kamilsk
milestone: null
parent: null
issueFields: {}
state: CLOSED
stateReason: COMPLETED
duplicateOf: null
createdAt: 2023-08-07T19:54:07Z
updatedAt: 2023-08-09T09:10:06Z
lastEditedAt: null
closedAt: 2023-08-09T09:10:06Z
---

# perf: avoid downloading deps

**Motivation:** it's unnecessary for that operation.

**Details:** https://github.com/octomation/vanity/actions/runs/5754091407/job/15598677427#step:5:28.

<!-- 2023-08-08T09:11Z https://github.com/octomation/vanity/issues/192#issuecomment-1669227459
solved by caching deps https://github.com/octomation/vanity/actions/runs/5795002283/job/15705722721#step:5:32
-->

<!-- 2023-08-09T09:10Z https://github.com/octomation/vanity/issues/192#issuecomment-1670956817
fixed 29729a5283d615a05cf2202741e8057b0471ed5b
-->
