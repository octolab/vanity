[![Vanity URLs][social.preview]][preview.config]

[![Mirror][mirror.icon]][mirror.page]

# 🤴 go.octolab.org

Vanity URLs for OctoLab's Go modules.

Every module served under `go.octolab.org` has an entry in [`modules/`](modules):
one JSON file that its project writes when it releases. The site is rendered
from these entries only: vanity never checks out a module and its delivery
holds no secret that reads another repository.

## 📦 How a project publishes itself

A project publishes its module from its own `cd.yml`, the workflow that runs on
a release tag `v*`, with [octomation/vanity-action][vanity-action]. The action
lists the packages of the released commit, writes `modules/<module path>.json`
to octolab/vanity as the OctoLab Releaser App (a signed commit on `main`) and
tags that commit `<name>--vX.Y.Z`, e.g. `indexit--v0.4.1`. The push to `main`
starts vanity's delivery, which checks the change and deploys the site.

Add a job to the project's `cd.yml`, the workflow that runs on `push: tags:
[ 'v*' ]` (see [octopot/indexit][indexit.cd] for the style); let it wait for
the release and add it to `notify.needs`. A repository without such a
workflow gets a `cd.yml` holding only this job, with a dispatch to publish a
tag again or dry: the template is in the [action's README][vanity-action].
The snippet below is the action's own:

```yaml
  # a job of its own: if publishing fails after the release is out, rerun
  # only this job; the catalog keeps stable releases only
  vanity:
    name: Publishing the module
    needs: [ release ]
    if: startsWith(github.ref, 'refs/tags/v') && !contains(github.ref_name, '-')
    runs-on: ubuntu-24.04
    permissions:
      contents: read

    steps:
      # without the Releaser credentials (a project generated from a template,
      # a private repository on the Free plan) warn and end successfully
      - name: Check the Releaser credentials
        id: preflight
        env:
          OCTOLAB_RELEASER_CLIENT_ID: ${{ secrets.OCTOLAB_RELEASER_CLIENT_ID }}
          OCTOLAB_RELEASER_KEY: ${{ secrets.OCTOLAB_RELEASER_KEY }}
        run: |
          if [ -n "${OCTOLAB_RELEASER_CLIENT_ID}" ] && [ -n "${OCTOLAB_RELEASER_KEY}" ]; then
            echo 'ready=true' >> "${GITHUB_OUTPUT}"
          else
            echo '::warning title=Vanity::OCTOLAB_RELEASER_CLIENT_ID and OCTOLAB_RELEASER_KEY are not available to this repository; set them as organization or repository secrets to publish the module to go.octolab.org. Nothing was published.'
            echo 'ready=false' >> "${GITHUB_OUTPUT}"
          fi
      - name: Checkout the repository
        if: steps.preflight.outputs.ready == 'true'
        uses: actions/checkout@v7.0.1
        with: { persist-credentials: false }
      - name: Set up Go environment
        if: steps.preflight.outputs.ready == 'true'
        uses: actions/setup-go@v7.0.0
        with: { go-version: 1.27.4, cache: false }
      - name: Mint the catalog token
        if: steps.preflight.outputs.ready == 'true'
        id: catalog
        uses: actions/create-github-app-token@v3.3.0
        with:
          client-id: ${{ secrets.OCTOLAB_RELEASER_CLIENT_ID }}
          private-key: ${{ secrets.OCTOLAB_RELEASER_KEY }}
          owner: octolab
          repositories: vanity
          permission-contents: write
      - name: Publish the module to go.octolab.org
        if: steps.preflight.outputs.ready == 'true'
        uses: octomation/vanity-action@v0.1.0
        with:
          token: ${{ steps.catalog.outputs.token }}
          packages: all
          # name: ecosystem/tablo # when the repository name is taken or doesn't fit
