import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import RoleGuard from './RoleGuard.jsx'
import { AuthContext } from '../context/AuthContext.jsx'

function renderWithAuth(ui, authValue = {}, initialEntry = '/protected') {
  const defaultAuth = {
    user: null,
    token: null,
    role: null,
    isLoading: false,
    isDemoAuth: false,
    login: async () => {},
    logout: async () => {},
    demoSwitchRole: async () => {},
    ...authValue,
  }

  return render(
    <AuthContext.Provider value={defaultAuth}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/protected" element={<RoleGuard allowedRoles={['instructor']}>{ui}</RoleGuard>} />
          <Route path="/" element={<div>Главная страница (редирект)</div>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

describe('RoleGuard component', () => {
  it('показывает лоадер при isLoading = true', () => {
    renderWithAuth(<div>Защищенный контент</div>, { isLoading: true })
    expect(screen.getByText('Проверка прав доступа...')).toBeInTheDocument()
    expect(screen.queryByText('Защищенный контент')).not.toBeInTheDocument()
  })

  it('редиректит на главную, если роль не соответствует (например, student)', () => {
    renderWithAuth(<div>Защищенный контент</div>, { role: 'student', user: { role: 'student' } })
    expect(screen.getByText('Главная страница (редирект)')).toBeInTheDocument()
    expect(screen.queryByText('Защищенный контент')).not.toBeInTheDocument()
  })

  it('отображает контент, если роль instructor', () => {
    renderWithAuth(<div>Защищенный контент</div>, { role: 'instructor', user: { role: 'instructor' } })
    expect(screen.getByText('Защищенный контент')).toBeInTheDocument()
    expect(screen.queryByText('Главная страница (редирект)')).not.toBeInTheDocument()
  })
})
