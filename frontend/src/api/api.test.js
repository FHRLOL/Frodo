import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiFetch, getToken, removeToken, setToken } from './client.js'
import { demoLogin, getMe, logout } from './auth.js'
import { getLabs, getStudentProgress } from './labs.js'
import { getStudentsMatrix, getUnanswered, reindexCourse, updateStudentProgress } from './teacher.js'
import { querySync, streamQuery } from './chat.js'

describe('API Client & Auth/Labs/Teacher Endpoints', () => {
  beforeEach(() => {
    localStorage.clear()
    document.cookie = 'frodo_token=; max-age=0'
    vi.restoreAllMocks()
  })

  it('сохраняет, извлекает и удаляет токен из localStorage и cookies', () => {
    expect(getToken()).toBeNull()

    setToken('jwt-abc-123')
    expect(getToken()).toBe('jwt-abc-123')
    expect(localStorage.getItem('frodo_token')).toBe('jwt-abc-123')

    removeToken()
    expect(getToken()).toBeNull()
    expect(localStorage.getItem('frodo_token')).toBeNull()
  })

  it('apiFetch добавляет Bearer токен в заголовок Authorization', async () => {
    setToken('token-test-456')

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ id: 42, role: 'student' }),
    })
    globalThis.fetch = mockFetch

    const data = await apiFetch('/api/auth/me')

    expect(data).toEqual({ id: 42, role: 'student' })
    expect(mockFetch).toHaveBeenCalledWith('/api/auth/me', expect.objectContaining({
      headers: expect.objectContaining({
        Authorization: 'Bearer token-test-456',
      }),
    }))
  })

  it('apiFetch очищает токен и генерирует событие при 401 Unauthorized', async () => {
    setToken('expired-token')
    const eventSpy = vi.fn()
    window.addEventListener('frodo:unauthorized', eventSpy)

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'JWT expired' }),
    })

    await expect(apiFetch('/api/auth/me')).rejects.toThrow('JWT expired')
    expect(getToken()).toBeNull()
    expect(eventSpy).toHaveBeenCalled()

    window.removeEventListener('frodo:unauthorized', eventSpy)
  })

  it('auth.js: getMe, demoLogin, logout', async () => {
    globalThis.fetch = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ id: 1, role: 'instructor' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ status: 'success', token: 'demo-token-123', user: { role: 'student' } }),
      })

    const me = await getMe('token-1')
    expect(me.role).toBe('instructor')

    const loginRes = await demoLogin('student')
    expect(loginRes.token).toBe('demo-token-123')
    expect(getToken()).toBe('demo-token-123')

    const logoutRes = await logout()
    expect(logoutRes.success).toBe(true)
    expect(getToken()).toBeNull()
  })

  it('labs.js: getLabs и getStudentProgress', async () => {
    const mockFetch = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => [{ id: 1, title: 'ЛР 01' }],
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => [{ lab_id: 1, status: 'passed' }],
      })
    globalThis.fetch = mockFetch

    const labs = await getLabs()
    expect(labs[0].title).toBe('ЛР 01')

    const progress = await getStudentProgress(42)
    expect(progress[0].status).toBe('passed')
    expect(mockFetch).toHaveBeenLastCalledWith(
      '/api/student/progress?user_id=42',
      expect.anything(),
    )
  })

  it('teacher.js: getStudentsMatrix, updateStudentProgress, getUnanswered, reindexCourse', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ status: 'success' }),
    })
    globalThis.fetch = mockFetch

    await getStudentsMatrix()
    expect(mockFetch).toHaveBeenCalledWith('/api/admin/students', expect.anything())

    await updateStudentProgress(42, 1, 'passed', 5)
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/admin/student/progress',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ user_id: 42, lab_id: 1, status: 'passed', grade: 5 }),
      }),
    )

    await getUnanswered(20, 10)
    expect(mockFetch).toHaveBeenCalledWith('/api/admin/unanswered?limit=20&offset=10', expect.anything())

    await reindexCourse()
    expect(mockFetch).toHaveBeenCalledWith('/api/reindex', expect.objectContaining({ method: 'POST' }))
  })

  it('chat.js: querySync отправляет вопрос и lab_id', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ answer: 'Тестовый ответ' }),
    })

    const res = await querySync('Как запустить?', 1, 'test-jwt')
    expect(res.answer).toBe('Тестовый ответ')
  })

  it('chat.js: streamQuery парсит Server-Sent Events', async () => {
    const encoder = new TextEncoder()
    const sseChunks = [
      'event: meta\ndata: {"mode":"socratic"}\n\n',
      'event: token\ndata: {"token":"Привет"}\n\n',
      'event: done\ndata: {"status":"complete"}\n\n',
    ]

    let chunkIndex = 0
    const stream = new ReadableStream({
      pull(controller) {
        if (chunkIndex < sseChunks.length) {
          controller.enqueue(encoder.encode(sseChunks[chunkIndex++]))
        } else {
          controller.close()
        }
      },
    })

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: stream,
    })

    const events = []
    const onDone = vi.fn()

    await new Promise((resolve) => {
      streamQuery('Тестовый вопрос', 1, 'tok', (event, data) => {
        events.push({ event, data })
      }, null, (data) => {
        onDone(data)
        resolve()
      })
    })

    expect(events.length).toBe(3)
    expect(events[0].event).toBe('meta')
    expect(events[1].event).toBe('token')
    expect(events[1].data).toEqual({ token: 'Привет' })
    expect(onDone).toHaveBeenCalledWith(expect.objectContaining({ status: 'complete' }))
  })
})
