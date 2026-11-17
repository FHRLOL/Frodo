import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import FormatSelect from '../components/FormatSelect.jsx'
import Topbar from '../components/Topbar.jsx'
import { useFormat } from '../context.js'
import { teacherApi, labsApi } from '../api/index.js'
import { students as fallbackStudents } from '../data/mock.js'

export default function TeacherAccess() {
  const { format, setFormat } = useFormat()
  const [studentList, setStudentList] = useState(fallbackStudents)
  const [labsList, setLabsList] = useState([])
  const [saveStatus, setSaveStatus] = useState('')
  const [isLive, setIsLive] = useState(false)

  useEffect(() => {
    let mounted = true

    Promise.allSettled([teacherApi.getStudentsMatrix(), labsApi.getLabs()]).then(
      ([matrixRes, labsRes]) => {
        if (!mounted) return

        if (labsRes.status === 'fulfilled' && Array.isArray(labsRes.value)) {
          setLabsList(labsRes.value)
        }

        if (matrixRes.status === 'fulfilled' && Array.isArray(matrixRes.value) && matrixRes.value.length > 0) {
          const mapped = matrixRes.value.map((item) => {
            const lab1 = item.labs?.find((l) => l.lab_id === 1) || item.labs?.[0]
            const isPassed = lab1?.status === 'passed'
            return {
              id: item.user_id,
              moodle_id: item.moodle_user_id,
              name: item.name,
              format: isPassed ? 'full' : 'hints',
              labs: item.labs || [],
            }
          })
          setStudentList(mapped)
          setIsLive(true)
        }
      }
    )

    return () => {
      mounted = false
    }
  }, [])

  async function handleFormatChange(studentId, newFormat) {
    // Обновляем локально
    setStudentList((prev) =>
      prev.map((s) => (s.id === studentId ? { ...s, format: newFormat } : s))
    )
    setFormat(newFormat)

    // Персистим в SQLite через API бэкенда
    const newStatus = newFormat === 'full' ? 'passed' : 'in_progress'
    const student = studentList.find((s) => s.id === studentId)
    const currentGrade = student?.labs?.[0]?.grade ?? (newFormat === 'full' ? 100.0 : 45.0)

    try {
      setSaveStatus('Сохранение…')
      await teacherApi.updateStudentProgress(studentId, 1, newStatus, currentGrade)
      setSaveStatus('Сохранено в SQLite')
      setTimeout(() => setSaveStatus(''), 2500)
    } catch {
      setSaveStatus('Локально изменено')
      setTimeout(() => setSaveStatus(''), 2000)
    }
  }

  const primaryStudent = studentList[0] || fallbackStudents[0]

  return (
    <>
      <Topbar title="Кабинет преподавателя">
        <span className="demo-note">
          {isLive ? '🟢 Синхронизировано с SQLite' : 'Демонстрационные данные'}
        </span>
      </Topbar>

      <div className="page-scroll">
        <div className="page">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <h1>Доступ студентов</h1>
              <p className="page-sub">Выберите формат ответа для каждого студента и лабораторной.</p>
            </div>
            {saveStatus && (
              <span
                style={{
                  padding: '4px 10px',
                  borderRadius: '12px',
                  fontSize: '12px',
                  background: 'var(--color-badge-green, #e5eee7)',
                  color: 'var(--color-primary, #263c35)',
                }}
              >
                {saveStatus}
              </span>
            )}
          </div>

          <div className="table-card access-table">
            <div className="table-row table-head">
              <span className="col-student">Студент</span>
              <span className="col-lab">
                {labsList[0]?.title ? `ЛР 01 · ${labsList[0].title}` : 'ЛР 01 · Сборка RAG'}
              </span>
              <span className="col-lab">
                {labsList[1]?.title ? `ЛР 02 · ${labsList[1].title}` : 'ЛР 02 · Оценка RAG'}
              </span>
            </div>

            {studentList.map((st) => (
              <div className="table-row" key={st.id || st.moodle_id || st.name}>
                <span className="col-student">
                  <strong>{st.name}</strong>
                  <em>{st.moodle_id || st.id}</em>
                </span>
                <span className="col-lab" data-label="ЛР 01">
                  <FormatSelect
                    value={st.id === primaryStudent.id ? format : st.format}
                    onChange={(val) => handleFormatChange(st.id, val)}
                  />
                </span>
                <span className="col-lab" data-label="ЛР 02">
                  <span className="static-format">Подсказки</span>
                </span>
              </div>
            ))}
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
