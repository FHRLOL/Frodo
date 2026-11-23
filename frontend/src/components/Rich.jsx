import { Fragment } from 'react'

// Инлайн-разметка из ответов модели: код, жирный, курсив и ссылки на источники [1]
const TOKEN_RE = /(`[^`\n]+`|\*\*[^*\n]+\*\*|\*[^*\n]+\*|\[\d+(?:[–-]\d+)?\])/g

export default function Rich({ text }) {
  const parts = String(text ?? '').split(TOKEN_RE)

  return (
    <>
      {parts.map((part, index) => {
        if (!part) return null

        if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
          return (
            <code className="md-code" key={index}>
              {part.slice(1, -1)}
            </code>
          )
        }

        if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
          return (
            <strong className="md-strong" key={index}>
              {part.slice(2, -2)}
            </strong>
          )
        }

        if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
          return (
            <em className="md-em" key={index}>
              {part.slice(1, -1)}
            </em>
          )
        }

        if (/^\[\d/.test(part)) {
          return (
            <span className="ref" key={index}>
              {part}
            </span>
          )
        }

        return <Fragment key={index}>{part}</Fragment>
      })}
    </>
  )
}
