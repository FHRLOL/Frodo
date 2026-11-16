import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { answers, suggestions } from '../data/mock.js'
import { renderApp } from '../test/renderApp.jsx'

const ANSWER_TIMEOUT = 3000

function setup(path = '/') {
  const user = userEvent.setup()
  renderApp(path)
  return user
}

async function findAnswer(title, level = 3) {
  return screen.findByRole('heading', { level, name: title }, { timeout: ANSWER_TIMEOUT })
}

describe('чат с наставником', () => {
  it('показывает состояние поиска и полный ответ на вопрос про видеопамять', async () => {
    const user = setup()

    await user.click(screen.getByRole('button', { name: suggestions[0] }))

    expect(screen.getByText('Твой вопрос')).toBeInTheDocument()
    expect(screen.getByText(suggestions[0])).toBeInTheDocument()
    expect(screen.getByText('Ищу ответ в методичке…')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Поиск…' })).toBeDisabled()

    expect(await findAnswer(answers.memory.full.title)).toBeInTheDocument()
    expect(screen.getByText(answers.memory.full.code)).toBeInTheDocument()
    expect(screen.getByText(answers.memory.full.codeCaption)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Открыть/ })).toBeInTheDocument()
  })

  it('отправляет вопрос из композера и очищает поле', async () => {
    const user = setup()
    const input = screen.getByLabelText('Вопрос по курсу')

    await user.type(input, '  Сколько нужно видеопамяти?  ')
    await user.click(screen.getByRole('button', { name: 'Отправить' }))

    expect(screen.getByText('Сколько нужно видеопамяти?')).toBeInTheDocument()
    expect(input).toHaveValue('')

    expect(await findAnswer(answers.memory.full.title)).toBeInTheDocument()
  })

  it('не отправляет пустой вопрос', async () => {
    const user = setup()

    await user.type(screen.getByLabelText('Вопрос по курсу'), '   ')
    await user.click(screen.getByRole('button', { name: 'Отправить' }))

    expect(screen.getByRole('heading', { level: 2, name: 'Спроси по лабораторной' })).toBeInTheDocument()
    expect(screen.queryByText('Твой вопрос')).not.toBeInTheDocument()
  })

  it('открывает и закрывает панель с источниками', async () => {
    const user = setup()

    await user.click(screen.getByRole('button', { name: suggestions[0] }))
    await findAnswer(answers.memory.full.title)
    await user.click(screen.getByRole('button', { name: /Открыть/ }))

    const panel = screen.getByRole('complementary', { name: 'Источник ответа' })
    expect(within(panel).getByRole('heading', { name: 'Методичка' })).toBeInTheDocument()
    expect(within(panel).getByText('Требования')).toBeInTheDocument()
    expect(within(panel).getByText(/строка 68/)).toBeInTheDocument()
    expect(within(panel).getByText(/строка 85/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Свернуть источник' })).toBeInTheDocument()

    await user.click(within(panel).getByRole('button', { name: 'Закрыть' }))

    expect(screen.queryByRole('complementary', { name: 'Источник ответа' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Свернуть источник' })).not.toBeInTheDocument()
  })

  it('показывает ответ «в материалах нет» и возвращает к пустому чату', async () => {
    const user = setup()

    await user.click(screen.getByRole('button', { name: suggestions[1] }))
    expect(await findAnswer(answers.none.title)).toBeInTheDocument()

    expect(screen.getByText(answers.none.paragraphs[0])).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: answers.none.action }))

    expect(screen.getByRole('heading', { level: 2, name: 'Спроси по лабораторной' })).toBeInTheDocument()
    expect(screen.queryByText('Твой вопрос')).not.toBeInTheDocument()
  })

  it('сбрасывает диалог кнопкой «Новый чат»', async () => {
    const user = setup()

    await user.click(screen.getByRole('button', { name: suggestions[0] }))
    await findAnswer(answers.memory.full.title)
    await user.click(screen.getByRole('button', { name: 'Новый чат' }))

    expect(screen.getByRole('heading', { level: 2, name: 'Спроси по лабораторной' })).toBeInTheDocument()
    expect(screen.queryByText('Твой вопрос')).not.toBeInTheDocument()
  })

  it('использует выбранный преподавателем формат подсказок', async () => {
    const user = setup('/teacher/access')

    await user.click(screen.getByRole('button', { name: /Полный ответ/ }))
    await user.click(screen.getByRole('option', { name: 'Подсказки' }))
    await user.click(screen.getByRole('link', { name: 'Посмотреть чат ЛР 01' }))

    expect(screen.getByText(/Сборка RAG \/ Подсказки/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: suggestions[0] }))
    expect(await findAnswer(answers.memory.hints.title)).toBeInTheDocument()
    expect(screen.queryByText(answers.memory.full.code)).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Открыть/ }))

    const panel = screen.getByRole('complementary', { name: 'Источник ответа' })
    expect(within(panel).getByText(/строка 68/)).toBeInTheDocument()
    expect(within(panel).queryByText(/строка 85/)).not.toBeInTheDocument()
  })
})