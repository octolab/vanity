'use client'

import { useEffect, useRef, useState } from 'react'

// A command to run, with a button that copies it. The `$ ` prompt is drawn
// but not copied.
export function Command({ children, label, className = '' }) {
  const [state, setState] = useState('')
  const timer = useRef(null)
  useEffect(() => () => clearTimeout(timer.current), [])
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(children)
      setState('Copied')
    } catch {
      setState('Select and copy')
    }
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setState(''), 2000)
  }
  return (
    <div className={`command ${className}`.trim()}>
      <code><span aria-hidden="true">$ </span>{children}</code>
      <button type="button" onClick={copy} aria-label={`Copy: ${label || children}`}>{state || 'Copy'}</button>
      <span className="command-status" role="status" aria-live="polite">{state}</span>
    </div>
  )
}
