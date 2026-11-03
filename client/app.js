/**
 * Frodo AI Mentor — Client Application
 * Holad Design System & LTI 1.1 / RAG Controller
 */

// ==================== СОСТОЯНИЕ ПРИЛОЖЕНИЯ ====================
const state = {
  token: null,
  user: null,           // { id, name, role, moodle_user_id, email }
  labs: [],             // [{ id, title, description, order_num }]
  progress: [],         // [{ lab_id, status, grade, can_master_mode, ... }]
  activeLabId: 1,
  currentView: 'student', // 'student' | 'instructor'
  adminTab: 'matrix',     // 'matrix' | 'gap' | 'rag'
  isStreaming: false
};

// ==================== ИНИЦИАЛИЗАЦИЯ ====================
document.addEventListener('DOMContentLoaded', async () => {
  initMarkdownConfig();
  initEventListeners();
  await initAuth();
  await checkSystemHealth();
});

// Настройка Marked.js для подсветки синтаксиса и безопасности
function initMarkdownConfig() {
  if (window.marked) {
    marked.setOptions({
      breaks: true,
      gfm: true
    });
  }
}

// ==================== АВТОРИЗАЦИЯ И LTI 1.1 ====================
async function initAuth() {
  // 1. Проверяем токен в URL (?token=...)
  const urlParams = new URLSearchParams(window.location.search);
  const urlToken = urlParams.get('token');
  
  if (urlToken) {
    state.token = urlToken;
    localStorage.setItem('frodo_jwt', urlToken);
    document.cookie = `frodo_token=${urlToken}; path=/; max-age=604800; SameSite=Lax`;
    // Очищаем URL от токена для чистоты адресной строки
    window.history.replaceState({}, document.title, window.location.pathname);
  } else {
    state.token = localStorage.getItem('frodo_jwt');
  }

  // 2. Если токен есть, валидируем через /api/auth/me
  let authenticated = false;
  if (state.token) {
    try {
      const res = await fetch('/api/auth/me', {
        headers: { 'Authorization': `Bearer ${state.token}` }
      });
      if (res.ok) {
        state.user = await res.json();
        authenticated = true;
      }
    } catch (e) {
      console.warn('[Frodo Auth] Не удалось проверить сохраненный JWT:', e);
    }
  }

  // 3. Если токена нет или он просрочен — выполняем мгновенный демо-вход как Студент
  if (!authenticated) {
    await loginDemoRole('student', false);
  } else {
    applyUserProfile();
  }
}

