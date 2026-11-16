import { useState } from 'react'

export default function Composer({ onSend, busy }) {
  const [value, setValue] = useState('')

  function handleSubmit(event) {
    event.preventDefault()
    const text = value.trim()
    if (!text || busy) return
    onSend(text)
    setValue('')
  }

  return (
    <div className="composer-wrap">
      <form className="composer" onSubmit={handleSubmit}>
        <input
          type="text"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="Задай вопрос по курсу"
          aria-label="Вопрос по курсу"
        />
        <button type="submit" className="btn-send" disabled={busy}>
          <span className="send-label">{busy ? 'Поиск…' : 'Отправить'}</span>
          <span className="send-arrow" aria-hidden="true">
            ↑
          </span>
        </button>
      </form>
      <p className="composer-note">Ответы основаны на материалах курса</p>
    </div>
  )
}