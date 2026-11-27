// The 404 of the site. GitHub Pages answers with it for any path that is not
// a module, a package or a directory of one, the go command included: for go,
// a 404 on a prefix of an import path only means "no module here".
import { SkipNavContent } from 'nextra/components'

export const metadata = { title: 'Not a module here' }

export default function NotFound() {
  return (
    <div className="vanity-home not-found">
      <SkipNavContent />
      <p className="eyebrow">404 · NOT A MODULE HERE</p>
      <h1>Nothing at this address.</h1>
      <p className="section-lead">
        go.octolab.org answers for its modules, their packages and their directories. This path is none of them:
        it may have moved, or it was never published.
      </p>
      <p><a className="button-primary" href="/#tools">Browse the catalog</a></p>
    </div>
  )
}
