import { Link, NavLink } from 'react-router-dom'
import Logo from './Logo.jsx'

function navClass({ isActive }) {
  return isActive ? 'nav-link is-active' : 'nav-link'
}

export default function Sidebar({ teacher }) {
  return (
    <aside className="sidebar">
      <Logo />

      <p className="side-role">{teacher ? 'Преподаватель' : 'Учебный курс'}</p>
      <p className="side-course">Локальные LLM и RAG</p>

      <nav className="side-nav" aria-label="Навигация">
        {teacher ? (
          <>
            <NavLink to="/teacher" end className={navClass}>
              Обзор
            </NavLink>
            <NavLink to="/teacher/materials" className={navClass}>
              Материалы курса
            </NavLink>
            <NavLink to="/teacher/access" className={navClass}>
              Доступ студентов
            </NavLink>
          </>
        ) : (
          <NavLink to="/" end className={navClass}>
            Чат с наставником
          </NavLink>
        )}
      </nav>

      <div className="side-foot">
        {teacher ? (
          <Link to="/">К чату студента</Link>
        ) : (
          <Link to="/teacher">Кабинет преподавателя</Link>
        )}
      </div>
    </aside>
  )
}