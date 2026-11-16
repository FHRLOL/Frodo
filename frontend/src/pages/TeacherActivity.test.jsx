import { screen } from '@testing-library/react'
import { renderApp } from '../test/renderApp.jsx'

describe('страница «Что спрашивают студенты»', () => {
  it('выводит статистику активности', () => {
    renderApp('/teacher')

    expect(screen.getByRole('heading', { level: 1, name: 'Что спрашивают студенты' })).toBeInTheDocument()
    expect(screen.getByText('Активность за последние 7 дней')).toBeInTheDocument()
    expect(screen.getByText('24')).toBeInTheDocument()
    expect(screen.getByText('студента задали вопросы')).toBeInTheDocument()
    expect(screen.getByText('86')).toBeInTheDocument()
    expect(screen.getByText('вопросов всего')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('вопросов без ответа')).toBeInTheDocument()
  })

  it('строит бары популярных тем пропорционально максимуму', () => {
    const { container } = renderApp('/teacher')

    expect(screen.getByText('Запуск локальной модели')).toBeInTheDocument()
    expect(screen.getByText('Поиск по материалам')).toBeInTheDocument()
    expect(screen.getByText('Оценка качества RAG')).toBeInTheDocument()

    const bars = container.querySelectorAll('.bar-fill')
    expect(bars).toHaveLength(3)
    expect(bars[0]).toHaveStyle({ width: '100%' })
    expect(bars[2]).toHaveStyle({ width: '61.11111111111111%' })
  })

  it('показывает вопросы без ответа и ведёт к материалам', () => {
    renderApp('/teacher')

    expect(screen.getByText('Как получить доступ к серверу кафедры?')).toBeInTheDocument()
    expect(screen.getByText('Куда сдавать отчёт по лабораторной?')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Перейти к материалам' })).toHaveAttribute('href', '/teacher/materials')
  })
})