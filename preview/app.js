let demoMode = window.RELOCATION_DEMO_MODE === true
const STORAGE_KEY = demoMode ? 'shanghai-relocation-calendar-en-demo-v1' : 'shanghai-relocation-calendar-en-v1'
const USER_KEY = demoMode ? 'shanghai-relocation-user-en-demo-v1' : 'shanghai-relocation-user-en-v1'
function hasSavedAppState() {
  try { return localStorage.getItem(STORAGE_KEY) !== null || localStorage.getItem(USER_KEY) !== null } catch (_) { return false }
}
const hadSavedAppStateAtLaunch = hasSavedAppState()
const PROFILE_GROUPS = [
  { title: 'About you', fields: [['name', 'Name', 'e.g. Alex'], ['destination_city', 'Destination city'], ['current_city', 'Current city', 'e.g. Hangzhou'], ['company_city', 'Work city'], ['company_district', 'Work district'], ['company_location', 'Work location', 'e.g. Zhangjiang Hi-Tech Park'], ['employment_type', 'Work situation']] },
  { title: 'Work and move timing', fields: [['start_date', 'First day at work'], ['move_deadline', 'Target move-in date'], ['housing_handover_date', 'New-home handover date'], ['planning_start_date', 'Planning start date'], ['full_process_deadline', 'Target date to feel settled'], ['availability_constraints', 'Availability', 'e.g. weekday evenings only'], ['moving_budget', 'One-time moving budget', 'e.g. CNY 3,000'], ['monthly_rent_budget', 'Monthly rent budget', 'e.g. CNY 3,500/month'], ['commute_preference', 'Preferred commute time']] },
  { title: 'Home and setup', fields: [['shared_housing', 'Open to shared housing'], ['pets', 'Pets'], ['housing_preferences', 'Home preferences'], ['current_housing', 'Current home or lease', 'e.g. current lease ends October 20'], ['social_insurance', 'Social insurance', 'e.g. previous employer paid through the end of September'], ['medical_insurance', 'Medical insurance', 'e.g. concerned about a coverage gap when changing jobs'], ['housing_fund', 'Housing provident fund (HPF)', 'e.g. transfer from another city'], ['household_registration', 'Residence permit / household registration', 'e.g. need to check residence permit requirements'], ['other_requirements', 'Other needs', 'e.g. remote work requires reliable internet']] },
]
const PROFILE_FIELDS = PROFILE_GROUPS.flatMap(group => group.fields.map(field => field[0]))
const DISTRICTS = ['Huangpu','Xuhui','Changning','Jing’an','Putuo','Hongkou','Yangpu','Pudong','Minhang','Baoshan','Jiading','Jinshan','Songjiang','Qingpu','Fengxian','Chongming']
const COMMUTE = ['Within 10 min','Within 20 min','Within 30 min','30–60 min','60–90 min','Within 2 hours','Flexible']
const REMINDER_TIMES = Array.from({ length: 31 }, (_, index) => `${String(7 + Math.floor(index / 2)).padStart(2, '0')}:${index % 2 ? '30' : '00'}`)
const HOUSING_OPTIONS = ['Near a metro station','Near a shopping mall','Near a wet market','Near a hospital']
let pickerState = null
const userState = loadUserState()
const messages = userState.conversation
const today = shanghaiTodayParts()
let viewMonth = new Date(today.year, today.month - 1, 1)
let selectedDate = shanghaiTodayKey()
let calendarState = loadCalendar()
saveCalendar()
let proposalSelection = new Set()
let busy = false
let directPlanRequest = false
let onboardingStep = 0
const onboardingDraft = { ...userState.profile }

const chat = document.querySelector('#chat')
const input = document.querySelector('#chat-input')
const send = document.querySelector('#send')
const proposalWrap = document.querySelector('#proposal-wrap')
let lastRequestError = null
function attachFeedback(row, message) {
  if (!row || !message || !message.content) return
  const controls = el('div', 'answer-feedback')
  controls.appendChild(el('span', '', 'Was this answer helpful?'))
  for (const [value, label] of [['helpful', 'Helpful'], ['inaccurate', 'Inaccurate'], ['missing', 'Missing evidence']]) {
    const button = el('button', `feedback-choice${message.feedback === value ? ' selected' : ''}`, label)
    button.type = 'button'
    button.setAttribute('aria-pressed', message.feedback === value ? 'true' : 'false')
    button.addEventListener('click', async () => {
      message.feedback = value
      controls.querySelectorAll('button').forEach(item => {
        item.classList.toggle('selected', item === button)
        item.setAttribute('aria-pressed', item === button ? 'true' : 'false')
      })
      saveUserState()
      if (demoMode) {
        controls.querySelector('.feedback-status')?.remove()
        controls.appendChild(el('span', 'feedback-status', 'Demo feedback is not collected.'))
        return
      }
      try {
        const response = await fetch('/api/feedback', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ rating: value, response_mode: message.responseMode || 'unknown' }) })
        const result = await response.json()
        if (!response.ok) throw new Error('Feedback was not synced')
        if (result.stored === false) {
          controls.querySelector('.feedback-status')?.remove()
          controls.appendChild(el('span', 'feedback-status', 'Demo feedback is not collected.'))
          return
        }
      } catch (_) {
        controls.querySelector('.feedback-status')?.remove()
        controls.appendChild(el('span', 'feedback-status', 'Feedback is saved locally. You can submit it again later.'))
      }
    })
    controls.appendChild(button)
  }
  row.querySelector('.bubble')?.appendChild(controls)
}
// The date picker is shared by profile fields and proposal dates. Keep it at
// phone level so it can open while the chat view is active too.
const sharedProfilePicker = document.querySelector('#profile-picker')
if (sharedProfilePicker) document.querySelector('.phone').appendChild(sharedProfilePicker)

function loadUserState() {
  try {
    const value = JSON.parse(localStorage.getItem(USER_KEY) || '{}')
    const profile = value.profile && typeof value.profile === 'object' ? value.profile : {}
    const conversation = Array.isArray(value.conversation) ? value.conversation.filter(item => item && ['user', 'assistant'].includes(item.role) && typeof item.content === 'string') : []
    const inputs = Array.isArray(value.inputs) ? value.inputs.filter(item => item && typeof item.content === 'string') : []
    const reminders = value.reminders && typeof value.reminders === 'object' ? value.reminders : {}
    return { profile, conversation, inputs, reminders: { inApp: reminders.inApp !== false, wechat: reminders.wechat === true, threeDays: /^\d{2}:\d{2}$/.test(reminders.threeDays || '') ? reminders.threeDays : '09:00', dueDay: /^\d{2}:\d{2}$/.test(reminders.dueDay || '') ? reminders.dueDay : '08:30' }, updatedAt: value.updatedAt || null, onboardingDone: value.onboardingDone === true }
  } catch (_) {
    return { profile: {}, conversation: [], inputs: [], reminders: { inApp: true, wechat: false, threeDays: '09:00', dueDay: '08:30' }, updatedAt: null, onboardingDone: false }
  }
}

function seedDemoState() {
  if (hadSavedAppStateAtLaunch) return false
  const todayKey = shanghaiTodayKey()
  const startDate = addCalendarDays(todayKey, 21)
  const moveDate = addCalendarDays(todayKey, 16)
  userState.profile = {
    name: 'Alex Chen', destination_city: 'Shanghai', current_city: 'Hangzhou',
    company_city: 'Shanghai', company_district: 'Pudong', company_location: 'Zhangjiang Hi-Tech Park',
    employment_type: 'Cross-city job change', start_date: startDate, move_deadline: moveDate,
    full_process_deadline: addCalendarDays(todayKey, 30), monthly_rent_budget: 'CNY 4,000/month',
    commute_preference: '30–60 min', shared_housing: 'Open to shared housing',
    other_requirements: 'Fictional sample profile for demonstration only.',
  }
  userState.conversation = []
  userState.inputs = []
  userState.onboardingDone = true
  userState.updatedAt = null
  messages.splice(0, messages.length)
  calendarState = {
    confirmed: [
      { id: 'demo-hr-check', title: 'List questions for HR onboarding', start_date: addCalendarDays(todayKey, 2), due_date: addCalendarDays(todayKey, 2), due_time: null, reminder_at: null, detail: 'Confirm the reporting location and required onboarding documents.', kind: 'task', hard_deadline: false, date_basis: '建议日期', source_note: 'Fictional sample calendar item; verify details with HR.', sources: [], depends_on_ids: [], done: false },
      { id: 'demo-home-check', title: 'Review housing handover conditions', start_date: addCalendarDays(todayKey, 8), due_date: addCalendarDays(todayKey, 8), due_time: null, reminder_at: null, detail: 'Check access, utility responsibilities, and move-in conditions with the relevant contact.', kind: 'task', hard_deadline: false, date_basis: '建议日期', source_note: 'Fictional sample calendar item; not a booking or confirmed service.', sources: [], depends_on_ids: [], done: false },
    ],
    pending: null, changes: [], bulkDeleteAll: false, pendingOnlyDelete: false,
    bulkDeletePreviousPending: null, bulkDeletePreviousChanges: [],
  }
  saveUserState()
  saveCalendar()
  updateIntro()
  selectedDate = calendarState.confirmed[0].due_date
  viewMonth = new Date(`${selectedDate}T00:00:00`)
  renderOnboarding()
  renderInAppReminders()
  renderCalendar()
  renderProposal()
  if (!document.querySelector('#profile-view').hidden) renderProfile()
  return true
}

function saveUserState() {
  try {
    localStorage.setItem(USER_KEY, JSON.stringify({ ...userState, conversation: messages.slice(-40) }))
    return true
  } catch (_) {
    document.querySelector('#profile-status').textContent = 'This browser is out of storage space. Your information was not saved.'
    document.querySelector('.footnote').textContent = 'This browser is out of storage space. Your profile was not saved. Check Profile.'
    return false
  }
}

function updateIntro() {
  const profile = userState.profile
  const known = [profile.destination_city, profile.company_location, profile.start_date, profile.commute_preference, profile.monthly_rent_budget].filter(Boolean).map(value => window.englishDisplay ? window.englishDisplay(value) : value)
  if (known.length) {
    document.querySelector('#intro-bubble').textContent = `I have your key details: ${known.join(', ')}. Ask about your next step, or tell me what has changed. You can review everything in Profile.`
  } else {
    document.querySelector('#intro-bubble').textContent = 'Start with your work location, first day, and target move-in date. We can add rent, commute, and housing preferences when you’re ready to compare areas.'
  }
}

