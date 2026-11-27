# Agent guide

This repository is go.octolab.org: the import paths of OctoLab's Go modules
and the catalog of what they are. Every address of the site has two readers.
A person who opens it gets a page: the catalog at `/`, a page per module,
package and directory of a module everywhere else. The go command that asks
for the same address with `?go-get=1` gets the same page and reads two tags
from its head. Keep both working; read this before changing anything.

## What writes what

| Path | Written by | Notes |
| --- | --- | --- |
| `modules/<module path>.json` | the module's release workflow, with [vanity-action](https://vanity-action.octolab.org/) as the OctoLab Releaser App | The entry: repository, branch, visibility, packages, topics, version. Never edit by hand except as the maintainer, as the README describes |
| `docs/catalog.json` | by hand | The cards of the catalog page: what a person reads about each module, and the groups of the page. Changes only when a module joins, leaves or is described anew |
| `docs/` other than `catalog.json` | by hand | The catalog page, Nextra on Next.js; see [docs/README.md](docs/README.md) |
| `bin/catalog.py` | by hand | The one place that knows the catalog: checks entries and cards, renders the package pages, prints the data of the catalog page (`site`), lays the page over `/` (`build --site`) |
| `bin/verify.py` | by hand | The independent check of every page, local and live |
| `bin/pages.py`, `.github/settings.json` | by hand | GitHub Pages: the declared settings, the smoke test of the live site, `doctor` |
| `bin/serve.py` | by hand | Serves a build as Pages does, and runs the go command against it |
| `dist/`, `docs/dist/`, `docs/.next/`, `docs/node_modules/` | the build | Ignored by git |

The version, the date of a release, the release history, the packages and
the repository are **not** in `docs/catalog.json`: the page reads them from
the entries and from the catalog tags `<name>--vX.Y.Z` at build time. A
release of a module therefore needs nothing here; a new module does.

## Two readers, one address

These hold for every page, and `bin/verify.py` fails the build otherwise:

- `go-import` and `go-source` appear exactly once, first in `<head>`, before
  any script, style or link. The go command reads the head with a lenient
  XML tokenizer and stops at the first thing it cannot read: an inline script
  before the tags could hide them.
- No redirect: the page is the answer for both readers.
- A page of a published package of a public module links its documentation
  on pkg.go.dev; a page of a private module links nothing there.
- `/` is the catalog page with the tags of the root module `go.octolab.org`.
  `bin/catalog.py build --site docs/dist` puts them right after `<head>` of
  the exported page, with no text between them (React hydrates the head).
  Never add them in `docs/app/layout.jsx` too: they must appear once.
- The export may not replace an import page or `modules.yml`; its `404/`
  folder is dropped (Pages answers with `404.html`, and `404` is a valid path
  segment of a module). Its other folders start with `_`, which a module path
  never does.

Nothing a publisher writes can fail the build of the site: a public module
without a card is listed under "Not described yet", and a card of a module
that became private is set aside. Both are warnings of
`python3 bin/catalog.py cards`, in the log of every build. Errors in
`docs/catalog.json` are the maintainer's own and stop the build, so check
them in the same change. Keep it this way when you change `bin/catalog.py`:
a module's release must never wait for someone to write its card.

## Add a module

For now a module joins the catalog page by hand. Its entry arrives first,
with the first release that runs vanity-action; its pages and `go get` work
from that moment. The card follows.

1. **Notice it.** `python3 bin/catalog.py cards` warns
   `go.octolab.org/<path>: no card in docs/catalog.json`; the delivery logs the
   same warning, and the page lists the module under "Not described yet".
