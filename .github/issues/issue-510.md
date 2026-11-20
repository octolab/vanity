---
code: null
id: I_kwDODBR9IM8AAAABhDmYOw
databaseId: 6513334331
number: 510
url: https://github.com/octolab/vanity/issues/510
title: "build: render the import pages without maintainer"
issueType: Task
labels:
  - "scope: code"
  - "type: improvement"
assignees:
  - kamilsk
milestone: null
parent: null
issueFields: {}
state: OPEN
stateReason: null
duplicateOf: null
createdAt: 2026-11-20T14:26:17Z
updatedAt: 2026-11-20T14:26:17Z
lastEditedAt: null
closedAt: null
---

# build: render the import pages without maintainer

## Motivation

The switch from pull to push ([[issue-500]]) changed where the entries come from, not who
renders the pages. `bin/lib/core/compile.bash` still turns the entries into `modules.yml`
(`bin/catalog.py` `manifest`) and calls `maintainer go vanity build`, and
`.github/actions/setup` installs the maintainer release `0.1.0-rc11` for it. The pages are
one static template: `go-import`, `go-source`, a refresh and a link to pkg.go.dev, one page
per package and per directory between the package and the module root. The site depends on
a pinned binary of another project for it, and maintainer cannot drop `go vanity` while it
does.

## PoC

```bash
make compile && cp -R dist /tmp/dist.maintainer   # today: maintainer go vanity build
# after the change
make compile && diff -r /tmp/dist.maintainer dist && echo identical
grep -n maintainer bin/lib/core/compile.bash .github/actions/setup/action.yml
```

## Acceptance criteria

- [x] The pages are rendered by Python in `bin/` (as `catalog.py` and `verify.py` are),
      with no binary to install; `compile.bash` no longer calls `maintainer`.
- [x] For the current catalog `dist/` is byte-identical to the output of
      `maintainer go vanity build` 0.1.0-rc11, the directory pages included.
- [x] `.github/actions/setup` installs no maintainer; `MAINTAINER_VERSION` and its checksum
      are gone.
- [x] Tests in `bin/tests` cover the directory pages and a module whose root has no Go files.
- [ ] A deploy of `cd.urls.yml` is green and `bin/verify-live.sh` passes.

## Out of scope

- Removing `go vanity` from maintainer: octomation/maintainer, after this task.
- Changes to the page template or to the entry format.

<!-- 2026-11-20T18:00Z
Done in the working tree, waiting for the push and a green deploy.

- `bin/catalog.py build DIR` renders the pages and `modules.yml` with the standard library, checks them with `bin/verify.py` and only then replaces `DIR`; `make` calls it directly. `bin/lib/core/compile.bash` and `modules.bash` are gone: CI runs no Bash script to build, `./Taskfile` keeps only the local smoke test and the seed.
- `dist/` of the current catalog is byte-identical to the one built by maintainer (453 files, `diff -r` empty), with no `maintainer` on PATH, under Python 3.15, 3.13 and 3.9.
- `.github/actions/setup` is gone with `setup-python`: the workflows use the `python3` of ubuntu-24.04, nothing is downloaded. `MAINTAINER_VERSION` and its checksum check are gone; README no longer lists maintainer.
- `verify.py` walks the pages with `catalog.rendered`, the same function as the build and the S5 invariant.
- `bin/tests` covers the page bytes, the directory pages of a module root without Go files and the `build` command (60 tests, OK).
-->
