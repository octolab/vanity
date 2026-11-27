'use client'

import { useState } from 'react'
import { Command } from './copy'

// The terminal of the first screen: pick a module and see both readers of its
// address. A browser gets the module's page; the go command gets the same
// page and reads go-import from its head. Nothing here runs: the tags are the
// ones the build writes, the version is the one the catalog serves.
export function Resolver({ items, host }) {
  const [current, setCurrent] = useState(0)
  const item = items[current]
  if (!item) return null
  const pick = (event, index) => {
    setCurrent(index)
    event.currentTarget.focus()
  }
  const onKeyDown = (event) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key]
    const jump = { Home: 0, End: items.length - 1 }[event.key]
    if (step === undefined && jump === undefined) return
    event.preventDefault()
    const next = jump ?? (current + step + items.length) % items.length
    setCurrent(next)
    event.currentTarget.parentElement.children[next]?.focus()
  }
  const path = item.module.slice(host.length)
  const at = item.version ?? 'latest'
  return (
    <div className="shelf">
      <div className="shelf-tabs" role="tablist" aria-label="Modules">
        {items.map((it, index) => (
          <button
            key={it.module}
            type="button"
            role="tab"
            id={`resolver-tab-${it.anchor}`}
            aria-selected={index === current}
            aria-controls="resolver-panel"
            tabIndex={index === current ? 0 : -1}
            onClick={(event) => pick(event, index)}
            onKeyDown={onKeyDown}
          >
            <span aria-hidden="true">{it.emoji}</span>
            <span>{it.title}</span>
          </button>
        ))}
      </div>
      <div className="terminal" role="tabpanel" id="resolver-panel" aria-labelledby={`resolver-tab-${item.anchor}`}>
        <div className="terminal-bar">
          <span><span className="terminal-dots" aria-hidden="true">●●●</span> {item.module}</span>
          <span className="terminal-version">{item.version ?? 'no release yet'}</span>
        </div>
        <div className="terminal-body">
          <p className="terminal-comment"># you, in a browser: the module’s page</p>
          <p className="terminal-line"><a href={item.page}>{`https://${host}${path}/`}</a></p>
          <p className="terminal-comment"># the go command, at the same address</p>
          <Command label={`fetch ${item.title}`}>{item.kind === 'library' ? `go get ${item.module}@${at}` : `go mod download ${item.module}@${at}`}</Command>
          <p className="terminal-trace">
            <span className="trace-verb">GET</span> {`https://${host}${path}?go-get=1`}
          </p>
          <p className="terminal-trace">
            <span className="trace-tag">{'<meta name="go-import"'}</span>{' '}
            <span className="trace-value">{`content="${item.module} git ${item.repository}"`}</span>
            <span className="trace-tag">{'>'}</span>
          </p>
          <p className="terminal-trace">
            <span className="trace-verb">git</span> {`${item.repository} @ ${at}`}
          </p>
          <p className="terminal-trace trace-ok">✓ verified by sum.golang.org</p>
        </div>
        <div className="terminal-caption">
          <span>{item.docs ? <>API reference: <a href={item.docs}>pkg.go.dev</a></> : 'A private module'}</span>
          <a href={`#${item.anchor}`}>The card <span aria-hidden="true">↓</span></a>
        </div>
      </div>
    </div>
  )
}
