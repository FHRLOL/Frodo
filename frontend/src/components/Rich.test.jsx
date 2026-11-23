import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import Rich from './Rich.jsx'

describe('Rich', () => {
  it('рендерит инлайн-код плашкой', () => {
    render(<Rich text="Используй `append`, чтобы дополнить список." />)

    const code = screen.getByText('append')
    expect(code.tagName).toBe('CODE')
    expect(code).toHaveClass('md-code')
  })

  it('рендерит жирный текст и курсив', () => {
    render(<Rich text="Параметр **неизменяемый**, а *порядок* важен." />)

    expect(screen.getByText('неизменяемый').tagName).toBe('STRONG')
    expect(screen.getByText('порядок').tagName).toBe('EM')
  })

  it('не ломает ссылки на источники', () => {
    render(<Rich text="Это указано в методичке [1] и в приложении [2–3]." />)

    expect(screen.getByText('[1]')).toHaveClass('ref')
    expect(screen.getByText('[2–3]')).toHaveClass('ref')
  })

  it('оставляет сырой текст без разметки как есть', () => {
    render(<Rich text="Обычный текст без звёздочек и бэктиков." />)

    expect(screen.getByText('Обычный текст без звёздочек и бэктиков.')).toBeInTheDocument()
  })
})
