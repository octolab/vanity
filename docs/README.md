# The catalog page

One English page at <https://go.octolab.org/>: what the catalog holds, a card
per module linked to its documentation, repository and own site, the private
modules by path, and how the same address answers both a person and the go
command. Nextra 4 on Next.js, the stack shared with octolab/skills,
octolab/homebrew-tap, octopot/indexit, octomation/maintainer and
octomation/pulse. The page has its own npm dependencies; the catalog itself
has none. How a module gets its card is in [AGENTS.md](../AGENTS.md#add-a-module).

The page is one of two layers. `bin/catalog.py build --site docs/dist` lays
its static export over the import pages that it renders itself, puts the
`go-import` and `go-source` tags of the root module first in its head, and
`bin/verify.py` checks the result page by page. So the page here never holds
those tags, and the pages of the packages are not part of this site.

## Run locally

Use Node 24 (the CI version), Python 3.9+ and git. From the repository root:

```sh
make deps            # npm ci in docs/
./Taskfile docs dev  # the page alone, live reload, http://localhost:3000
./Taskfile demo      # the whole site as Pages serves it, http://127.0.0.1:8040
```

The data is read once when the server starts: restart `docs dev` after you
change `docs/catalog.json` or an entry.

## Build

```sh
make                 # the export with SITE_URL=https://go.octolab.org/, then the whole site in dist/
make docs            # the export only, in docs/dist/
```

`SITE_URL` is the origin of canonical and social links, required for a static
export; the [delivery](../.github/workflows/cd.urls.yml) passes the one Pages
reports. A local build keeps the production origin: its assets are
root-relative, so it works on any host.

## Where the page comes from

| Location | Purpose |
| --- | --- |
| `catalog.json` | The cards and the groups of the page, written by hand |
| `catalog.mjs` | Runs `python3 bin/catalog.py site` once: the entries joined with the cards, the release history from the catalog tags, the counts |
| `content/index.mdx` | The page: the order of its sections and the notes at the end |
| `content/_meta.js` | The navbar: anchors to the sections |
| `components/catalog.jsx` | The sections rendered at build time: the first screen, the groups, the modules without a card, the private band, how it works |
| `components/resolver.jsx` | The terminal of the first screen: pick a module, see what a browser and the go command get at its address |
| `components/copy.jsx` | A command with a button that copies it, as on octolab/homebrew-tap |
| `app/globals.css` | Shared layouts, kept identical to octopot/indexit |
| `app/brand.css` | The tokens of go.octolab.org: cool paper, navy ink, the teal of Go's gopher blue, the gold of the crown |
| `app/landing.css` | The page itself, adapted from octolab/homebrew-tap |
| `app/layout.jsx`, `app/[[...mdxPath]]/page.jsx` | Site identity, Nextra theme, titles and social metadata |
| `app/not-found.jsx` | The 404 of the whole site, the import paths included |
| `public/icon.svg` | The favicon: 🤴 from Noto Emoji, Apache-2.0 |
| `public/og.png`, `scripts/og.html`, `scripts/og.mjs` | The social preview, its source and its renderer |

What a card shows and where it comes from:

| On the card | Source |
| --- | --- |
| Emoji, title, tagline, summary, site, release notes, install command | `catalog.json` |
| Module path, repository, packages, visibility | the entry in `modules/` |
| Version | the entry; it links the release notes, or the tag in the repository |
| Date of the release, the last release of the catalog | the commit of the catalog tag `<name>--v<version>`; none in a shallow clone |
| Documentation | `https://pkg.go.dev/<module>`, for a public module |

## Social preview image

`public/og.png`, 1733×908, is rendered from `scripts/og.html`: the wordmark,
the slogan and the two readers of an address. It names no module and no
version, so neither a release nor a new module changes it. Render it with
headless Chrome and a copy of `playwright-core` the script can import:

```sh
PLAYWRIGHT_CORE=/path/to/playwright-core/index.mjs CHROME=/path/to/chrome node scripts/og.mjs
```

## Dependencies

`package.json` and the lockfile follow octolab/skills. They pin Zod to
`4.1.12` under `nextra-theme-docs` to avoid
[a validation regression](https://github.com/shuding/nextra/issues/5036), and
override the xmldom dependency of `speech-rule-engine@4.1.4`; the docs README
of octomation/pulse says when to drop both. Overrides also lift KaTeX to
0.18 and minimatch to 11, which Nextra 4.6.1 pins below their advisories;
Zod stays vulnerable on purpose. `.github/self-control.md` lists every
override, why it is there and when to drop it. Search is disabled: one
page needs none.
