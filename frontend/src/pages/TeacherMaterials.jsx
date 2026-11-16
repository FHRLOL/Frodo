import { useRef, useState } from 'react'
import Topbar from '../components/Topbar.jsx'
import { labs, materials } from '../data/mock.js'

export default function TeacherMaterials() {
  const [lab, setLab] = useState(labs[0].id)
  const [fileName, setFileName] = useState('')
  const fileRef = useRef(null)

  return (
    <>
      <Topbar title="Кабинет преподавателя">
        <span className="demo-note">Демонстрационные данные</span>
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

            {materials.map((item) => (
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

          <h2 className="section-title">Загрузка материала</h2>
          <hr className="rule" />

          <div className="upload">
            <label className="field-label" htmlFor="lab-select">
              Лабораторная работа
            </label>
            <div className="upload-row">
              <select id="lab-select" className="select" value={lab} onChange={(event) => setLab(event.target.value)}>
                {labs.map((item) => (
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
            </div>
            {fileName && <p className="file-note">Выбран файл: {fileName}</p>}
          </div>
        </div>
      </div>
    </>
  )
}