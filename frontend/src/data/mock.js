export const course = {
  title: 'Локальные LLM и RAG',
  lab: 'ЛР 01 · Сборка RAG',
}

export const suggestions = [
  'Сколько видеопамяти нужно для лабораторной по RAG?',
  'Как получить доступ к серверу кафедры?',
]

export const courseCard = {
  label: 'Материалы курса',
  title: 'Лабораторная по RAG',
  text: 'Запуск локальной модели, поиск по документам и проверка качества ответов.',
}

export const answers = {
  memory: {
    full: {
      title: 'Нужно от 6 ГБ видеопамяти',
      paragraphs: [
        'Для лабораторной нужна видеокарта NVIDIA с 6 ГБ видеопамяти или больше. В требованиях также указаны Windows 10/11 и 16 ГБ оперативной памяти. [1]',
        'Доступный модели объём памяти можно проверить командой из методички. Посмотри значение free. [2]',
      ],
      code: 'llama-server --list-devices',
      codeCaption: 'README.md · строка 68',
      source: {
        ref: '[1–2]',
        title: 'Лабораторная по RAG',
        sub: 'Технические сведения о стенде',
      },
    },
    hints: {
      title: 'Начни с требований к стенду',
      paragraphs: [
        'Открой раздел «Технические сведения о стенде». В строке «Требования» найди, какой объём памяти указан рядом с NVIDIA. [1]',
        'Чтобы сверить требования со своим компьютером, перейди к шагу 0 «Проверка видеокарты».',
      ],
      code: null,
      codeCaption: null,
      source: {
        ref: '[1]',
        title: 'Лабораторная по RAG',
        sub: 'Технические сведения о стенде',
      },
    },
  },
  none: {
    title: 'В материалах курса ответа нет',
    paragraphs: [
      'В методичке и материалах курса нет раздела про доступ к серверу кафедры. Уточни у преподавателя или попробуй переформулировать вопрос.',
    ],
    action: 'Спросить по другому разделу',
  },
}

export const citations = [
  {
    ref: '[1] README.md, строка 68',
    title: 'Требования',
    text: 'Windows 10/11, видеокарта NVIDIA с 6+ ГБ памяти (GTX 16xx, RTX 20/30/40/50), 16 ГБ ОЗУ, ~15 ГБ свободного места на диске.',
    tone: 'peach',
  },
  {
    ref: '[2] README.md, строка 85',
    title: null,
    text: 'Реальный бюджет показывает llama-server --list-devices в поле free — на карте 6 ГБ это около 5 ГБ.',
    tone: 'cool',
  },
]

export const activity = {
  stats: [
    { value: '24', label: 'студента задали вопросы' },
    { value: '86', label: 'вопросов всего' },
    { value: '12', label: 'вопросов без ответа', tone: 'brown' },
  ],
  topics: [
    { label: 'Запуск локальной модели', value: 36 },
    { label: 'Поиск по материалам', value: 28 },
    { label: 'Оценка качества RAG', value: 22 },
  ],
  unanswered: [
    { text: 'Как получить доступ к серверу кафедры?', count: 5 },
    { text: 'Как проверить работу на Linux?', count: 4 },
    { text: 'Куда сдавать отчёт по лабораторной?', count: 3 },
  ],
}

export const materials = [
  {
    title: 'Лабораторная по RAG',
    file: 'README.md',
    format: 'Markdown',
    status: 'В базе курса',
  },
]

export const students = [
  {
    name: 'Дарья Смирнова',
    id: 'РИ-250903',
  },
]

export const labs = [
  { id: 'lr1', title: 'ЛР 01 · Сборка RAG' },
  { id: 'lr2', title: 'ЛР 02 · Оценка RAG' },
]