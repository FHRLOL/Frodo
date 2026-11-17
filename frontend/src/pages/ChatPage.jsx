import { useEffect, useRef, useState } from 'react'
import Composer from '../components/Composer.jsx'
import Rich from '../components/Rich.jsx'
import SourcePanel from '../components/SourcePanel.jsx'
import Topbar from '../components/Topbar.jsx'
import { FORMAT_LABELS, useFormat } from '../context.js'
import { useAuth } from '../context/AuthContext.jsx'
import { chatApi, labsApi } from '../api/index.js'
import { courseCard, suggestions, answers } from '../data/mock.js'

function parseAnswerText(rawText) {
  if (!rawText) return { paragraphs: [], code: null, codeCaption: null }

  // Проверка на блок кода markdown ```
  const codeRegex = /```(?:[a-zA-Z0-9_-]+)?\s*([\s\S]*?)```/
  const match = rawText.match(codeRegex)

  let code = null
  let codeCaption = null
  let textWithoutCode = rawText

  if (match) {
    code = match[1].trim()
    codeCaption = 'Пример из базы знаний курса'
    textWithoutCode = rawText.replace(match[0], '').trim()
  }

  const paragraphs = textWithoutCode
    .split(/\n\n+/)
    .map((p) => p.trim())
    .filter(Boolean)

  return { paragraphs: paragraphs.length ? paragraphs : [rawText], code, codeCaption }
}

function EmptyState({ onAsk, labs = [], selectedLabId, onSelectLab }) {
  return (
    <div className="chat-inner">
      <div className="hero">
        <p className="mobile-course">Локальные LLM и RAG</p>
        <h2>Спроси по лабораторной</h2>
        <p className="hero-sub">Frodo найдёт нужное место в методичке и покажет его рядом с ответом.</p>

        {labs.length > 0 && (
          <div className="lab-selector" style={{ margin: '16px 0' }}>
            <label htmlFor="lab-choice" style={{ fontSize: '13px', marginRight: '8px', opacity: 0.8 }}>
              Активная лабораторная:
            </label>
            <select
              id="lab-choice"
              className="select"
              style={{ padding: '6px 12px', fontSize: '13px' }}
              value={selectedLabId || ''}
              onChange={(e) => onSelectLab(Number(e.target.value))}
            >
              {labs.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.title}
                </option>
              ))}
            </select>
          </div>
        )}

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
      <p className="answer-by">
        Frodo {mode === 'master' ? '· Режим Мастера' : '· Сократовский диалог'}
      </p>
      <h3 className="answer-title">{data.title}</h3>

      {data.paragraphs.map((text, idx) => (
        <p key={idx}>
          <Rich text={text} />
        </p>
      ))}

      {data.code && (
        <div className="code-block">
          <code>{data.code}</code>
          {data.codeCaption && <span className="code-caption">{data.codeCaption}</span>}
        </div>
      )}

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

      {sourceOpen && (
        <SourcePanel
          inline
          mode={mode}
          items={data.citationsList}
          title={data.source?.sub}
          docName={data.source?.title}
          onClose={onCloseSource}
        />
      )}
    </div>
  )
}

function NoAnswer({ data, onReset }) {
  return (
    <div className="answer">
      <p className="answer-by">Frodo · Проверка Guardrail</p>
      <h3 className="answer-title">{data.title}</h3>
      <p>{data.paragraphs[0]}</p>
      <button type="button" className="btn-soft" onClick={onReset}>
        {data.action || 'Спросить другой вопрос'}
      </button>
    </div>
  )
}

