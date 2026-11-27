// The sections of the page, rendered at build time from what bin/catalog.py
// says about the catalog (see ../catalog.mjs): the entries of modules/, the
// cards of docs/catalog.json and the catalog tags.
import { catalog, formatDate } from '../catalog.mjs'
import { Command } from './copy'
import { Resolver } from './resolver'

const data = catalog()
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`
const host = (url) => new URL(url).host + new URL(url).pathname.replace(/\/$/, '')
const KIND = { tool: 'Tool', library: 'Library', template: 'Template', service: 'Service' }

// The release of a version: its tree at the tag in the module's repository.
const tagUrl = (item) => item.version && `${item.repository}/tree/${item.version}`

export function Hero() {
  const tools = data.groups.find((g) => g.id === 'tools')?.items ?? []
  // public modules only: a private one is listed by its path (#499); without
  // the tools and the root, any other public module, or no terminal at all
  const featured = [...tools, data.root].filter((item) => item?.visibility === 'public')
  const fallback = [...data.groups.flatMap((g) => g.items), ...data.unlisted].slice(0, 4)
  const picks = (featured.length ? featured : fallback).map((item) => ({
    anchor: item.anchor,
    kind: item.kind,
    emoji: item.emoji ?? '📦',
    title: item.title,
    module: item.module,
    repository: item.repository,
    version: item.version,
    page: item.page,
    docs: item.docs,
  }))
  const latest = data.latest
  return (
    <section className="hero" id="top">
      <div>
        {latest && (
          <a className="release-pill" href={`#${latest.anchor}`}>
            <span>{`Last release · ${latest.title} ${latest.version}`}{latest.published && ` · ${formatDate(latest.published)}`}</span>
            <span aria-hidden="true">↓</span>
          </a>
        )}
        <p className="eyebrow">THE GO MODULES OF OCTOLAB</p>
        <h1>One import path, <em>two readers.</em></h1>
        <p className="hero-lead">
          Tools, libraries and templates of OctoLab live under <code>go.octolab.org</code>. Open an import path in
          a browser and you get the module’s page: what it is, its version, its packages and its links.
          The same address tells <code>go get</code> where the code is.
        </p>
        <div className="hero-actions">
          <Command label="add the root module">{`go get ${data.host}@latest`}</Command>
          <a className="button-text" href={`#${data.groups[0]?.id ?? 'how'}`}>Browse the catalog<span aria-hidden="true">↓</span></a>
        </div>
        <p className="hero-note">
          {plural(data.counts.modules, 'module', 'modules')} · {plural(data.counts.packages, 'package', 'packages')} ·{' '}
          {data.counts.released} released through the catalog · {data.counts.public} public, {data.counts.private} private
        </p>
      </div>
      {picks.length > 0 && <Resolver items={picks} host={data.host} />}
    </section>
  )
}

function Version({ item }) {
  if (!item.version) return <span className="version version-none">not released through the catalog yet</span>
  const href = item.releaseNotes ?? tagUrl(item)
  return (
    <span className="version">
      <a href={href} title={item.releaseNotes ? 'Release notes' : `The ${item.version} tag of the repository`}>{item.version}</a>
      {item.published && <span className="version-date"> · {formatDate(item.published)}</span>}
    </span>
  )
}

function Links({ item }) {
  return (
    <nav className="product-links" aria-label={`${item.title} links`}>
      {item.site && <a href={item.site}>{host(item.site)} <span aria-hidden="true">↗</span></a>}
      {item.docs && <a href={item.docs}>Documentation</a>}
      <a href={item.repository}>Repository</a>
      {item.releaseNotes && <a href={item.releaseNotes}>Release notes</a>}
      <a href={item.page}>Module page</a>
    </nav>
  )
}

// The packages of a module, as pkg.go.dev lists its directories; each links
// to its page on this site.
function Packages({ item }) {
  const below = item.packages.filter((p) => p.path)
  if (!below.length) return null
  return (
    <details className="packages">
      <summary>{plural(below.length, 'package', 'packages')} below the root</summary>
      <ul>
        {below.map((p) => (
          <li key={p.path}>
            <a href={p.page}>{p.path.slice(1)}</a>
            {p.path.split('/').includes('internal') && <small>internal</small>}
          </li>
        ))}
      </ul>
    </details>
  )
}

function Card({ item }) {
  return (
    <article className="product" id={item.anchor} data-module={item.module}>
      <header className="product-head">
        <span className="module-emoji" aria-hidden="true">{item.emoji}</span>
        <div>
          <h3><a href={item.site ?? item.page}>{item.title}</a></h3>
          <Version item={item} />
        </div>
        <span className="kind">{KIND[item.kind]}</span>
      </header>
      <p className="product-tagline">{item.tagline}</p>
      <p className="product-summary">{item.summary}</p>
      <p className="module-path"><a href={item.page}><code>{item.module}</code></a></p>
      {item.command && <Command label={`install ${item.title}`}>{item.command}</Command>}
      <Links item={item} />
      <Packages item={item} />
    </article>
  )
}

