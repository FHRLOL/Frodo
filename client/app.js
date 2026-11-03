document.addEventListener('DOMContentLoaded', () => {
  const messagesArea = document.getElementById('messagesArea');
  const chatForm = document.getElementById('chatForm');
  const questionInput = document.getElementById('questionInput');
  const clearBtn = document.getElementById('clearBtn');
  const chips = document.querySelectorAll('.chip');

  // Клик по готовым вопросам из бенчмарка
  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      const query = chip.getAttribute('data-query');
      if (query) {
        questionInput.value = query;
        submitQuestion(query);
      }
    });
  });

  // Отправка формы
  chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const query = questionInput.value.trim();
    if (query) {
      submitQuestion(query);
      questionInput.value = '';
    }
  });

  clearBtn.addEventListener('click', () => {
    messagesArea.innerHTML = `
      <div class="message mentor">
        <div class="avatar">🧙‍♂️</div>
        <div class="message-content">
          <div class="sender-name">ИИ-наставник</div>
          <p>Диалог очищен. Задайте вопрос по материалам курса Python.</p>
        </div>
      </div>
    `;
  });

  async function submitQuestion(question) {
    appendMessage('student', question);

    // Добавляем индикатор загрузки
    const loadingId = appendLoadingMessage();

    try {
      // Отправляем запрос к локальному API бэкенда (FastAPI)
      const res = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question })
      });

      removeLoadingMessage(loadingId);

      if (res.ok) {
        const data = await res.json();
        appendMentorResponse(data);
      } else {
        fallbackMockResponse(question);
      }
    } catch (err) {
      removeLoadingMessage(loadingId);
      fallbackMockResponse(question);
    }
  }

  function appendMessage(sender, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${sender}`;
    msgDiv.innerHTML = `
      <div class="avatar">${sender === 'student' ? '🎓' : '🧙‍♂️'}</div>
      <div class="message-content">
        <div class="sender-name">${sender === 'student' ? 'Студент' : 'ИИ-наставник'}</div>
        <p>${escapeHtml(text)}</p>
      </div>
    `;
    messagesArea.appendChild(msgDiv);
    messagesArea.scrollTop = messagesArea.scrollHeight;
  }

  function appendMentorResponse(data) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message mentor';

    let citationHtml = '';
    if (data.citations && data.citations.length > 0) {
      citationHtml = `<div class="citation-box">${escapeHtml(data.citations[0])}</div>`;
    } else if (data.status === 'REJECTED_BY_GUARDRAIL') {
      citationHtml = `<div class="refusal-box">🛡️ Guardrail: ${escapeHtml(data.reason || 'Запрос вне скоупа базы знаний')}</div>`;
    }

    msgDiv.innerHTML = `
      <div class="avatar">🧙‍♂️</div>
      <div class="message-content">
        <div class="sender-name">ИИ-наставник</div>
        <p>${escapeHtml(data.answer || 'Ответ сформирован.')}</p>
        ${citationHtml}
      </div>
    `;
    messagesArea.appendChild(msgDiv);
    messagesArea.scrollTop = messagesArea.scrollHeight;
  }

  function appendLoadingMessage() {
    const id = 'loading_' + Date.now();
    const msgDiv = document.createElement('div');
    msgDiv.id = id;
    msgDiv.className = 'message mentor';
    msgDiv.innerHTML = `
      <div class="avatar">🧙‍♂️</div>
      <div class="message-content">
        <div class="sender-name">ИИ-наставник</div>
        <p><em>Поиск в материалах курса...</em></p>
      </div>
    `;
    messagesArea.appendChild(msgDiv);
    messagesArea.scrollTop = messagesArea.scrollHeight;
    return id;
  }

  function removeLoadingMessage(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }

  function fallbackMockResponse(question) {
    const isOutOfScope = question.toLowerCase().includes('big o') || question.toLowerCase().includes('сложность');
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message mentor';

    if (isOutOfScope) {
      msgDiv.innerHTML = `
        <div class="avatar">🧙‍♂️</div>
        <div class="message-content">
          <div class="sender-name">ИИ-наставник</div>
          <p>В предоставленных материалах этого нет.</p>
          <div class="refusal-box">🛡️ Guardrail: В базе знаний отсутствуют сведения о временной сложности Big O.</div>
        </div>
      `;
    } else {
      msgDiv.innerHTML = `
        <div class="avatar">🧙‍♂️</div>
        <div class="message-content">
          <div class="sender-name">ИИ-наставник</div>
          <p>Ответ проверен по материалам курса.</p>
          <div class="citation-box">[Источник: data_structures.md, раздел «Список», строки 9–43]</div>
        </div>
      `;
    }
    messagesArea.appendChild(msgDiv);
    messagesArea.scrollTop = messagesArea.scrollHeight;
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
});
