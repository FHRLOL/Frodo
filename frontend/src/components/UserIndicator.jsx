import { useAuth } from '../context/AuthContext.jsx'

export default function UserIndicator({ compact = false }) {
  const { user, role, isDemoAuth, demoSwitchRole } = useAuth()

  const displayName = user?.name || (role === 'instructor' ? 'Преподаватель' : 'Студент')
  const roleLabel = role === 'instructor' ? 'Преподаватель' : 'Студент'

  return (
    <div className={`user-indicator ${compact ? 'user-indicator--compact' : ''}`}>
      <div className="user-profile" title={user?.email ? `${displayName} (${user.email})` : displayName}>
        <span className="user-name">{displayName}</span>
        <span className={`user-role-badge user-role-badge--${role || 'guest'}`}>
          {roleLabel}
        </span>
      </div>

      {isDemoAuth && (
        <div className="demo-switcher" aria-label="Демо-переключатель ролей">
          <span className="demo-label">Демо:</span>
          <div className="demo-buttons" role="group" aria-label="Выбор роли для тестирования">
            <button
              type="button"
              className={`demo-btn ${role === 'student' ? 'is-active' : ''}`}
              onClick={() => demoSwitchRole('student')}
              title="Переключиться на роль Студента"
            >
              Студент
            </button>
            <button
              type="button"
              className={`demo-btn ${role === 'instructor' ? 'is-active' : ''}`}
              onClick={() => demoSwitchRole('instructor')}
              title="Переключиться на роль Преподавателя"
            >
              Преподаватель
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
