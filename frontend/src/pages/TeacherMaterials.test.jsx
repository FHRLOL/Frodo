import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderApp } from '../test/renderApp.jsx'

describe('страница «Материалы курса»', () => {
  it('показывает таблицу материалов', () => {
    renderApp('/teacher/materials')

    expect(screen.getByRole('heading', { level: 1, name: 'Материалы курса' })).toBeInTheDocument()
    expect(screen.getByText('Лабораторная по RAG')).toBeInTheDocument()
    expect(screen.getByText('README.md')).toBeInTheDocument()
    expect(screen.getByText('Markdown')).toBeInTheDocument()
    expect(screen.getByText('В базе курса')).toBeInTheDocument()
  })

  it('переключает лабораторную для загрузки', async () => {
    const user = userEvent.setup()
    renderApp('/teacher/materials')

    const select = screen.getByRole('combobox', { name: 'Лабораторная работа' })
    expect(select).toHaveValue('lr1')

    await user.selectOptions(select, 'lr2')

    expect(select).toHaveValue('lr2')
  })

  it('показывает имя выбранного файла', async () => {
    const user = userEvent.setup()
    const { container } = renderApp('/teacher/materials')
    const input = container.querySelector('input[type="file"]')
    const file = new File(['# README'], 'notes.md', { type: 'text/markdown' })

    await user.upload(input, file)

    expect(screen.getByText('Выбран файл: notes.md')).toBeInTheDocument()
  })
})