// Быстрый переключатель ролей (демо-логин)
async function loginDemoRole(role, notify = true) {
  try {
    const res = await fetch(`/api/auth/demo-login?role=${role}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role })
    });

    if (!res.ok) throw new Error(`Ошибка входа: статус ${res.status}`);

    const data = await res.json();
    state.token = data.token;
    state.user = data.user;
    localStorage.setItem('frodo_jwt', data.token);
    document.cookie = `frodo_token=${data.token}; path=/; credentials=same-origin; SameSite=Lax`;

    applyUserProfile();

    if (notify) {
      showToast(
        `Вы вошли как ${state.user.role === 'instructor' ? 'Преподаватель' : 'Студент'}: ${state.user.name}`,
        'success'
      );
    }

    // Если вошли как преподаватель — открываем панель преподавателя
    if (state.user.role === 'instructor') {
      switchView('instructor');
      loadAdminStudentsMatrix();
    } else {
      switchView('student');
    }

    await loadLabsAndProgress();
  } catch (err) {
    console.error('[Frodo Auth] Ошибка demo-login:', err);
    showToast(`Ошибка авторизации: ${err.message}`, 'danger');
  }
}

// Обновление элементов интерфейса профиля
function applyUserProfile() {
  if (!state.user) return;

  const userNameEl = document.getElementById('userName');
  const userRoleEl = document.getElementById('userRoleBadge');
  const userAvatarEl = document.getElementById('userAvatar');
  const btnRoleStudent = document.getElementById('btnRoleStudent');
  const btnRoleInstructor = document.getElementById('btnRoleInstructor');
  const viewSwitcherNav = document.getElementById('viewSwitcherNav');

  // ФИО
  userNameEl.textContent = state.user.name;

  // Инициалы для аватарки
  const initials = state.user.name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map(p => p[0].toUpperCase())
    .join('');
  userAvatarEl.textContent = initials || '👤';

  // Роль и стили
  const isInstructor = state.user.role === 'instructor';
  
  if (isInstructor) {
    userRoleEl.textContent = 'Преподаватель (instructor_1)';
    userRoleEl.className = 'text-[10px] text-purple-400 font-mono';
    userAvatarEl.className = 'w-8 h-8 rounded-full bg-purple-500/20 text-purple-300 flex items-center justify-center font-bold text-xs border border-purple-500/30';
    
    // Подсветка кнопок переключения
    btnRoleInstructor.className = 'px-2.5 py-1 text-xs rounded-md font-semibold transition-all min-h-[36px] flex items-center gap-1.5 text-purple-300 bg-purple-500/20 border border-purple-500/40 shadow-sm';
    btnRoleStudent.className = 'px-2.5 py-1 text-xs rounded-md font-medium transition-all min-h-[36px] flex items-center gap-1.5 text-[#94a3b8] hover:text-[#f8fafc]';

    // Показываем переключатель экранов в шапке
    viewSwitcherNav.classList.remove('hidden');
    viewSwitcherNav.classList.add('flex');
  } else {
    userRoleEl.textContent = 'Студент (student_42)';
    userRoleEl.className = 'text-[10px] text-[#10b981] font-mono';
    userAvatarEl.className = 'w-8 h-8 rounded-full bg-[#10b981]/20 text-[#10b981] flex items-center justify-center font-bold text-xs border border-[#10b981]/30';

    btnRoleStudent.className = 'px-2.5 py-1 text-xs rounded-md font-semibold transition-all min-h-[36px] flex items-center gap-1.5 text-[#10b981] bg-[#10b981]/15 border border-[#10b981]/30 shadow-sm';
    btnRoleInstructor.className = 'px-2.5 py-1 text-xs rounded-md font-medium transition-all min-h-[36px] flex items-center gap-1.5 text-[#94a3b8] hover:text-[#f8fafc]';

    viewSwitcherNav.classList.remove('flex');
    viewSwitcherNav.classList.add('hidden');
  }
}

// Переключение экранов Студент / Преподаватель
function switchView(targetView) {
  state.currentView = targetView;
  const studentView = document.getElementById('studentView');
  const instructorDashboard = document.getElementById('instructorDashboard');
  const btnSwitchToStudent = document.getElementById('btnSwitchToStudent');
  const btnSwitchToInstructor = document.getElementById('btnSwitchToInstructor');

  if (targetView === 'instructor') {
    studentView.classList.add('hidden');
    instructorDashboard.classList.remove('hidden');

    btnSwitchToInstructor.className = 'px-3 py-1.5 text-xs font-semibold rounded-md transition-all text-[#f8fafc] bg-[#151b2b] shadow-sm flex items-center gap-1.5 min-h-[36px]';
    btnSwitchToStudent.className = 'px-3 py-1.5 text-xs font-medium rounded-md transition-all text-[#94a3b8] hover:text-[#f8fafc] flex items-center gap-1.5 min-h-[36px]';

    loadAdminStudentsMatrix();
  } else {
    instructorDashboard.classList.add('hidden');
    studentView.classList.remove('hidden');

    btnSwitchToStudent.className = 'px-3 py-1.5 text-xs font-semibold rounded-md transition-all text-[#f8fafc] bg-[#151b2b] shadow-sm flex items-center gap-1.5 min-h-[36px]';
    btnSwitchToInstructor.className = 'px-3 py-1.5 text-xs font-medium rounded-md transition-all text-[#94a3b8] hover:text-[#f8fafc] flex items-center gap-1.5 min-h-[36px]';

    loadLabsAndProgress();
  }
}

// ==================== ЛАБОРАТОРНЫЕ РАБОТЫ И ПРОГРЕСС ====================
async function loadLabsAndProgress() {
  try {
    // 1. Получаем каталог лаб
    const labsRes = await fetch('/api/labs');
    if (labsRes.ok) {
      state.labs = await labsRes.json();
    }

    // 2. Получаем прогресс текущего пользователя
    if (state.token) {
      const progRes = await fetch('/api/student/progress', {
        headers: { 'Authorization': `Bearer ${state.token}` }
      });
      if (progRes.ok) {
        state.progress = await progRes.json();
      }
    }

    renderLabsSelector();
    updateMentorModeBanner();
  } catch (err) {
    console.error('[Frodo Labs] Ошибка загрузки лаб/прогресса:', err);
  }
}

function renderLabsSelector() {
  const container = document.getElementById('labsSelectorContainer');
  if (!container || !state.labs.length) return;

  container.innerHTML = '';

  state.labs.forEach(lab => {
    // Находим статус студента по этой лабе
    const p = state.progress.find(item => item.lab_id === lab.id);
    const status = p ? p.status : 'not_started';
    const isActive = lab.id === state.activeLabId;

    let badgeIcon = '⚪';
    let badgeText = 'Не начато';
    let badgeClass = 'text-[#94a3b8] bg-white/5';

    if (status === 'passed') {
      badgeIcon = '🟢';
      badgeText = 'Зачтено';
      badgeClass = 'text-[#10b981] bg-[#10b981]/15 border border-[#10b981]/30';
    } else if (status === 'in_progress') {
      badgeIcon = '🟡';
      badgeText = 'В процессе';
      badgeClass = 'text-[#f59e0b] bg-[#f59e0b]/15 border border-[#f59e0b]/30';
    }

    const btn = document.createElement('button');
    btn.className = `px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-2 min-h-[36px] ${
      isActive 
        ? 'bg-[#151b2b] text-[#f8fafc] border border-[rgba(255,255,255,0.2)] shadow-md ring-1 ring-[rgba(255,255,255,0.1)]' 
        : 'bg-[#0b0f19] text-[#94a3b8] border border-[rgba(255,255,255,0.06)] hover:bg-[#151b2b] hover:text-[#f8fafc]'
    }`;
    btn.setAttribute('aria-label', `Выбрать лабораторную работу: ${lab.title}`);
    btn.innerHTML = `
      <span class="font-bold">Лаба ${lab.order_num}</span>
      <span class="text-[10px] px-1.5 py-0.5 rounded ${badgeClass} font-mono">${badgeIcon} ${badgeText}</span>
    `;

    btn.addEventListener('click', () => {
      state.activeLabId = lab.id;
      renderLabsSelector();
      updateMentorModeBanner();
    });

    container.appendChild(btn);
  });
}

// Обновление баннера режима (Сократ vs Мастер)
function updateMentorModeBanner() {
  const banner = document.getElementById('mentorModeBanner');
  const bannerIcon = document.getElementById('bannerIconWrapper');
  const bannerTitle = document.getElementById('bannerTitle');
  const bannerBadge = document.getElementById('bannerBadge');
  const bannerDesc = document.getElementById('bannerDesc');
  const activeLabGrade = document.getElementById('activeLabGrade');
  const labGradeVal = document.getElementById('labGradeVal');

  const p = state.progress.find(item => item.lab_id === state.activeLabId);
  const isPassed = p && p.status === 'passed';
  const grade = p ? p.grade : 0;

  // Оценка
  if (grade > 0) {
    activeLabGrade.classList.remove('hidden');
    labGradeVal.textContent = `${grade} / 100`;
  } else {
    activeLabGrade.classList.add('hidden');
  }

  if (isPassed) {
    // 🟢 РЕЖИМ МАСТЕРА (лабораторная сдана)
    banner.className = 'p-3.5 sm:p-4 rounded-xl border transition-all duration-300 flex items-start gap-3.5 bg-[#151b2b] border-[#10b981]/40 shadow-[0_0_20px_rgba(16,185,129,0.12)]';
    bannerIcon.className = 'w-10 h-10 rounded-lg flex items-center justify-center text-xl shrink-0 bg-[#10b981]/15 text-[#10b981] border border-[#10b981]/30';
    bannerIcon.textContent = '🎓';
    bannerTitle.textContent = 'Режим углубления (Мастер)';
    bannerBadge.className = 'holad-badge holad-badge-primary text-[11px]';
    bannerBadge.textContent = 'Лабораторная работа зачтена • Полный доступ';
    bannerDesc.textContent = 'Лабораторная работа зачтена. Вам доступны полные академические решения, синтаксис и разбор для подготовки к защите.';
  } else {
    // 🟡 РЕЖИМ СОКРАТА (лабораторная не сдана)
    banner.className = 'p-3.5 sm:p-4 rounded-xl border transition-all duration-300 flex items-start gap-3.5 bg-[#151b2b] border-[#f59e0b]/40 shadow-[0_0_20px_rgba(245,158,11,0.08)]';
    bannerIcon.className = 'w-10 h-10 rounded-lg flex items-center justify-center text-xl shrink-0 bg-[#f59e0b]/10 text-[#f59e0b] border border-[#f59e0b]/30';
    bannerIcon.textContent = '🛡️';
    bannerTitle.textContent = 'Режим наставника (Сократ)';
    bannerBadge.className = 'holad-badge holad-badge-warning text-[11px]';
    bannerBadge.textContent = p && p.status === 'in_progress' ? 'В процессе выполнения' : 'Не начато';
    bannerDesc.textContent = 'Наставник подробно объясняет теорию и правила курса по теме вопроса и помогает наводящими вопросами, не решая задачу за вас.';
  }
}

// ==================== ЧАТ И ПОТОКОВАЯ ГЕНЕРАЦИЯ (SSE) ====================
function initEventListeners() {
  const chatForm = document.getElementById('chatForm');
  const questionInput = document.getElementById('questionInput');
  const clearChatBtn = document.getElementById('clearChatBtn');
  const btnRoleStudent = document.getElementById('btnRoleStudent');
  const btnRoleInstructor = document.getElementById('btnRoleInstructor');
  const btnSwitchToStudent = document.getElementById('btnSwitchToStudent');
  const btnSwitchToInstructor = document.getElementById('btnSwitchToInstructor');

  // Вкладки преподавателя
  document.getElementById('tabBtnMatrix').addEventListener('click', () => switchAdminTab('matrix'));
  document.getElementById('tabBtnGap').addEventListener('click', () => switchAdminTab('gap'));
  document.getElementById('tabBtnRag').addEventListener('click', () => switchAdminTab('rag'));

  // Кнопки обновления
  document.getElementById('refreshMatrixBtn').addEventListener('click', loadAdminStudentsMatrix);
  document.getElementById('refreshGapBtn').addEventListener('click', loadAdminGapAnalysis);
  document.getElementById('reindexBtn').addEventListener('click', reindexKnowledgeBase);

  // Переключение ролей LTI
  btnRoleStudent.addEventListener('click', () => loginDemoRole('student'));
  btnRoleInstructor.addEventListener('click', () => loginDemoRole('instructor'));

  // Навигация между экранами
  btnSwitchToStudent.addEventListener('click', () => switchView('student'));
  btnSwitchToInstructor.addEventListener('click', () => switchView('instructor'));

  // Отправка формы чата
  chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    handleQuestionSubmit();
  });

  // Автоматический перенос строк и Enter для отправки
  questionInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleQuestionSubmit();
    }
  });

  // Клик по готовым пресетам вопросов
  document.addEventListener('click', (e) => {
    const chip = e.target.closest('.preset-chip');
    if (chip) {
      const query = chip.getAttribute('data-query');
      if (query) {
        questionInput.value = query;
        handleQuestionSubmit();
      }
    }
  });

  // Очистка диалога
  clearChatBtn.addEventListener('click', () => {
    const messagesArea = document.getElementById('messagesArea');
    messagesArea.innerHTML = `
      <div class="flex items-start gap-3 max-w-3xl">
        <div class="w-8 h-8 rounded-lg bg-[#10b981]/15 border border-[#10b981]/30 text-[#10b981] flex items-center justify-center text-sm shrink-0">
          🧙‍♂️
        </div>
        <div class="flex-1 bg-[#151b2b] border border-[rgba(255,255,255,0.08)] rounded-xl p-4">
          <div class="flex items-center justify-between mb-1">
            <span class="text-xs font-bold text-[#f8fafc]">Frodo AI Mentor</span>
            <span class="holad-badge holad-badge-muted text-[10px]">История сброшена</span>
          </div>
          <p class="text-xs sm:text-sm text-[#94a3b8]">Диалог очищен. Задайте вопрос по лабораторной работе.</p>
        </div>
      </div>
    `;
    showToast('История диалога очищена', 'success');
  });
}

function handleQuestionSubmit() {
  const input = document.getElementById('questionInput');
  const question = input.value.trim();
  if (!question || state.isStreaming) return;

  input.value = '';
  input.style.height = 'auto';
  streamQuery(question);
}

// Основной метод потокового обращения к /api/query/stream
async function streamQuery(question) {
  state.isStreaming = true;
  setSendButtonLoading(true);

  // 1. Добавляем сообщение студента в ленту
  appendStudentMessage(question);

  // 2. Создаем контейнер для потокового ответа наставника
  const { messageCard, contentEl, metaEl, citationEl, metricsEl } = createMentorMessageSkeleton();

  const startTime = Date.now();
  let accumulatedText = '';
  let tokenCount = 0;
  let firstTokenReceived = false;

  try {
    const response = await fetch('/api/query/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${state.token}`
      },
      body: JSON.stringify({
        question: question,
        lab_id: state.activeLabId,
        token: state.token
      })
    });

    if (!response.ok) {
      throw new Error(`Ошибка сервера: ${response.status} ${response.statusText}`);
    }

    // Читаем SSE поток через ReadableStream
    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split('\n\n');
      buffer = events.pop(); // Оставляем незавершенный кусок

      for (const evText of events) {
        if (!evText.trim()) continue;

        const lines = evText.split('\n');
        let eventType = 'message';
        let dataStr = '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            dataStr = line.slice(6).trim();
          }
        }

        if (!dataStr) continue;

        try {
          const payload = JSON.parse(dataStr);

          // Обработка разных типов SSE событий:
          if (eventType === 'meta') {
            handleStreamMeta(payload, metaEl);
          } else if (eventType === 'token') {
            if (!firstTokenReceived) {
              firstTokenReceived = true;
              const ttft = Date.now() - startTime;
              metricsEl.innerHTML = `<span class="holad-badge holad-badge-muted text-[10px] font-mono">TTFT: ${ttft} ms</span>`;
            }
            tokenCount++;
            accumulatedText += payload.token;
            renderStreamingContent(accumulatedText, contentEl, true);
          } else if (eventType === 'citation') {
            handleStreamCitation(payload, citationEl);
          } else if (eventType === 'done') {
            const totalDuration = (Date.now() - startTime) / 1000;
            const speed = totalDuration > 0 ? (tokenCount / totalDuration).toFixed(1) : 0;
            const ttftText = metricsEl.textContent.trim();
            metricsEl.innerHTML = `
              <span class="holad-badge holad-badge-muted text-[10px] font-mono">${ttftText}</span>
              <span class="holad-badge holad-badge-muted text-[10px] font-mono">⚡ ${speed} tok/s</span>
            `;
          }
        } catch (jsonErr) {
          console.warn('[Frodo SSE] Ошибка парсинга data payload:', dataStr, jsonErr);
        }
      }
    }

    // Завершение стриминга — убираем каретку
    renderStreamingContent(accumulatedText, contentEl, false);
    attachCopyCodeButtons(contentEl);

  } catch (err) {
    console.error('[Frodo Stream] Ошибка стриминга:', err);
    contentEl.innerHTML = `
      <div class="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs">
        ⚠️ Не удалось получить ответ: ${escapeHtml(err.message)}
      </div>
    `;
  } finally {
    state.isStreaming = false;
    setSendButtonLoading(false);
    scrollChatToBottom();
  }
}

