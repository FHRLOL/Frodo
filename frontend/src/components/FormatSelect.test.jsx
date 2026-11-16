import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import FormatSelect from './FormatSelect.jsx'

describe('FormatSelect', () => {
  it('раскрывает список и отмечает текущий вариант', async () => {
    const user = userEvent.setup()
    render(<FormatSelect value="full" onChange={() => {}} />)

    const trigger = screen.getByRole('button', { name: /Полный ответ/ })
    expect(trigger).toHaveAttribute('aria-expanded', 'false')

    await user.click(trigger)

    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    const listbox = screen.getByRole('listbox', { name: 'Формат ответа' })
    expect(screen.getByRole('option', { name: 'Полный ответ' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('option', { name: 'Подсказки' })).toHaveAttribute('aria-selected', 'false')
    expect(listbox).toBeInTheDocument()
  })

  it('передаёт выбранный формат и закрывает меню', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<FormatSelect value="full" onChange={onChange} />)

    await user.click(screen.getByRole('button', { name: /Полный ответ/ }))
    await user.click(screen.getByRole('option', { name: 'Подсказки' }))

    expect(onChange).toHaveBeenCalledWith('hints')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('закрывается по клику вне меню', async () => {
    const user = userEvent.setup()
    render(<FormatSelect value="full" onChange={() => {}} />)

    await user.click(screen.getByRole('button', { name: /Полный ответ/ }))
    expect(screen.getByRole('listbox')).toBeInTheDocument()

    await user.click(document.body)

    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('закрывается по Escape', async () => {
    const user = userEvent.setup()
    render(<FormatSelect value="full" onChange={() => {}} />)

    await user.click(screen.getByRole('button', { name: /Полный ответ/ }))
    await user.keyboard('{Escape}')

    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })
})