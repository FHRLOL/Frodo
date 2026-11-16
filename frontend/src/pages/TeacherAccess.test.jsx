import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderApp } from '../test/renderApp.jsx'

describe('страница «Доступ студентов»', () => {
  it('показывает студента и форматы по лабораторным', () => {
    renderApp('/teacher/access')

    expect(screen.getByRole('heading', { level: 1, name: 'Доступ студентов' })).toBeInTheDocument()
    expect(screen.getByText('Дарья Смирнова')).toBeInTheDocument()
    expect(screen.getByText('РИ-250903')).toBeInTheDocument()
    expect(screen.getByText('ЛР 01 · Сборка RAG')).toBeInTheDocument()
    expect(screen.getByText('ЛР 02 · Оценка RAG')).toBeInTheDocument()
    expect(screen.getByText('Подсказки')).toBeInTheDocument()
  })

  it('меняет формат первой лабораторной через селект', async () => {
    const user = userEvent.setup()
    renderApp('/teacher/access')

    const trigger = screen.getByRole('button', { name: /Полный ответ/ })
    await user.click(trigger)
    await user.click(screen.getByRole('option', { name: 'Подсказки' }))

    expect(screen.getByRole('button', { name: /Подсказки/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Полный ответ/ })).not.toBeInTheDocument()
  })

  it('содержит пояснение и ссылку на чат', () => {
    renderApp('/teacher/access')

    expect(screen.getByText('Как работает доступ')).toBeInTheDocument()
    expect(screen.getByText('Подсказки — следующий шаг. Полный ответ — разбор.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Посмотреть чат ЛР 01' })).toHaveAttribute('href', '/')
  })
})