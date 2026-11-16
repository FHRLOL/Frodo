import { useEffect, useRef, useState } from 'react'
import { FORMAT_LABELS } from '../context.js'

function Chevron({ open }) {
  return (
    <svg
      className={open ? 'chevron is-open' : 'chevron'}
      width="10"
      height="6"
      viewBox="0 0 10 6"
      fill="none"
      aria-hidden="true"
    >
      <path d="M1 1l4 4 4-4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export default function FormatSelect({ value, onChange }) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef(null)

  useEffect(() => {
    if (!open) return

    function handlePointer(event) {
      if (rootRef.current && !rootRef.current.contains(event.target)) setOpen(false)
    }

    function handleKey(event) {
      if (event.key === 'Escape') setOpen(false)
    }

    document.addEventListener('mousedown', handlePointer)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('mousedown', handlePointer)
      document.removeEventListener('keydown', handleKey)
    }
  }, [open])

  return (
    <div className="format-select" ref={rootRef}>
      <button
        type="button"
        className="format-trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        {FORMAT_LABELS[value]}
        <Chevron open={open} />
      </button>

      {open && (
        <div className="format-menu" role="listbox" aria-label="Формат ответа">
          <p className="format-menu-label">Выбрать формат</p>
          {['hints', 'full'].map((key) => (
            <button
              key={key}
              type="button"
              role="option"
              aria-selected={value === key}
              className={value === key ? 'format-option is-selected' : 'format-option'}
              onClick={() => {
                onChange(key)
                setOpen(false)
              }}
            >
              {FORMAT_LABELS[key]}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}