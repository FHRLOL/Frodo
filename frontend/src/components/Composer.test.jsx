import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Composer from './Composer.jsx'

describe('Composer', () => {
  it('отправляет обрезанный текст и очищает поле', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<Composer onSend={onSend} busy={false} />)

    const input = screen.getByLabelText('Вопрос по курсу')
    await user.type(input, '  Сколько видеопамяти?  ')
    await user.click(screen.getByRole('button', { name: 'Отправить' }))

    expect(onSend).toHaveBeenCalledWith('Сколько видеопамяти?')
    expect(input).toHaveValue('')
  })

  it('игнорирует пустой ввод', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<Composer onSend={onSend} busy={false} />)

    await user.type(screen.getByLabelText('Вопрос по курсу'), '   ')
    await user.click(screen.getByRole('button', { name: 'Отправить' }))

    expect(onSend).not.toHaveBeenCalled()
  })

  it('блокирует отправку во время поиска', () => {
    render(<Composer onSend={() => {}} busy />)

    expect(screen.getByRole('button', { name: 'Поиск…' })).toBeDisabled()
    expect(screen.getByLabelText('Вопрос по курсу')).toBeInTheDocument()
  })

  it('показывает подпись под полем', () => {
    render(<Composer onSend={() => {}} busy={false} />)

    expect(screen.getByText('Ответы основаны на материалах курса')).toBeInTheDocument()
  })
})