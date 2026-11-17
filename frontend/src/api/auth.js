import { apiFetch, removeToken, setToken } from './client.js'

/**
 * Получение профиля текущего авторизованного пользователя.
 */
export async function getMe(token = null) {
  return await apiFetch('/api/auth/me', {
    method: 'GET',
    token,
  })
}

/**
 * Быстрый демо-вход для смены ролей (student / instructor).
 */
export async function demoLogin(role = 'student') {
  const data = await apiFetch('/api/auth/demo-login', {
    method: 'POST',
    body: { role },
  })

  if (data?.token) {
    setToken(data.token)
  }

  return data
}

/**
 * Завершение сессии пользователя.
 */
export async function logout() {
  removeToken()
  return { success: true }
}
