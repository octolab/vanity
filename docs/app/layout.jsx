import { Footer, Layout, Navbar } from 'nextra-theme-docs'
import { Head } from 'nextra/components'
import { getPageMap } from 'nextra/page-map'
import 'nextra-theme-docs/style.css'
import './globals.css'
import './brand.css'
import './landing.css'
import { siteUrl } from '../site.mjs'

// The go-import and go-source tags of the root module are not here: the build
// (bin/catalog.py build --site) puts them first in the head of the exported
// page, where the go command reads them, and checks them with bin/verify.py.
export const metadata = {
  title: { default: 'go.octolab.org — The Go modules of OctoLab', template: '%s · go.octolab.org' },
  description: 'The Go modules of OctoLab under one import path: tools, libraries and templates, each linked to its own site, documentation and repository.',
  metadataBase: new URL(siteUrl),
  icons: { icon: `${process.env.BASE_PATH || ''}/icon.svg` },
}

export default async function RootLayout({ children }) {
  return (
    <html lang="en" dir="ltr" suppressHydrationWarning>
      <Head color={{ hue: 192, saturation: 100, lightness: { light: 25, dark: 66 } }} backgroundColor={{ light: 'rgb(247, 248, 250)', dark: 'rgb(14, 19, 26)' }} />
      <body>
        <Layout
          navbar={<Navbar logo={<span className="wordmark"><span className="brand-emoji" aria-hidden="true">🤴</span>go.octolab.org</span>} projectLink="https://github.com/octolab/vanity" />}
          pageMap={await getPageMap()}
          docsRepositoryBase="https://github.com/octolab/vanity/tree/main/docs"
          footer={<Footer><div className="site-footer"><span><b>go.octolab.org</b> <span>One import path for every OctoLab module.</span></span><span>MIT © {new Date().getFullYear()} <a href="https://github.com/octolab">OctoLab</a></span></div></Footer>}
          search={null}
          copyPageButton={false}
          feedback={{ content: 'Something wrong with a module page?', link: 'https://github.com/octolab/vanity/issues/new' }}
          nextThemes={{ defaultTheme: 'system' }}
        >
          {children}
        </Layout>
      </body>
    </html>
  )
}