function needsOnboarding() {
  const core = ['company_location', 'start_date', 'move_deadline']
  return !userState.onboardingDone && messages.length === 0 && core.filter(key => userState.profile[key]).length < 3
}

function onboardingInput(form, label, key, type, placeholder, required = true) {
  const field = el('label', 'onboarding-field')
  field.appendChild(el('span', '', label))
  const control = el('input')
    control.name = key
  control.type = type
  control.required = required
  control.placeholder = placeholder || ''
  if (type === 'date') {
    const todayKey = shanghaiTodayKey()
    control.min = todayKey
    const savedDate = parseDateValue(onboardingDraft[key])
    control.value = savedDate && savedDate >= todayKey ? savedDate : ''
  } else {
    const saved = onboardingDraft[key] || ''
    control.dataset.originalValue = saved
    control.value = window.englishDisplay ? window.englishDisplay(saved).replace(/ CNY(?:\/month)?$/, '') : saved.replace(/元(?:\/月)?$/, '')
  }
  field.appendChild(control)
  form.appendChild(field)
}

function onboardingSelect(form, label, key, options) {
  const field = el('label', 'onboarding-field')
  field.appendChild(el('span', '', label))
  const control = el('select')
  control.className = 'onboarding-native-select'
  control.name = key
  control.required = true
  control.appendChild(new Option('Please select', ''))
  for (const option of options) control.appendChild(new Option(option, option))
  control.value = key === 'shared_housing' ? selectValue(key, onboardingDraft[key] || '') : onboardingDraft[key] || ''
  const dropdown = el('div', 'cute-dropdown onboarding-dropdown')
    const trigger = el('button', 'cute-trigger', control.value || 'Please select')
  trigger.type = 'button'; trigger.setAttribute('aria-label', label); trigger.setAttribute('aria-expanded', 'false'); trigger.classList.toggle('has-value', Boolean(control.value))
  const optionsBox = el('div', 'cute-options'); optionsBox.hidden = true
  for (const choice of options) {
    const option = el('button', 'cute-option', choice); option.type = 'button'; option.classList.toggle('selected', control.value === choice)
    option.addEventListener('click', () => { control.value = choice; trigger.textContent = choice; trigger.classList.add('has-value'); optionsBox.querySelectorAll('.cute-option').forEach(item => item.classList.toggle('selected', item === option)); optionsBox.hidden = true; trigger.setAttribute('aria-expanded', 'false') })
    optionsBox.appendChild(option)
  }
  trigger.addEventListener('click', () => { optionsBox.hidden = !optionsBox.hidden; trigger.setAttribute('aria-expanded', String(!optionsBox.hidden)) })
  dropdown.append(control, trigger, optionsBox); field.appendChild(dropdown)
  form.appendChild(field)
}

function renderOnboarding() {
  const card = document.querySelector('#onboarding-card')
  card.replaceChildren()
  const visible = needsOnboarding()
  card.hidden = !visible
  document.querySelector('#intro-row').hidden = visible
  if (!visible) return
  const titles = ['Where will you work?', 'Set your key dates']
  card.appendChild(el('div', 'onboarding-progress', `2 steps · ${onboardingStep + 1}/2`))
  card.appendChild(el('h2', '', titles[onboardingStep]))
  card.appendChild(el('p', '', ['An office area or nearby transit hub is enough to get started.', 'Tell me your first day at work and your target move-in date. Housing budget and preferences can come later.'][onboardingStep]))
  const form = el('form', 'onboarding-form')
  if (onboardingStep === 0) {
    const destination = el('div', 'onboarding-destination', 'Destination city · Shanghai')
    form.appendChild(destination)
    onboardingInput(form, 'Office area or transit hub', 'company_location', 'text', 'e.g. Zhangjiang Hi-Tech Park or Lujiazui')
  } else if (onboardingStep === 1) {
    onboardingInput(form, 'First day at work', 'start_date', 'date')
    onboardingInput(form, 'Target move-in date', 'move_deadline', 'date')
  }
  const actions = el('div', 'onboarding-actions')
  if (onboardingStep) {
    const back = el('button', 'onboarding-back', 'Back')
    back.type = 'button'
    back.addEventListener('click', () => { onboardingStep -= 1; renderOnboarding() })
    actions.appendChild(back)
  }
  const next = el('button', 'primary', onboardingStep === 1 ? 'Save and generate plan' : 'Next')
  next.type = 'submit'
  actions.appendChild(next)
  form.appendChild(actions)
  form.addEventListener('submit', event => {
    event.preventDefault()
    if (!form.reportValidity()) return
    for (const control of form.elements) {
      if (!control.name) continue
      const value = control.value.trim()
      const original = control.dataset.originalValue || ''
      const shownOriginal = window.englishDisplay ? window.englishDisplay(original).replace(/ CNY(?:\/month)?$/, '') : original.replace(/元(?:\/月)?$/, '')
      onboardingDraft[control.name] = value === shownOriginal && original ? original : (/budget/.test(control.name) && value && /^\d/.test(value) ? `CNY ${value}` : value)
    }
    if (onboardingStep < 1) { onboardingStep += 1; renderOnboarding(); return }
    userState.profile = { ...userState.profile, ...onboardingDraft, destination_city: 'Shanghai' }
    userState.onboardingDone = true
    userState.updatedAt = new Date().toISOString()
    saveUserState()
    updateIntro()
    renderOnboarding()
    directPlanRequest = true
      input.value = 'Create a complete relocation plan using my saved information. Cover onboarding, date conflicts, housing, closing out my current home, moving, internet, housing provident fund, and other necessary tasks. Put every task in a pending plan for my confirmation. Do not give a general answer first.'
    document.querySelector('#chat-form').requestSubmit()
  })
  card.appendChild(form)
  const skip = el('button', 'onboarding-skip onboarding-skip-top', 'Skip')
  skip.type = 'button'
  skip.addEventListener('click', () => { userState.onboardingDone = true; saveUserState(); renderOnboarding(); input.focus() })
  card.appendChild(skip)
}

function dateKey(value) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function shanghaiTodayKey() {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date())
  const part = key => parts.find(item => item.type === key)?.value || '00'
  return `${part('year')}-${part('month')}-${part('day')}`
}

function shanghaiTodayParts() {
  const [year, month, day] = shanghaiTodayKey().split('-').map(Number)
  return { year, month, day }
}

function addCalendarDays(key, count) {
  const [year, month, day] = key.split('-').map(Number)
  const value = new Date(Date.UTC(year, month - 1, day + count))
  return `${value.getUTCFullYear()}-${String(value.getUTCMonth() + 1).padStart(2, '0')}-${String(value.getUTCDate()).padStart(2, '0')}`
}

function clampProposalDates(events, confirmed = []) {
  const todayKey = shanghaiTodayKey()
  const existingIds = new Set(confirmed.map(event => event.id))
  return (events || []).map(event => {
    const next = { ...event }
    if (existingIds.has(next.id) || !['Suggested date', '建议日期'].includes(next.date_basis)) return next
    if (next.due_date && next.due_date < todayKey) next.due_date = todayKey
    if (next.start_date && next.start_date < todayKey) next.start_date = todayKey
    if (next.start_date && next.due_date && next.start_date > next.due_date) next.start_date = next.due_date
    return next
  })
}

function dedupeCurrentEvents(events) {
  const todayKey = shanghaiTodayKey()
  const seen = new Set()
  return (events || []).filter(event => {
    // Keep past history intact, but only retain one current or future copy of an event.
    if (event.due_date && event.due_date < todayKey) return true
    const key = String(event.title || '').replace(/[\s\u3000，。、“”‘’：:；;（）()、/·-]/g, '').toLowerCase()
    if (!key || seen.has(key)) return !key
    seen.add(key)
    return true
  })
}

function loadCalendar() {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
    const pending = Array.isArray(value.pending) ? dedupeCurrentEvents(value.pending) : null
    return {
      confirmed: Array.isArray(value.confirmed) ? dedupeCurrentEvents(value.confirmed) : [],
      pending,
      changes: Array.isArray(value.changes) ? value.changes : [],
      bulkDeleteAll: value.bulkDeleteAll === true,
      pendingOnlyDelete: value.pendingOnlyDelete === true,
      bulkDeletePreviousPending: Array.isArray(value.bulkDeletePreviousPending) ? value.bulkDeletePreviousPending : null,
      bulkDeletePreviousChanges: Array.isArray(value.bulkDeletePreviousChanges) ? value.bulkDeletePreviousChanges : [],
    }
  } catch (_) {
    return { confirmed: [], pending: null, changes: [], bulkDeleteAll: false, pendingOnlyDelete: false, bulkDeletePreviousPending: null, bulkDeletePreviousChanges: [] }
  }
}

function saveCalendar() {
  try {
    const serialized = JSON.stringify(calendarState)
    localStorage.setItem(STORAGE_KEY, serialized)
    return localStorage.getItem(STORAGE_KEY) === serialized
  } catch (_) {
    return false
  }
}

function el(tag, className, text) {
  const node = document.createElement(tag)
  if (className) node.className = className
  if (text !== undefined) node.textContent = text
  return node
}

function appendEventSources(container, event) {
  const sources = Array.isArray(event.sources) ? event.sources : []
  if (!sources.length && !event.source_note) return
  const details = el('details', 'event-sources')
  details.appendChild(el('summary', '', 'Evidence and status'))
  if (event.source_note) details.appendChild(el('div', 'source-basis', event.source_note))
  for (const source of sources) {
    const entry = el('div', 'source-entry')
    if (source.source_url?.startsWith('https://')) {
      const link = el('a', 'evidence-link', source.source_name || 'View source')
      link.href = source.source_url
      link.target = '_blank'
      link.rel = 'noopener noreferrer'
      entry.appendChild(link)
    } else entry.appendChild(el('div', '', source.source_name || 'Information to be confirmed'))
    entry.appendChild(el('div', 'source-meta', [source.source_status, source.verified_at ? `Verified: ${source.verified_at}` : ''].filter(Boolean).join(' · ')))
    details.appendChild(entry)
  }
  container.appendChild(details)
}