```

- `name` is the short name in the catalog tag `<name>--vX.Y.Z` and in the
  entry. It defaults to the repository name (`pkg` for go.octolab.org, from
  octolab/pkg) and must be unique in the catalog: kebab-case segments joined
  by `/` (`^[a-z0-9]+(-[a-z0-9]+)*(/[a-z0-9]+(-[a-z0-9]+)*)*$`, at most 64
  characters). Set it explicitly when the repository name is taken or does
  not fit: `ecosystem/tablo` (octopot/tablo), `pulse` (octomation/tablo, to be
  renamed), `sparkle` and `tact` (both repositories are named `service`).
- `packages` decides what go.octolab.org publishes: `root` the module root
  only, `all` every package directory, `auto` (default) `root` for a private or
  internal repository and `all` for a public one. Every integration of this
  rollout sets `all` explicitly.
- A token that exists but cannot write to octolab/vanity fails the job: only
  missing credentials are skipped.

### Release tags

- A release is a signed, annotated tag `vX.Y.Z` on the released commit. A
  lightweight or unsigned tag is an error; a prerelease (`v1.0.0-rc1`) is
  skipped.
- The tag follows Go's major-version rule: `v0`/`v1` for a module path without
  a suffix, `vN` (N ≥ 2) only for a module path ending in `/vN`.
- The module is the one at the repository root (`go.mod` at the top).
- A release older than the published version is a successful no-op (a backport).

### The contract (#507)

A project that publishes here promises:

- its module path is exactly its URL under go.octolab.org, and no other
  project or template declares that path;
- releases are signed, annotated `vX.Y.Z` tags, and a published tag is never
  deleted or moved (protect `refs/tags/v*` with a ruleset where the plan
  allows it): Go's checksum database remembers every published version;
- it publishes only its own module: the catalog refuses an entry that moves an
  existing module to another repository or renames it.

### What a human sets up

- The OctoLab Releaser App installed on octolab/vanity with Contents: write
  (no Workflows, no Administration).
- `OCTOLAB_RELEASER_CLIENT_ID` and `OCTOLAB_RELEASER_KEY` visible to the
  project: an organization secret, or repository secrets for a private
  repository of an organization on the Free plan.
- A tag ruleset protecting `v*` in the project, where the plan allows it.

## 🗂 Entries

`modules/<module path>.json`, e.g. `modules/go.octolab.org/toolset/indexit.json`
(the root module: `modules/go.octolab.org.json`). Exactly these keys in this
order, two-space JSON, ASCII, a trailing newline:

| Key | Rule |
|:--|:--|
| `schema` | `1` |
| `name` | short unique name for catalog tags: kebab-case segments joined by `/`, at most 64 characters |
| `module` | the module path; equals the file path between `modules/` and `.json`; a `/vN` suffix only for N ≥ 2, and `version` follows it |
| `repository` | `https://github.com/<owner>/<name>` |
| `branch` | the default branch (go-source links) |
| `visibility` | `public`, `private` or `internal` |
| `scope` | `all` or `root` (`root` ⇒ `packages` is `[""]`) |
| `packages` | package directories relative to the module, `""` first, sorted |
| `topics` | repository topics, sorted |
| `version` | the published `vX.Y.Z`, `null` for an entry seeded from the submodules |
| `commit` | the commit the packages were listed from |

The catalog also holds: the root module `go.octolab.org` has an entry; no
package path is published by two entries, and no entry renders a parent page
over another entry's package; names are unique. Catalog tags
`<name>--vX.Y.Z` count only on a commit of `main`.

The 35 entries of the migration (issue 500) were seeded once from the
submodules of `0f56e6a` with `./Taskfile seed --action <vanity-action checkout>
--rev 0f56e6a` (`bin/seed.py`): each entry is what the action's own `entry`
command prints for the pinned tree, byte for byte what a release would write.
Their `version` stays `null` until the next release of each project:
a release displaces its seed. `python3 bin/catalog.py progress` counts
them ("Self-published: N of 35 modules; on seeds: K (names)"), and
**Continuous delivery** writes the same to its log and job summary.

### Private modules

vanity cannot read private repositories: what a private module publishes is
what its own release workflow writes. With `packages: auto` that is the module
root only, enough for `go get` in module mode by someone with access. This
rollout publishes `all` for every module, as the submodules did; what private
modules should disclose is open in #499.

## 🔐 Security model

Two identities write to `main`: the maintainer (`kamilsk`, signed commits) and
the Releaser App, whose tokens any project with the key can mint. Every
publisher is trusted not to be hostile; the delivery still refuses what a
publisher has no business changing:

1. The gate in `.github/workflows/cd.urls.yml` (the trust anchor: the App has
   no Workflows permission) first checks the push itself: if its
   GitHub-authenticated sender is not the maintainer, `before..after` may
   change `modules/<module path>.json` only.
2. It then takes the last successful github-pages deployment B, requires
   `B..HEAD` to be linear, and attributes every commit to the push that
   brought it, by the pusher recorded in the repository activity, never by
   commit metadata. A commit no push accounts for counts as a publisher's.
3. A path whose last writer is not the maintainer must be
   `modules/<module path>.json`; anything else fails the run.
4. Those entries, and every publisher commit that touched them, are judged by
   `bin/catalog.py` as it was at B, not by the candidate's own copy: valid, not
   deleted, and keeping the `repository` and `name` they had before the commit.
