import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

export default function RoleGuard({ allowedRoles = ['instructor'], children }) {
  const { role, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="role-guard-loading" aria-live="polite">
        <span>Проверка прав доступа...</span>
      </div>
    )
  }

  const isAllowed = role && (Array.isArray(allowedRoles) ? allowedRoles.includes(role) : role === allowedRoles)

  if (!isAllowed) {
    return (
      <Navigate
        to="/"
        replace
        state={{
          accessDenied: true,
          requiredRole: allowedRoles,
          from: location.pathname,
        }}
      />
    )
  }

  return children
}
