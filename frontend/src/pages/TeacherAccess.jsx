import { Link } from 'react-router-dom'
import FormatSelect from '../components/FormatSelect.jsx'
import Topbar from '../components/Topbar.jsx'
import { useFormat } from '../context.js'
import { students } from '../data/mock.js'

export default function TeacherAccess() {
  const { format, setFormat } = useFormat()
  const student = students[0]

  return (
    <>
      <Topbar title="Кабинет преподавателя">
        <span className="demo-note">Демонстрационные данные</span>
      </Topbar>

      <div className="page-scroll">
        <div className="page">
          <h1>Доступ студентов</h1>
          <p className="page-sub">Выберите формат ответа для каждого студента и лабораторной.</p>

          <div className="table-card access-table">
            <div className="table-row table-head">
              <span className="col-student">Студент</span>
              <span className="col-lab">ЛР 01 · Сборка RAG</span>
              <span className="col-lab">ЛР 02 · Оценка RAG</span>
            </div>

            <div className="table-row">
              <span className="col-student">
                <strong>{student.name}</strong>
                <em>{student.id}</em>
              </span>
              <span className="col-lab" data-label="ЛР 01 · Сборка RAG">
                <FormatSelect value={format} onChange={setFormat} />
              </span>
              <span className="col-lab" data-label="ЛР 02 · Оценка RAG">
                <span className="static-format">Подсказки</span>
              </span>
            </div>
          </div>

          <h2 className="section-title">Как работает доступ</h2>
          <hr className="rule" />

          <div className="access-note">
            <div className="access-field">
              <span className="field-label">Форматы ответа</span>
              <div className="info-field">Подсказки — следующий шаг. Полный ответ — разбор.</div>
            </div>
            <Link className="btn-green" to="/">
              Посмотреть чат ЛР 01
            </Link>
          </div>
        </div>
      </div>
    </>
  )
}