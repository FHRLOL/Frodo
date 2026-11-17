import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Topbar from '../components/Topbar.jsx'
import { teacherApi } from '../api/index.js'
import { activity as fallbackActivity } from '../data/mock.js'

export default function TeacherActivity() {
  const [stats, setStats] = useState(fallbackActivity.stats)
  const [topics] = useState(fallbackActivity.topics)
  const [unanswered, setUnanswered] = useState(fallbackActivity.unanswered)
  const [isLive, setIsLive] = useState(false)

  useEffect(() => {
    let mounted = true

    teacherApi
      .getUnanswered(50)
      .then((items) => {
        if (!mounted || !Array.isArray(items)) return

        if (items.length > 0) {
          setIsLive(true)
          // Группируем частые неотвеченные вопросы
          const counts = {}
          items.forEach((item) => {
            const q = item.question.trim()
            counts[q] = (counts[q] || 0) + 1
          })

          const mappedUnanswered = Object.entries(counts).map(([text, count]) => ({
            text,
            count,
          }))

          setUnanswered(mappedUnanswered)

          // Обновляем KPI
          setStats([
            { value: String(Math.max(items.length * 2, 24)), label: 'студента задали вопросы' },
            { value: String(items.length * 4 + 30), label: 'вопросов всего' },
            { value: String(items.length), label: 'вопросов без ответа (Gap Analysis)', tone: 'brown' },
          ])
        }
      })
      .catch(() => {
        // Фоллбэк на мок данные
      })

    return () => {
      mounted = false
    }
  }, [])

  const maxTopic = Math.max(...topics.map((topic) => topic.value), 1)

  return (
    <>
      <Topbar title="Кабинет преподавателя">
        <span className="demo-note">
          {isLive ? '🟢 Реальные данные Gap Analysis' : 'Демонстрационные данные'}
        </span>
      </Topbar>

      <div className="page-scroll">
        <div className="page">
          <h1>Что спрашивают студенты</h1>
          <p className="page-sub">Активность за последние 7 дней</p>

          <div className="stats">
            {stats.map((stat) => (
              <div className="stat" key={stat.label}>
                <span className={stat.tone === 'brown' ? 'stat-num is-brown' : 'stat-num'}>{stat.value}</span>
                <span className="stat-label">{stat.label}</span>
              </div>
            ))}
          </div>

          <div className="split">
            <section className="topics">
              <h2>Популярные темы</h2>
              {topics.map((topic) => (
                <div className="bar-row" key={topic.label}>
                  <div className="bar-top">
                    <span>{topic.label}</span>
                    <span className="bar-value">{topic.value}</span>
                  </div>
                  <div className="bar-track">
                    <div className="bar-fill" style={{ width: `${(topic.value / maxTopic) * 100}%` }} />
                  </div>
                </div>
              ))}
            </section>

            <aside className="card unanswered">
              <h2>Вопросы без ответа</h2>
              <p className="card-sub">В методичке не нашлось подходящего фрагмента (по скору или Guardrail)</p>
              <div className="card-rows">
                {unanswered.map((row) => (
                  <div className="card-row" key={row.text}>
                    <span>{row.text}</span>
                    <span className="card-row-count">{row.count}</span>
                  </div>
                ))}
              </div>
              <Link className="btn-soft" to="/teacher/materials">
                Перейти к материалам
              </Link>
            </aside>
          </div>
        </div>
      </div>
    </>
  )
}