export default function ChatPage() {
  const { format, setFormat } = useFormat()
  const { token } = useAuth()
  const [labs, setLabs] = useState([])
  const [selectedLabId, setSelectedLabId] = useState(1)
  const [messages, setMessages] = useState([])
  const [searching, setSearching] = useState(false)
  const [sourceOpen, setSourceOpen] = useState(false)
  const [chatId, setChatId] = useState(0)
  const msgSeqRef = useRef(0)

  const abortRef = useRef(null)
  const scrollRef = useRef(null)
  const fallbackTimerRef = useRef(null)

  // Загружаем список реальных лабораторных с бэкенда
  useEffect(() => {
    let mounted = true
    labsApi
      .getLabs()
      .then((data) => {
        if (mounted && Array.isArray(data) && data.length > 0) {
          setLabs(data)
          setSelectedLabId(data[0].id)
        }
      })
      .catch(() => {
        // Фоллбэк: оставляем дефолтную лабу 1
      })
    return () => {
      mounted = false
    }
  }, [])

  useEffect(() => () => {
    if (abortRef.current) abortRef.current.abort()
    clearTimeout(fallbackTimerRef.current)
  }, [])

  useEffect(() => {
    const node = scrollRef.current
    if (node) node.scrollTop = node.scrollHeight
  }, [messages])

  function ask(text) {
    if (searching) return

    const id = ++msgSeqRef.current
    setSourceOpen(false)
    setSearching(true)

    const initialMode = format === 'hints' ? 'socratic' : 'master'
    const newMessage = {
      id,
      question: text,
      status: 'searching',
      mode: initialMode,
      rawAnswer: '',
      answerData: null,
      citationsList: [],
      isRejected: false,
    }

    setMessages((prev) => [...prev, newMessage])

    // Запускаем реальный SSE запрос
    let accumulatedText = ''
    let citationsAcc = []
    let detectedMode = initialMode
    let isRejection = false
    let rejectionReason = ''

    abortRef.current = chatApi.streamQuery(
      text,
      selectedLabId,
      token,
      (eventType, data) => {
        if (eventType === 'meta') {
          if (data?.mode) {
            detectedMode = data.mode
            // Синхронизируем формат с контекстом приложения
            setFormat(data.mode === 'socratic' ? 'hints' : 'full')
          }
          if (data?.status === 'REJECTED_BY_GUARDRAIL') {
            isRejection = true
            rejectionReason = data.reason || 'В предоставленных материалах этого нет'
          }
        } else if (eventType === 'token') {
          const chunk = typeof data === 'object' && data.token !== undefined ? data.token : String(data || '')
          accumulatedText += chunk
          const parsed = parseAnswerText(accumulatedText)

          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === id
                ? {
                    ...msg,
                    status: 'searching',
                    rawAnswer: accumulatedText,
                    mode: detectedMode,
                    answerData: {
                      title: isRejection ? 'В материалах курса ответа нет' : (parsed.paragraphs[0]?.slice(0, 40) || 'Ответ наставника'),
                      paragraphs: parsed.paragraphs,
                      code: parsed.code,
                      codeCaption: parsed.codeCaption,
                      source: citationsAcc[0] ? {
                        ref: citationsAcc[0].ref,
                        title: citationsAcc[0].docName || 'Материалы курса',
                        sub: citationsAcc[0].title || 'Раздел методички',
                      } : null,
                      citationsList: citationsAcc,
                    },
                  }
                : msg
            )
          )
        } else if (eventType === 'citation') {
          const citeObj = {
            ref: `[${citationsAcc.length + 1}] ${data.doc_name || ''}, строки ${data.line_start || ''}–${data.line_end || ''}`,
            title: data.section_title || 'Раздел методички',
            text: data.citation || '',
            docName: data.doc_name || 'Методичка',
            tone: citationsAcc.length === 0 ? 'peach' : 'cool',
          }
          citationsAcc = [...citationsAcc, citeObj]
        } else if (eventType === 'done') {
          finishAnswer(id, accumulatedText, citationsAcc, detectedMode, isRejection, rejectionReason)
        }
      },
      (_err) => {
        // Задержка фоллбэка для плавного отображения состояния поиска
        fallbackTimerRef.current = setTimeout(() => {
          chatApi
            .querySync(text, selectedLabId, token)
            .then((res) => {
              const isRej =
                res.status === 'REJECTED_BY_GUARDRAIL' ||
                (res.answer && res.answer.includes('В предоставленных материалах этого нет'))
              const cites = (res.citations || []).map((cStr, idx) => ({
                ref: `[${idx + 1}]`,
                title: res.top_chunk?.section_title || 'Раздел курса',
                text: cStr,
                docName: res.top_chunk?.doc_name || 'Материалы курса',
                tone: idx === 0 ? 'peach' : 'cool',
              }))

              finishAnswer(id, res.answer, cites, res.mode || detectedMode, isRej, res.reason)
            })
            .catch(() => {
              // Если сервер бэкенда вообще оффлайн — graceful fallback на локальный mock
              const fallbackKey = /видеопамят|памят|требован|rag|стенд|nvidia/i.test(text) ? 'memory' : 'none'
              if (fallbackKey === 'memory') {
                const mockData = answers.memory[format] || answers.memory.full
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === id
                      ? {
                          ...msg,
                          status: 'done',
                          isRejected: false,
                          answerData: mockData,
                          citationsList: [],
                        }
                      : msg
                  )
                )
              } else {
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === id
                      ? {
                          ...msg,
                          status: 'done',
                          isRejected: true,
                          answerData: answers.none,
                        }
                      : msg
                  )
                )
              }
              setSearching(false)
            })
        }, 120)
      },
      () => {
        // onDone
        finishAnswer(id, accumulatedText, citationsAcc, detectedMode, isRejection, rejectionReason)
      }
    )
  }

  function finishAnswer(id, fullText, citationsList, mode, isRejection, rejectionReason) {
    const isActuallyRejected =
      isRejection ||
      !fullText ||
      fullText.includes('В предоставленных материалах этого нет') ||
      fullText.includes('Запрос отклонен')

    const parsed = parseAnswerText(fullText)
    const firstCite = citationsList[0]

    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.id !== id) return msg
        return {
          ...msg,
          status: 'done',
          isRejected: isActuallyRejected,
          mode: mode || msg.mode,
          answerData: isActuallyRejected
            ? {
                title: 'В материалах курса ответа нет',
                paragraphs: [
                  rejectionReason ||
                    'В методичке и материалах курса нет подходящего раздела по данному вопросу. Попробуй переформулировать или уточни у преподавателя.',
                ],
                action: 'Спросить по другому разделу',
              }
            : {
                title: parsed.paragraphs[0]?.slice(0, 48) || 'Ответ наставника',
                paragraphs: parsed.paragraphs,
                code: parsed.code,
                codeCaption: parsed.codeCaption,
                source: firstCite
                  ? {
                      ref: firstCite.ref,
                      title: firstCite.docName,
                      sub: firstCite.title,
                    }
                  : null,
                citationsList,
              },
        }
      })
    )
    setSearching(false)
  }

  function reset() {
    if (abortRef.current) abortRef.current.abort()
    clearTimeout(fallbackTimerRef.current)
    setMessages([])
    setSearching(false)
    setSourceOpen(false)
    setChatId((value) => value + 1)
  }

  const activeMessage = messages.length ? messages[messages.length - 1] : null
  const activeMode = activeMessage?.mode || (format === 'hints' ? 'socratic' : 'master')

  const currentLabTitle =
    labs.find((l) => l.id === selectedLabId)?.title || 'ЛР 01 · Сборка RAG'

  return (
    <div className={sourceOpen ? 'chat-layout is-split' : 'chat-layout'}>
      <div className="chat-column">
        <Topbar title="Чат с наставником">
          <span className="lab-badge">
            {currentLabTitle} / {FORMAT_LABELS[format] || 'Полный ответ'}
          </span>
          <button type="button" className="btn-outline" onClick={reset}>
            Новый чат
          </button>
        </Topbar>

        <div className="chat-scroll" ref={scrollRef}>
          {messages.length === 0 ? (
            <EmptyState
              onAsk={ask}
              labs={labs}
              selectedLabId={selectedLabId}
              onSelectLab={setSelectedLabId}
            />
          ) : (
            <div className="thread">
              {messages.map((message, index) => (
                <article className="msg" key={message.id}>
                  <p className="msg-label">Твой вопрос</p>
                  <p className="msg-question">{message.question}</p>
                  <hr className="rule" />

                  {message.status === 'searching' && !message.answerData && (
                    <div className="answer">
                      <p className="answer-by">Frodo</p>
                      <h3 className="answer-title">Ищу ответ в методичке…</h3>
                    </div>
                  )}

                  {message.answerData && !message.isRejected && (
                    <Answer
                      data={message.answerData}
                      mode={message.mode}
                      sourceOpen={sourceOpen && index === messages.length - 1}
                      onOpenSource={() => setSourceOpen(true)}
                      onCloseSource={() => setSourceOpen(false)}
                    />
                  )}

                  {message.answerData && message.isRejected && (
                    <NoAnswer data={message.answerData} onReset={reset} />
                  )}
                </article>
              ))}
            </div>
          )}
        </div>

        <Composer key={chatId} onSend={ask} busy={searching} />
      </div>

      {sourceOpen && (
        <SourcePanel
          mode={activeMode}
          items={activeMessage?.answerData?.citationsList}
          title={activeMessage?.answerData?.source?.sub}
          docName={activeMessage?.answerData?.source?.title}
          onClose={() => setSourceOpen(false)}
        />
      )}
    </div>
  )
}
