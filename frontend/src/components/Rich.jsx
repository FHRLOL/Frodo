import { Fragment } from 'react'

export default function Rich({ text }) {
  const parts = text.split(/(\[\d+(?:–\d+)?\])/g)

  return (
    <>
      {parts.map((part, index) =>
        /^\[/.test(part) ? (
          <span className="ref" key={index}>
            {part}
          </span>
        ) : (
          <Fragment key={index}>{part}</Fragment>
        ),
      )}
    </>
  )
}