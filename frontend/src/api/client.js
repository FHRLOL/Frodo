const TOKEN_STORAGE_KEY = 'frodo_token'

/**
 * Извлекает токен авторизации из localStorage или cookie frodo_token.
 */
export function getToken() {
  if (typeof window === 'undefined') return null

  // 1. Поиск в localStorage
  try {
    const localToken = window.localStorage?.getItem(TOKEN_STORAGE_KEY)
    if (localToken) return localToken
  } catch {
    // В некоторых окружениях доступ к localStorage может быть заблокирован
  }

  // 2. Поиск в cookies
  try {
    const match = document.cookie?.match(new RegExp(`(?:^|; )${TOKEN_STORAGE_KEY}=([^;]*)`))
    if (match) return decodeURIComponent(match[1])
  } catch {
    // Ошибки чтения cookie
  }

  return null
}

/**
 * Сохраняет токен авторизации в localStorage и cookie.
 */
export function setToken(token) {
  if (typeof window === 'undefined') return

  try {
    if (token) {
      window.localStorage?.setItem(TOKEN_STORAGE_KEY, token)
      document.cookie = `${TOKEN_STORAGE_KEY}=${encodeURIComponent(token)}; path=/; max-age=86400; SameSite=Lax`
    } else {
      removeToken()
    }
  } catch {
    // Безопасный перехват
  }
}

/**
 * Удаляет токен авторизации из хранилищ.
 */
export function removeToken() {
  if (typeof window === 'undefined') return

  try {
    window.localStorage?.removeItem(TOKEN_STORAGE_KEY)
    document.cookie = `${TOKEN_STORAGE_KEY}=; path=/; max-age=0; SameSite=Lax`
  } catch {
    // Безопасный перехват
  }
}

/**
 * Базовый HTTP-клиент с автоматическим добавлением Bearer токена и обработкой 401.
 */
export async function apiFetch(endpoint, options = {}) {
  const { headers = {}, body, token: customToken, ...customOptions } = options

  const token = customToken || getToken()

  const finalHeaders = {
    Accept: 'application/json',
    ...headers,
  }

  if (token && !finalHeaders['Authorization']) {
    finalHeaders['Authorization'] = `Bearer ${token}`
  }

  let finalBody = body
  if (body && typeof body === 'object' && !(body instanceof FormData) && !(body instanceof Blob)) {
    finalHeaders['Content-Type'] = 'application/json'
    finalBody = JSON.stringify(body)
  }

  const url = endpoint.startsWith('http')
    ? endpoint
    : endpoint.startsWith('/')
      ? endpoint
      : `/api/${endpoint}`

  const response = await fetch(url, {
    ...customOptions,
    headers: finalHeaders,
    body: finalBody,
  })

  if (response.status === 401) {
    removeToken()
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('frodo:unauthorized', { detail: { status: 401 } }))
    }

    let errorDetail = 'Необходима авторизация'
    try {
      const errJson = await response.json()
      errorDetail = errJson.detail || errorDetail
    } catch {
      // Игнорируем ошибки парсинга ответа ошибки
    }
    const err = new Error(errorDetail)
    err.status = 401
    throw err
  }

  if (!response.ok) {
    let errorDetail = `Ошибка запроса (${response.status})`
    try {
      const errJson = await response.json()
      errorDetail = errJson.detail || errorDetail
    } catch {
      // Игнорируем ошибки парсинга ответа ошибки
    }
    const err = new Error(errorDetail)
    err.status = response.status
    throw err
  }

  if (response.status === 204) {
    return null
  }

  const contentType = response.headers.get('content-type')
  if (contentType && contentType.includes('application/json')) {
    return await response.json()
  }

  return await response.text()
}

export const apiClient = {
  get: (endpoint, options = {}) => apiFetch(endpoint, { ...options, method: 'GET' }),
  post: (endpoint, body, options = {}) => apiFetch(endpoint, { ...options, method: 'POST', body }),
  put: (endpoint, body, options = {}) => apiFetch(endpoint, { ...options, method: 'PUT', body }),
  delete: (endpoint, options = {}) => apiFetch(endpoint, { ...options, method: 'DELETE' }),
  request: apiFetch,
}
