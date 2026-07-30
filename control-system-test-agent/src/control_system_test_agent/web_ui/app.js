const conversation = document.querySelector('#conversation')
const form = document.querySelector('#chatForm')
const input = document.querySelector('#messageInput')
const sendButton = document.querySelector('#sendButton')
const newTaskButton = document.querySelector('#newTask')

const state = {
  taskId: localStorage.getItem('core-agent-task-id') || crypto.randomUUID(),
  sessionId: crypto.randomUUID()
}
localStorage.setItem('core-agent-task-id', state.taskId)

function token() {
  return localStorage.getItem('genb-client-token') || localStorage.getItem('core-component-agent-token') || ''
}

function addMessage(role, text) {
  const article = document.createElement('article')
  article.className = `message ${role === 'user' ? 'user-message' : 'assistant-message'}`
  if (role !== 'user') {
    const avatar = document.createElement('div')
    avatar.className = 'avatar'
    avatar.textContent = 'AI'
    article.appendChild(avatar)
  }
  const bubble = document.createElement('div')
  bubble.className = 'bubble'
  bubble.textContent = text
  article.appendChild(bubble)
  conversation.appendChild(article)
  conversation.scrollTop = conversation.scrollHeight
}

function addSkill(skill) {
  if (!skill?.skillMarkdown) return
  const card = document.createElement('section')
  card.className = 'skill-card'
  const title = document.createElement('strong')
  title.textContent = `${skill.name || 'Skill'} · v${skill.version || 1}`
  const content = document.createElement('pre')
  content.textContent = skill.skillMarkdown
  card.append(title, content)
  conversation.appendChild(card)
}

function addDiagnostics(data) {
  const details = document.createElement('details')
  details.className = 'diagnostics'
  const summary = document.createElement('summary')
  summary.textContent = '查看本轮能力调用详情'
  const body = document.createElement('div')
  const d = data.diagnostics
  body.textContent = `组件：${d.components.join(' / ')}\n模型：${d.provider} · ${d.model}\n记忆命中：${d.context_message_count} 条\nToken：${d.input_tokens} 输入 / ${d.output_tokens} 输出\n请求：${d.request_id}`
  details.append(summary, body)
  conversation.appendChild(details)
}

async function send(message) {
  const accessToken = token()
  if (!accessToken) {
    addMessage('assistant', '当前页面没有检测到 GenB 登录状态。请从统一门户登录后，通过“我的智能体”打开本页面。')
    return
  }
  addMessage('user', message)
  sendButton.disabled = true
  sendButton.textContent = '思考中'
  try {
    const response = await fetch('./api/customer/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
      body: JSON.stringify({ taskId: state.taskId, sessionId: state.sessionId, message })
    })
    const payload = await response.json()
    if (!response.ok) throw new Error(payload.detail || '智能体暂时无法回答')
    addMessage('assistant', payload.data.answer)
    addSkill(payload.data.skill)
    addDiagnostics(payload.data)
  } catch (error) {
    addMessage('assistant', error instanceof Error ? error.message : '调用失败，请稍后重试。')
  } finally {
    sendButton.disabled = false
    sendButton.textContent = '发送'
    input.focus()
  }
}

form.addEventListener('submit', (event) => {
  event.preventDefault()
  const message = input.value.trim()
  if (!message) return
  input.value = ''
  void send(message)
})

input.addEventListener('input', () => {
  input.style.height = 'auto'
  input.style.height = `${Math.min(input.scrollHeight, 150)}px`
})

document.querySelectorAll('[data-prompt]').forEach((button) => {
  button.addEventListener('click', () => {
    input.value = button.dataset.prompt
    input.focus()
  })
})

newTaskButton.addEventListener('click', () => {
  state.taskId = crypto.randomUUID()
  state.sessionId = crypto.randomUUID()
  localStorage.setItem('core-agent-task-id', state.taskId)
  conversation.querySelectorAll('.message:not(.intro-message), .skill-card, .diagnostics').forEach((node) => node.remove())
  addMessage('assistant', '新任务已经开始。你可以直接描述目标。')
})
