// The data of the catalog page, read once at build time.
//
// bin/catalog.py is the one place that knows the catalog: it reads the
// entries in modules/ (written by each module's release), the cards in
// docs/catalog.json (written by hand) and the catalog tags <name>--vX.Y.Z,
// checks the cards and prints what the page shows (`catalog.py site`). The
// page renders it and decides nothing about the catalog itself, so the pages
// of the packages, which catalog.py renders, and this page never disagree.
//
// Zero dependencies: Node, python3 (3.9+) and, for the dates, git.

import { execFileSync } from 'node:child_process'
import { join, resolve } from 'node:path'

// docs/ lives in the root of the catalog; next runs from docs/.
export const ROOT = resolve(process.cwd(), '..')

export function loadCatalog(root = ROOT) {
  let out
  try {
    out = execFileSync(process.env.PYTHON || 'python3', ['-I', join(root, 'bin/catalog.py'), '--root', root, 'site'], {
      encoding: 'utf8',
      maxBuffer: 1024 * 1024 * 1024,
      stdio: ['ignore', 'pipe', 'pipe'],
    })
  } catch (e) {
    throw new Error(`the catalog page cannot read the catalog (python3 bin/catalog.py site):\n${(e.stderr || e.message || '').trim()}`)
  }
  return JSON.parse(out)
}

let cached
export const catalog = () => (cached ??= loadCatalog())

export function formatDate(day) {
  if (!day) return null
  return new Date(`${day}T00:00:00Z`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })
}

// Every module of the catalog, once: the groups, then those without a card.
export function allItems(data) {
  return [...data.groups.flatMap((g) => g.items), ...data.unlisted, ...data.private]
}
