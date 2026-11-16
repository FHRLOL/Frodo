import { NavLink, Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar.jsx'

export default function Layout() {
  const { pathname } = useLocation()
  const teacher = pathname.startsWith('/teacher')

  return (
    <div className="app">
      <Sidebar teacher={teacher} />
      <div className="main">
        {teacher && (
          <nav className="mobile-tabs" aria-label="Разделы кабинета">
            <NavLink to="/teacher" end>
              Обзор
            </NavLink>
            <NavLink to="/teacher/materials">Материалы</NavLink>
            <NavLink to="/teacher/access">Доступ</NavLink>
            <NavLink to="/">Чат</NavLink>
          </nav>
        )}
        <Outlet />
      </div>
    </div>
  )
}