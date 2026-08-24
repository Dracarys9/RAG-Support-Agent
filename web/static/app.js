const messagesEl = document.querySelector('#messages');
const form = document.querySelector('#chat-form');
const input = document.querySelector('#message-input');
const sendButton = document.querySelector('#send-button');
const newChatButton = document.querySelector('#new-chat');
const statusDot = document.querySelector('#status-dot');
const statusText = document.querySelector('#status-text');
const modeValue = document.querySelector('#mode-value');
const sourceCount = document.querySelector('#source-count');
const sourceArea = document.querySelector('#source-area');
const sourceList = document.querySelector('#source-list');
const handoffArea = document.querySelector('#handoff-area');
const characterCount = document.querySelector('#character-count');
const toggleDetails = document.querySelector('#toggle-details');
const detailsContent = document.querySelector('#details-content');

let sessionId = null;

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function formatAnswer(value) {
  let html = escapeHtml(value);
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  return html.split(/\n\s*\n/).map((paragraph) => `<p>${paragraph.replaceAll('\n', '<br>')}</p>`).join('');
}

function timeLabel() {
  return new Intl.DateTimeFormat([], { hour: 'numeric', minute: '2-digit' }).format(new Date());
}

function addMessage(role, text, pending = false) {
  const article = document.createElement('article');
  article.className = `message ${role}${pending ? ' pending' : ''}`;
  article.innerHTML = `
    <div class="message-avatar">${role === 'assistant' ? 'AR' : 'YOU'}</div>
    <div class="message-stack">
      <div class="message-meta"><strong>${role === 'assistant' ? 'Aster & Row' : 'You'}</strong><span>${timeLabel()}</span></div>
      <div class="bubble">${pending ? '<p>Thinking…</p>' : formatAnswer(text)}</div>
    </div>
  `;
  messagesEl.appendChild(article);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return article;
}

function setBusy(isBusy) {
  sendButton.disabled = isBusy;
  input.disabled = isBusy;
  sendButton.innerHTML = isBusy ? '<span class="spinner" aria-label="Sending"></span>' : '<span aria-hidden="true">↑</span>';
}

function updateDetails(data) {
  const mode = data.generation_mode === 'llm' ? 'Gemini LLM' : 'Local fallback';
  modeValue.textContent = mode;
  sourceCount.textContent = data.tool_used === 'order_lookup'
    ? 'Order lookup'
    : `${data.sources?.length || 0} source${data.sources?.length === 1 ? '' : 's'}`;
  sourceList.replaceChildren();

  (data.retrieved_passages || []).slice(0, 6).forEach((passage) => {
    const card = document.createElement('div');
    card.className = 'source-card';
    card.innerHTML = `<b>${escapeHtml(passage.file_name || 'Knowledge base')}</b>${escapeHtml(passage.heading || '')}<br><span>match score ${escapeHtml(passage.score ?? '—')}</span>`;
    sourceList.appendChild(card);
  });
  sourceArea.classList.toggle('hidden', !data.retrieved_passages?.length);

  if (data.handoff) {
    handoffArea.textContent = 'Human help is recommended for this request. The assistant did not complete any unsupported action.';
    handoffArea.classList.remove('hidden');
  } else {
    handoffArea.classList.add('hidden');
  }
}

async function checkHealth() {
  try {
    const response = await fetch('/api/health');
    const data = await response.json();
    statusDot.className = 'status-dot online';
    statusText.textContent = data.llm_enabled ? `Connected · ${data.model}` : 'Connected · local mode';
  } catch (error) {
    statusDot.className = 'status-dot offline';
    statusText.textContent = 'Support server is not available';
  }
}

async function sendMessage(message) {
  const pending = addMessage('assistant', '', true);
  setBusy(true);
  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, message }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'The support server could not answer.');
    sessionId = data.session_id;
    pending.classList.remove('pending');
    pending.querySelector('.bubble').innerHTML = formatAnswer(data.answer);
    updateDetails(data);
  } catch (error) {
    pending.remove();
    addMessage('assistant', `I could not reach the support server. ${error.message}`);
  } finally {
    setBusy(false);
    input.focus();
  }
}

form.addEventListener('submit', (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message || sendButton.disabled) return;
  addMessage('user', message);
  input.value = '';
  input.style.height = 'auto';
  characterCount.textContent = '0 / 2,000';
  sendMessage(message);
});

input.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

input.addEventListener('input', () => {
  input.style.height = 'auto';
  input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
  characterCount.textContent = `${input.value.length.toLocaleString()} / 2,000`;
});

document.querySelectorAll('[data-question]').forEach((button) => {
  button.addEventListener('click', () => {
    input.value = button.dataset.question;
    input.dispatchEvent(new Event('input'));
    input.focus();
  });
});

toggleDetails.addEventListener('click', () => {
  const isCollapsed = detailsContent.classList.toggle('is-collapsed');
  toggleDetails.textContent = isCollapsed ? 'Show' : 'Hide';
  toggleDetails.setAttribute('aria-expanded', String(!isCollapsed));
});

newChatButton.addEventListener('click', async () => {
  try {
    const response = await fetch('/api/reset', { method: 'POST' });
    sessionId = (await response.json()).session_id;
  } catch (error) {
    sessionId = null;
  }
  messagesEl.innerHTML = `
    <div class="day-divider"><span>Today</span></div>
    <article class="message assistant welcome-message">
      <div class="message-avatar">AR</div>
      <div class="message-stack">
        <div class="message-meta"><strong>Aster & Row</strong><span>${timeLabel()}</span></div>
        <div class="bubble"><p>New conversation started. What can I help you with?</p></div>
      </div>
    </article>
  `;
  modeValue.textContent = '—';
  sourceCount.textContent = '—';
  sourceArea.classList.add('hidden');
  handoffArea.classList.add('hidden');
  input.focus();
});

checkHealth();