// Отображение метаданных генерации (режим, Guardrail, скор)
function handleStreamMeta(meta, metaEl) {
  let badgeHtml = '';
  if (meta.mode === 'master') {
    badgeHtml = '<span class="holad-badge holad-badge-primary text-[10px]">Режим: Мастер</span>';
  } else {
    badgeHtml = '<span class="holad-badge holad-badge-warning text-[10px]">Режим: Сократ</span>';
  }

  if (meta.score !== undefined) {
    const scoreColor = meta.score >= 0.42 ? 'text-[#10b981]' : 'text-[#f59e0b]';
    badgeHtml += ` <span class="text-[10px] text-[#94a3b8] font-mono">Скор: <strong class="${scoreColor}">${meta.score}</strong></span>`;
  }

  if (meta.status === 'REJECTED_BY_GUARDRAIL') {
    badgeHtml += ' <span class="holad-badge holad-badge-danger text-[10px]">🛡️ Guardrail rejection</span>';
  }

  metaEl.innerHTML = badgeHtml;
}

// Интерактивный аккордеон источника цитирования
function handleStreamCitation(citationData, citationEl) {
  if (!citationData || !citationData.doc_name) return;

  const docName = escapeHtml(citationData.doc_name);
  const section = escapeHtml(citationData.section_title || 'Основной раздел');
  const lines = citationData.line_start ? `строки ${citationData.line_start}–${citationData.line_end}` : '';
  const fullCitation = escapeHtml(citationData.citation || `[Источник: ${docName}, ${section}, ${lines}]`);

  citationEl.innerHTML = `
    <div class="citation-accordion">
      <div class="citation-header" onclick="this.parentElement.classList.toggle('open')">
        <div class="flex items-center gap-1.5 min-w-0 truncate">
          <span>📖</span>
          <span class="truncate font-mono">${fullCitation}</span>
        </div>
        <span class="text-xs transition-transform transform">▼</span>
      </div>
      <div class="citation-body">
        <div class="text-[11px] text-[#94a3b8] mb-1">
          Документ: <strong class="text-[#f8fafc]">${docName}</strong> • Раздел: <strong class="text-[#f8fafc]">«${section}»</strong> (${lines})
        </div>
        <p class="text-xs italic text-[#cbd5e1] bg-black/30 p-2 rounded border border-white/5">
          «${fullCitation}»
        </p>
      </div>
    </div>
  `;
}