5. Then the whole catalog is checked and built; the deploy refuses a commit
   older than the live site (a re-run of an old run), and the live site must
   serve this build's `modules.yml` and a page for every published package.

A failure deploys nothing and notifies Slack; a later maintainer commit to the
path clears it. When the gate cannot attribute a push (no deployment yet, lost
activity), the maintainer dispatches **Continuous delivery** with `vouch`.
Left to a key holder: claiming an unused module path, editing branch,
packages or topics of an entry.

## 🔗 Dependencies

- [Maintainer](https://maintainer.octolab.org/)
  [v0.1.0-rc11](https://github.com/octomation/maintainer/releases/tag/v0.1.0-rc11)
  renders the pages; the workflows download it and check its release checksum.
- Python 3.9+ (the workflows use 3.15.2), Bash 4+, Git.
- Only for the one-off seed: Go and the GitHub CLI with read access to the
  private repositories.

## Build and verify

```sh
make validate  # check the entries and the catalog invariants
make list      # print the manifest built from the entries
make           # validate, render and verify dist/ before replacing the previous build
make verify    # check all module roots and package pages of dist/ again
make test      # tests of the catalog tools
```

`bin/verify.py` checks `go-import`, `go-source` (repository and branch) and the
redirect to pkg.go.dev of every page against the entries, and that pages and
published packages match. With `--url https://go.octolab.org` it checks the
live site (`--packages` for every package), including a 404 for an unknown
path.

## GitHub Pages and HTTPS

The public endpoint is `https://go.octolab.org`. DNS must point the subdomain's
`CNAME` to `octolab.github.io` (without `/vanity`). In this repository's
[Pages settings](https://github.com/octolab/vanity/settings/pages), configure:

- Source: **GitHub Actions**.
- Custom domain: **go.octolab.org**.
- **Enforce HTTPS**, once GitHub has issued the domain certificate.

For an Actions deployment, a checked-in `CNAME` file does not configure the
domain; GitHub [ignores it](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/troubleshooting-custom-domains-and-github-pages).
DNS alone is insufficient: without the Pages custom-domain setting, GitHub
serves its default certificate, which does not cover `go.octolab.org`.
Verify the domain under [the organization's Pages settings](https://github.com/organizations/octolab/settings/pages)
and keep the TXT record. See [GitHub's domain verification instructions](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/verifying-your-custom-domain-for-github-pages).

**Continuous delivery** runs on a push to `main` that changes the catalog or
its tools, monthly, and on dispatch. It needs no secret but `SLACK_WEBHOOK`.

After a deploy:

```sh
make check
```

This checks the root, CLI, and config modules over verified HTTPS, then downloads
the root module at `v0.12.0` and `v0.12.2`, CLI at `v0.6.4`, and config at
`v0.0.5` into an empty temporary module cache with `GOPROXY=direct` and checksum
verification enabled. These targets follow the dependency upgrade in indexit
after the investigation in [indexit#102](https://github.com/octopot/indexit/issues/102)
found that the historical config `v0.0.4` tag is missing from GitHub.
To check the entire published catalog, run
`python3 bin/verify.py --url https://go.octolab.org --packages`.

Two maintainer scripts need `gh` signed in with read access (and admin of the
organizations for the second one):

```sh
bin/verify-live.sh --packages      # green CD on main, the live site, every catalog tag
bin/releaser-secrets.sh --pem key  # prove a Releaser key, then set or rotate its secrets (--apply)
```

`bin/verify-live.sh` runs this checkout's `bin/verify.py` against the entries
of `main` read as data, and checks that every catalog tag is a verified commit
of the Releaser App on `main` whose entry holds that version.

<p align="right">made with ❤️ for everyone by <a href="https://www.octolab.org/">OctoLab</a></p>

[indexit.cd]:       https://github.com/octopot/indexit/blob/main/.github/workflows/cd.yml
[vanity-action]:    https://github.com/octomation/vanity-action

[social.preview]:   https://cdn.octolab.org/repo/vanity.png
[preview.config]:   https://socialify.git.ci/octolab/vanity?description=1&font=Raleway&language=1&name=1&owner=1&pattern=Circuit%20Board&theme=Light
[preview.fallback]: https://socialify.git.ci/octolab/vanity/image?description=1&font=Raleway&language=1&name=1&owner=1&pattern=Circuit%20Board&theme=Light

[mirror.page]:      https://bitbucket.org/kamilsk/vanity
[mirror.icon]:      https://img.shields.io/badge/mirror-bitbucket-blue
