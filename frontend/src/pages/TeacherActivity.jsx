import { Link } from 'react-router-dom'
import Topbar from '../components/Topbar.jsx'
import { activity } from '../data/mock.js'

export default function TeacherActivity() {
  const maxTopic = Math.max(...activity.topics.map((topic) => topic.value))

  return (
    <>
      <Topbar title="Кабинет преподавателя">
        <span className="demo-note">Демонстрационные данные</span>
      </Topbar>

      <div className="page-scroll">
        <div className="page">
          <h1>Что спрашивают студенты</h1>
          <p className="page-sub">Активность за последние 7 дней</p>

          <div className="stats">
            {activity.stats.map((stat) => (
              <div className="stat" key={stat.label}>
                <span className={stat.tone === 'brown' ? 'stat-num is-brown' : 'stat-num'}>{stat.value}</span>
                <span className="stat-label">{stat.label}</span>
              </div>
            ))}
          </div>

          <div className="split">
            <section className="topics">
              <h2>Популярные темы</h2>
              {activity.topics.map((topic) => (
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
              <p className="card-sub">В методичке не нашлось подходящего фрагмента</p>
              <div className="card-rows">
                {activity.unanswered.map((row) => (
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