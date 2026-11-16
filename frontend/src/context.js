import { createContext, useContext } from 'react'

export const FormatContext = createContext({
  format: 'full',
  setFormat: () => {},
})

export function useFormat() {
  return useContext(FormatContext)
}

export const FORMAT_LABELS = {
  full: 'Полный ответ',
  hints: 'Подсказки',
}