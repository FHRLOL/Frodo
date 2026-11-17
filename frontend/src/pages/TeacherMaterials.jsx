import { useEffect, useRef, useState } from 'react'
import Topbar from '../components/Topbar.jsx'
import { labs as fallbackLabs, materials as fallbackMaterials } from '../data/mock.js'
import { labsApi, teacherApi } from '../api/index.js'

export default function TeacherMaterials() {
  const [labList, setLabList] = useState(fallbackLabs)
  const [lab, setLab] = useState(fallbackLabs[0].id)
  const [fileName, setFileName] = useState('')
  const [reindexStatus, setReindexStatus] = useState('')
  const [isReindexing, setIsReindexing] = useState(false)
  const [isLive, setIsLive] = useState(false)
  const fileRef = useRef(null)

  useEffect(() => {
    let mounted = true
    labsApi
      .getLabs()
      .then((data) => {
        if (!mounted || !Array.isArray(data) || data.length === 0) return
        setLabList(data)
        setLab(data[0].id)
        setIsLive(true)
      })
      .catch(() => {
        // Фоллбэк на мок
      })

    return () => {
      mounted = false
    }
  }, [])

  async function handleReindex() {
    setIsReindexing(true)
    setReindexStatus('Выполняется индексация базы знаний…')
    try {
      const res = await teacherApi.reindexCourse()
      setReindexStatus(
        res.indexed_chunks !== undefined
          ? `Успешно проиндексировано ${res.indexed_chunks} фрагментов знаний`
          : 'Индексация успешно завершена'
      )
    } catch (err) {
      setReindexStatus(`Ошибка переиндексации: ${err.message}`)
    } finally {
      setIsReindexing(false)
    }
  }

  return (
    <>
      <Topbar title="Кабинет преподавателя">
        <span className="demo-note">
          {isLive ? '🟢 Синхронизировано с FastAPI' : 'Демонстрационные данные'}
        </span>
      </Topbar>

      <div className="page-scroll">
        <div className="page">
          <h1>Материалы курса</h1>
          <p className="page-sub">Документы, по которым Frodo отвечает студентам</p>

          <div className="table-card">
            <div className="table-row table-head">
              <span className="col-name">Документ</span>
              <span className="col-format">Формат</span>
              <span className="col-status">Статус</span>
            </div>

            {fallbackMaterials.map((item) => (
              <div className="table-row" key={item.title}>
                <span className="col-name">
                  <strong>{item.title}</strong>
                  <em>{item.file}</em>
                </span>
                <span className="col-format">{item.format}</span>
                <span className="col-status status-ok">{item.status}</span>
              </div>
            ))}
          </div>

          <h2 className="section-title">Загрузка и переиндексация базы знаний</h2>
          <hr className="rule" />

          <div className="upload">
            <label className="field-label" htmlFor="lab-select">
              Лабораторная работа
            </label>
            <div className="upload-row">
              <select id="lab-select" className="select" value={lab} onChange={(event) => setLab(event.target.value)}>
                {labList.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.title}
                  </option>
                ))}
              </select>

              <button type="button" className="btn-green" onClick={() => fileRef.current?.click()}>
                + Выбрать файл
              </button>
              <input
                ref={fileRef}
                type="file"
                className="visually-hidden"
                accept=".md,.txt,.pdf,.docx"
                onChange={(event) => setFileName(event.target.files?.[0]?.name ?? '')}
              />

              <button
                type="button"
                className="btn-outline"
                disabled={isReindexing}
                onClick={handleReindex}
              >
                {isReindexing ? 'Индексация…' : '🔄 Переиндексировать RAG'}
              </button>
            </div>
            {fileName && <p className="file-note">Выбран файл: {fileName}</p>}
            {reindexStatus && (
              <p
                className="file-note"
                style={{
                  color: reindexStatus.startsWith('Ошибка') ? '#c0392b' : 'var(--color-primary, #263c35)',
                  fontWeight: 500,
                  marginTop: '8px',
                }}
              >
                {reindexStatus}
              </p>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
