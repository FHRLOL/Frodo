import { apiFetch, getToken } from './client.js'

/**
 * Синхронный запрос к ИИ-наставнику (/api/query).
 */
export async function querySync(question, labId = null, token = null) {
  const authToken = token || getToken()
  return await apiFetch('/api/query', {
    method: 'POST',
    token: authToken,
    body: {
      question,
      lab_id: labId ? Number(labId) : null,
      token: authToken,
    },
  })
}

/**
 * Потоковый запрос к ИИ-наставнику через Server-Sent Events (/api/query/stream).
 * Поддерживает обработку событий meta, token, citation, done.
 *
 * @param {string} question Вопрос пользователя
 * @param {number|null} labId ID лабораторной работы
 * @param {string|null} token JWT токен
 * @param {function} onEvent Обработчик входящих событий SSE
 * @param {function} onError Обработчик ошибок
 * @param {function} onDone Обработчик завершения стрима
 * @returns {AbortController} Контроллер для прерывания запроса
 */
export function streamQuery(question, labId = null, token = null, onEvent = null, onError = null, onDone = null) {
  const controller = new AbortController()
  const authToken = token || getToken()

  const headers = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
  }

  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`
  }

  const payloadBody = JSON.stringify({
    question,
    lab_id: labId ? Number(labId) : null,
    token: authToken,
  })

  ;(async () => {
    let doneCalled = false
    try {
      const response = await fetch('/api/query/stream', {
        method: 'POST',
        headers,
        body: payloadBody,
        signal: controller.signal,
      })

      if (!response.ok) {
        let errDetail = `HTTP ${response.status}`
        try {
          const errJson = await response.json()
          errDetail = errJson.detail || errDetail
        } catch {
          // Игнорируем ошибку парсинга
        }
        throw new Error(errDetail)
      }

      if (!response.body) {
        throw new Error('Ответ сервера не содержит потока данных')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        // Оставляем незавершенный кусок в буфере
        buffer = parts.pop() || ''

        for (const part of parts) {
          if (!part.trim()) continue

          let eventType = 'message'
          let eventDataRaw = ''

          const lines = part.split('\n')
          for (const line of lines) {
            if (line.startsWith('event:')) {
              eventType = line.slice(6).trim()
            } else if (line.startsWith('data:')) {
              const dataVal = line.slice(5).trim()
              eventDataRaw = eventDataRaw ? `${eventDataRaw}\n${dataVal}` : dataVal
            }
          }

          let eventData = eventDataRaw
          try {
            eventData = JSON.parse(eventDataRaw)
          } catch {
            // Оставляем сырой строкой
          }

          if (eventType === 'done') {
            doneCalled = true
          }

          if (typeof onEvent === 'function') {
            if (onEvent.length >= 2) {
              onEvent(eventType, eventData)
            } else {
              onEvent({ event: eventType, data: eventData })
            }
          }

          if (eventType === 'done' && typeof onDone === 'function') {
            onDone(eventData)
          }
        }
      }

      // Если в конце буфера остался полный блок
      if (buffer.trim()) {
        let eventType = 'message'
        let eventDataRaw = ''
        const lines = buffer.split('\n')
        for (const line of lines) {
          if (line.startsWith('event:')) {
            eventType = line.slice(6).trim()
          } else if (line.startsWith('data:')) {
            const dataVal = line.slice(5).trim()
            eventDataRaw = eventDataRaw ? `${eventDataRaw}\n${dataVal}` : dataVal
          }
        }
        let eventData = eventDataRaw
        try {
          eventData = JSON.parse(eventDataRaw)
        } catch {
          // Оставляем сырой строкой
        }
        if (typeof onEvent === 'function') {
          if (onEvent.length >= 2) {
            onEvent(eventType, eventData)
          } else {
            onEvent({ event: eventType, data: eventData })
          }
        }
        if (eventType === 'done') {
          doneCalled = true
          if (typeof onDone === 'function') onDone(eventData)
        }
      }

      if (!doneCalled && typeof onDone === 'function') {
        onDone()
      }
    } catch (err) {
      if (err.name !== 'AbortError' && typeof onError === 'function') {
        onError(err)
      }
    }
  })()

  return controller
}