// Рендеринг содержимого с поддержкой <thought> и каретки
function renderStreamingContent(rawText, containerEl, isLive = false) {
  let processedText = rawText;
  let thoughtHtml = '';

  // Проверяем наличие блока рассуждений модели Gemma 4 E4B: <thought>...</thought>
  const thoughtMatch = rawText.match(/<thought>([\s\S]*?)<\/thought>/);
  if (thoughtMatch) {
    const thoughtBody = thoughtMatch[1].trim();
    processedText = rawText.replace(/<thought>[\s\S]*?<\/thought>/, '').trim();

    thoughtHtml = `
      <div class="thought-accordion">
        <div class="thought-header" onclick="this.parentElement.classList.toggle('open')">
          <span class="flex items-center gap-1.5">
            <span>🧠</span> <strong>Ход рассуждения модели (Thinking Process)</strong>
          </span>
          <span class="text-[10px] text-[#64748b]">нажмите для раскрытия</span>
        </div>
        <div class="thought-content">${escapeHtml(thoughtBody)}</div>
      </div>
    `;
  } else if (rawText.startsWith('<thought>')) {
    // В процессе стриминга блока thought
    const partialThought = rawText.replace('<thought>', '');
    containerEl.innerHTML = `
      <div class="thought-accordion open">
        <div class="thought-header">
          <span class="flex items-center gap-1.5 text-[#10b981]">
            <span class="animate-pulse">🧠</span> <strong>Анализ контекста и генерация наставлений...</strong>
          </span>
        </div>
        <div class="thought-content">${escapeHtml(partialThought)}<span class="streaming-caret"></span></div>
      </div>
    `;
    return;
  }

  // Рендерим Markdown
  let html = renderMarkdown(processedText);

  if (isLive) {
    html += '<span class="streaming-caret"></span>';
  }

  containerEl.innerHTML = thoughtHtml + html;
  scrollChatToBottom();
}