function addMessage(role, content, evidence = [], structuredSources = []) {
  const row = el('div', `row ${role}`)
  const bubble = el('div', 'bubble')
  content = String(content || '').replace(/\\n/g, '\n')
  const followUpHeading = content.includes('Follow-up questions:') ? 'Follow-up questions:' : '最后追问：'
  if (role === 'assistant' && content.includes(followUpHeading)) {
    const index = content.lastIndexOf(followUpHeading)
    const before = content.slice(0, index).trimEnd()
    const questions = content.slice(index + followUpHeading.length).split('\n')
      .map(line => line.trim().replace(/^(?:\d+[.、．)]|[一二三四五六七八九十]+[、.．)])\s*/, ''))
      .filter(line => /[？?]$/.test(line) && !/^(?:Please provide|Please verify|Complete|After completing|Review|Please check|Please arrange|First,? complete|请补充|补充|请核对|核对|先完成|完成后|请查看|查看|请办理|办理后|建议先)/i.test(line))
      .slice(0, 3)
    content = questions.length ? `${before}\n${followUpHeading}\n${questions.map((line, number) => `${number + 1}. ${line}`).join('\n')}` : before
  }
  content = content.replace(/(Follow-up questions:|Upcoming tasks:|Task details:|Key assumptions:|Please confirm:|Information and status:|Evidence and status:|You can send this to HR:|最后追问：|近期要完成的事：|接下来按以下顺序推进：|你需要做的是：|关键假设：|需要确认的假设：|需要确认：|请确认：|你可以直接发给HR：|信息状态与依据：|依据与状态：)([^\n]*)/g, (_, heading, items) => {
    const separated = items.replace(/[；;]/g, '\n').replace(/\s+(?=(?:\d+|[一二三四五六七八九十])[、.)．])/g, '\n')
    return `${heading}\n${separated.trim()}`
  })
  content = content
    .replace(/\s*(?=(?:Evidence and status|Information and status):)/g, '\n')
    .replace(/\s*(?=(?:Key assumptions|Please confirm|You can send this to HR):)/g, '\n')
    .replace(/Evidence and status:([\s\S]*?)(?=\n(?:Summary of current information|Upcoming tasks|Task details|Follow-up questions|You can send this to HR|Key assumptions|Please confirm)|$)/g, (_, body) => `Evidence and status:${body.replace(/\n+/g, '; ').trim()}`)
    .replace(/([：。；！？])\s*(?=[一二三四五六七八九十]+、)/g, '$1\n')
    .replace(/\s+(?=[一二三四五六七八九十]+、)/g, '\n')
  if (role === 'assistant' && (evidence.length || /(?:依据与状态|信息依据或入口)：/.test(content))) {
    const annotations = new Map(evidence.map(item => [item.line, item]))
    const structured = [...structuredSources]
    content.split('\n').forEach((line, index) => {
  const sourceLine = /^(Information and entry point|Evidence and status):/.test(line)
      const part = sourceLine ? el('details', 'answer-line answer-source') : el('div', 'answer-line', line || '\u00a0')
      const contentPart = sourceLine ? el('div', 'answer-source-body') : part
      if (sourceLine) {
        const summary = el('summary', '', 'Evidence and status')
        part.append(summary, contentPart)
      }
      if (/^(Summary of current information|Upcoming tasks|Task details|Follow-up questions|Key assumptions|Please confirm|You can send this to HR|Information and status|Evidence and status)/.test(line)) part.classList.add('answer-heading')
      else if (/^(Why|When|Prerequisites|Completion standard):/.test(line)) part.classList.add('answer-field')
      const sourceData = sourceLine ? structured.shift() : null
      if (sourceLine && sourceData) {
        contentPart.replaceChildren()
        const basis = String(sourceData.basis || '').replace(/https?:\/\/\S+/g, '').trim()
        if (basis) contentPart.appendChild(el('div', 'source-basis', basis))
        for (const source of sourceData.sources || []) {
          const entry = el('div', 'source-entry')
          if (source.source_url) {
            const link = el('a', 'evidence-link', source.source_name || 'Source')
            link.href = source.source_url; link.target = '_blank'; link.rel = 'noopener noreferrer'
            entry.appendChild(link)
          } else entry.appendChild(el('span', '', source.source_name || 'Information to be confirmed'))
          entry.appendChild(el('div', 'source-meta', [source.source_status, source.verified_at ? `Verified: ${source.verified_at}` : ''].filter(Boolean).join(' · ')))
          contentPart.appendChild(entry)
        }
        bubble.appendChild(part)
        return
      }
      const sourceUrls = [...line.matchAll(/https?:\/\/[^\s；，。）》）]+/g)].map(match => match[0])
      if (sourceLine && sourceUrls.length) {
          const raw = line.replace(/^(Information and entry point|Evidence and status):\s*/, '').replace(/\[Source\]\(https?:\/\/[^)]+\)/g, '').replace(/https?:\/\/[^\s,;.)]+/g, '').trim()
        const segments = raw.split(/[；;]/).map(item => item.trim()).filter(Boolean)
        const status = segments.filter(item => /official source verified|verified(?: on|:)|verification date|data date|官方来源已核验|核验日期|验证日期|数据日期/i.test(item)).join('; ')
        const entries = segments.filter(item => !/official source verified|verified(?: on|:)|verification date|data date|官方来源已核验|核验日期|验证日期|数据日期/i.test(item))
        contentPart.replaceChildren()
        entries.forEach((item, itemIndex) => {
          const row = el('div', 'source-entry', `${itemIndex + 1}. ${item}`)
          if (sourceUrls[itemIndex]) { const link = el('a', 'evidence-link', 'Source'); link.href = sourceUrls[itemIndex]; link.target = '_blank'; link.rel = 'noopener noreferrer'; row.appendChild(document.createTextNode(' ')); row.appendChild(link) }
          contentPart.appendChild(row)
        })
        if (status) contentPart.appendChild(el('div', 'answer-status', status))
        return
      }
      if (sourceUrls.length) {
        const visible = line
          .replace(/^(Information and entry point|Evidence and status|信息依据或入口|依据与状态)[:：]?\s*/, '')
          .replace(/\[来源\]\(https?:\/\/[^)]+\)/g, '')
          .replace(/https?:\/\/[^\s；，。）》）]+/g, '')
          .replace(/，{2,}/g, '，')
          .replace(/来源：\s*；?/g, '')
          .replace(/来源:\s*;?/g, '')
          .replace(/\s{2,}/g, ' ')
          .trim()
        contentPart.textContent = visible
        if (sourceLine) contentPart.classList.add('answer-status')
        sourceUrls.forEach(url => {
          const link = el('a', 'evidence-link', 'Source')
          link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer'
          contentPart.appendChild(document.createTextNode(' ')); contentPart.appendChild(link)
        })
      }
      const annotation = annotations.get(index)
      if (annotation) {
        const badges = el('div', 'evidence-badges')
        for (const tag of annotation.tags || []) badges.appendChild(el('span', `evidence-badge${/待确认|待核验/.test(tag) ? ' pending' : ''}`, tag))
        if (annotation.verified_url) {
          const link = el('a', 'evidence-link', 'Source')
          link.href = annotation.verified_url
          link.target = '_blank'
          link.rel = 'noopener noreferrer'
          badges.appendChild(link)
        }
        contentPart.appendChild(badges)
      }
      bubble.appendChild(part)
    })
  } else bubble.textContent = content
  row.appendChild(bubble)
  chat.appendChild(row)
  chat.scrollTop = chat.scrollHeight
  return row
}

function setTab(name) {
  document.querySelector('#chat-view').hidden = name !== 'chat'
  document.querySelector('#calendar-view').hidden = name !== 'calendar'
  document.querySelector('#profile-view').hidden = name !== 'profile'
  document.querySelectorAll('.tab').forEach(tab => tab.classList.toggle('active', tab.dataset.tab === name))
  if (name === 'calendar') renderCalendar()
  if (name === 'profile') renderProfile()
  if (name === 'chat') renderInAppReminders()
}

function showProposalStart() {
  if (proposalWrap.hidden) return
  const cardTop = proposalWrap.getBoundingClientRect().top
  const chatTop = chat.getBoundingClientRect().top
  chat.scrollTop += cardTop - chatTop - 8
}

function renderInAppReminders() {
  const banner = document.querySelector('#in-app-reminders')
  if (!banner) return
  const current = shanghaiTodayKey()
  const horizon = addCalendarDays(current, 3)
  const due = userState.reminders.inApp
    ? calendarState.confirmed.filter(item => {
        if (item.done || !item.due_date) return false
        if (item.reminder_at) return item.reminder_at <= `${current}T${new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date())}` && item.due_date >= current
        return item.due_date >= current && item.due_date <= horizon
      }).sort((a, b) => a.due_date.localeCompare(b.due_date)).slice(0, 3)
    : []
  banner.hidden = due.length === 0
  if (due.length) banner.textContent = `Upcoming reminders · ${due.map(item => `${window.englishDisplay ? window.englishDisplay(item.title) : item.title} (${item.due_date === current ? 'Today' : item.due_date.slice(5)})`).join(', ')}  ›`
}
document.querySelector('#in-app-reminders')?.addEventListener('click', () => setTab('calendar'))
setInterval(renderInAppReminders, 60000)

document.querySelectorAll('.tab').forEach(tab => tab.addEventListener('click', () => setTab(tab.dataset.tab)))
document.querySelectorAll('[data-demo-prompt]').forEach(button => button.addEventListener('click', () => {
  input.value = button.dataset.demoPrompt || ''
  document.querySelector('#chat-form').requestSubmit()
}))
document.querySelector('#reset-demo').addEventListener('click', () => {
  if (!window.confirm('Reset the fictional demo profile, sample calendar, and local browser history?')) return
  localStorage.removeItem(USER_KEY)
  localStorage.removeItem(STORAGE_KEY)
  window.location.reload()
})
fetch('/health').then(response => response.json()).then(status => {
  if ((status.demo_mode === true) !== demoMode) {
    input.disabled = true
    send.disabled = true
    addMessage('error', 'Demo configuration changed after this page loaded. Reload before continuing so browser data stays isolated.')
    return
  }
  const mode = document.querySelector('#mode')
  if (mode) mode.textContent = status.demo_mode
      ? 'Interactive portfolio demo · scripted answers; no model calls or server-side visitor profile storage.'
      : status.llm_configured ? 'LLM connected · Calendar changes are saved only after your confirmation.' : 'No language model configured. Follow the README to set up an API.'
}).catch(() => { const mode = document.querySelector('#mode'); if (mode) mode.textContent = 'Unable to connect to the service.' })

