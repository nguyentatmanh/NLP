const state = {
  mode: 'open_domain',
  config: null,
  sending: false,
};

const chatScroll = document.getElementById('chatScroll');
const messageInput = document.getElementById('messageInput');
const contextInput = document.getElementById('contextInput');
const topKRetrieve = document.getElementById('topKRetrieve');
const topKReader = document.getElementById('topKReader');
const sendBtn = document.getElementById('sendBtn');
const contextPanel = document.getElementById('contextPanel');
const modeButtons = Array.from(document.querySelectorAll('.mode-btn'));
const serverStatus = document.getElementById('serverStatus');
const reindexBtn = document.getElementById('reindexBtn');

function setMode(mode) {
  state.mode = mode;
  modeButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.mode === mode));
  contextPanel.classList.toggle('hidden', mode !== 'context');
}

function scrollToBottom(smooth = true) {
  chatScroll.scrollTo({ top: chatScroll.scrollHeight, behavior: smooth ? 'smooth' : 'auto' });
}

function createMessage(role, badge, html, sources = []) {
  const tpl = document.getElementById('messageTemplate');
  const node = tpl.content.firstElementChild.cloneNode(true);
  node.classList.add(role === 'user' ? 'user' : 'assistant');
  node.querySelector('.message-role').textContent = role === 'user' ? 'Bạn' : 'Hệ thống';
  node.querySelector('.message-badge').textContent = badge;
  node.querySelector('.message-body').innerHTML = html;
  const sourceList = node.querySelector('.source-list');
  if (!sources.length) {
    sourceList.remove();
  } else {
    sources.forEach(item => sourceList.appendChild(createSourceCard(item)));
  }
  chatScroll.appendChild(node);
  scrollToBottom();
}

function createSourceCard(item) {
  const card = document.createElement('div');
  card.className = 'source-card';
  const title = item.title || 'Nguồn';
  const source = item.source || '';
  const retrieval = typeof item.retrieval_score === 'number' ? item.retrieval_score.toFixed(3) : null;
  const reader = typeof item.reader_score === 'number' ? item.reader_score.toFixed(3) : null;
  const badges = [
    source ? `<span class="source-pill">${escapeHtml(source)}</span>` : '',
    retrieval ? `<span class="source-pill">retrieve ${retrieval}</span>` : '',
    reader ? `<span class="source-pill">reader ${reader}</span>` : ''
  ].filter(Boolean).join('');
  card.innerHTML = `
    <div class="source-head">
      <div class="source-title">${escapeHtml(title)}</div>
      <div class="source-badges">${badges}</div>
    </div>
    <div class="source-excerpt">${escapeHtml(item.excerpt || '')}</div>
  `;
  return card;
}

function escapeHtml(text) {
  return String(text ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function createTyping() {
  const tpl = document.getElementById('typingTemplate');
  const node = tpl.content.firstElementChild.cloneNode(true);
  chatScroll.appendChild(node);
  scrollToBottom();
  return node;
}

function normalizeAnswerMode(mode) {
  if (mode === 'reader') return 'Trích xuất';
  if (mode === 'fallback') return 'Tổng hợp';
  if (mode === 'no_answer') return 'Không khớp';
  return 'Hoàn tất';
}

async function sendMessage() {
  if (state.sending) return;
  const message = messageInput.value.trim();
  if (!message) return;
  if (state.mode === 'context' && !contextInput.value.trim()) {
    createMessage('assistant', 'Thiếu ngữ cảnh', '<p>Vui lòng dán đoạn văn trước khi hỏi theo ngữ cảnh.</p>');
    return;
  }

  createMessage('user', state.mode === 'context' ? 'Theo đoạn văn' : 'Tra cứu kho dữ liệu', `<p>${escapeHtml(message)}</p>`);
  messageInput.value = '';
  autoGrow(messageInput);
  state.sending = true;
  sendBtn.disabled = true;
  const typingNode = createTyping();

  try {
    const payload = {
      message,
      mode: state.mode,
      context: state.mode === 'context' ? contextInput.value : null,
      top_k_retrieve: Number(topKRetrieve.value || 6),
      top_k_reader: Number(topKReader.value || 4),
    };

    const res = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Không thể xử lý yêu cầu.');
    }

    const data = await res.json();
    typingNode.remove();
    createMessage('assistant', normalizeAnswerMode(data.answer_mode), data.html, data.sources || []);
    serverStatus.textContent = 'Đã phản hồi';
  } catch (error) {
    typingNode.remove();
    createMessage('assistant', 'Lỗi', `<p>${escapeHtml(error.message || 'Đã xảy ra lỗi.')}</p>`);
    serverStatus.textContent = 'Có lỗi';
  } finally {
    state.sending = false;
    sendBtn.disabled = false;
  }
}

function autoGrow(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 180) + 'px';
}

async function loadConfig() {
  try {
    const res = await fetch('/config');
    const config = await res.json();
    state.config = config;
    document.getElementById('brandName').textContent = config.app_name || 'Lumina';
    document.getElementById('brandTagline').textContent = config.app_tagline || 'Kho tri thức nội bộ';
    document.title = config.app_name || 'Lumina';
    document.getElementById('retrieverBadge').textContent = config.retriever || '-';
    document.getElementById('readerBadge').textContent = config.reader_model || '-';
    document.getElementById('fallbackBadge').textContent = config.fallback_provider || 'disabled';
  } catch {
    serverStatus.textContent = 'Không kết nối';
  }
}

async function reindex() {
  reindexBtn.disabled = true;
  const oldLabel = reindexBtn.textContent;
  reindexBtn.textContent = 'Đang nạp...';
  try {
    const res = await fetch('/reindex', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
    if (!res.ok) throw new Error('Không thể nạp lại kho dữ liệu.');
    await loadConfig();
    serverStatus.textContent = 'Đã nạp lại';
  } catch (error) {
    createMessage('assistant', 'Lỗi', `<p>${escapeHtml(error.message || 'Không thể nạp lại kho dữ liệu.')}</p>`);
  } finally {
    reindexBtn.disabled = false;
    reindexBtn.textContent = oldLabel;
  }
}

messageInput.addEventListener('input', () => autoGrow(messageInput));
messageInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
});
sendBtn.addEventListener('click', sendMessage);
reindexBtn.addEventListener('click', reindex);
modeButtons.forEach(btn => btn.addEventListener('click', () => setMode(btn.dataset.mode)));

setMode('open_domain');
autoGrow(messageInput);
loadConfig();
