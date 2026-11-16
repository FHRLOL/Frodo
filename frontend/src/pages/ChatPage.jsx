import { useEffect, useRef, useState } from 'react'
import Composer from '../components/Composer.jsx'
import Rich from '../components/Rich.jsx'
import SourcePanel from '../components/SourcePanel.jsx'
import Topbar from '../components/Topbar.jsx'
import { FORMAT_LABELS, useFormat } from '../context.js'
import { answers, courseCard, suggestions } from '../data/mock.js'

function EmptyState({ onAsk }) {
  return (
    <div className="chat-inner">
      <div className="hero">
        <p className="mobile-course">Локальные LLM и RAG</p>
        <h2>Спроси по лабораторной</h2>
        <p className="hero-sub">Frodo найдёт нужное место в методичке и покажет его рядом с ответом.</p>
        <hr className="rule hero-rule" />
        <p className="hero-label">С чего начать</p>
        <div className="suggest">
          {suggestions.map((question) => (
            <button type="button" key={question} onClick={() => onAsk(question)}>
              <span>{question}</span>
              <span className="arrow" aria-hidden="true">
                ↗
              </span>
            </button>
          ))}
        </div>
      </div>

      <aside className="side-card">
        <div className="side-card-top">
          <span>{courseCard.label}</span>
          <span className="cover" aria-hidden="true" />
        </div>
        <h3>{courseCard.title}</h3>
        <p>{courseCard.text}</p>
      </aside>
    </div>
  )
}

function Answer({ data, mode, sourceOpen, onOpenSource, onCloseSource }) {
  return (
    <div className="answer">
      <p className="answer-by">Frodo</p>
      <h3 className="answer-title">{data.title}</h3>

      <p>
        <Rich text={data.paragraphs[0]} />
      </p>

      {data.code && (
        <div className="code-block">
          <code>{data.code}</code>
          <span className="code-caption">{data.codeCaption}</span>
        </div>
      )}

      {data.paragraphs.slice(1).map((text) => (
        <p key={text}>
          <Rich text={text} />
        </p>
      ))}

      {data.source && (
        <button type="button" className="source-card" onClick={onOpenSource}>
          <span className="source-meta">
            <span className="source-ref">{data.source.ref}</span>
            <span className="source-title">{data.source.title}</span>
            <span className="source-sub">{data.source.sub}</span>
          </span>
          <span className="source-open">Открыть</span>
        </button>
      )}

      {sourceOpen && <SourcePanel inline mode={mode} onClose={onCloseSource} />}
    </div>
  )
}

function NoAnswer({ data, onReset }) {
  return (
    <div className="answer">
      <p className="answer-by">Frodo</p>
      <h3 className="answer-title">{data.title}</h3>
      <p>{data.paragraphs[0]}</p>
      <button type="button" className="btn-soft" onClick={onReset}>
        {data.action}
      </button>
    </div>
  )
}

export default function ChatPage() {
  const { format } = useFormat()
  const [messages, setMessages] = useState([])
  const [searching, setSearching] = useState(false)
  const [sourceOpen, setSourceOpen] = useState(false)
  const [chatId, setChatId] = useState(0)
  const timerRef = useRef(null)
  const scrollRef = useRef(null)

  useEffect(() => () => clearTimeout(timerRef.current), [])

  useEffect(() => {
    const node = scrollRef.current
    if (node) node.scrollTop = node.scrollHeight
  }, [messages])

  function ask(text) {
    if (searching) return

    const id = Date.now()
    setSourceOpen(false)
    setSearching(true)
    setMessages((prev) => [...prev, { id, question: text, status: 'searching', mode: format }])

    timerRef.current = setTimeout(() => {
      const answerKey = /видеопамят|памят|требован|rag|стенд|nvidia/i.test(text) ? 'memory' : 'none'
      setMessages((prev) => prev.map((item) => (item.id === id ? { ...item, status: 'done', answerKey } : item)))
      setSearching(false)
    }, 1200)
  }

  function reset() {
    clearTimeout(timerRef.current)
    setMessages([])
    setSearching(false)
    setSourceOpen(false)
    setChatId((value) => value + 1)
  }

  const activeMode = messages.length ? messages[messages.length - 1].mode : format

  return (
    <div className={sourceOpen ? 'chat-layout is-split' : 'chat-layout'}>
      <div className="chat-column">
        <Topbar title="Чат с наставником">
          <span className="lab-badge">ЛР 01 · Сборка RAG / {FORMAT_LABELS[format]}</span>
          <button type="button" className="btn-outline" onClick={reset}>
            Новый чат
          </button>
        </Topbar>

        <div className="chat-scroll" ref={scrollRef}>
          {messages.length === 0 ? (
            <EmptyState onAsk={ask} />
          ) : (
            <div className="thread">
              {messages.map((message, index) => (
                <article className="msg" key={message.id}>
                  <p className="msg-label">Твой вопрос</p>
                  <p className="msg-question">{message.question}</p>
                  <hr className="rule" />

                  {message.status === 'searching' && (
                    <div className="answer">
                      <p className="answer-by">Frodo</p>
                      <h3 className="answer-title">Ищу ответ в методичке…</h3>
                    </div>
                  )}

                  {message.status === 'done' && message.answerKey === 'memory' && (
                    <Answer
                      data={answers.memory[message.mode ?? 'full']}
                      mode={message.mode ?? 'full'}
                      sourceOpen={sourceOpen && index === messages.length - 1}
                      onOpenSource={() => setSourceOpen(true)}
                      onCloseSource={() => setSourceOpen(false)}
                    />
                  )}

                  {message.status === 'done' && message.answerKey === 'none' && (
                    <NoAnswer data={answers.none} onReset={reset} />
                  )}
                </article>
              ))}
            </div>
          )}
        </div>

        <Composer key={chatId} onSend={ask} busy={searching} />
      </div>

      {sourceOpen && <SourcePanel mode={activeMode} onClose={() => setSourceOpen(false)} />}
    </div>
  )
}