document.querySelector('#chat-form').addEventListener('submit', async event => {
  event.preventDefault()
  const content = input.value.trim()
  if (!content || busy) return
  lastRequestError?.remove()
  lastRequestError = null
  const wasDirectPlanRequest = directPlanRequest
  input.value = ''
  messages.push({ role: 'user', content })
  userState.inputs.push({ content, at: new Date().toISOString() })
  saveUserState()
  renderOnboarding()
    const userRow = addMessage('user', content)
  busy = true
  send.disabled = true
  const waiting = addMessage('assistant', 'Preparing your plan…')
  waiting.classList.add('planning-status')
  // Yield once so the loading state is painted before the model request begins.
  await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))
  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: messages.slice(-24).map(({ role, content }) => ({ role, content: window.englishDisplay ? window.englishDisplay(content) : content })), profile: englishProfile(userState.profile), calendar: { confirmed: calendarState.confirmed, pending: calendarState.bulkDeleteAll ? calendarState.bulkDeletePreviousPending : calendarState.pending } }),
    })
    const data = await response.json()
    waiting.remove()
    if (!response.ok) throw new Error(data.error || 'Service unavailable')
    const answerRow = directPlanRequest ? null : addMessage('assistant', data.answer, data.answer_evidence || [], data.answer_sources || [])
    if (!directPlanRequest && Array.isArray(data.quick_choices) && data.quick_choices.length) {
      const choices = el('div', 'quick-choice-row')
      data.quick_choices.slice(0, 4).forEach(choice => {
        const button = el('button', 'quick-choice', choice)
        button.type = 'button'
        button.addEventListener('click', () => {
          input.value = choice
          document.querySelector('#chat-form').requestSubmit()
        })
        choices.appendChild(button)
      })
      answerRow?.appendChild(choices)
    }
    if (!directPlanRequest) {
      const answerMessage = { role: 'assistant', content: data.answer, evidence: data.answer_evidence || [], sources: data.answer_sources || [], responseMode: data.response_mode || 'unknown' }
      messages.push(answerMessage)
      attachFeedback(answerRow, answerMessage)
    }
    directPlanRequest = false
    if (data.profile && typeof data.profile === 'object') {
      userState.profile = data.profile
      userState.updatedAt = new Date().toISOString()
      updateIntro()
    }
    saveUserState()
    if (Array.isArray(data.calendar_clarifications) && data.calendar_clarifications.length) {
      const questions = data.calendar_clarifications.map(item => {
        const oldDate = item.existing_date || 'Date to be confirmed'
        const newDate = item.proposed_date || 'Date to be confirmed'
        const proposed = item.proposed_title && item.proposed_title !== item.existing_title ? `; proposed title: “${window.englishDisplay ? window.englishDisplay(item.proposed_title) : item.proposed_title}”` : ''
        if (item.existing_status === 'pending') {
          return `The pending draft already contains “${window.englishDisplay ? window.englishDisplay(item.existing_title) : item.existing_title}” (${oldDate}). This proposal may change it to ${newDate}${proposed}. It is not yet in your calendar. Would you like to update the draft?`
        }
        return `Your calendar already contains “${window.englishDisplay ? window.englishDisplay(item.existing_title) : item.existing_title}” (${oldDate}). This information may change it to ${newDate}${proposed}. Would you like to update this confirmed event?`
      })
      const clarificationText = questions.join('\n')
      addMessage('assistant', clarificationText)
      messages.push({ role: 'assistant', content: clarificationText })
      saveUserState()
    }
    if (data.proposal?.clear_pending) {
      calendarState.pending = null
      calendarState.changes = []
      calendarState.bulkDeleteAll = false
      calendarState.pendingOnlyDelete = false
      calendarState.bulkDeletePreviousPending = null
      calendarState.bulkDeletePreviousChanges = []
      proposalSelection = new Set()
      saveCalendar()
      renderProposal()
      renderInAppReminders()
    const removed = (data.proposal.removed_pending || []).map(item => `“${window.englishDisplay ? window.englishDisplay(item.title) : item.title}”`).join(', ')
      addMessage('assistant', removed ? `Withdrawn from the pending list: ${window.englishDisplay ? window.englishDisplay(removed) : removed}. Your calendar has not changed.` : 'The pending changes were withdrawn. Your calendar has not changed.')
    } else if (data.proposal) {
      if (data.proposal.bulk_delete_all && !calendarState.bulkDeleteAll) {
        calendarState.bulkDeletePreviousPending = calendarState.pending
        calendarState.bulkDeletePreviousChanges = calendarState.changes
      } else if (!data.proposal.bulk_delete_all) {
        calendarState.bulkDeletePreviousPending = null
        calendarState.bulkDeletePreviousChanges = []
      }
      calendarState.bulkDeleteAll = data.proposal.bulk_delete_all === true
      calendarState.pendingOnlyDelete = data.proposal.pending_only_delete === true
      calendarState.pending = clampProposalDates(data.proposal.events, calendarState.confirmed)
      calendarState.changes = data.proposal.changes
      const proposalBase = calendarState.pendingOnlyDelete ? calendarState.bulkDeletePreviousPending || [] : calendarState.confirmed
      proposalSelection = new Set(scopedProposalImpact(calendarState.pending, proposalBase).changes.map(change => (change.next || change.old).id))
      saveCalendar()
      renderProposal()
      renderInAppReminders()
      if (!data.proposal.bulk_delete_all && Array.isArray(data.proposal.removed_pending) && data.proposal.removed_pending.length) {
        addMessage('assistant', `Withdrawn from the pending list: ${data.proposal.removed_pending.map(item => window.englishDisplay ? window.englishDisplay(item.title) : item.title).join(', ')}. No confirmed calendar events were deleted.`)
      }
    }
    if (wasDirectPlanRequest && (!data.proposal || !data.proposal.changes?.length) && !data.calendar_clarifications?.length) {
      addMessage('error', 'The plan was not generated. Your profile is saved; send again to retry or add more information.')
    }
    // Keep the response first and the confirmation card second in the same scroll area.
    if (data.proposal?.bulk_delete_all && !proposalWrap.hidden) showProposalStart()
    else if (answerRow) chat.scrollTop = answerRow.offsetTop - chat.offsetTop
  } catch (error) {
    waiting.remove()
    userRow.remove()
    messages.pop()
    userState.inputs.pop()
    saveUserState()
    input.value = content
    lastRequestError = addMessage('error', `Unable to answer for now: ${error.message}. Your question has been kept.`)
    const retry = el('button', 'retry-request', 'Retry')
    retry.type = 'button'
    retry.addEventListener('click', () => document.querySelector('#chat-form').requestSubmit())
    lastRequestError.querySelector('.bubble')?.appendChild(retry)
  } finally {
    directPlanRequest = false
    busy = false
    send.disabled = false
    input.focus()
  }
})

function eventDateLabel(event) {
  if (!event.due_date) return 'Date to be confirmed'
  const start = event.start_date || event.due_date
  return `${start !== event.due_date ? start + ' – ' : ''}${event.due_date}${event.due_time ? ' ' + event.due_time : ''}`
}

function proposalDateLabel(event) {
  return event.due_date ? `${event.due_date}${event.due_time ? ' ' + event.due_time : ''}` : 'Date to be confirmed'
}

function visibleOnDate(event, key) {
  return Boolean(event.due_date && (event.start_date || event.due_date) <= key && key <= event.due_date)
}

function protectedDeadline(event) {
  return event?.hard_deadline === true || (event?.kind === 'deadline' && ['User-stated', '用户明确'].includes(event?.date_basis))
}

function proposalImpact(candidate, confirmed) {
  const before = new Map(confirmed.map(item => [item.id, item]))
  const after = new Map(candidate.map(item => [item.id, item]))
  const changes = []
  const hardIssues = []
  for (const next of candidate) {
    const old = before.get(next.id)
    if (!old) { changes.push({ old: null, next, kind: 'add' }); continue }
    const dateChanged = old.start_date !== next.start_date || old.due_date !== next.due_date || old.due_time !== next.due_time
    const changed = ['title', 'detail', 'kind', 'hard_deadline', 'date_basis', 'source_note', 'reminder_at', 'done'].some(key => old[key] !== next[key])
    if (dateChanged || changed) changes.push({ old, next, kind: dateChanged ? 'move' : 'edit' })
    if (protectedDeadline(old) && (dateChanged || !protectedDeadline(next))) hardIssues.push({ id: old.id, title: old.title, text: `${eventDateLabel(old)} → ${eventDateLabel(next)}` })
  }
  for (const old of confirmed) {
    if (after.has(old.id)) continue
    changes.push({ old, next: null, kind: 'delete' })
    if (protectedDeadline(old)) hardIssues.push({ id: old.id, title: old.title, text: `Hard deadline scheduled for ${eventDateLabel(old)}` })
  }
  return { changes, hardIssues }
}

function scopedProposalImpact(candidate, confirmed) {
  const all = proposalImpact(candidate, confirmed)
  const scoped = new Map((calendarState.changes || [])
    .filter(change => change && change.id)
    .map(change => [change.id, change.type]))
  if (!scoped.size) return all
  const kindFor = type => type === 'add' || type === 'Added' ? 'add' : type === 'delete' || type === 'Deleted' ? 'delete' : 'edit'
  const changes = all.changes
    .filter(change => scoped.has((change.next || change.old).id))
    .map(change => ({ ...change, kind: kindFor(scoped.get((change.next || change.old).id)) }))
  const selectedIds = new Set(changes.map(change => (change.next || change.old).id))
  return { changes, hardIssues: all.hardIssues.filter(issue => selectedIds.has(issue.id)) }
}

