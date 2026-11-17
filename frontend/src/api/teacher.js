import { apiFetch } from './client.js'

/**
 * Получение сводной матрицы успеваемости всех студентов.
 * Доступно только преподавателям.
 */
export async function getStudentsMatrix() {
  return await apiFetch('/api/admin/students', { method: 'GET' })
}

/**
 * Обновление статуса лабораторной работы и оценки студента.
 * Доступно только преподавателям.
 *
 * @param {number} userId ID студента
 * @param {number} labId ID лабораторной работы
 * @param {string} status 'not_started' | 'in_progress' | 'passed'
 * @param {number|null} grade Оценка (например, 2-5 или баллы)
 */
export async function updateStudentProgress(userId, labId, status, grade = null) {
  return await apiFetch('/api/admin/student/progress', {
    method: 'POST',
    body: {
      user_id: Number(userId),
      lab_id: Number(labId),
      status,
      grade: grade !== null && grade !== undefined ? Number(grade) : null,
    },
  })
}

/**
 * Получение списка неотвеченных запросов студентов (Gap Analysis).
 *
 * @param {number} limit Количество записей (по умолчанию 50)
 * @param {number} offset Смещение (по умолчанию 0)
 */
export async function getUnanswered(limit = 50, offset = 0) {
  return await apiFetch(`/api/admin/unanswered?limit=${encodeURIComponent(limit)}&offset=${encodeURIComponent(offset)}`, {
    method: 'GET',
  })
}

/**
 * Переиндексация материалов курса в векторном хранилище и FTS.
 */
export async function reindexCourse() {
  return await apiFetch('/api/reindex', {
    method: 'POST',
  })
}