// Markdown парсер с фоллбэком
function renderMarkdown(md) {
  if (window.marked && typeof window.marked.parse === 'function') {
    let html = window.marked.parse(md);
    // Оборачиваем pre блоки кнопками копирования
    html = html.replace(/<pre><code(?:\s+class="language-([^"]+)")?>([\s\S]*?)<\/code><\/pre>/gi, (match, lang, code) => {
      const language = lang || 'code';
      return `
        <div class="code-block-wrapper">
          <div class="code-block-header">
            <span>${language}</span>
            <button class="code-copy-btn" onclick="copyCodeFromBlock(this)" aria-label="Скопировать фрагмент кода">
              <span>📋</span> Копировать
            </button>
          </div>
          <pre><code>${code}</code></pre>
        </div>
      `;
    });
    return html;
  }

  // Фоллбэк если библиотека Marked недоступна
  return `<p class="whitespace-pre-wrap">${escapeHtml(md)}</p>`;
}

// Копирование кода в буфер обмена
window.copyCodeFromBlock = function(btn) {
  const wrapper = btn.closest('.code-block-wrapper');
  if (!wrapper) return;
  const codeEl = wrapper.querySelector('code');
  if (!codeEl) return;

  const textToCopy = codeEl.innerText || codeEl.textContent;
  navigator.clipboard.writeText(textToCopy).then(() => {
    btn.innerHTML = '<span>✅</span> Скопировано!';
    btn.classList.add('copied');
    setTimeout(() => {
      btn.innerHTML = '<span>📋</span> Копировать';
      btn.classList.remove('copied');
    }, 2000);
  }).catch(err => {
    console.warn('Не удалось скопировать код:', err);
  });
};

function attachCopyCodeButtons(container) {
  // Обработчики уже повешены через onclick
}

// Скелет сообщения наставника в чате
function createMentorMessageSkeleton() {
  const messagesArea = document.getElementById('messagesArea');
  const msgWrapper = document.createElement('div');
  msgWrapper.className = 'flex items-start gap-3 max-w-3xl animate-in fade-in duration-200';

  msgWrapper.innerHTML = `
    <div class="w-8 h-8 rounded-lg bg-[#10b981]/15 border border-[#10b981]/30 text-[#10b981] flex items-center justify-center text-sm shrink-0 mt-0.5">
      🧙‍♂️
    </div>
    <div class="flex-1 bg-[#151b2b] border border-[rgba(255,255,255,0.08)] rounded-xl p-4 shadow-lg min-w-0">
      <div class="flex items-center justify-between mb-2 pb-1.5 border-b border-[rgba(255,255,255,0.05)] flex-wrap gap-2">
        <div class="flex items-center gap-2">
          <span class="text-xs font-bold text-[#f8fafc]">Frodo AI Mentor</span>
          <div class="mentor-meta flex items-center gap-1.5">
            <span class="holad-badge holad-badge-muted text-[10px]">Генерация...</span>
          </div>
        </div>
        <div class="mentor-metrics flex items-center gap-1.5"></div>
      </div>
      <div class="mentor-content prose-dark text-xs sm:text-sm text-[#cbd5e1] leading-relaxed">
        <span class="streaming-caret"></span>
      </div>
      <div class="mentor-citation"></div>
    </div>
  `;

  messagesArea.appendChild(msgWrapper);
  scrollChatToBottom();

  return {
    messageCard: msgWrapper,
    contentEl: msgWrapper.querySelector('.mentor-content'),
    metaEl: msgWrapper.querySelector('.mentor-meta'),
    citationEl: msgWrapper.querySelector('.mentor-citation'),
    metricsEl: msgWrapper.querySelector('.mentor-metrics')
  };
}