function selectedImpact(candidate, confirmed) {
  const all = proposalImpact(candidate, confirmed).changes
  const selected = all.filter(change => proposalSelection.has((change.next || change.old).id))
  const effective = confirmed.filter(old => !selected.some(change => (change.next || change.old).id === old.id))
  effective.push(...selected.filter(change => change.next).map(change => change.next))
  return proposalImpact(effective, confirmed)
}

proposalSelection = calendarState.pending
  ? new Set(scopedProposalImpact(calendarState.pending, calendarState.confirmed).changes.map(change => (change.next || change.old).id))
  : new Set()

function proposalOrder(event) {
  const title = String(event.title || '').toLowerCase()
  if (/hr|onboarding|check.in|start date|date conflict/.test(title)) return 0
  if (/provident fund|social insurance|medical insurance|residence registration|residence permit/.test(title)) return 4
  if (/broadband|internet|utilit|electricity|water|gas/.test(title)) return 3
  if (/mov(e|ing)|old.home|vacat|turnover/.test(title)) return 2
  if (/rent|view|housing|lease|sign|handover|move.in/.test(title)) return 1
  return 5
}

function openProposalDatePicker(event) {
  const todayKey = shanghaiTodayKey()
  const selected = event.due_date && event.due_date >= todayKey ? event.due_date : todayKey
  const [year, month, day] = selected.split('-').map(Number)
  pickerState = { key: 'proposal_date', values: [year, month, day], onConfirm: value => {
    const target = calendarState.pending?.find(item => item.id === event.id)
    if (!target) return
    const safeValue = value < todayKey ? todayKey : value
    target.due_date = safeValue
    target.start_date = safeValue
    target.date_basis = 'User-stated'
    renderProposal()
  } }
  document.querySelector('#picker-title').textContent = `Set date for “${window.englishDisplay ? window.englishDisplay(event.title) : event.title}”`
  document.querySelector('#picker-search-wrap').hidden = true
  document.querySelector('#picker-city-labels').hidden = true
  const columns = document.querySelector('#picker-columns')
  columns.replaceChildren()
  buildWheel(columns, Array.from({ length: 41 }, (_, i) => 2020 + i), 0, value => String(value))
  buildWheel(columns, Array.from({ length: 12 }, (_, i) => i + 1), 1, value => new Intl.DateTimeFormat('en-US', { month: 'long' }).format(new Date(2020, value - 1, 1)))
  buildDayWheel(columns)
  document.querySelector('#profile-picker').hidden = false
  requestAnimationFrame(() => columns.querySelectorAll('.wheel-column').forEach(column => { column.scrollTop = Number(column.dataset.index) * 42 }))
}

function renderProposal() {
  proposalWrap.replaceChildren()
  if (calendarState.pending) calendarState.pending = clampProposalDates(calendarState.pending, calendarState.confirmed)
  const events = calendarState.pending
  if (!events || !calendarState.changes.length) {
    proposalWrap.hidden = true
    return
  }
  proposalWrap.hidden = false
  const card = el('div', 'proposal-card')
  card.appendChild(el('div', 'proposal-title', calendarState.bulkDeleteAll ? 'Plans proposed for deletion' : 'Your proposed plan'))
  card.appendChild(el('div', 'proposal-sub proposal-lead', calendarState.bulkDeleteAll ? 'Review the items to delete. Confirmed events will stay unchanged until you confirm.' : 'Select the items to add, update, or delete. They will be saved to your calendar only after confirmation.'))
  const proposalBase = calendarState.pendingOnlyDelete ? calendarState.bulkDeletePreviousPending || [] : calendarState.confirmed
  const impact = scopedProposalImpact(events, proposalBase)
  if (!impact.changes.length) {
    proposalWrap.hidden = true
    return
  }
  const counts = [
    ['Added', impact.changes.filter(item => item.kind === 'add').length],
    ['Changed', impact.changes.filter(item => item.kind === 'move' || item.kind === 'edit').length],
    ['Deleted', impact.changes.filter(item => item.kind === 'delete').length],
  ].filter(([, count]) => count).map(([label, count]) => `${label}: ${count}`)
  card.appendChild(el('div', 'proposal-sub', `Showing only these changes: ${counts.join(' · ')}. The calendar remains unchanged until confirmation.`))
  if (calendarState.bulkDeleteAll && !calendarState.pendingOnlyDelete) {
    const confirmedIds = new Set(calendarState.confirmed.map(item => item.id))
    const draftCount = (calendarState.bulkDeletePreviousPending || []).filter(item => !confirmedIds.has(item.id)).length
    if (draftCount) card.appendChild(el('div', 'proposal-sub', `${draftCount} additional pending draft(s) not yet in the calendar will also be withdrawn if you confirm deletion.`))
  }
  const table = el('table', 'proposal-table proposal-plan-table')
  const head = el('thead')
  const headRow = el('tr')
  for (const label of ['Task', 'Expected due date', '']) headRow.appendChild(el('th', '', label))
  head.appendChild(headRow)
  table.appendChild(head)
  const body = el('tbody')
  const orderedChanges = [...impact.changes].sort((a, b) => {
    const left = a.next || a.old; const right = b.next || b.old
    const leftDate = left.due_date || '9999-12-31'
    const rightDate = right.due_date || '9999-12-31'
    return leftDate.localeCompare(rightDate) || proposalOrder(left) - proposalOrder(right) || left.title.localeCompare(right.title)
  })
  for (const change of orderedChanges) {
    const event = change.next || change.old
    const row = el('tr')
    const content = el('td', 'proposal-task-cell')
    content.appendChild(el('div', 'event-title', change.old && change.next && change.old.title !== change.next.title ? `${change.old.title} → ${change.next.title}` : event.title))
    if (change.kind !== 'delete' && event.detail) content.appendChild(el('div', 'event-note', event.detail))
    if (change.kind !== 'delete' && event.reminder_at && change.old?.reminder_at !== event.reminder_at) content.appendChild(el('div', 'event-note', `In-app reminder: ${change.old?.reminder_at?.replace('T', ' ') || 'Not set'} → ${event.reminder_at.replace('T', ' ')}`))
    if (change.kind !== 'delete') appendEventSources(content, event)
    row.appendChild(content)
    const dateCell = el('td', 'proposal-date-cell')
    if (change.kind !== 'delete') {
      const dateButton = el('button', 'proposal-date-button', '')
      dateButton.type = 'button'
      if (change.old && change.next && change.old.due_date !== change.next.due_date) {
        const oldDate = el('span', 'proposal-old-date', proposalDateLabel(change.old))
        const newDate = el('span', 'proposal-new-date', proposalDateLabel(event))
        dateButton.append(oldDate, newDate)
      } else {
        dateButton.textContent = proposalDateLabel(event)
      }
      dateButton.addEventListener('click', () => openProposalDatePicker(event))
      dateCell.appendChild(dateButton)
      dateCell.appendChild(el('small', '', event.due_date ? 'Swipe to edit' : 'Tap to choose a date'))
    }
    const selectCell = el('td', 'proposal-select-cell')
    if (change.kind === 'delete') selectCell.appendChild(el('span', 'proposal-delete-note', 'Delete'))
    const select = el('button', `proposal-select${proposalSelection.has(event.id) ? ' selected' : ''}`, proposalSelection.has(event.id) ? '✓' : '')
    select.type = 'button'; select.setAttribute('aria-label', `${proposalSelection.has(event.id) ? 'Deselect ' : 'Select '}${change.kind === 'delete' ? 'deletion of ' : ''}${window.englishDisplay ? window.englishDisplay(event.title) : event.title}`); select.setAttribute('aria-pressed', proposalSelection.has(event.id) ? 'true' : 'false')
    select.addEventListener('click', () => { if (proposalSelection.has(event.id)) proposalSelection.delete(event.id); else proposalSelection.add(event.id); renderProposal() })
    selectCell.appendChild(select)
    if (change.kind !== 'delete') row.appendChild(dateCell)
    else row.appendChild(el('td', 'proposal-date-cell'))
    row.appendChild(selectCell)
    body.appendChild(row)
  }
  table.appendChild(body)
  card.appendChild(table)
  const hardIssues = selectedImpact(events, proposalBase).hardIssues
  if (hardIssues.length) {
    const warningText = hardIssues.map(item => `${item.title}（${item.text}）`).join('；')
    card.appendChild(el('div', 'proposal-hard-warning', `A hard deadline change requires verification: ${window.englishDisplay ? window.englishDisplay(warningText) : warningText}`))
    const warning = el('label', 'hard-confirm')
    const check = el('input')
    check.type = 'checkbox'; check.id = 'hard-confirm'
    warning.append(check, el('span', '', 'I verified that the hard deadline above may be changed or deleted, and still want to save the proposed schedule.'))
    card.appendChild(warning)
  }
  const deleteCount = impact.changes.filter(item => item.kind === 'delete' && proposalSelection.has(item.old.id)).length
  card.appendChild(el('div', 'proposal-sub', `${proposalSelection.size} selected${deleteCount ? `, including ${deleteCount} deletion(s)` : ''}`))
  const actions = el('div', 'proposal-actions')
  const yes = el('button', 'confirm', calendarState.bulkDeleteAll ? 'Confirm deletion' : 'Yes, update my calendar')
  yes.type = 'button'
  yes.disabled = proposalSelection.size === 0
  if (hardIssues.length) {
    yes.disabled = true
    card.querySelector('#hard-confirm').addEventListener('change', event => { yes.disabled = !event.target.checked || proposalSelection.size === 0 })
  }
  yes.addEventListener('click', confirmProposal)
  const no = el('button', 'decline', 'Keep my calendar unchanged')
  no.type = 'button'
  no.addEventListener('click', declineProposal)
  actions.append(yes, no)
  card.appendChild(actions)
  proposalWrap.appendChild(card)
  chat.appendChild(proposalWrap)
}

