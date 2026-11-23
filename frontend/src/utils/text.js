/**
 * Обрезает текст по границе последнего целого слова и добавляет многоточие.
 * Если текст короче лимита — возвращает его без изменений.
 */
export function truncateAtWord(text, maxLength = 60) {
  const clean = String(text ?? '')
    .replace(/\s+/g, ' ')
    .trim()

  if (clean.length <= maxLength) return clean

  const cut = clean.slice(0, maxLength)
  const lastSpace = cut.lastIndexOf(' ')
  // Если пробел слишком далеко от начала, режем по лимиту, чтобы не терять смысл
  const base = lastSpace > maxLength * 0.5 ? cut.slice(0, lastSpace) : cut

  return `${base.replace(/[\s.,;:!?—–-]+$/u, '')}…`
}
