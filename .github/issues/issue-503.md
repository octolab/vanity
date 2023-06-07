---
code: null
id: I_kwDODBR9IM8AAAABeoNG6Q
databaseId: 6350391017
number: 503
url: https://github.com/octomation/vanity/issues/503
title: "ci/cd: assess vanity promises every month"
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
createdAt: 2026-11-12T13:03:26Z
updatedAt: 2026-11-12T13:03:26Z
lastEditedAt: null
closedAt: null
---

# ci/cd: assess vanity promises every month

## Motivation

The promises of vanity are assessed only when someone starts an agent by
hand. Delivery was down from December 2025 to November 2026 and nobody
noticed: the CD schedule rebuilds the site, it does not check it, and the
history of runs is deleted every month (`retain_days: 0`,
`keep_minimum_runs: 0` in `cleanup.runs.yml`). This covers the promises
watch, availability and durability. The promises are in the note "Обещания vanity" (Mindset); the first two assessments are the reports of 2026-11-10 and 2026-11-12.

## PoC

```bash
grep -n cron .github/workflows/*.yml          # only rebuilds and cleanups
gh run list -L 5                              # no assessment runs
echo | openssl s_client -servername go.octolab.org -connect go.octolab.org:443 2>/dev/null \
  | openssl x509 -noout -enddate              # notAfter=Dec 18 03:26:19 2026 GMT
curl -s https://proxy.golang.org/go.octolab.org/toolkit/config/@v/list   # v0.0.1 … v0.0.5
git ls-remote --tags https://github.com/octolab/config                  # only v0.0.5
```

## Scope

- A workflow with a monthly `schedule` (and `workflow_dispatch`) that checks,
  without secrets that read other repositories:
  - discovery: `bin/verify.py --url https://go.octolab.org`;
  - availability: HTTP answer, days left on the certificate, the CNAME to
    `octomation.github.io.`, `https_enforced` and the verified domain of Pages;
  - delivery: the last Pages deployment is on `origin/main`, the last CD run
    succeeded, no workflow is `disabled_inactivity`;
  - durability: for every public module, versions in
    `proxy.golang.org/<module>/@v/list` still have their tags on GitHub.
- A failed check fails the run and notifies Slack; the run stays in the
  history.
- The runs cleanup keeps the history of this workflow for at least a year.

## Acceptance criteria

- [ ] A scheduled run exists and passes against today's site.
- [ ] Each check fails the run when broken on purpose (a wrong host, a
      certificate threshold above its days left, a missing tag).
- [ ] The runs cleanup no longer deletes the history of the assessment.
- [ ] The workflow reports which promise is not kept and why, in the run
      summary.

## Out of scope

- Repairing what the run finds: that stays with the keeper agent and with
  the projects.
- Restoring the tags of octolab/config.
- Private modules: the run has no access to them.
