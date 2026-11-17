// oxlint-disable react/only-export-components
// oxlint-disable react/set-state-in-effect
import { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react'
import { getMe, demoLogin, logout as apiLogout } from '../api/auth.js'
import { getToken, setToken as saveToken, removeToken as clearToken } from '../api/client.js'

export const DEMO_USERS = {
  student: {
    id: 42,
    moodle_id: 'student_42',
    name: 'Алексей Иванов',
    email: 'student_42@university.edu',
    role: 'student',
  },
  instructor: {
    id: 1,
    moodle_id: 'instructor_1',
    name: 'Проф. Смирнов А.В.',
    email: 'instructor_1@university.edu',
    role: 'instructor',
  },
}

export const AuthContext = createContext({
  user: null,
  token: null,
  role: null, // 'student' | 'instructor'
  isLoading: false,
  isDemoAuth: false,
  login: async () => {},
  logout: async () => {},
  demoSwitchRole: async () => {},
})

export function useAuth() {
  return useContext(AuthContext)
}

export function AuthProvider({ children, initialAuth = null }) {
  const isDemoAuth = import.meta.env.VITE_DEMO_AUTH === 'true'

  const [token, setTokenState] = useState(() => {
    if (initialAuth?.token !== undefined) return initialAuth.token
    if (typeof window === 'undefined') return null

    // 1. Проверяем URL query параметры (?token=...)
    try {
      const urlParams = new URLSearchParams(window.location.search)
      const urlToken = urlParams.get('token')
      if (urlToken) {
        saveToken(urlToken)
        urlParams.delete('token')
        const newSearch = urlParams.toString()
        const newUrl = window.location.pathname + (newSearch ? `?${newSearch}` : '') + window.location.hash
        window.history.replaceState({}, document.title, newUrl)
        return urlToken
      }
    } catch {
      // Игнорируем ошибки доступа к window
    }

    // 2. Проверяем localStorage / cookie
    const storedToken = getToken()
    if (storedToken) return storedToken

    return null
  })

  const [role, setRole] = useState(() => {
    if (initialAuth?.role !== undefined) return initialAuth.role
    if (initialAuth?.user?.role) return initialAuth.user.role
    if (typeof window !== 'undefined') {
      const savedRole = window.localStorage?.getItem('frodo_demo_role')
      if (savedRole && (savedRole === 'student' || savedRole === 'instructor')) {
        return savedRole
      }
    }
    return isDemoAuth ? 'instructor' : null
  })

  const [user, setUser] = useState(() => {
    if (initialAuth?.user !== undefined) return initialAuth.user
    if (isDemoAuth) {
      const fallbackRole = (initialAuth?.role !== undefined ? initialAuth.role : null) || (typeof window !== 'undefined' && window.localStorage?.getItem('frodo_demo_role')) || 'instructor'
      return DEMO_USERS[fallbackRole] || null
    }
    return null
  })

  const [isLoading, setIsLoading] = useState(() => {
    if (initialAuth?.isLoading !== undefined) return initialAuth.isLoading
    return !!token && !initialAuth?.user
  })

  // Валидация сессии при наличии токена
  const validateSession = useCallback(async (tokenToVerify) => {
    if (!tokenToVerify) {
      setIsLoading(false)
      return
    }

    setIsLoading(true)
    try {
      const profile = await getMe(tokenToVerify)
      setUser(profile)
      setRole(profile.role)
      if (typeof window !== 'undefined') {
        window.localStorage?.setItem('frodo_demo_role', profile.role)
      }
    } catch (err) {
      if (err.status === 401) {
        clearToken()
        setTokenState(null)
        setUser(null)
        setRole(null)
      } else if (isDemoAuth) {
        const fallbackRole = role || 'instructor'
        setUser(DEMO_USERS[fallbackRole])
        setRole(fallbackRole)
      }
    } finally {
      setIsLoading(false)
    }
  }, [isDemoAuth, role])

  useEffect(() => {
    if (initialAuth) return

    if (token) {
      validateSession(token)
    }
  }, [token, initialAuth, validateSession])

  const login = useCallback(async (newToken) => {
    saveToken(newToken)
    setTokenState(newToken)
    await validateSession(newToken)
  }, [validateSession])

  const logout = useCallback(async () => {
    await apiLogout()
    clearToken()
    setTokenState(null)
    setUser(null)
    setRole(null)
    if (typeof window !== 'undefined') {
      window.localStorage?.removeItem('frodo_demo_role')
    }
  }, [])

  const demoSwitchRole = useCallback(async (targetRole) => {
    if (!isDemoAuth) {
      console.warn('Демо-переключение ролей отключено настройкой VITE_DEMO_AUTH')
      return
    }

    const safeRole = targetRole === 'instructor' ? 'instructor' : 'student'

    try {
      const res = await demoLogin(safeRole)
      if (res?.token) {
        setTokenState(res.token)
        saveToken(res.token)
      }
      if (res?.user) {
        setUser(res.user)
        setRole(res.user.role)
      } else {
        setUser(DEMO_USERS[safeRole])
        setRole(safeRole)
      }
    } catch {
      setUser(DEMO_USERS[safeRole])
      setRole(safeRole)
    }

    if (typeof window !== 'undefined') {
      window.localStorage?.setItem('frodo_demo_role', safeRole)
    }
  }, [isDemoAuth])

  const contextValue = useMemo(() => ({
    user,
    token,
    role,
    isLoading,
    isDemoAuth,
    login,
    logout,
    demoSwitchRole,
  }), [user, token, role, isLoading, isDemoAuth, login, logout, demoSwitchRole])

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  )
}

export default AuthProvider
