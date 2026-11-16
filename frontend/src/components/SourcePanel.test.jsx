import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SourcePanel from './SourcePanel.jsx'

describe('SourcePanel', () => {
  it('показывает две цитаты в полном режиме', () => {
    render(<SourcePanel mode="full" onClose={() => {}} />)

    const panel = screen.getByRole('complementary', { name: 'Источник ответа' })
    expect(within(panel).getByText(/строка 68/)).toBeInTheDocument()
    expect(within(panel).getByText('Требования')).toBeInTheDocument()
    expect(within(panel).getByText(/строка 85/)).toBeInTheDocument()
    expect(within(panel).getByRole('button', { name: /Открыть всю методичку/ })).toBeInTheDocument()
  })

  it('показывает одну цитату в режиме подсказок', () => {
    render(<SourcePanel mode="hints" onClose={() => {}} />)

    const panel = screen.getByRole('complementary', { name: 'Источник ответа' })
    expect(within(panel).getByText(/строка 68/)).toBeInTheDocument()
    expect(within(panel).queryByText(/строка 85/)).not.toBeInTheDocument()
  })

  it('закрывается по кнопке', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(<SourcePanel mode="full" onClose={onClose} />)

    await user.click(screen.getByRole('button', { name: 'Закрыть' }))

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('в инлайн-варианте показывает первый источник и сворачивается', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(<SourcePanel inline mode="full" onClose={onClose} />)

    expect(screen.getByText(/строка 68/)).toBeInTheDocument()
    expect(screen.getByText('Технические сведения о стенде')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Свернуть источник' }))

    expect(onClose).toHaveBeenCalledTimes(1)
  })
})