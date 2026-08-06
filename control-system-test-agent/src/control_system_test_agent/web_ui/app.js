const uid = (prefix) => `${prefix}-${crypto.randomUUID()}`

const scenarioDefinitions = {
  short: {
    title: '记住本次交流',
    subtitle: '告诉智能体一件事，再问问它是否还记得。',
    heading: '本次交流记忆体验',
    hint: '预计需要2轮对话',
    goal: '它能记住刚刚聊过的内容吗？',
    goalText: '先告诉它一件具体的事，再用下一句话追问。测试标识会在后台自动保持一致。',
    success: '第二轮能准确说明你刚才告诉它的内容，并明确显示“本次交流记忆验证成功”。',
    stages: ['告诉它一件事', '追问刚才的内容', '确认是否记住'],
    initial: '你好，我们来做一个很简单的记忆体验。\n\n请告诉我一件具体的事，例如你正在为哪家公司办理什么业务，以及你偏好怎样的方案。',
    suggestions: ['我正在为A公司办理授信，我偏好低风险方案']
  },
  long: {
    title: '跨会话记住我',
    subtitle: '告诉智能体一个长期偏好，换个会话后再问它。',
    heading: '跨会话长期记忆体验',
    hint: '预计需要2次交流和1次会话切换',
    goal: '换一个会话后，它还认识你的偏好吗？',
    goalText: '先说一个长期、稳定且不敏感的偏好。保存成功后，新建一个看得见的对话；旧对话仍保留在上方，可随时切回。',
    success: '新会话中仍能找回你的偏好，并说明它来自之前的对话，而不是本次临时上下文。',
    stages: ['告诉它长期偏好', '开始一个新会话', '询问并确认记忆'],
    initial: '这次我们测试长期记忆。请告诉我一个希望以后仍然记得的稳定偏好。\n\n不要填写密码、验证码或其他敏感信息。',
    suggestions: ['我长期偏好稳健、低波动的授信方案']
  },
  skill: {
    title: '一步步生成Skill',
    subtitle: '先说想生成什么，智能体会逐步追问，准备好后再生成。',
    heading: 'Skill共创体验',
    hint: '轮数取决于需求是否完整',
    goal: '它会先理解和澄清，而不是直接拼一个结果吗？',
    goalText: '用自然语言描述目标。智能体会追问输入、输出、规则和边界，信息足够后自动生成可查看的Skill。',
    success: '未说清楚时继续提问；关键信息完整后才生成Skill，并给出名称、版本和完整正文。',
    stages: ['说出想生成什么', '回答澄清问题', '生成并检查Skill'],
    initial: '你想生成一个什么样的Skill？\n\n先用一句话告诉我目标即可。我会根据你的回答继续询问，直到信息足够再生成。',
    suggestions: ['我想生成一个银行对公授信材料检查Skill']
  }
}

function createConversationState(key, seed = {}) {
  const definition = scenarioDefinitions[key]
  const now = new Date().toISOString()
  return {
    conversationId: uid(`${key}-conversation`),
    key,
    title: '新对话',
    createdAt: now,
    updatedAt: now,
    phase: 0,
    taskId: uid(`${key}-task`),
    sessionId: uid(`${key}-session`),
    firstMessage: '',
    busy: false,
    messages: [{ role: 'assistant', text: definition.initial }],
    suggestions: [...definition.suggestions],
    evidence: null,
    skill: null,
    ...seed
  }
}

function createScenarioState(key) {
  const first = createConversationState(key)
  return { key, activeConversationId: first.conversationId, conversations: [first] }
}

const state = {
  active: 'short',
  authenticated: false,
  scenarios: Object.fromEntries(Object.keys(scenarioDefinitions).map((key) => [key, createScenarioState(key)]))
}

const thread = document.querySelector('#conversationThread')
const composer = document.querySelector('#messageComposer')
const input = document.querySelector('#messageInput')
const sendButton = composer.querySelector('button[type="submit"]')

function activeWorkspace() { return state.scenarios[state.active] }

function activeState() {
  const workspace = activeWorkspace()
  return workspace.conversations.find((item) => item.conversationId === workspace.activeConversationId)
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[character])
}

