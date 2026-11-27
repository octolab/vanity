export default {
  '*': { theme: { timestamp: false } },
  index: {
    title: 'Home', type: 'page', display: 'hidden',
    theme: { layout: 'full', sidebar: false, toc: false, breadcrumb: false, pagination: false, copyPage: false },
  },
  tools: { title: 'Tools', type: 'page', href: '/#tools' },
  libraries: { title: 'Libraries', type: 'page', href: '/#libraries' },
  templates: { title: 'Templates', type: 'page', href: '/#templates' },
  how: { title: 'How it works', type: 'page', href: '/#how' },
}
