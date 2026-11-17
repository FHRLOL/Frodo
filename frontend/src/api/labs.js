import { apiFetch } from './client.js'

/**
 * Получение каталога лабораторных работ.
 */
export async function getLabs() {
  return await apiFetch('/api/labs', { method: 'GET' })
}

/**
 * Получение прогресса по лабораторным работам.
 * Студент получает собственный прогресс, преподаватель может запросить по userId.
 */
export async function getStudentProgress(userId = null) {
  const url = userId ? `/api/student/progress?user_id=${encodeURIComponent(userId)}` : '/api/student/progress'
  return await apiFetch(url, { method: 'GET' })
}