function confirmProposal() {
  if (!calendarState.pending) return
  const before = JSON.stringify(calendarState)
  const beforeSelection = new Set(proposalSelection)
  const proposalBase = calendarState.pendingOnlyDelete ? calendarState.bulkDeletePreviousPending || [] : calendarState.confirmed
  const impact = proposalImpact(calendarState.pending, proposalBase)
  const deletedIds = new Set(impact.changes.filter(change => change.kind === 'delete' && proposalSelection.has(change.old.id)).map(change => change.old.id))
  if (!proposalSelection.size) return
  if (selectedImpact(calendarState.pending, proposalBase).hardIssues.length && !document.querySelector('#hard-confirm')?.checked) return
  if (calendarState.pendingOnlyDelete) {
    const remaining = proposalBase.filter(item => !deletedIds.has(item.id))
    calendarState.pending = remaining.length ? remaining : null
    calendarState.changes = remaining.map(item => ({ id: item.id, type: 'Added', title: item.title }))
    calendarState.bulkDeleteAll = false
    calendarState.pendingOnlyDelete = false
    calendarState.bulkDeletePreviousPending = null
    calendarState.bulkDeletePreviousChanges = []
    proposalSelection = new Set(remaining.map(item => item.id))
    if (!saveCalendar()) {
      calendarState = JSON.parse(before)
      proposalSelection = beforeSelection
      renderProposal()
      addMessage('error', 'This browser is out of storage space. The pending draft was not saved; your calendar is unchanged. Check browser storage and try again.')
      return
    }
    renderProposal()
    addMessage('assistant', `Withdrew ${deletedIds.size} pending draft item(s). No confirmed calendar events changed.`)
    return
  }
  const selected = clampProposalDates(calendarState.pending, calendarState.confirmed).filter(event => proposalSelection.has(event.id))
  calendarState.confirmed = dedupeCurrentEvents(calendarState.confirmed.filter(event => !proposalSelection.has(event.id) && !deletedIds.has(event.id)).concat(selected.map(event => ({ ...event }))))
  calendarState.pending = null
  proposalSelection = new Set()
  calendarState.changes = []
  calendarState.bulkDeleteAll = false
  calendarState.pendingOnlyDelete = false
  calendarState.bulkDeletePreviousPending = null
  calendarState.bulkDeletePreviousChanges = []
  if (!saveCalendar()) {
    calendarState = JSON.parse(before)
    proposalSelection = beforeSelection
    renderProposal()
    addMessage('error', 'This browser is out of storage space. The calendar was not updated; existing events are unchanged. Check browser storage and try again.')
    return
  }
  renderProposal()
  renderInAppReminders()
  const firstEvent = calendarState.confirmed.find(event => event.due_date)
  const firstDate = firstEvent?.start_date || firstEvent?.due_date
  if (firstDate) {
    selectedDate = firstDate
    const [year, month] = firstDate.split('-').map(Number)
    viewMonth = new Date(year, month - 1, 1)
  }
  addMessage('assistant', 'The plan calendar was updated as confirmed. You can request more changes in chat; each proposal will be shown for confirmation first.')
  setTab('calendar')
}

function declineProposal() {
  if (calendarState.bulkDeleteAll) {
    calendarState.pending = calendarState.bulkDeletePreviousPending
    calendarState.changes = calendarState.bulkDeletePreviousChanges
  } else {
    calendarState.pending = null
    calendarState.changes = []
  }
  calendarState.bulkDeleteAll = false
  calendarState.pendingOnlyDelete = false
  calendarState.bulkDeletePreviousPending = null
  calendarState.bulkDeletePreviousChanges = []
  saveCalendar()
  renderProposal()
  addMessage('assistant', 'Your current calendar was kept unchanged. The proposed changes were not applied.')
}

document.querySelector('#prev-month').addEventListener('click', () => {
  viewMonth = new Date(viewMonth.getFullYear(), viewMonth.getMonth() - 1, 1)
  renderCalendar()
})
document.querySelector('#next-month').addEventListener('click', () => {
  viewMonth = new Date(viewMonth.getFullYear(), viewMonth.getMonth() + 1, 1)
  renderCalendar()
})

const customModal = document.querySelector('#custom-modal')
const customForm = document.querySelector('#custom-event-form')
const customError = document.querySelector('#custom-error')

function closeCustomModal() {
  customModal.hidden = true
  document.querySelector('#add-custom-event').focus()
}

document.querySelector('#add-custom-event').addEventListener('click', () => {
  customForm.reset()
  customError.textContent = ''
  document.querySelector('#custom-start').value = selectedDate
  document.querySelector('#custom-end').value = selectedDate
  customModal.hidden = false
  document.querySelector('#custom-description').focus()
})
document.querySelector('#cancel-custom').addEventListener('click', closeCustomModal)
customModal.addEventListener('click', event => {
  if (event.target === customModal) closeCustomModal()
})
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && !customModal.hidden) closeCustomModal()
})