function Row({ item }) {
  return (
    <article className="row" id={item.anchor} data-module={item.module}>
      <span className="module-emoji" aria-hidden="true">{item.emoji ?? '📦'}</span>
      <div className="row-main">
        <h3>
          <a href={item.site ?? item.page}>{item.title}</a>
          {item.kind && <span className={`status status-${item.kind}`}>{KIND[item.kind]}</span>}
        </h3>
        {item.tagline && <p className="row-tagline">{item.tagline}</p>}
        {item.summary && <p>{item.summary}</p>}
        <p className="module-path"><a href={item.page}><code>{item.module}</code></a></p>
        <Links item={item} />
      </div>
      <div className="row-side">
        <Version item={item} />
        {item.command && <Command className="command-small" label={`install ${item.title}`}>{item.command}</Command>}
      </div>
    </article>
  )
}

function Heading({ id, eyebrow, title, lead }) {
  return (
    <div className="section-heading">
      <p className="eyebrow">{eyebrow}</p>
      <h2 id={`${id}-title`}>{title}</h2>
      {lead && <p className="section-lead">{lead}</p>}
    </div>
  )
}

// Every group renders, even one without a public card, so that the anchors of
// the navbar and of the first screen always lead somewhere.
export function Groups() {
  return data.groups.map((group) => (
    <section className="catalog-section" id={group.id} key={group.id} aria-labelledby={`${group.id}-title`}>
      <Heading {...group} />
      {!group.items.length
        ? <p className="section-lead">No public module here yet.</p>
        : group.id === 'more'
          ? <div className="rows">{group.items.map((item) => <Row key={item.module} item={item} />)}</div>
          : <div className={`product-grid product-grid-${group.id}`}>{group.items.map((item) => <Card key={item.module} item={item} />)}</div>}
    </section>
  ))
}

// Public modules that published themselves before anyone wrote their card.
export function Unlisted() {
  if (!data.unlisted.length) return null
  return (
    <section className="catalog-section" id="unlisted" aria-labelledby="unlisted-title">
      <Heading id="unlisted" eyebrow="NOT DESCRIBED YET" title="New here: published, not described yet."
        lead="These modules published themselves with a release. Their description follows; until then, their pages and repositories say what they are." />
      <div className="rows">{data.unlisted.map((item) => <Row key={item.module} item={item} />)}</div>
    </section>
  )
}

// Private modules: their path only (#499). go get works for those with access.
export function Private() {
  if (!data.private.length) return null
  return (
    <section className="private" id="private" aria-labelledby="private-title">
      <div className="private-copy">
        <p className="eyebrow">PRIVATE MODULES</p>
        <h2 id="private-title">{`${data.private.length} more, for those with access.`}</h2>
        <p>
          Their import paths resolve here like any other, but the code stays in private repositories:
          <code>go get</code> works for those who can read them, with <code>GOPRIVATE</code> set to the module path
          and git credentials for GitHub. pkg.go.dev never shows them, and this page lists their paths only.
        </p>
        <Command label="tell go a module is private">{'go env -w GOPRIVATE=go.octolab.org/<path>'}</Command>
      </div>
      <ul className="private-list">
        {data.private.map((item) => (
          <li key={item.module} id={item.anchor} data-module={item.module}>
            <a href={item.page}><code>{item.module.slice(data.host.length + 1) || item.module}</code></a>
          </li>
        ))}
      </ul>
    </section>
  )
}

export function How() {
  const sample = data.groups.find((g) => g.id === 'tools')?.items[0] ?? data.root
  const path = sample.module.slice(data.host.length)
  return (
    <section className="catalog-section how" id="how" aria-labelledby="how-title">
      <Heading id="how" eyebrow="HOW IT WORKS" title="The same address answers you and the go command."
        lead="Every module, package and directory of a module has a page here. Nothing redirects you away: the page itself is the answer, for both readers." />
      <div className="how-grid">
        <div>
          <span className="card-number">01 / YOU</span>
          <h3>Open an import path</h3>
          <p>
            <a href={sample.page}><code>{`${data.host}${path}`}</code></a> is the page of {sample.title}: its version,
            its packages, the command to get it, and links to its documentation on pkg.go.dev, its source and its own site.
          </p>
        </div>
        <div>
          <span className="card-number">02 / GO GET</span>
          <h3>Ask with ?go-get=1</h3>
          <p>
            The go command asks for the same page and reads two tags from its head: <code>go-import</code> names the
            repository, <code>go-source</code> where its files are. Then it fetches the code from GitHub and checks it
            against sum.golang.org.
          </p>
        </div>
        <div>
          <span className="card-number">03 / A RELEASE</span>
          <h3>Publish with a signed tag</h3>
          <p>
            A module’s release workflow writes its entry into the catalog with{' '}
            <a href="https://vanity-action.octolab.org/">vanity-action</a>; the site is rebuilt and checked, page by page,
            against the entries. The whole catalog is also data: <a href="/modules.yml">modules.yml</a>.
          </p>
        </div>
      </div>
      <Command label="see what the go command reads">{`curl -sL 'https://${data.host}${path}?go-get=1' | grep go-import`}</Command>
    </section>
  )
}

// "Last release: <date>." when git knows the date, nothing otherwise.
export function Updated() {
  return data.updated ? <>{` Last release: ${formatDate(data.updated)}.`}</> : null
}