function renderMessages() {
  const current = activeState()
  thread.innerHTML = current.messages.map((message) => {
    if (message.role === 'divider') return `<div class="conversation-divider">${escapeHtml(message.text)}</div>`
    const role = message.role === 'user' ? 'user' : 'assistant'
    const error = message.error ? ' error' : ''
    const avatar = role === 'user' ? '你' : 'AI'
    return `<div class="message-row ${role}"><span class="mini-avatar">${avatar}</span><div class="message-bubble${error}">${escapeHtml(message.text)}</div></div>`
  }).join('')

  if (current.skill) {
    const skill = current.skill
    thread.insertAdjacentHTML('beforeend', `<article class="skill-result"><small>SKILL 已生成 · v${escapeHtml(skill.version || 1)}</small><h4>${escapeHtml(skill.name || '新Skill')}</h4><pre>${escapeHtml(skill.skillMarkdown || '')}</pre></article>`)
  }
  requestAnimationFrame(() => { thread.scrollTop = thread.scrollHeight })
}

function renderSuggestions() {
  const bar = document.querySelector('#suggestionBar')
  bar.innerHTML = activeState().suggestions.map((suggestion) => {
    const value = typeof suggestion === 'string' ? suggestion : suggestion.label
    const action = typeof suggestion === 'string' ? '' : ` data-action="${suggestion.action}"`
    return `<button class="suggestion" type="button"${action}>${escapeHtml(value)}</button>`
  }).join('')
}

function formatConversationTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '刚刚'
  return date.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function renderConversationList() {
  const workspace = activeWorkspace()
  const list = document.querySelector('#conversationList')
  list.innerHTML = [...workspace.conversations]
    .sort((left, right) => String(right.updatedAt).localeCompare(String(left.updatedAt)))
    .map((conversation) => {
      const active = conversation.conversationId === workspace.activeConversationId
      return `<button class="conversation-tab${active ? ' active' : ''}" type="button" data-conversation-id="${escapeHtml(conversation.conversationId)}" aria-current="${active ? 'true' : 'false'}"><strong>${escapeHtml(conversation.title)}</strong><small>${escapeHtml(formatConversationTime(conversation.updatedAt))}</small></button>`
    }).join('')
}

function renderStages() {
  const current = activeState()
  const completed = current.phase >= 2
  document.querySelector('#stageList').innerHTML = scenarioDefinitions[state.active].stages.map((stage, index) => {
    const status = completed || index < current.phase ? 'done' : index === current.phase ? 'active' : ''
    return `<li class="${status}">${escapeHtml(stage)}</li>`
  }).join('')
}

function renderScenario() {
  const definition = scenarioDefinitions[state.active]
  const current = activeState()
  document.querySelectorAll('[data-scenario]').forEach((button) => {
    const selected = button.dataset.scenario === state.active
    button.classList.toggle('active', selected)
    button.setAttribute('aria-selected', String(selected))
  })
  document.querySelector('#scenarioTitle').textContent = definition.title
  document.querySelector('#scenarioSubtitle').textContent = definition.subtitle
  document.querySelector('#chatHeading').textContent = definition.heading
  document.querySelector('#chatHint').textContent = definition.hint
  document.querySelector('#scenarioGoal').textContent = definition.goal
  document.querySelector('#scenarioGoalText').textContent = definition.goalText
  document.querySelector('#successRule').textContent = definition.success
  document.querySelector('#phaseBadge').textContent = current.phase >= 2 ? '验证完成' : current.phase === 1 ? '进行中' : '准备开始'
  document.querySelector('#evidencePayload').textContent = current.evidence ? JSON.stringify(current.evidence, null, 2) : '尚未产生调用记录'
  input.placeholder = state.active === 'skill' ? '回答问题，或继续补充你的要求……' : '在这里回复智能体……'
  input.disabled = current.busy
  sendButton.disabled = current.busy
  sendButton.querySelector('span').textContent = current.busy ? '思考中' : '发送'
  renderConversationList()
  renderMessages()
  renderSuggestions()
  renderStages()
}

function addMessage(current, role, text, error = false) {
  current.messages.push({ role, text, error })
  current.updatedAt = new Date().toISOString()
  if (activeState()?.conversationId === current.conversationId) renderMessages()
}

async function ensureSession() {
  if (state.authenticated) return true
  const response = await fetch('./api/session', { credentials: 'include' })
  if (response.ok) {
    state.authenticated = true
    return true
  }
  window.location.assign('./auth/login')
  return false
}