2. **Private?** A private module gets no card: the page lists private modules
   by their path only (#499). Stop here.
3. **Read the project.** Take the facts from the project's own site, its
   README and its `AGENTS.md`, not from memory: the emoji it uses, its slogan,
   what it does for the user, the URL pattern of its release notes. Open every
   URL you are going to write (`curl -sI`), and the release notes of the
   published version.
4. **Check the command.** A tool's `install` must work as written: a Formula
   of `octolab/tap`, or `go install <module>@latest` tried in an empty GOPATH
   (`GOBIN=$(mktemp -d) GOPATH=$(mktemp -d) go install …`). A library needs no
   `install`: the card shows `go get <module>@latest`.
5. **Add the card** to `items` in `docs/catalog.json`. The order of `items`
   within a group is the order on the page: products first, by how much they
   are used. Fields:

   | Field | Required | Meaning |
   | --- | --- | --- |
   | `module` | yes | The module path, as in its entry |
   | `group` | yes | The `id` of a group in `groups`: `tools` for a tool with its own site, `libraries`, `templates`, `more` for utilities and earlier services |
   | `kind` | yes | `tool`, `library`, `template` or `service` |
   | `emoji` | yes | The project's own emoji, as its README or site shows it |
   | `title` | yes | The name as the project writes it |
   | `tagline` | yes | The project's own slogan, one short sentence ending with a period |
   | `summary` | yes | One or two sentences on what the user gets, in user terms |
   | `site` | no | The project's own site, `https://` with a path (at least `/`), when one answers; without it the card links the module's page |
   | `releaseNotes` | no | The URL of a release note with `{version}` in place of the version without `v`, e.g. `https://pulse.octolab.org/changelog/v{version}/`; without it the version links the tag in the repository |
   | `install` | no | One command that installs a tool; a library shows `go get` without it |

   Write in English, as the projects' sites do; no promises of unreleased
   behaviour, no history of the project. A card is anchored at the module's
   name (`/#indexit`); a name that the page itself uses as an id (a section:
   `top`, `how`, `unlisted`, `private`, `notes`; a group id; a name ending in
   `-title` or starting with `resolver-`) is anchored at its module path
   instead; nothing to do.
6. **Check**, from the repository root:

   ```sh
   make validate   # entries and cards
   make test       # the tools of the catalog
   make deps       # once: npm ci in docs/
   make            # the catalog page over the import pages, verified
   make resolve    # the go command against this build, not the live site
   ./Taskfile resolve --all   # every released public module, the new one included
   ```

7. **Look at it.** `make serve` serves the build at <http://127.0.0.1:8040/>
   as Pages would; open the card, the module's page and one package page, in
   light and dark, on a wide and a narrow screen. `./Taskfile docs dev` is the
   page alone with live reload, without the import pages and their tags.
8. **Hand it over.** The maintainer commits: stage the change and give one
   message, `docs(catalog): add <name>`.

## Change or remove

| Event | By hand |
| --- | --- |
| A new release of a module | nothing: the delivery rebuilds the site and its smoke test fails while a card shows another version |
| A new site, release notes path or install command | the card's fields; check the URLs; `docs(catalog): update <name>` |
| A module becomes private | delete its card (a warning until then) |
| A module is retired from the catalog | the maintainer deletes its entry and its card in one commit: a card without an entry stops the build |
| A new group | add it to `groups` (`id` in lowercase letters, not a section of the page); a group renders even with no public card, and the navbar in `docs/content/_meta.js` links `tools`, `libraries` and `templates` by id: rename them together |
| The page's texts | `docs/content/index.mdx` and `docs/components/`; they name no module by hand, keep them so |
| The social preview | `docs/scripts/og.html`, rendered by `docs/scripts/og.mjs` (see docs/README.md); it names no module and no version |

## Pages and HTTPS

The site is served from the custom domain `go.octolab.org` by GitHub Pages,
built by GitHub Actions, with Enforce HTTPS on; `.github/settings.json`
declares all three. The delivery checks the settings on GitHub before it
builds (`bin/pages.py settings`) and, after the deploy, that every page
serves `go get` (`bin/verify.py --url`), and that the catalog page, its
assets, its 404, a card per module at its version and the redirect of
`http://` to `https://` are there (`bin/pages.py smoke`).
`python3 bin/pages.py doctor` runs the same checks on demand and lists
workflows that are off.

## Ground rules

- The agent prepares a change in full and hands over its commit message; the
  maintainer reviews, commits and pushes.
- Facts on the page come from the catalog or from the project's own site; a
  claim neither supports does not go on the page.
- Nothing about a private module beyond what its entry already publishes.
- The dependencies of the page follow octolab/skills and octolab/homebrew-tap;
  Dependabot proposes npm updates of `docs/` daily.