function appendStudentMessage(text) {
  const messagesArea = document.getElementById('messagesArea');
  const msgWrapper = document.createElement('div');
  msgWrapper.className = 'flex items-start gap-3 justify-end max-w-3xl ml-auto animate-in fade-in duration-200';

  msgWrapper.innerHTML = `
    <div class="bg-[#10b981]/10 border border-[#10b981]/25 rounded-xl p-3.5 max-w-[85%] text-xs sm:text-sm text-[#f8fafc] shadow-md">
      <div class="flex items-center justify-between gap-3 mb-1 text-[11px] text-[#10b981] font-semibold">
        <span>${escapeHtml(state.user ? state.user.name : 'Студент')}</span>
        <span class="text-[10px] opacity-75 font-mono">Вы</span>
      </div>
      <div class="whitespace-pre-wrap leading-relaxed">${escapeHtml(text)}</div>
    </div>
    <div class="w-8 h-8 rounded-lg bg-emerald-700/30 border border-emerald-500/30 text-[#10b981] flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
      🎓
    </div>
  `;

  messagesArea.appendChild(msgWrapper);
  scrollChatToBottom();
}

function setSendButtonLoading(loading) {
  const sendBtn = document.getElementById('sendBtn');
  const sendIcon = document.getElementById('sendIcon');
  const sendSpinner = document.getElementById('sendSpinner');

  if (loading) {
    sendBtn.disabled = true;
    sendIcon.classList.add('hidden');
    sendSpinner.classList.remove('hidden');
  } else {
    sendBtn.disabled = false;
    sendIcon.classList.remove('hidden');
    sendSpinner.classList.add('hidden');
  }
}

function scrollChatToBottom() {
  const messagesArea = document.getElementById('messagesArea');
  if (messagesArea) {
    messagesArea.scrollTop = messagesArea.scrollHeight;
  }
}

// ==================== ПАНЕЛЬ ПРЕПОДАВАТЕЛЯ (ADMIN) ====================
function switchAdminTab(tabKey) {
  state.adminTab = tabKey;

  const btnMatrix = document.getElementById('tabBtnMatrix');
  const btnGap = document.getElementById('tabBtnGap');
  const btnRag = document.getElementById('tabBtnRag');

  const paneMatrix = document.getElementById('paneMatrix');
  const paneGap = document.getElementById('paneGap');
  const paneRag = document.getElementById('paneRag');

  // Сброс стилей кнопок
  [btnMatrix, btnGap, btnRag].forEach(b => {
    b.className = 'holad-btn-secondary text-xs py-2 px-4 font-semibold text-[#94a3b8] flex items-center gap-2';
  });

  // Скрытие панелей
  paneMatrix.classList.add('hidden');
  paneGap.classList.add('hidden');
  paneRag.classList.add('hidden');

  if (tabKey === 'matrix') {
    btnMatrix.className = 'holad-btn-secondary text-xs py-2 px-4 font-semibold text-[#10b981] bg-[#10b981]/15 border-[#10b981]/40 flex items-center gap-2';
    paneMatrix.classList.remove('hidden');
    loadAdminStudentsMatrix();
  } else if (tabKey === 'gap') {
    btnGap.className = 'holad-btn-secondary text-xs py-2 px-4 font-semibold text-[#f59e0b] bg-[#f59e0b]/15 border-[#f59e0b]/40 flex items-center gap-2';
    paneGap.classList.remove('hidden');
    loadAdminGapAnalysis();
  } else if (tabKey === 'rag') {
    btnRag.className = 'holad-btn-secondary text-xs py-2 px-4 font-semibold text-[#10b981] bg-[#10b981]/15 border-[#10b981]/40 flex items-center gap-2';
    paneRag.classList.remove('hidden');
  }
}