async function postJson(url, body) {
  if (!(await ensureSession())) throw new Error('登录状态已失效，正在重新登录。')
  const response = await fetch(url, {
    method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(payload.detail || '这次没有完成，请稍后再试。')
  return payload.data
}

function conversationPayload(current) {
  return {
    scenario: current.key,
    title: current.title,
    taskId: current.taskId,
    sessionId: current.sessionId,
    phase: current.phase,
    firstMessage: current.firstMessage,
    messages: current.messages,
    suggestions: current.suggestions,
    evidence: current.evidence,
    skill: current.skill,
    createdAt: current.createdAt
  }
}

async function saveConversation(current) {
  current.updatedAt = new Date().toISOString()
  const response = await fetch(`./api/conversations/${current.conversationId}`, {
    method: 'PUT', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(conversationPayload(current))
  })
  if (!response.ok) throw new Error('对话历史保存失败')
}

function restoreConversation(key, item) {
  return {
    ...createConversationState(key),
    ...item,
    key,
    busy: false,
    messages: Array.isArray(item.messages) && item.messages.length ? item.messages : [{ role: 'assistant', text: scenarioDefinitions[key].initial }],
    suggestions: Array.isArray(item.suggestions) ? item.suggestions : []
  }
}

async function loadConversationHistory(key) {
  const response = await fetch(`./api/conversations?scenario=${encodeURIComponent(key)}`, { credentials: 'include' })
  if (!response.ok) throw new Error('对话历史读取失败')
  const payload = await response.json()
  const items = Array.isArray(payload.data) ? payload.data : []
  const workspace = state.scenarios[key]
  if (items.length) {
    workspace.conversations = items.map((item) => restoreConversation(key, item))
    workspace.activeConversationId = workspace.conversations[0].conversationId
  } else {
    await saveConversation(workspace.conversations[0])
  }
}

async function createConversation(key, seed = {}) {
  const workspace = state.scenarios[key]
  const conversation = createConversationState(key, seed)
  workspace.conversations.unshift(conversation)
  workspace.activeConversationId = conversation.conversationId
  await saveConversation(conversation)
  if (state.active === key) renderScenario()
  return conversation
}

async function handleShort(current, message) {
  const data = await postJson('./api/component-tests/short-term', {
    taskId: current.taskId, sessionId: current.sessionId, message
  })
  current.evidence = data
  if (current.phase === 0) {
    current.firstMessage = message
    current.phase = 1
    current.suggestions = ['我刚才告诉了你什么？']
    addMessage(current, 'assistant', `好的，我已经记下了：\n“${message}”\n\n现在请再问我一句，看看我能不能从本次交流中想起来。`)
  } else if (data.contextMessageCount > 0) {
    current.phase = 2
    current.suggestions = []
    addMessage(current, 'assistant', `记得。你刚才告诉我：\n“${current.firstMessage}”\n\n本次交流记忆验证成功，我从前一轮找到了 ${data.contextMessageCount} 条相关消息。`)
  } else {
    addMessage(current, 'assistant', '我没有找回上一轮内容，这次验证没有通过。你可以点击“开始新测试”再试一次。', true)
  }
}

async function handleLong(current, message) {
  if (current.phase === 0) {
    const data = await postJson('./api/component-tests/long-term/extractions', { sessionId: current.sessionId, message })
    current.evidence = data
    if (data.status === 'SUCCEEDED' && data.writtenCount > 0) {
      current.firstMessage = message
      current.phase = 1
      current.suggestions = [{ label: '新建对话并验证', action: 'new-long-session' }]
      addMessage(current, 'assistant', `好的，我已把这项稳定偏好保存下来：\n“${message}”\n\n下一步请新建一个对话。旧对话会保留在上方，新对话中再问我是否还记得。`)
    } else {
      addMessage(current, 'assistant', '这句话没有形成可保存的长期记忆。请换成明确、长期、稳定且不敏感的偏好再试一次。', true)
    }
    return
  }
  const data = await postJson('./api/component-tests/long-term/search', {
    sessionId: current.sessionId,
    query: '',
    sourceTypes: ['CONVERSATION']
  })
  current.evidence = data
  if (data.items.length) {
    current.phase = 2
    current.suggestions = []
    const memories = data.items.map((item) => `• ${item.content}`).join('\n')
    addMessage(current, 'assistant', `记得。虽然这是一个新会话，我仍然找到了你以前告诉我的内容：\n${memories}\n\n跨会话长期记忆验证成功。`)
  } else {
    addMessage(current, 'assistant', '我没有在以前的对话记忆中找到相关内容。可以换一个更接近原偏好的问法再试一次。', true)
  }
}

async function handleSkill(current, message) {
  const data = await postJson('./api/customer/chat', {
    taskId: current.taskId, sessionId: current.sessionId, message
  })
  current.evidence = { mode: data.mode, planning: data.planning, diagnostics: data.diagnostics }
  let reply = data.answer || '请继续补充你的要求。'
  if (data.skill) {
    current.skill = data.skill
    current.phase = 2
    current.suggestions = []
  } else {
    current.phase = 1
    const questions = (data.planning?.questions || [])
      .map((item) => typeof item === 'string' ? item : item.question)
      .filter(Boolean)
    if (questions.length) {
      reply = `为了把这个Skill做对，我还需要确认 ${questions.length} 件事：\n\n${questions.map((question, index) => `${index + 1}. ${question}`).join('\n\n')}\n\n你可以一次回答，也可以分几次告诉我。`
      current.suggestions = [{ label: '填入一份完整回答示例', action: 'skill-complete-example' }]
    } else {
      current.suggestions = []
    }
  }
  addMessage(current, 'assistant', reply)
}

async function sendMessage(message) {
  const scenarioKey = state.active
  const current = activeState()
  if (current.busy || !message.trim()) return
  current.busy = true
  input.disabled = true
  sendButton.disabled = true
  sendButton.querySelector('span').textContent = '思考中'
  current.suggestions = []
  if (current.title === '新对话') current.title = message.trim().slice(0, 24)
  addMessage(current, 'user', message.trim())
  renderSuggestions()
  try {
    if (scenarioKey === 'short') await handleShort(current, message.trim())
    else if (scenarioKey === 'long') await handleLong(current, message.trim())
    else await handleSkill(current, message.trim())
  } catch (error) {
    addMessage(current, 'assistant', error instanceof Error ? error.message : '这次没有完成，请稍后再试。', true)
  } finally {
    current.busy = false
    try {
      await saveConversation(current)
    } catch (error) {
      current.evidence = { ...(current.evidence || {}), conversationHistoryWarning: error instanceof Error ? error.message : '对话历史保存失败' }
    }
    if (state.active === scenarioKey) {
      renderScenario()
      input.focus()
    }
  }
}

async function beginNewLongSession() {
  await createConversation('long', {
    title: '长期记忆验证',
    phase: 1,
    messages: [{ role: 'assistant', text: '这是一个全新的对话。上一段对话仍保留在上方，你可以随时切回。\n\n现在请问我：“你还记得我的长期偏好吗？”' }],
    suggestions: ['你还记得我的长期偏好吗？']
  })
}

document.querySelectorAll('[data-scenario]').forEach((button) => {
  button.addEventListener('click', () => { state.active = button.dataset.scenario; renderScenario(); input.focus() })
})

document.querySelector('#conversationList').addEventListener('click', (event) => {
  const button = event.target.closest('[data-conversation-id]')
  if (!button) return
  activeWorkspace().activeConversationId = button.dataset.conversationId
  renderScenario()
  input.focus()
})

document.querySelector('#newConversationButton').addEventListener('click', () => {
  void createConversation(state.active)
})

document.querySelector('#suggestionBar').addEventListener('click', (event) => {
  const button = event.target.closest('.suggestion')
  if (!button) return
  if (button.dataset.action === 'new-long-session') void beginNewLongSession()
  else if (button.dataset.action === 'skill-complete-example') {
    input.value = '输入材料由客户经理上传，格式为PDF。固定清单包括有效期内的营业执照、最新版公司章程、近三年审计报告、授信申请表和全部担保材料，每类至少一份；缺少任一必需材料即判为不齐全。逐项检查文件是否清晰、完整、在有效期内，并核对营业执照与章程中的企业名称、法定代表人和注册资本，以及审计报告与授信申请表中的营业收入、净利润和负债数据是否一致。输出Markdown检查表，列出材料、状态、异常原因和页码证据。不得修改原文件，也不自动作出授信审批结论；文件模糊、损坏、乱码或无法解析时，将该项标记为无法识别并停止给出结论，交给授信审批人员确认。'
    input.focus()
  }
  else { input.value = button.textContent; input.focus() }
})

composer.addEventListener('submit', (event) => {
  event.preventDefault()
  const message = input.value
  input.value = ''
  input.style.height = 'auto'
  void sendMessage(message)
})

input.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); composer.requestSubmit() }
})

input.addEventListener('input', () => {
  input.style.height = 'auto'
  input.style.height = `${Math.min(input.scrollHeight, 110)}px`
})

document.querySelector('#restartButton').addEventListener('click', () => {
  document.querySelector('#technicalEvidence').open = false
  void createConversation(state.active)
})

renderScenario()

async function initialize() {
  if (!(await ensureSession())) return
  try {
    await Promise.all(Object.keys(scenarioDefinitions).map((key) => loadConversationHistory(key)))
  } catch (error) {
    activeState().evidence = { conversationHistoryWarning: error instanceof Error ? error.message : '对话历史读取失败' }
  }
  renderScenario()
}

void initialize()
