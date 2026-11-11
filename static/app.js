const uploadForm = document.querySelector('#upload-form');
const fileInput = document.querySelector('#file-input');
const uploadButton = document.querySelector('#upload-button');
const uploadStatus = document.querySelector('#upload-status');
const documentList = document.querySelector('#document-list');
const documentCount = document.querySelector('#document-count');
const chatForm = document.querySelector('#chat-form');
const questionInput = document.querySelector('#question-input');
const sendButton = document.querySelector('#send-button');
const messages = document.querySelector('#messages');
const welcome = document.querySelector('#welcome');
const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function renderDocuments(documents) {
  documentCount.textContent = documents.length;
  documentList.replaceChildren();
  if (!documents.length) {
    const empty = document.createElement('li');
    empty.className = 'empty-library';
    empty.textContent = 'Your documents will appear here.';
    documentList.append(empty);
    return;
  }

  for (const doc of documents) {
    const row = document.createElement('li');
    row.className = 'document-row';
    const icon = document.createElement('span');
    icon.className = 'file-icon';
    icon.setAttribute('aria-hidden', 'true');
    icon.textContent = doc.name.split('.').pop().slice(0, 4).toUpperCase();
    const name = document.createElement('span');
    name.className = 'file-name';
    name.title = `${doc.name} · ${formatSize(doc.bytes)}`;
    name.textContent = doc.name;
    row.append(icon, name);
    documentList.append(row);
  }
}

async function refreshDocuments() {
  const response = await fetch('/api/documents');
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Could not load documents.');
  renderDocuments(data.documents);
}

function addMessage(role, text, { pending = false, error = false } = {}) {
  welcome.hidden = true;
  const message = document.createElement('article');
  message.className = `message ${role}${pending ? ' pending' : ''}`;
  const label = document.createElement('p');
  label.className = 'message-label';
  const mark = document.createElement('span');
  mark.className = 'message-mark';
  mark.setAttribute('aria-hidden', 'true');
  mark.textContent = role === 'assistant' ? 'F' : 'Y';
  label.append(mark, document.createTextNode(role === 'assistant' ? 'FIELDNOTES' : 'YOU'));
  const body = document.createElement('div');
  body.className = `message-body${error ? ' error-message' : ''}`;
  body.textContent = text;
  message.append(label, body);
  messages.append(message);
  message.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  return { message, body };
}

uploadButton.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', async () => {
  const [file] = fileInput.files;
  if (!file) return;
  uploadStatus.classList.remove('error');
  uploadStatus.textContent = `Adding ${file.name}...`;
  uploadButton.disabled = true;
  const formData = new FormData();
  formData.append('file', file);
  try {
    const response = await fetch('/api/documents', {
      method: 'POST',
      headers: { 'X-CSRF-Token': csrfToken },
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Upload failed.');
    uploadStatus.textContent = `Added ${data.document.name}`;
    await refreshDocuments();
  } catch (error) {
    uploadStatus.classList.add('error');
    uploadStatus.textContent = error.message;
  } finally {
    uploadButton.disabled = false;
    fileInput.value = '';
  }
});

chatForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!question) return;
  addMessage('user', question);
  questionInput.value = '';
  questionInput.style.height = 'auto';
  const reply = addMessage('assistant', 'Searching your documents...', { pending: true });
  sendButton.disabled = true;
  try {
    const response = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
      body: JSON.stringify({ question }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'The question could not be answered.');
    reply.body.textContent = data.answer || 'The model returned an empty answer.';
    reply.message.classList.remove('pending');
  } catch (error) {
    reply.body.textContent = error.message;
    reply.body.classList.add('error-message');
    reply.message.classList.remove('pending');
  } finally {
    sendButton.disabled = false;
    questionInput.focus();
  }
});

questionInput.addEventListener('input', () => {
  questionInput.style.height = 'auto';
  questionInput.style.height = `${Math.min(questionInput.scrollHeight, 140)}px`;
});

questionInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});

document.querySelectorAll('.suggestion').forEach((button) => {
  button.addEventListener('click', () => {
    questionInput.value = button.textContent;
    questionInput.focus();
    questionInput.dispatchEvent(new Event('input'));
  });
});

refreshDocuments().catch((error) => {
  uploadStatus.classList.add('error');
  uploadStatus.textContent = error.message;
});
