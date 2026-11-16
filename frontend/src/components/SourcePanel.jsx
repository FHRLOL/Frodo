import { citations } from '../data/mock.js'

export default function SourcePanel({ mode, onClose, inline = false }) {
  if (inline) {
    const first = citations[0]
    return (
      <div className="source-inline">
        <p className="cite-ref">{first.ref}</p>
        <p className="source-inline-title">Технические сведения о стенде</p>
        <p className="source-inline-text">{first.text}</p>
        <button type="button" className="btn-outline source-inline-btn" onClick={onClose}>
          Свернуть источник
        </button>
      </div>
    )
  }

  const list = mode === 'hints' ? citations.slice(0, 1) : citations

  return (
    <aside className="source-panel" aria-label="Источник ответа">
      <div className="panel-head">
        <h2>Методичка</h2>
        <button type="button" className="btn-outline" onClick={onClose}>
          Закрыть
        </button>
      </div>

      <p className="panel-doc">Лабораторная по RAG</p>
      <p className="panel-sub">Технические сведения о стенде</p>

      <div className="cites">
        {list.map((cite) => (
          <article key={cite.ref} className={cite.tone === 'peach' ? 'cite cite--peach' : 'cite'}>
            <p className="cite-ref">{cite.ref}</p>
            {cite.title && <strong>{cite.title}</strong>}
            <p>{cite.text}</p>
          </article>
        ))}
      </div>

      <button type="button" className="panel-link">
        Открыть всю методичку с этого места <span aria-hidden="true">↗</span>
      </button>
    </aside>
  )
}