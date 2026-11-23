import { describe, expect, it } from 'vitest'
import { truncateAtWord } from './text.js'

describe('truncateAtWord', () => {
  it('не трогает текст короче лимита', () => {
    expect(truncateAtWord('Короткий ответ', 40)).toBe('Короткий ответ')
  })

  it('обрезает по границе целого слова и ставит многоточие', () => {
    const result = truncateAtWord('Для лабораторной нужна видеокарта NVIDIA с 6 ГБ видеопамяти', 40)

    expect(result.endsWith('…')).toBe(true)
    expect(result.length).toBeLessThanOrEqual(41)
    expect('Для лабораторной нужна видеокарта NVIDIA с 6 ГБ видеопамяти'.startsWith(result.slice(0, -1))).toBe(true)
    expect(result.slice(0, -1).endsWith(' ')).toBe(false)
    expect(result).not.toMatch(/видеоп…$/)
  })

  it('схлопывает лишние пробелы и переносы', () => {
    expect(truncateAtWord('  Первая\n\nстрока   текста  ', 60)).toBe('Первая строка текста')
  })

  it('убирает знаки препинания перед многоточием', () => {
    expect(truncateAtWord('Первое предложение, второе предложение', 20)).toBe('Первое предложение…')
  })

  it('возвращает пустую строку для пустого ввода', () => {
    expect(truncateAtWord(null, 40)).toBe('')
    expect(truncateAtWord(undefined, 40)).toBe('')
  })
})