// Загрузка матрицы студентов (GET /api/admin/students)
async function loadAdminStudentsMatrix() {
  const tbody = document.getElementById('matrixTableBody');
  if (!tbody) return;

  tbody.innerHTML = `
    <tr>
      <td colspan="5" class="py-6 text-center text-[#94a3b8]">
        <div class="inline-block animate-spin w-5 h-5 border-2 border-[#10b981] border-t-transparent rounded-full mr-2"></div>
        Загрузка матрицы успеваемости студентов...
      </td>
    </tr>
  `;

  try {
    const res = await fetch('/api/admin/students', {
      headers: { 'Authorization': `Bearer ${state.token}` }
    });

    if (!res.ok) {
      if (res.status === 403) {
        tbody.innerHTML = `<tr><td colspan="5" class="py-6 text-center text-red-400">Доступ запрещен: требуется роль преподавателя (instructor).</td></tr>`;
        return;
      }
      throw new Error(`Статус ${res.status}`);
    }

    const students = await res.json();
    document.getElementById('statStudentsCount').textContent = students.length;

    if (!students.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="py-6 text-center text-[#94a3b8]">Студенты не найдены в базе данных.</td></tr>`;
      return;
    }

    tbody.innerHTML = '';

    students.forEach(item => {
      const student = item.student;
      const labs = item.labs || [];

      const tr = document.createElement('tr');
      tr.className = 'hover:bg-white/[0.02] transition-colors';

      // Колонка Студент
      let studentCol = `
        <td class="py-3 px-3">
          <div class="font-bold text-[#f8fafc]">${escapeHtml(student.name)}</div>
          <div class="text-[11px] text-[#94a3b8] font-mono">${escapeHtml(student.email || student.moodle_user_id)}</div>
        </td>
      `;

      // Колонки Лаб 1, 2, 3 с выпадающими списками статусов
      let labsCols = '';
      for (let i = 1; i <= 3; i++) {
        const labItem = labs.find(l => l.order_num === i) || { lab_id: i, status: 'not_started', grade: 0 };
        const status = labItem.status;
        
        let selectBg = 'bg-[#0b0f19] text-[#94a3b8] border-white/10';
        if (status === 'passed') selectBg = 'bg-[#10b981]/20 text-[#10b981] border-[#10b981]/40 font-bold';
        else if (status === 'in_progress') selectBg = 'bg-[#f59e0b]/20 text-[#f59e0b] border-[#f59e0b]/40 font-bold';

        labsCols += `
          <td class="py-3 px-3">
            <select 
              class="lab-status-select text-xs py-1 px-2 rounded border focus:outline-none focus:ring-1 focus:ring-[#10b981] ${selectBg}"
              data-user-id="${student.id}"
              data-lab-id="${labItem.lab_id}"
              aria-label="Изменить статус Лабы ${i} для студента ${escapeHtml(student.name)}"
            >
              <option value="not_started" ${status === 'not_started' ? 'selected' : ''}>⚪ Не начато</option>
              <option value="in_progress" ${status === 'in_progress' ? 'selected' : ''}>🟡 В процессе</option>
              <option value="passed" ${status === 'passed' ? 'selected' : ''}>🟢 Зачтено (Мастер)</option>
            </select>
          </td>
        `;
      }

      // Быстрое действие
      let actionsCol = `
        <td class="py-3 px-3">
          <button 
            class="holad-btn-secondary text-[11px] py-1 px-2.5 min-h-[28px] view-student-chat-btn"
            data-user-id="${student.id}"
            aria-label="Открыть чат от лица студента"
          >
            Войти как студент ↗
          </button>
        </td>
      `;

      tr.innerHTML = studentCol + labsCols + actionsCol;
      tbody.appendChild(tr);
    });

    // Навешиваем слушатели на изменение селекторов статуса лабы
    document.querySelectorAll('.lab-status-select').forEach(select => {
      select.addEventListener('change', async (e) => {
        const userId = parseInt(e.target.getAttribute('data-user-id'));
        const labId = parseInt(e.target.getAttribute('data-lab-id'));
        const newStatus = e.target.value;
        const newGrade = newStatus === 'passed' ? 100.0 : (newStatus === 'in_progress' ? 50.0 : 0.0);

        await updateStudentLabStatus(userId, labId, newStatus, newGrade, e.target);
      });
    });

    // Навешиваем слушатели на кнопку "Войти как студент"
    document.querySelectorAll('.view-student-chat-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        await loginDemoRole('student');
      });
    });

  } catch (err) {
    console.error('[Frodo Matrix] Ошибка загрузки матрицы:', err);
    tbody.innerHTML = `<tr><td colspan="5" class="py-6 text-center text-red-400">Ошибка: ${escapeHtml(err.message)}</td></tr>`;
  }
}

// Отправка POST /api/admin/student/progress
async function updateStudentLabStatus(userId, labId, status, grade, selectEl) {
  try {
    const res = await fetch('/api/admin/student/progress', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${state.token}`
      },
      body: JSON.stringify({
        user_id: userId,
        lab_id: labId,
        status: status,
        grade: grade
      })
    });

    if (!res.ok) throw new Error(`Статус ${res.status}`);

    const updated = await res.json();
    
    // Мгновенная подсветка
    if (status === 'passed') {
      selectEl.className = 'lab-status-select text-xs py-1 px-2 rounded border focus:outline-none focus:ring-1 focus:ring-[#10b981] bg-[#10b981]/20 text-[#10b981] border-[#10b981]/40 font-bold';
      showToast(`Лаба ${labId} успешно зачтена! Разблокирован Режим Мастера.`, 'success');
    } else if (status === 'in_progress') {
      selectEl.className = 'lab-status-select text-xs py-1 px-2 rounded border focus:outline-none focus:ring-1 focus:ring-[#10b981] bg-[#f59e0b]/20 text-[#f59e0b] border-[#f59e0b]/40 font-bold';
      showToast(`Статус Лабы ${labId} переведен в «В процессе» (Режим Сократа).`, 'warning');
    } else {
      selectEl.className = 'lab-status-select text-xs py-1 px-2 rounded border focus:outline-none focus:ring-1 focus:ring-[#10b981] bg-[#0b0f19] text-[#94a3b8] border-white/10';
      showToast(`Статус Лабы ${labId} сброшен в «Не начато».`, 'warning');
    }

    // Если обновляли лабу для demo student, синхронизируем локальный прогресс
    const localProg = state.progress.find(p => p.lab_id === labId);
    if (localProg) {
      localProg.status = status;
      localProg.grade = grade;
      localProg.can_master_mode = (status === 'passed');
      updateMentorModeBanner();
      renderLabsSelector();
    }

  } catch (err) {
    console.error('[Frodo Admin] Ошибка обновления прогресса:', err);
    showToast(`Не удалось обновить статус: ${err.message}`, 'danger');
  }
}

