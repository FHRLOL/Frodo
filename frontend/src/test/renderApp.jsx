import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from '../App.jsx'

export function renderApp(path = '/', options = {}) {
  const { initialAuth, role, ...renderOptions } = options

  let authToPass = initialAuth
  if (!authToPass && role) {
    authToPass = {
      role,
      user: role === 'instructor'
        ? { id: 1, name: 'Проф. Смирнов А.В.', email: 'instructor_1@university.edu', role: 'instructor' }
        : { id: 42, name: 'Алексей Иванов', email: 'student_42@university.edu', role: 'student' },
      token: 'test-token',
      isLoading: false,
    }
  }

  return render(
    <MemoryRouter initialEntries={[path]}>
      <App initialAuth={authToPass} />
    </MemoryRouter>,
    renderOptions,
  )
}
