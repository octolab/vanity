---
code: null
id: I_kwDODBR9IM8AAAABeXEDaw
databaseId: 6332416875
number: 500
url: https://github.com/octomation/vanity/issues/500
title: "build: let projects publish their modules to octolab/vanity"
issueType: Task
labels:
  - "scope: code"
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
createdAt: 2026-11-11T16:11:11Z
updatedAt: 2026-11-11T16:11:30Z
lastEditedAt: null
closedAt: null
---

# build: let projects publish their modules to octolab/vanity

## Motivation

vanity pulls every module in as a git submodule and reads its code in CI to
render the pages. That has three costs:

- CD needs a long-lived token that reads every private repository of four
  organizations. `DEPENDABOT_TOKEN`, a personal classic PAT from 2023, has
  expired, and delivery has been down since: run 43007265539 fails at checkout
  with `could not read Username`.
- A new module, a moved repository or a new release reaches go.octolab.org
  only when someone edits `.gitmodules` and bumps the pin by hand.
- vanity decides what a private module exposes, which is what [[issue-499]]
  questions.

The other catalogs already work the other way round. A tool's release
workflow writes to octolab/homebrew-tap (goreleaser) and to octolab/skills
(octomation/skills-action) with a token minted per run from the OctoLab
Releaser App, and octolab/skills tags each publication `<tool>--v<version>`.
The tap is getting the same tags in octolab/homebrew-tap#10. vanity should
join them: move to octolab/vanity, and let each project publish its own
module there on release.

## PoC

```bash
gh run view 43007265539 --log-failed | grep 'could not read Username'
gh api repos/octolab/skills/tags --jq '.[].name'          # indexit--v0.4.1 …
gh api /orgs/octolab/installations \
  --jq '.installations[] | select(.app_slug == "octolab-releaser") | .repository_selection'
grep -c '^\[submodule' .gitmodules                          # 31, pinned by hand
```

## Scope

- **Transfer** octomation/vanity to octolab/vanity. go.octolab.org keeps
  serving the same import paths with no gap; the custom domain and its
  verification move with the repository.
- **Entries instead of submodules.** vanity renders the pages from an entry
  per module (module path, repository, branch, packages to publish, version)
  committed in the repository. It no longer checks out module code, and its
  CD has no secret that reads other repositories.
- **A publishing action.** A separate action, by analogy with
  octomation/skills-action, that a project's `cd.yml` calls after a release:
  it writes or updates the module's entry in octolab/vanity and tags the
  commit `<tool>--v<version>`. The module decides what it publishes, for
  example only its root when the repository is private.
- **`cd.yml` refactoring in the tools.** In octomation/maintainer and
  octopot/indexit the release, the tap, the skill and vanity each become a
  separate action call (and job), so the workflow reads as a list of
  publications instead of inline token and goreleaser plumbing.
- **Migration** of the modules that have no release workflow: their entries
  are seeded once from today's `.gitmodules`; then the submodules,
  `go.work` entries and `DEPENDABOT_TOKEN` usage go away.

## Acceptance criteria

- [ ] octolab/vanity serves go.octolab.org; `python3 bin/verify.py --url
      https://go.octolab.org` passes for every module that is published today,
      and `bin/lib/core/check.bash` passes.
- [ ] A release of indexit (or maintainer) updates its entry in
      octolab/vanity and creates the tag `indexit--v<version>` without any
      manual step; the site shows it after the vanity build.
- [ ] A new Go project gets onto go.octolab.org by adding the action call to
      its `cd.yml` only.
- [ ] vanity workflows reference no secret with access to other repositories;
      `.gitmodules` is gone.
- [ ] In maintainer and indexit `cd.yml` the goreleaser/tap part and the
      skill part are calls of their own actions; a release of each still
      publishes the tap formula and the skill.
- [ ] [[issue-499]] is closed with a reference to this task.
- [ ] README of vanity describes how a project publishes itself.

## Out of scope

- Tags in octolab/homebrew-tap: octolab/homebrew-tap#10.
- Moving other repositories between organizations.
- Changing the import paths of any module.

<!-- 2026-11-11T19:30Z https://github.com/octomation/vanity/issues/500#issuecomment-6800920004
## Algorithm

A suggested order: each step leaves go.octolab.org working, so the work can stop between steps.