// Загрузка неотвеченных вопросов (GET /api/admin/unanswered)
async function loadAdminGapAnalysis() {
  const tbody = document.getElementById('gapTableBody');
  if (!tbody) return;

  tbody.innerHTML = `
    <tr>
      <td colspan="4" class="py-6 text-center text-[#94a3b8]">
        <div class="inline-block animate-spin w-5 h-5 border-2 border-[#f59e0b] border-t-transparent rounded-full mr-2"></div>
        Анализ отклоненных Guardrail запросов...
      </td>
    </tr>
  `;

  try {
    const res = await fetch('/api/admin/unanswered', {
      headers: { 'Authorization': `Bearer ${state.token}` }
    });

    if (!res.ok) throw new Error(`Статус ${res.status}`);

    const list = await res.json();
    document.getElementById('statUnansweredCount').textContent = list.length;

    if (!list.length) {
      tbody.innerHTML = `<tr><td colspan="4" class="py-6 text-center text-[#94a3b8]">Неотвеченных вопросов нет. Все запросы успешно покрыты базой знаний!</td></tr>`;
      return;
    }

    tbody.innerHTML = '';

    list.forEach(item => {
      const tr = document.createElement('tr');
      tr.className = 'hover:bg-white/[0.02] transition-colors';

      const dateStr = item.created_at ? new Date(item.created_at).toLocaleString('ru-RU') : 'Недавно';
      const score = item.score !== null ? item.score : 0.0;
      const scoreColor = score < 0.42 ? 'text-red-400 bg-red-500/10 border-red-500/20' : 'text-amber-400 bg-amber-500/10 border-amber-500/20';

      tr.innerHTML = `
        <td class="py-3 px-3 text-[#94a3b8] font-mono whitespace-nowrap text-[11px]">${escapeHtml(dateStr)}</td>
        <td class="py-3 px-3">
          <div class="font-medium text-[#f8fafc] text-xs">${escapeHtml(item.question)}</div>
          <div class="text-[10px] text-[#64748b]">Студент: ${escapeHtml(item.user_name || 'Не указан')}</div>
        </td>
        <td class="py-3 px-3 font-mono">
          <span class="holad-badge ${scoreColor} text-[10px]">${score}</span>
        </td>
        <td class="py-3 px-3 text-xs text-[#cbd5e1]">
          <span class="inline-flex items-center gap-1.5 bg-red-500/10 text-red-300 border border-red-500/20 px-2 py-0.5 rounded text-[11px]">
            🛡️ ${escapeHtml(item.reason || 'Guardrail rejection')}
          </span>
        </td>
      `;

      tbody.appendChild(tr);
    });

  } catch (err) {
    console.error('[Frodo Gap] Ошибка загрузки пробелов:', err);
    tbody.innerHTML = `<tr><td colspan="4" class="py-6 text-center text-red-400">Ошибка: ${escapeHtml(err.message)}</td></tr>`;
  }
}

// Переиндексация базы знаний (POST /api/reindex)
async function reindexKnowledgeBase() {
  const btn = document.getElementById('reindexBtn');
  const resultArea = document.getElementById('reindexResultArea');
  const resultText = document.getElementById('reindexResultText');

  btn.disabled = true;
  btn.innerHTML = `
    <span class="inline-block animate-spin w-4 h-4 border-2 border-black border-t-transparent rounded-full mr-1.5"></span>
    Индексация методичек курса...
  `;

  try {
    const res = await fetch('/api/reindex', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${state.token}` }
    });

    if (!res.ok) throw new Error(`Статус ${res.status}`);

    const data = await res.json();
    resultArea.classList.remove('hidden');
    resultText.textContent = `Успешно проиндексировано фрагментов: ${data.indexed_chunks}`;
    showToast(`База знаний обновлена: ${data.indexed_chunks} чанков проиндексировано`, 'success');
  } catch (err) {
    console.error('[Frodo Reindex] Ошибка переиндексации:', err);
    showToast(`Ошибка переиндексации: ${err.message}`, 'danger');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `⚡ Переиндексировать базу знаний`;
  }
}

// Проверка доступности локальных моделей
async function checkSystemHealth() {
  try {
    const res = await fetch('/api/health');
    if (res.ok) {
      const data = await res.json();
      const dotEmbedder = document.getElementById('embedderStatusDot');
      const dotLlm = document.getElementById('llmStatusDot');

      if (dotEmbedder) dotEmbedder.className = 'status-dot online';
      if (dotLlm) dotLlm.className = 'status-dot online';
    }
  } catch (e) {
    console.warn('[Frodo Health] Локальный API проверки статуса оффлайн:', e);
  }
}

// ==================== TOAST УВЕДОМЛЕНИЯ ====================
function showToast(message, type = 'success', duration = 3500) {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;

  let icon = '✅';
  if (type === 'warning') icon = '⚠️';
  if (type === 'danger') icon = '❌';

  toast.innerHTML = `
    <span class="text-base">${icon}</span>
    <span class="flex-1 leading-snug">${escapeHtml(message)}</span>
    <button class="text-[#94a3b8] hover:text-[#f8fafc] text-xs p-1" onclick="this.parentElement.remove()" aria-label="Закрыть уведомление">✕</button>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('toast-out');
    setTimeout(() => toast.remove(), 250);
  }, duration);
}

// Экранирование HTML для предотвращения XSS
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