customForm.addEventListener('submit', event => {
  event.preventDefault()
  const start = document.querySelector('#custom-start').value
  const end = document.querySelector('#custom-end').value
  const description = document.querySelector('#custom-description').value.trim()
  if (!start || !end || !description) {
    customError.textContent = 'Enter a start date, end date, and event description.'
    return
  }
  if (start > end) {
    customError.textContent = 'The end date cannot be earlier than the start date.'
    return
  }
  if (calendarState.confirmed.length >= 40 || (calendarState.pending && calendarState.pending.length >= 40)) {
    customError.textContent = 'The calendar has reached its 40-event limit.'
    return
  }
  const id = `m_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
  const firstLine = description.split(/[。！!？?\n]/)[0].trim() || description
  const customEvent = {
    id,
    title: firstLine.slice(0, 80),
    start_date: start,
    due_date: end,
    due_time: null,
    detail: description.length > 80 ? description : '',
    kind: 'task',
    hard_deadline: document.querySelector('#custom-hard').checked,
    date_basis: 'User-stated',
    source_note: 'User-created',
    done: false,
  }
  calendarState.confirmed.push(customEvent)
  if (calendarState.pending) calendarState.pending.push({ ...customEvent })
  if (!saveCalendar()) {
    calendarState.confirmed = calendarState.confirmed.filter(item => item.id !== id)
    if (calendarState.pending) calendarState.pending = calendarState.pending.filter(item => item.id !== id)
    customError.textContent = 'This browser is out of storage space. The event was not saved.'
    return
  }
  selectedDate = start
  const [year, month] = start.split('-').map(Number)
  viewMonth = new Date(year, month - 1, 1)
  closeCustomModal()
  renderCalendar()
  renderProposal()
  renderInAppReminders()
})

function renderCalendar() {
  const year = viewMonth.getFullYear()
  const month = viewMonth.getMonth()
  const hireDate = parseDateValue(userState.profile.start_date)
  document.querySelector('#month-title').textContent = new Intl.DateTimeFormat('en-US', { year: 'numeric', month: 'long' }).format(new Date(year, month, 1))
  const first = new Date(year, month, 1)
  const offset = (first.getDay() + 6) % 7
  const cellCount = Math.ceil((offset + new Date(year, month + 1, 0).getDate()) / 7) * 7
  const grid = document.querySelector('#month-grid')
  grid.replaceChildren()
  for (let i = 0; i < cellCount; i += 1) {
    const day = new Date(year, month, 1 - offset + i)
    const key = dateKey(day)
    const events = calendarState.confirmed.filter(event => visibleOnDate(event, key) && !event.done)
    const hard = calendarState.confirmed.some(event => event.hard_deadline && event.due_date === key)
    const isHireDate = key === hireDate
    const cell = el('button', `day-cell${day.getMonth() !== month ? ' other' : ''}${events.length ? ' has-events' : ''}${key === selectedDate ? ' selected' : ''}${hard ? ' hard-date' : ''}`)
    cell.type = 'button'
    cell.setAttribute('aria-label', `${key}${isHireDate ? ', start date' : ''}, ${events.length} tasks${hard ? ', hard deadline' : ''}`)
    cell.appendChild(el('span', 'num', String(day.getDate())))
    if (isHireDate) cell.appendChild(el('span', 'hire-label', 'Start'))
    if (events.length) cell.appendChild(el('span', 'hint', events.length === 1 ? events[0].title : `${events.length} items`))
    cell.addEventListener('click', () => {
      selectedDate = key
      if (day.getMonth() !== month) viewMonth = new Date(day.getFullYear(), day.getMonth(), 1)
      renderCalendar()
      document.querySelector('.calendar-body').scrollTop = 0
    })
    grid.appendChild(cell)
  }
  const [selectedYear, selectedMonth, selectedDay] = selectedDate.split('-').map(Number)
  document.querySelector('#day-title').textContent = new Intl.DateTimeFormat('en-US', { month: 'long', day: 'numeric', year: 'numeric' }).format(new Date(selectedYear, selectedMonth - 1, selectedDay))
  const dayEvents = calendarState.confirmed.filter(event => visibleOnDate(event, selectedDate))
  document.querySelector('#day-count').textContent = `${dayEvents.length} items`
  renderEventList(document.querySelector('#day-events'), dayEvents, 'There are no events for this day. Ask the assistant to generate a plan.')
  const undated = calendarState.confirmed.filter(event => !event.due_date)
  document.querySelector('#undated-section').hidden = !undated.length
  document.querySelector('#undated-count').textContent = `${undated.length} items`
  renderEventList(document.querySelector('#undated-events'), undated, '')
}

function renderEventList(container, events, emptyText) {
  container.replaceChildren()
  if (!events.length) {
    if (emptyText) container.appendChild(el('div', 'empty', emptyText))
    return
  }
  for (const event of events) {
    const card = el('article', `event-card${event.done ? ' done' : ''}`)
    const check = el('button', 'event-check', event.done ? '✓' : '')
    check.type = 'button'
    check.setAttribute('aria-label', event.done ? `Mark ${window.englishDisplay ? window.englishDisplay(event.title) : event.title} incomplete` : `Mark ${window.englishDisplay ? window.englishDisplay(event.title) : event.title} complete`)
    check.addEventListener('click', () => toggleDone(event.id))
    const main = el('div', 'event-main')
    main.appendChild(el('div', 'event-name', event.title))
    if (event.detail) main.appendChild(el('div', 'event-detail', event.detail))
    appendEventSources(main, event)
    card.append(check, main)
    if (event.id.startsWith('m_')) {
      const remove = el('button', 'event-delete', 'Delete')
      remove.type = 'button'
      remove.setAttribute('aria-label', `Delete custom event: ${window.englishDisplay ? window.englishDisplay(event.title) : event.title}`)
      remove.addEventListener('click', () => {
        if (remove.dataset.confirm === 'yes') {
          deleteCustomEvent(event.id)
        } else {
          remove.dataset.confirm = 'yes'
          remove.textContent = 'Confirm deletion'
        }
      })
      card.appendChild(remove)
    }
    container.appendChild(card)
  }
}

function deleteCustomEvent(id) {
  const beforeConfirmed = calendarState.confirmed
  const beforePending = calendarState.pending
  calendarState.confirmed = beforeConfirmed.filter(item => item.id !== id)
  if (beforePending) calendarState.pending = beforePending.filter(item => item.id !== id)
  if (!saveCalendar()) {
    calendarState.confirmed = beforeConfirmed
    calendarState.pending = beforePending
    document.querySelector('#day-events').prepend(el('div', 'calendar-error', 'This browser is out of storage space. The event was not deleted.'))
    return
  }
  renderCalendar()
  renderProposal()
  renderInAppReminders()
}

function toggleDone(id) {
  const item = calendarState.confirmed.find(event => event.id === id)
  if (!item) return
  item.done = !item.done
  if (calendarState.pending) {
    const pendingItem = calendarState.pending.find(event => event.id === id)
    if (pendingItem) pendingItem.done = item.done
  }
  saveCalendar()
  renderCalendar()
  renderProposal()
  renderInAppReminders()
}

function choices(key) {
  return {
    destination_city: ['Shanghai'], company_city: ['Shanghai'], company_district: DISTRICTS,
    employment_type: ['First job after graduation', 'Changing jobs across cities'], shared_housing: ['Yes', 'No'], pets: ['Yes', 'No'],
  }[key]
}

function selectValue(key, value) {
  if (key === 'destination_city' || key === 'company_city') return /shanghai/i.test(value) || value.includes('上海') ? 'Shanghai' : window.englishDisplay ? window.englishDisplay(value) : value
  if (key === 'shared_housing') return /not open|no shared|不接受|不合租|否/i.test(value) ? 'No' : /^(yes|true|接受合租|可以合租)$/i.test(value) ? 'Yes' : value ? 'Yes' : ''
  if (key === 'pets') return /^(no|none|false|没有|无|不养)$/i.test(value) ? 'No' : value ? 'Yes' : ''
  if (key === 'employment_type') return /graduate|first job|应届|首次/i.test(value) ? 'First job after graduation' : /change|跨城市|换工作|跳槽/i.test(value) ? 'Changing jobs across cities' : value
  return window.englishDisplay ? window.englishDisplay(value) : value
}

function parseDateValue(value) {
  // Profile facts extracted from a chat may omit the year (for example,
  // "10月15日").  The backend treats those as dates in the current year, so
  // use the same rule here.  Otherwise opening and saving the picker silently
  // replaces an existing date with today.
  const found = String(value || '').match(/(?:(20\d{2})[-年/.])?(\d{1,2})[-月/.](\d{1,2})日?/)
  if (!found) return ''
  const y = Number(found[1] || shanghaiTodayParts().year), m = Number(found[2]), d = Number(found[3])
  if (m < 1 || m > 12 || d < 1 || d > new Date(y, m, 0).getDate()) return ''
  return `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

function renderProfile() {
  const fields = document.querySelector('#profile-fields')
  fields.replaceChildren()
  for (const group of PROFILE_GROUPS) {
    const card = el('section', 'profile-group')
    card.appendChild(el('h2', '', group.title))
    for (const [key, label, placeholder] of group.fields) {
      const wrapper = el(key === 'housing_preferences' || choices(key) ? 'div' : 'label', 'profile-field')
      wrapper.appendChild(el('span', '', label))
      const raw = userState.profile[key] || ''
      if (key === 'housing_preferences') {
        const box = el('div', 'housing-choices')
        box.dataset.original = raw
        for (const choice of HOUSING_OPTIONS) {
          const item = el('label', 'housing-choice')
          const check = el('input')
          check.type = 'checkbox'; check.name = key; check.value = choice
          check.checked = (window.englishDisplay ? window.englishDisplay(raw) : raw).includes(choice)
          check.addEventListener('change', () => { box.dataset.touched = 'true' })
          item.append(check, el('span', '', choice))
          box.appendChild(item)
        }
        wrapper.appendChild(box)
      } else if (key === 'start_date' || key === 'move_deadline' || key === 'commute_preference') {
        const control = el('input', 'picker-input')
        control.name = key; control.dataset.originalValue = raw; control.readOnly = true; control.value = key === 'commute_preference' ? (window.englishDisplay ? window.englishDisplay(raw) : raw) : parseDateValue(raw) || raw
        control.placeholder = 'Tap to choose'
        control.addEventListener('click', () => openPicker(key, label, control))
        wrapper.appendChild(control)
      } else if (choices(key)) {
        const control = el('select')
        control.name = key
        control.appendChild(new Option('Please select', ''))
        for (const choice of choices(key)) control.appendChild(new Option(choice, choice))
        if (key === 'company_district' && !raw) {
          const location = userState.profile.company_location || ''
          control.value = /张江|陆家嘴|金桥|zhangjiang|lujiazui|jinqiao/i.test(location) ? 'Pudong' : /徐家汇|xujiahui/i.test(location) ? 'Xuhui' : ''
        } else control.value = selectValue(key, raw)
        if (key === 'company_city' && !raw && (userState.profile.company_location || userState.profile.company_district)) control.value = 'Shanghai'
        if (key === 'pets') {
          control.dataset.original = raw
          control.addEventListener('change', () => { control.dataset.touched = 'true' })
        }
        const dropdown = el('div', 'cute-dropdown')
        const trigger = el('button', 'cute-trigger', control.value || 'Please select')
        trigger.type = 'button'
        trigger.setAttribute('aria-label', label)
        trigger.setAttribute('aria-expanded', 'false')
        trigger.classList.toggle('has-value', Boolean(control.value))
        const options = el('div', 'cute-options')
        options.hidden = true
        for (const choice of choices(key)) {
          const option = el('button', 'cute-option', choice)
          option.type = 'button'
          option.classList.toggle('selected', control.value === choice)
          option.addEventListener('click', () => {
            control.value = choice
            control.dispatchEvent(new Event('change'))
            trigger.textContent = choice
            trigger.classList.add('has-value')
            options.querySelectorAll('.cute-option').forEach(item => item.classList.toggle('selected', item === option))
            options.hidden = true
            trigger.setAttribute('aria-expanded', 'false')
          })
          options.appendChild(option)
        }
        trigger.addEventListener('click', () => {
          document.querySelectorAll('.cute-options').forEach(list => { if (list !== options) list.hidden = true })
          options.hidden = !options.hidden
          trigger.setAttribute('aria-expanded', String(!options.hidden))
          if (!options.hidden) {
            const selected = options.querySelector('.selected')
            if (selected) options.scrollTop = Math.max(0, selected.offsetTop - 100)
          }
        })
        dropdown.append(control, trigger, options)
        wrapper.appendChild(dropdown)
      } else {
        const control = el(key === 'other_requirements' ? 'textarea' : 'input')
        control.name = key; control.dataset.originalValue = raw
        control.value = window.englishDisplay ? window.englishDisplay(raw) : raw
        control.placeholder = placeholder || ''
        control.maxLength = key === 'other_requirements' ? 1500 : 300
        wrapper.appendChild(control)
      }
      card.appendChild(wrapper)
    }
    fields.appendChild(card)
  }
  const count = PROFILE_FIELDS.filter(key => userState.profile[key]).length
  document.querySelector('#profile-count').textContent = `${count} profile item(s) saved`
  document.querySelector('#history-count').textContent = `· ${userState.inputs.length}`
  const history = document.querySelector('#history-list')
  history.replaceChildren()
  if (!userState.inputs.length) history.appendChild(el('div', 'history-empty', 'No chat inputs yet.'))
  for (const item of [...userState.inputs].reverse()) {
    const row = el('div', 'history-item')
    const stamp = item.at ? new Date(item.at) : null
    if (stamp && !Number.isNaN(stamp.getTime())) row.appendChild(el('time', '', stamp.toLocaleString('en-US')))
    row.appendChild(el('div', '', window.englishDisplay ? window.englishDisplay(item.content) : item.content))
    history.appendChild(row)
  }
}

function renderReminderSettings() {
  const settings = userState.reminders
  document.querySelector('#reminder-in-app').checked = settings.inApp
  document.querySelector('#reminder-wechat').checked = settings.wechat
  document.querySelector('#reminder-three-days').value = settings.threeDays
  document.querySelector('#reminder-due-day').value = settings.dueDay
  const list = document.querySelector('#reminder-status-list')
  list.replaceChildren()
  const upcoming = calendarState.confirmed.filter(event => !event.done && event.due_date && event.due_date >= shanghaiTodayKey()).sort((a, b) => a.due_date.localeCompare(b.due_date)).slice(0, 3)
  if (!upcoming.length) list.appendChild(el('div', 'reminder-status-empty', 'No plans need reminders'))
  for (const event of upcoming) {
    const row = el('div', 'reminder-status-row')
    row.append(el('span', '', new Date(`${event.due_date}T12:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })), el('strong', '', event.title), el('em', settings.inApp ? 'In-app on' : settings.wechat ? 'WeChat not connected' : 'Off'))
    list.appendChild(row)
  }
}

function openReminderSettings() {
  document.querySelector('.profile-body').hidden = true
  document.querySelector('#reminder-settings').hidden = false
  renderReminderSettings()
}

function openReminderTimePicker(control, title) {
  const columns = document.querySelector('#picker-columns')
  columns.replaceChildren()
  const selected = REMINDER_TIMES.includes(control.value) ? control.value : '09:00'
  pickerState = { key: 'reminder_time', control, values: [Math.max(0, REMINDER_TIMES.indexOf(selected))] }
  document.querySelector('#picker-title').textContent = window.englishDisplay ? window.englishDisplay(title) : title
  document.querySelector('#picker-search-wrap').hidden = true
  document.querySelector('#picker-city-labels').hidden = true
  buildWheel(columns, REMINDER_TIMES, 0, value => value)
  document.querySelector('#profile-picker').hidden = false
  requestAnimationFrame(() => { const column = columns.querySelector('.wheel-column'); if (column) column.scrollTop = Number(column.dataset.index) * 42 })
}

function closeReminderSettings() {
  document.querySelector('#reminder-settings').hidden = true
  document.querySelector('.profile-body').hidden = false
}

function openPicker(key, title, control) {
  const modal = document.querySelector('#profile-picker')
  const columns = document.querySelector('#picker-columns')
  columns.replaceChildren()
  document.querySelector('#picker-title').textContent = title
  document.querySelector('#picker-search-wrap').hidden = true
  document.querySelector('#picker-city-labels').hidden = true
  const date = parseDateValue(control.value) || shanghaiTodayKey()
  const [year, month, day] = date.split('-').map(Number)
  pickerState = { key, control, values: key === 'commute_preference' ? [Math.max(0, COMMUTE.indexOf(control.value))] : [year, month, day] }
  if (key === 'commute_preference') buildWheel(columns, COMMUTE, 0, value => value)
  else {
    buildWheel(columns, Array.from({ length: 41 }, (_, i) => 2020 + i), 0, value => String(value))
    buildWheel(columns, Array.from({ length: 12 }, (_, i) => i + 1), 1, value => new Intl.DateTimeFormat('en-US', { month: 'long' }).format(new Date(2020, value - 1, 1)))
    buildDayWheel(columns)
  }
  modal.hidden = false
  requestAnimationFrame(() => columns.querySelectorAll('.wheel-column').forEach(column => column.scrollTop = Number(column.dataset.index) * 42))
}

function buildDayWheel(container) {
  const [year, month, day] = pickerState.values
  const limit = new Date(year, month, 0).getDate()
  pickerState.values[2] = Math.min(day, limit)
  container.querySelector('.wheel-column[data-part="2"]')?.remove()
  buildWheel(container, Array.from({ length: limit }, (_, i) => i + 1), 2, value => String(value))
  requestAnimationFrame(() => { const column = container.querySelector('.wheel-column[data-part="2"]'); if (column) column.scrollTop = Number(column.dataset.index) * 42 })
}

function buildWheel(container, values, part, label) {
  const column = el('div', 'wheel-column')
  column.dataset.part = String(part)
  column.dataset.index = String(Math.max(0, values.indexOf(pickerState.values[part])))
  column.setAttribute('role', 'listbox')
  for (const [index, value] of values.entries()) {
    const option = el('button', 'wheel-option', label(value))
    option.type = 'button'
    option.addEventListener('click', () => { column.scrollTo({ top: index * 42, behavior: 'smooth' }); choose(index) })
    column.appendChild(option)
  }
  const choose = index => {
    const next = Math.min(values.length - 1, Math.max(0, index))
    if (pickerState.values[part] === values[next]) return
    pickerState.values[part] = values[next]
    column.dataset.index = String(next)
    if (part < 2 && pickerState.key !== 'commute_preference') buildDayWheel(container)
  }
  let timer
  column.addEventListener('scroll', () => {
    clearTimeout(timer)
    timer = setTimeout(() => choose(Math.round(column.scrollTop / 42)), 60)
  })
  container.appendChild(column)
}

function closePicker() {
  document.querySelector('#profile-picker').hidden = true
  pickerState = null
}

document.querySelector('#picker-cancel').addEventListener('click', closePicker)
document.querySelector('#picker-confirm').addEventListener('click', () => {
  if (!pickerState) return
  const columns = [...document.querySelectorAll('#picker-columns .wheel-column')]
  if (pickerState.key === 'reminder_time') {
    const column = columns[0]
    const index = column ? Math.min(REMINDER_TIMES.length - 1, Math.max(0, Math.round(column.scrollTop / 42))) : 4
    pickerState.control.value = REMINDER_TIMES[index]
    closePicker()
    return
  }
  for (const column of columns) {
    const part = Number(column.dataset.part)
    const index = Math.round(column.scrollTop / 42)
    pickerState.values[part] = part === 0 && pickerState.key !== 'commute_preference' ? 2020 + index : part === 1 ? 1 + index : part === 2 ? 1 + index : index
  }
  const { key, control, values } = pickerState
  const selectedDate = `${values[0]}-${String(values[1]).padStart(2, '0')}-${String(Math.min(values[2], new Date(values[0], values[1], 0).getDate())).padStart(2, '0')}`
  if (key === 'proposal_date') pickerState.onConfirm(selectedDate)
  else control.value = key === 'commute_preference' ? COMMUTE[values[0]] : selectedDate
  closePicker()
})
document.querySelector('#profile-picker').addEventListener('click', event => { if (event.target.id === 'profile-picker') closePicker() })
document.querySelector('#profile-menu-button').addEventListener('click', () => {
  const menu = document.querySelector('#profile-menu')
  menu.hidden = !menu.hidden
  document.querySelector('#history-panel').hidden = true
  document.querySelector('#open-history').hidden = false
  document.querySelector('#profile-menu-button').setAttribute('aria-expanded', String(!menu.hidden))
})
document.querySelector('#open-history').addEventListener('click', () => {
  document.querySelector('#open-history').hidden = true
  document.querySelector('#history-panel').hidden = false
})
document.querySelector('#back-history').addEventListener('click', () => {
  document.querySelector('#history-panel').hidden = true
  document.querySelector('#open-history').hidden = false
})
document.addEventListener('click', event => {
  if (!event.target.closest('.profile-hero')) {
    document.querySelector('#profile-menu').hidden = true
    document.querySelector('#profile-menu-button').setAttribute('aria-expanded', 'false')
  }
})
document.querySelector('#profile-form').addEventListener('submit', event => {
  event.preventDefault()
  const form = event.currentTarget
  const next = {}
  for (const key of PROFILE_FIELDS) {
    const control = form.elements.namedItem(key)
    const original = control?.dataset?.originalValue || ''
    const shownOriginal = window.englishDisplay ? window.englishDisplay(original) : original
    if (key !== 'housing_preferences' && key !== 'pets' && original && control && control.value.trim() === shownOriginal) {
      next[key] = original
      continue
    }
    const value = key === 'housing_preferences'
      ? (form.querySelector('.housing-choices').dataset.touched
          ? [...form.querySelectorAll('input[name="housing_preferences"]:checked')].map(item => item.value).join(', ')
        : form.querySelector('.housing-choices').dataset.original)
      : key === 'pets' && !form.elements.namedItem(key).dataset.touched
        ? form.elements.namedItem(key).dataset.original || form.elements.namedItem(key).value.trim()
        : form.elements.namedItem(key).value.trim()
    if (value) next[key] = value
  }
  for (const key of PROFILE_FIELDS) {
    if (key === 'housing_preferences' || key === 'pets' || key === 'start_date' || key === 'move_deadline' || key === 'commute_preference' || choices(key)) continue
    const control = form.elements.namedItem(key)
    const original = control?.dataset?.originalValue || ''
    const shownOriginal = window.englishDisplay ? window.englishDisplay(original) : original
    if (control && original && control.value === shownOriginal) next[key] = original
  }
  if (!next.company_city && (next.company_district || next.company_location)) next.company_city = 'Shanghai'
  userState.profile = next
  userState.updatedAt = new Date().toISOString()
  updateIntro()
  renderOnboarding()
  const saved = saveUserState()
  renderProfile()
  if (saved) document.querySelector('#profile-status').textContent = 'Profile saved and will be used in future chats.'
})

document.querySelector('#open-reminders').addEventListener('click', openReminderSettings)
document.querySelector('#back-reminders').addEventListener('click', closeReminderSettings)
document.querySelector('#save-reminders').addEventListener('click', () => {
  userState.reminders = {
    inApp: document.querySelector('#reminder-in-app').checked,
    wechat: document.querySelector('#reminder-wechat').checked,
    threeDays: document.querySelector('#reminder-three-days').value || '09:00',
    dueDay: document.querySelector('#reminder-due-day').value || '08:30',
  }
  saveUserState()
  renderReminderSettings()
  renderInAppReminders()
  document.querySelector('#save-reminders').textContent = 'Saved'
  setTimeout(() => { const button = document.querySelector('#save-reminders'); if (button) button.textContent = 'Save reminder settings' }, 1200)
})
document.querySelector('#reminder-three-days').addEventListener('click', event => openReminderTimePicker(event.currentTarget, '3 days before due date'))
document.querySelector('#reminder-due-day').addEventListener('click', event => openReminderTimePicker(event.currentTarget, 'On the due date'))

document.querySelector('#clear-user-data').addEventListener('click', () => {
  if (!window.confirm('Clear your profile, chat history, and reminder preferences? Confirmed calendar events will remain.')) return
  localStorage.removeItem(USER_KEY)
  window.location.reload()
})

window.addEventListener('storage', event => {
  if (event.key === STORAGE_KEY) {
    calendarState = loadCalendar()
    renderCalendar()
    renderProposal()
  } else if (event.key === USER_KEY) {
    const current = loadUserState()
    messages.splice(0, messages.length, ...current.conversation)
    userState.profile = current.profile
    userState.inputs = current.inputs
    userState.reminders = current.reminders
    userState.updatedAt = current.updatedAt
    userState.onboardingDone = current.onboardingDone
    updateIntro()
    renderOnboarding()
    if (!document.querySelector('#profile-view').hidden) renderProfile()
  }
})

for (const message of messages.slice(-40)) {
  const row = addMessage(message.role, message.content, message.evidence || [], message.sources || [])
  if (message.role === 'assistant') attachFeedback(row, message)
}

if (demoMode) {
  document.querySelector('#demo-notice').hidden = false
  document.querySelector('#demo-prompts').hidden = false
  document.querySelector('.footnote').textContent = 'Fictional demo data is stored in this browser only. Requests are processed transiently; no language model is called. Do not enter real personal information.'
  document.querySelector('.privacy-note').textContent = 'Portfolio demo: use fictional details only. Profile, calendar, and chat history stay in this browser; demo requests are not stored by the application server and are not sent to a language model. Reset demo clears this app’s demo-only browser data.'
  seedDemoState()
}

function englishProfile(profile) {
  return Object.fromEntries(Object.entries(profile || {}).map(([key, value]) => [key, window.englishDisplay ? window.englishDisplay(value) : value]))
}
updateIntro()
renderOnboarding()
renderInAppReminders()
renderCalendar()
renderProposal()
if (calendarState.bulkDeleteAll) requestAnimationFrame(showProposalStart)