**0. Freeze the current state**
- Save the list of published roots and packages: `make` and keep `dist/` aside, or `find dist -name index.html`. It is the baseline for the comparison in step 4.
- Dependabot no longer bumps submodules (`gitsubmodule` was removed from `.github/dependabot.yml`).

**1. Entry format and a build from entries** (in octomation/vanity, before the transfer)
- One file per module, for example `modules/<module path>.json`:
  `{ "module": "go.octolab.org/toolset/indexit", "repository": "https://github.com/octopot/indexit", "branch": "main", "version": "v0.4.1", "packages": ["", "/cmd/...", ...], "topics": [...] }`.
  An empty `packages` (or only the root) is what a private module publishes, see #499.
- `bin/lib/core/modules.bash` reads the entries instead of `.gitmodules` + `gh repo view` + `go list`. Keep `go list` in a helper that the action reuses to compute `packages`.
- `bin/verify.py` checks entries: module path format, a repository URL on github.com, no duplicate module paths.
- Seed entries for all 31 modules from today's submodules with a one-off script (run locally, where `gh` can read private repositories) and commit them.
- Compare the built `dist/` with the baseline from step 0: the same roots and packages, except what is deliberately dropped for private modules.

**2. Transfer the repository**
- Check before: who can push, branch protection, Pages settings, `CNAME`, the secrets the workflows use (`SLACK_WEBHOOK` exists in both organizations; the vanity workflows need nothing else once step 5 is done).
- Verify go.octolab.org for the octolab organization (Settings → Pages → verified domains) *before* the transfer, so Pages accepts the custom domain at once.
- Transfer octomation/vanity → octolab/vanity. GitHub redirects the old URL; update the links in the READMEs of the modules and in `bin/` of the report.
- Re-run CD, then `bin/lib/core/check.bash` and `bin/verify.py --url https://go.octolab.org`.
- Add vanity to the selected repositories of the OctoLab Releaser installation on octolab (Contents: write). UI, or `PUT /user/installations/167161714/repositories/<repo id>`.

**3. The publishing action** (new repository, by analogy with octomation/skills-action)
- Inputs: `token` (Releaser token for octolab/vanity), `module` (from `go.mod` by default), `packages` (`all` | `root` | a list), `source-tag`, `source-sha`, `catalog-repository` (default octolab/vanity).
- Steps: compute the entry (go list in the checkout of the tool), clone octolab/vanity, write `modules/<module>.json`, commit as the App (signed), tag `<tool>--<version>`, push with a retry on a non-fast-forward (parallel releases).
- Idempotent: the same entry and the same tag on the same commit is a success with `changed=false`, as skills-action does.
- Outputs: `changed`, `catalog-commit`, `catalog-tag`.
- vanity CD runs on push to `main` (entries changed), so a publication triggers a deploy; App tokens do trigger workflows, unlike `GITHUB_TOKEN`.

**4. Refactor `cd.yml` in maintainer and indexit**
- `release` job: build and the GitHub release only.
- `tap` job: mint the tap token + goreleaser publishing to the tap, as one action call (a composite action in a shared repository, or `goreleaser` split into `release` and `publish` steps). Ties in with octolab/homebrew-tap#10 (tags).
- `skill` job: one call of octomation/skills-action; the token minting can move into the action (it takes `client-id` and `private-key`).
- `vanity` job: one call of the new action.
- `notify` waits for all of them; each publication job can be re-run alone.

**5. Remove the old way**
- Delete `.gitmodules`, `src/`, the `use` lines of `go.work` that point into `src/`, and every `DEPENDABOT_TOKEN` reference in `.github/workflows`.
- `warmup.caches.yml` no longer needs submodules; drop or simplify it.
- Delete the `DEPENDABOT_TOKEN` organization secret in octomation once no workflow there uses it (check with `gh secret list --org octomation` and a code search).
- Close #499 with a reference to this task.

**Risks**
- Pages downtime during the transfer: verify the domain for octolab first, and check `dig go.octolab.org` and `curl -sI https://go.octolab.org` right after.
- Every tool's workflow with the Releaser key can rewrite any entry. The action should write only `modules/<its module>.json`; vanity CI can check that each commit touches one entry whose `repository` matches the commit's tag prefix.
- tact-app has no Releaser secrets, so its modules either get the secrets or stay seeded by hand.
-->
