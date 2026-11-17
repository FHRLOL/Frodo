import { citations as defaultCitations } from '../data/mock.js'

export default function SourcePanel({ mode, onClose, inline = false, items = null, title = null, docName = null }) {
  const activeList = items && items.length > 0 ? items : defaultCitations

  if (inline) {
    const first = activeList[0]
    return (
      <div className="source-inline">
        <p className="cite-ref">{first.ref}</p>
        <p className="source-inline-title">{title || 'Технические сведения о стенде'}</p>
        <p className="source-inline-text">{first.text}</p>
        <button type="button" className="btn-outline source-inline-btn" onClick={onClose}>
          Свернуть источник
        </button>
      </div>
    )
  }

  const list = mode === 'hints' || mode === 'socratic' ? activeList.slice(0, 1) : activeList

  return (
    <aside className="source-panel" aria-label="Источник ответа">
      <div className="panel-head">
        <h2>Методичка</h2>
        <button type="button" className="btn-outline" onClick={onClose}>
          Закрыть
        </button>
      </div>

      <p className="panel-doc">{docName || 'Лабораторная по RAG'}</p>
      <p className="panel-sub">{title || 'Технические сведения о стенде'}</p>

      <div className="cites">
        {list.map((cite, index) => (
          <article key={cite.ref || index} className={cite.tone === 'peach' ? 'cite cite--peach' : 'cite'}>
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
