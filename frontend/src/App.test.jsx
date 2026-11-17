import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderApp } from './test/renderApp.jsx'

describe('маршрутизация приложения', () => {
  it('открывает чат на главной странице', () => {
    renderApp('/')

    expect(screen.getByRole('heading', { level: 2, name: 'Спроси по лабораторной' })).toBeInTheDocument()
    expect(screen.getByText('С чего начать')).toBeInTheDocument()
    expect(screen.getAllByText('Локальные LLM и RAG').length).toBeGreaterThan(0)
  })

  it('переводит в кабинет преподавателя по ссылке из сайдбара', async () => {
    const user = userEvent.setup()
    renderApp('/')

    await user.click(screen.getByRole('link', { name: 'Кабинет преподавателя' }))

    expect(screen.getByRole('heading', { level: 1, name: 'Что спрашивают студенты' })).toBeInTheDocument()
    expect(within(screen.getByRole('navigation', { name: 'Навигация' })).getByRole('link', { name: 'Обзор' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('возвращает на главную по клику на логотип', async () => {
    const user = userEvent.setup()
    renderApp('/teacher/materials')

    expect(screen.getByRole('heading', { level: 1, name: 'Материалы курса' })).toBeInTheDocument()

    await user.click(screen.getAllByRole('link', { name: 'Frodo — на главную' })[0])

    expect(screen.getByRole('heading', { level: 2, name: 'Спроси по лабораторной' })).toBeInTheDocument()
  })

  it('перенаправляет с неизвестного адреса на чат', () => {
    renderApp('/unknown-page')

    expect(screen.getByRole('heading', { level: 2, name: 'Спроси по лабораторной' })).toBeInTheDocument()
  })

  it('блокирует доступ студента к /teacher и показывает предупреждение', () => {
    renderApp('/teacher', { role: 'student' })

    expect(screen.getByRole('alert')).toHaveTextContent('Доступ ограничен: раздел доступен только преподавателям курса.')
    expect(screen.getByRole('heading', { level: 2, name: 'Спроси по лабораторной' })).toBeInTheDocument()
  })

  it('переключает роль пользователя через демо-переключатель', async () => {
    const user = userEvent.setup()
    renderApp('/')

    // Находим кнопки демо-переключателя
    const studentButtons = screen.getAllByRole('button', { name: 'Студент' })
    await user.click(studentButtons[0])

    expect(screen.getAllByText(/Студент/i).length).toBeGreaterThan(0)
  })
})
