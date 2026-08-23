<template>
  <div class="chat-page">
    <!-- 左侧侧边栏 -->
    <div class="sidebar" :class="{ 'sidebar-employee': !isAdmin }">
      <div class="sidebar-header">
        <button class="new-chat-btn" @click="newChat">
          <span>✚</span> 新建对话
        </button>
        <button class="sidebar-action-btn" @click="openPasswordModal">
          <span>🔒</span> 修改密码
        </button>
      </div>
      <div class="chat-history">
        <div class="history-title">对话历史</div>
        <div class="history-list">
          <div
            v-for="s in sessions"
            :key="s.id"
            class="history-item"
            :class="{ active: s.id === currentSessionId }"
            @click="loadSession(s.id)"
          >
            <span class="history-icon">💬</span>
            <span class="history-name">{{ s.title }}</span>
          </div>
          <div v-if="sessions.length === 0" class="history-empty">暂无历史对话</div>
        </div>
      </div>
      <div class="nav-section" v-if="isAdmin">
        <div class="nav-title">数据管理</div>
        <div
          v-for="item in navItems"
          :key="item.id"
          class="nav-item"
          :class="{ active: activeModule === item.id }"
          @click="loadDataModule(item.id)"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          <span class="nav-label">{{ item.label }}</span>
        </div>
      </div>
    </div>

    <!-- 右侧主区域 -->
    <div class="main-area">
      <!-- 顶部栏 -->
      <div class="top-bar">
        <div class="top-bar-left">
          <span class="top-bar-title">HR 智能助手</span>
        </div>
        <div class="top-bar-right">
          <div class="user-info">
            <div class="user-avatar">{{ displayName.charAt(0) }}</div>
            <div class="user-detail">
              <div class="user-name">{{ displayName }}</div>
              <div class="user-role">{{ isAdmin ? '管理员' : '员工' }} · {{ employeeCode }}</div>
            </div>
          </div>
          <button class="notif-btn" @click="toggleNotifPanel" title="通知">
            🔔
            <span class="notif-badge" v-if="unreadCount > 0">{{ unreadCount > 9 ? '9+' : unreadCount }}</span>
          </button>
          <button class="logout-btn" @click="handleLogout" title="退出登录">⏻</button>
        </div>
      </div>

      <!-- 通知下拉面板 -->
      <div class="notif-dropdown" v-if="showNotifPanel">
        <div class="notif-dropdown-header">
          <span>通知消息</span>
          <button class="notif-close" @click="showNotifPanel = false">✕</button>
        </div>
        <div class="notif-dropdown-body">
          <div v-if="notifList.length === 0" class="notif-empty">暂无新通知</div>
          <div v-for="(n, i) in notifList" :key="i" class="notif-item" :class="{ 'notif-approval': n.type === 'approval' }">
            <div class="notif-icon">{{ n.type === 'approval' ? '📋' : '✅' }}</div>
            <div class="notif-content">
              <div class="notif-title">{{ n.title }}</div>
              <div class="notif-detail">{{ n.detail }}</div>
              <div class="notif-time" v-if="n.created_at">{{ n.created_at }}</div>
              <!-- 管理员审核按钮 -->
              <div class="notif-actions" v-if="n.type === 'approval' && !n.processed">
                <button class="notif-btn-approve" @click="handleApprove(n, true)" :disabled="n.processing">✓ 通过</button>
                <button class="notif-btn-reject" @click="handleApprove(n, false)" :disabled="n.processing">✗ 驳回</button>
              </div>
              <!-- 驳回原因输入 -->
              <div class="reject-reason-box" v-if="n.showRejectInput">
                <input v-model="n.rejectReason" placeholder="请输入驳回原因" @keyup.enter="submitReject(n)" />
                <button class="notif-btn-confirm-reject" @click="submitReject(n)">提交</button>
              </div>
              <!-- 处理结果 -->
              <div class="notif-processed" v-if="n.processed">✓ 已{{ n.processedStatus }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 内容区 -->
      <div class="content-area">
        <!-- 欢迎页 (无消息时) -->
        <div class="welcome-page" v-if="messages.length === 0 && !showDataPanel">
          <div class="welcome-container">
            <div class="welcome-icon">👋</div>
            <div class="welcome-title">{{ greeting }},{{ displayName }}</div>
            <div class="welcome-subtitle">{{ isAdmin ? 'HR 管理工作台，对话即工作台' : '有什么可以帮你？' }}</div>
            <div class="welcome-cards">
              <div
                v-for="card in welcomeCards"
                :key="card.title"
                class="welcome-card"
                @click="sendQuickMessage(card.prompt)"
              >
                <div class="card-icon">{{ card.icon }}</div>
                <div class="card-body">
                  <div class="card-title">{{ card.title }}</div>
                  <div class="card-desc">{{ card.desc }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 聊天区域 -->
        <div class="chat-area" v-else-if="messages.length > 0 && !showDataPanel">
          <div class="messages-container" ref="messagesContainer">
            <div
              v-for="(msg, idx) in messages"
              :key="idx"
              class="message-row"
              :class="msg.role"
            >
              <div class="message-avatar">
                {{ msg.role === 'user' ? displayName.charAt(0) : '🤖' }}
              </div>
              <div class="message-content">
                <div class="message-role">{{ msg.role === 'user' ? displayName : 'HR 助手' }}</div>
                <div class="message-text" v-html="renderMarkdown(msg.content)"></div>
              </div>
            </div>
            <div v-if="chatLoading" class="message-row assistant">
              <div class="message-avatar">🤖</div>
              <div class="message-content">
                <div class="message-role">HR 助手</div>
                <div class="message-text typing">正在思考中...</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 数据管理面板 -->
        <div class="data-panel" v-if="showDataPanel">
          <div class="data-header">
            <h3>{{ currentModuleTitle }}</h3>
            <div class="data-actions">
              <button class="data-btn" @click="refreshData">🔄 刷新</button>
              <button class="data-btn primary" v-if="!currentModuleReadonly" @click="showAddForm">➕ 新增</button>
              <button class="data-btn" @click="showDataPanel = false">← 返回对话</button>
            </div>
          </div>
          <div class="data-table-wrapper">
            <table class="data-table" v-if="dataRows.length > 0">
              <thead>
                <tr>
                  <th v-for="col in dataColumns" :key="col.key">{{ col.label }}</th>
                  <th v-if="!currentModuleReadonly">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, idx) in dataRows" :key="idx">
                  <td v-for="col in dataColumns" :key="col.key">{{ row[col.key] ?? '' }}</td>
                  <td v-if="!currentModuleReadonly" class="action-cell">
                    <button class="row-btn" @click="showEditForm(row)">编辑</button>
                    <button class="row-btn danger" @click="deleteRow(row)">删除</button>
                  </td>
                </tr>
              </tbody>
            </table>
            <div v-else class="data-empty">暂无数据</div>
          </div>
        </div>
      </div>

      <!-- 底部输入区 -->
      <div class="input-area" v-if="!showDataPanel">
        <div class="quick-prompts" v-if="messages.length === 0">
          <span
            v-for="p in quickPrompts"
            :key="p"
            class="quick-tag"
            @click="sendQuickMessage(p)"
          >{{ p }}</span>
        </div>
        <div class="input-card">
          <button
            v-if="isAdmin"
            class="upload-btn"
            @click="triggerUpload"
            :disabled="chatLoading"
            title="上传简历"
          >📎</button>
          <input
            v-if="isAdmin"
            ref="fileInput"
            type="file"
            accept=".pdf,.doc,.docx"
            style="display:none"
            @change="handleUpload"
          />
          <input
            v-model="inputMessage"
            type="text"
            placeholder="输入消息..."
            @keyup.enter="sendMessage"
            :disabled="chatLoading"
          />
          <button class="send-btn" @click="sendMessage" :disabled="!inputMessage.trim() || chatLoading">
            发送
          </button>
        </div>
      </div>
    </div>

    <div class="form-overlay" v-if="passwordModalVisible" @click.self="closePasswordModal">
      <div class="form-modal password-modal">
        <div class="form-header">
          <h3>修改密码</h3>
        </div>
        <div class="form-body">
          <div class="form-field">
            <label>旧密码</label>
            <input v-model="passwordForm.oldPassword" type="password" placeholder="请输入旧密码" />
          </div>
          <div class="form-field">
            <label>新密码</label>
            <input v-model="passwordForm.newPassword" type="password" placeholder="请输入新密码" />
          </div>
          <div class="form-field">
            <label>确认新密码</label>
            <input v-model="passwordForm.confirmPassword" type="password" placeholder="请再次输入新密码" />
          </div>
          <div class="password-hint" v-if="passwordError">{{ passwordError }}</div>
        </div>
        <div class="form-footer">
          <button class="data-btn" @click="closePasswordModal">取消</button>
          <button class="data-btn primary" @click="submitPasswordChange" :disabled="passwordSubmitting">保存</button>
        </div>
      </div>
    </div>

    <!-- 新增/编辑表单弹窗 -->
    <div class="form-overlay" v-if="formVisible" @click.self="formVisible = false">
      <div class="form-modal">
        <div class="form-header">
          <h3>{{ formMode === 'add' ? '新增' : '编辑' }}{{ currentModuleTitle }}</h3>
        </div>
        <div class="form-body">
          <div v-for="field in formFields" :key="field.key" class="form-field">
            <label>{{ field.label }}</label>
            <select v-if="field.type === 'select'" v-model="formData[field.key]">
              <option value="">请选择</option>
              <option v-for="opt in field.options" :key="opt" :value="opt">{{ opt }}</option>
            </select>
            <input
              v-else
              v-model="formData[field.key]"
              :type="field.type || 'text'"
              :placeholder="field.placeholder || ''"
            />
          </div>
        </div>
        <div class="form-footer">
          <button class="data-btn" @click="formVisible = false">取消</button>
          <button class="data-btn primary" @click="submitForm">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { marked } from 'marked'
import api from '../api'

// 配置 marked
marked.setOptions({ breaks: true, gfm: true })

const router = useRouter()
const userStore = useUserStore()

// ===== 状态 =====
const messages = ref([])
const inputMessage = ref('')
const currentSessionId = ref('')
const chatLoading = ref(false)
const sessions = ref([])
const showDataPanel = ref(false)
const activeModule = ref('')
const dataRows = ref([])
const formVisible = ref(false)
const formMode = ref('add')
const formData = ref({})
const messagesContainer = ref(null)
const fileInput = ref(null)
const uploadedFilePath = ref('')
const showNotifPanel = ref(false)
const notifList = ref([])
const unreadCount = ref(0)
const passwordModalVisible = ref(false)
const passwordSubmitting = ref(false)
const passwordError = ref('')
const passwordForm = ref({ oldPassword: '', newPassword: '', confirmPassword: '' })
let notifTimer = null
const sessionStorageKey = computed(() => `hr-chat-sessions:${employeeCode.value || 'guest'}`)

const isAdmin = computed(() => userStore.isAdmin)
const displayName = computed(() => userStore.displayName)
const employeeCode = computed(() => userStore.employeeCode)

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '凌晨好'
  if (h < 12) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

// ===== 导航项 =====
const navItems = [
  { id: 'employees', icon: '👤', label: '员工管理' },
  { id: 'attendance', icon: '🕐', label: '考勤管理' },
  { id: 'leave', icon: '🏖️', label: '请假管理' },
  { id: 'leaveBalances', icon: '📊', label: '假期余额' },
  { id: 'payroll', icon: '💰', label: '薪酬管理' },
  { id: 'recruitment', icon: '📋', label: '招聘管理' },
  { id: 'interviews', icon: '📅', label: '面试管理' },
  { id: 'notifications', icon: '🔔', label: '通知日志' },
  { id: 'audit', icon: '📝', label: '审计日志' },
]

// ===== 模块配置 =====
const moduleConfig = {
  employees: {
    title: '员工管理', readonly: false,
    columns: [
      { key: 'employee_code', label: '工号' },
      { key: 'name', label: '姓名' },
      { key: 'department', label: '部门' },
      { key: 'position', label: '职位' },
      { key: 'phone', label: '手机号' },
      { key: 'email', label: '邮箱' },
      { key: 'status', label: '状态' },
    ],
    fields: [
      { key: 'employee_code', label: '工号' },
      { key: 'name', label: '姓名' },
      { key: 'gender', label: '性别' },
      { key: 'department', label: '部门' },
      { key: 'position', label: '职位' },
      { key: 'phone', label: '手机号' },
      { key: 'email', label: '邮箱' },
      { key: 'hire_date', label: '入职日期' },
      { key: 'status', label: '状态' },
    ],
  },
  attendance: {
    title: '考勤管理', readonly: false,
    columns: [
      { key: 'id', label: 'ID' },
      { key: 'employee_code', label: '工号' },
      { key: 'date', label: '日期' },
      { key: 'clock_in', label: '上班打卡' },
      { key: 'clock_out', label: '下班打卡' },
      { key: 'overtime_hours', label: '加班' },
      { key: 'status', label: '状态' },
    ],
    fields: [
      { key: 'employee_code', label: '工号' },
      { key: 'date', label: '日期' },
      { key: 'clock_in', label: '上班时间' },
      { key: 'clock_out', label: '下班时间' },
      { key: 'overtime_hours', label: '加班小时' },
      { key: 'status', label: '状态', type: 'select', options: ['正常', '迟到', '早退', '缺勤', '加班'] },
    ],
  },
  leave: {
    title: '请假管理', readonly: false,
    columns: [
      { key: 'id', label: 'ID' },
      { key: 'employee_code', label: '工号' },
      { key: 'leave_type', label: '类型' },
      { key: 'start_date', label: '开始' },
      { key: 'end_date', label: '结束' },
      { key: 'total_days', label: '天数' },
      { key: 'status', label: '状态' },
      { key: 'reason', label: '原因' },
    ],
    fields: [
      { key: 'employee_code', label: '工号' },
      { key: 'leave_type', label: '类型', type: 'select', options: ['年假', '事假', '病假', '婚假', '产假', '调休'] },
      { key: 'start_date', label: '开始日期' },
      { key: 'end_date', label: '结束日期' },
      { key: 'total_days', label: '天数' },
      { key: 'status', label: '状态', type: 'select', options: ['待审批', '已批准', '已驳回', '已取消'] },
      { key: 'reason', label: '原因' },
    ],
  },
  leaveBalances: {
    title: '假期余额总览', readonly: true,
    columns: [
      { key: 'employee_code', label: '工号' },
      { key: 'name', label: '姓名' },
      { key: 'department', label: '部门' },
      { key: '年假', label: '年假' },
      { key: '事假', label: '事假' },
      { key: '病假', label: '病假' },
      { key: '婚假', label: '婚假' },
      { key: '产假', label: '产假' },
      { key: '调休', label: '调休' },
    ],
    fields: [],
  },
  payroll: {
    title: '薪酬管理', readonly: false,
    columns: [
      { key: 'employee_code', label: '工号' },
      { key: 'year', label: '年' },
      { key: 'month', label: '月' },
      { key: 'gross_pay', label: '应发' },
      { key: 'net_pay', label: '实发' },
    ],
    fields: [
      { key: 'employee_code', label: '工号' },
      { key: 'year', label: '年' },
      { key: 'month', label: '月' },
      { key: 'base_salary', label: '基本工资' },
      { key: 'performance', label: '绩效' },
    ],
  },
  recruitment: {
    title: '招聘管理', readonly: false,
    columns: [
      { key: 'id', label: 'ID' },
      { key: 'position_name', label: '职位' },
      { key: 'candidate_name', label: '候选人' },
      { key: 'candidate_phone', label: '电话' },
      { key: 'candidate_email', label: '邮箱' },
      { key: 'status', label: '状态' },
      { key: 'created_at', label: '申请日期' },
    ],
    fields: [
      { key: 'position_name', label: '职位' },
      { key: 'candidate_name', label: '候选人' },
      { key: 'candidate_phone', label: '电话' },
      { key: 'candidate_email', label: '邮箱' },
      { key: 'department', label: '部门' },
      { key: 'status', label: '状态', type: 'select', options: ['简历筛选', '初试', '复试', '终试', '已拒绝', '已发offer', '已入职'] },
    ],
  },
  interviews: {
    title: '面试管理', readonly: false,
    columns: [
      { key: 'id', label: 'ID' },
      { key: 'recruitment_id', label: '招聘ID' },
      { key: 'candidate_name', label: '候选人' },
      { key: 'position_name', label: '职位' },
      { key: 'round', label: '轮次' },
      { key: 'interview_date', label: '面试时间' },
      { key: 'interviewer_code', label: '面试官' },
      { key: 'status', label: '状态' },
      { key: 'result', label: '结果' },
    ],
    fields: [
      { key: 'recruitment_id', label: '招聘ID' },
      { key: 'round', label: '轮次', type: 'select', options: ['初试', '复试', '终试'] },
      { key: 'interview_date', label: '面试时间' },
      { key: 'interviewer_code', label: '面试官工号' },
      { key: 'location', label: '地点' },
      { key: 'status', label: '状态', type: 'select', options: ['待面试', '已完成', '已取消'] },
      { key: 'result', label: '结果', type: 'select', options: ['', '通过', '不通过', '待定'] },
    ],
  },
  notifications: {
    title: '通知日志', readonly: true,
    columns: [
      { key: 'id', label: 'ID' },
      { key: 'type', label: '类型' },
      { key: 'recipient', label: '接收人' },
      { key: 'subject', label: '主题' },
      { key: 'status', label: '状态' },
      { key: 'sent_at', label: '发送时间' },
    ],
    fields: [],
  },
  audit: {
    title: '审计日志', readonly: true,
    columns: [
      { key: 'id', label: 'ID' },
      { key: 'operator_code', label: '操作人' },
      { key: 'action', label: '操作' },
      { key: 'target_table', label: '目标表' },
      { key: 'created_at', label: '时间' },
    ],
    fields: [],
  },
}

const currentModuleTitle = computed(() => activeModule.value ? moduleConfig[activeModule.value]?.title : '')
const currentModuleReadonly = computed(() => activeModule.value ? moduleConfig[activeModule.value]?.readonly : false)
const dataColumns = computed(() => activeModule.value ? moduleConfig[activeModule.value]?.columns || [] : [])
const formFields = computed(() => activeModule.value ? moduleConfig[activeModule.value]?.fields || [] : [])

// ===== 欢迎页卡片 =====
const welcomeCards = computed(() => {
  if (isAdmin.value) {
    return [
      { icon: '👤', title: '查询员工信息', desc: '按工号、姓名或部门查询', prompt: '查询技术部所有员工' },
      { icon: '🕐', title: '查看考勤记录', desc: '查询员工打卡、请假记录', prompt: '查询EMP001上个月的考勤记录' },
      { icon: '💰', title: '薪酬个税查询', desc: '工资明细、个税计算', prompt: '月薪18000元交多少税？' },
      { icon: '📚', title: '制度知识问答', desc: '员工手册、考勤制度', prompt: '员工手册中关于迟到的规定是什么？' },
    ]
  }
  return [
    { icon: '🕐', title: '查看我的考勤', desc: '查询近期打卡、加班记录', prompt: '查询我的考勤记录' },
    { icon: '💰', title: '工资明细查询', desc: '查看月度工资详情', prompt: '查看我的工资明细' },
    { icon: '🏖️', title: '假期余额查询', desc: '年假、事假等剩余天数', prompt: '我还有多少年假？' },
    { icon: '📚', title: '制度知识问答', desc: '员工手册、考勤制度', prompt: '员工手册中关于迟到的规定' },
  ]
})

const quickPrompts = computed(() => {
  if (isAdmin.value) {
    return ['查看公司员工概览', '月薪18000交多少税?', '年假有几天?', '查看招聘进度']
  }
  return ['查询我的考勤记录', '查看我的工资明细', '我还有多少年假？', '员工手册中关于迟到的规定']
})

// ===== 方法 =====
function generateSessionId() {
  return Date.now().toString(36) + Math.random().toString(36).substr(2, 5)
}

function cloneMessages(items) {
  return items.map(item => ({ ...item }))
}

function normalizeSessions(rawSessions) {
  return (rawSessions || [])
    .filter(session => session && session.id)
    .map(session => ({
      id: session.id,
      title: session.title || '新对话',
      messages: Array.isArray(session.messages) ? cloneMessages(session.messages) : [],
      updatedAt: session.updatedAt || Date.now(),
    }))
    .sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0))
}

function persistSessions() {
  if (!employeeCode.value) return
  localStorage.setItem(sessionStorageKey.value, JSON.stringify(normalizeSessions(sessions.value)))
}

function hydrateSessions() {
  if (!employeeCode.value) {
    sessions.value = []
    return
  }
  try {
    const cached = JSON.parse(localStorage.getItem(sessionStorageKey.value) || '[]')
    sessions.value = normalizeSessions(cached)
  } catch {
    sessions.value = []
  }
}

function upsertCurrentSession() {
  if (!currentSessionId.value) return
  const currentIndex = sessions.value.findIndex(session => session.id === currentSessionId.value)
  if (messages.value.length === 0) {
    if (currentIndex >= 0) {
      sessions.value.splice(currentIndex, 1)
      persistSessions()
    }
    return
  }
  const title = messages.value.find(message => message.role === 'user')?.content?.slice(0, 20) || '新对话'
  const record = {
    id: currentSessionId.value,
    title,
    messages: cloneMessages(messages.value),
    updatedAt: Date.now(),
  }
  if (currentIndex >= 0) {
    sessions.value.splice(currentIndex, 1, record)
  } else {
    sessions.value.unshift(record)
  }
  sessions.value = normalizeSessions(sessions.value)
  persistSessions()
}

function newChat() {
  upsertCurrentSession()
  messages.value = []
  currentSessionId.value = generateSessionId()
  showDataPanel.value = false
  showNotifPanel.value = false
}

function loadSession(sid) {
  const target = sessions.value.find(session => session.id === sid)
  if (!target) return
  upsertCurrentSession()
  currentSessionId.value = sid
  messages.value = cloneMessages(target.messages || [])
  showDataPanel.value = false
  showNotifPanel.value = false
}

async function sendMessage() {
  const msg = inputMessage.value.trim()
  if (!msg || chatLoading.value) return
  inputMessage.value = ''
  if (!currentSessionId.value) currentSessionId.value = generateSessionId()

  messages.value.push({ role: 'user', content: msg })
  chatLoading.value = true
  await scrollToBottom()

  try {
    const res = await api.chat(msg, currentSessionId.value)
    messages.value.push({ role: 'assistant', content: res.data?.response || '抱歉，处理请求时出现错误。' })
  } catch (e) {
    messages.value.push({ role: 'assistant', content: `请求失败: ${e.message}` })
  } finally {
    chatLoading.value = false
    upsertCurrentSession()
    await scrollToBottom()
    refreshNotif()
  }
}

function sendQuickMessage(prompt) {
  inputMessage.value = prompt
  sendMessage()
}

function triggerUpload() {
  fileInput.value?.click()
}

async function handleUpload(e) {
  const file = e.target.files[0]
  if (!file) return
  e.target.value = '' // 重置以便重复选同一文件

  if (!currentSessionId.value) currentSessionId.value = generateSessionId()

  // 显示用户上传消息
  messages.value.push({ role: 'user', content: `📎 已上传简历: ${file.name}` })
  chatLoading.value = true
  await scrollToBottom()

  try {
    // 1. 上传文件到服务器
    const uploadRes = await api.uploadFile(file)
    const filePath = uploadRes.data?.file_path || ''

    // 2. 把文件路径传给 Agent，让 Agent 调用 resume_parse_tool
    const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}')
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Code': userInfo.employee_code || '',
        'X-User-Role': userInfo.role || 'employee',
      },
      body: JSON.stringify({
        message: `请解析这份简历文件: ${file.name}`,
        session_id: currentSessionId.value,
        file_path: filePath,
        user_info: {
          role: userInfo.role || 'employee',
          employee_code: userInfo.employee_code || '',
          name: userInfo.name || '',
          department: userInfo.department || '',
        },
      }),
    })
    const data = await res.json()
    messages.value.push({
      role: 'assistant',
      content: data.data?.response || '简历解析完成，但未获取到结果。',
    })
  } catch (e) {
    messages.value.push({ role: 'assistant', content: `上传失败: ${e.message}` })
  } finally {
    chatLoading.value = false
    await scrollToBottom()
  }
}

function openPasswordModal() {
  passwordError.value = ''
  passwordForm.value = { oldPassword: '', newPassword: '', confirmPassword: '' }
  passwordModalVisible.value = true
}

function closePasswordModal() {
  if (passwordSubmitting.value) return
  passwordModalVisible.value = false
}

async function submitPasswordChange() {
  const { oldPassword, newPassword, confirmPassword } = passwordForm.value
  if (!oldPassword || !newPassword || !confirmPassword) {
    passwordError.value = '请完整填写密码信息'
    return
  }
  if (newPassword !== confirmPassword) {
    passwordError.value = '两次输入的新密码不一致'
    return
  }
  if (newPassword.length < 6) {
    passwordError.value = '新密码至少 6 位'
    return
  }
  passwordSubmitting.value = true
  passwordError.value = ''
  try {
    await api.changePassword({
      employee_code: employeeCode.value,
      old_password: oldPassword,
      new_password: newPassword,
    })
    passwordModalVisible.value = false
    alert('密码修改成功，请使用新密码重新登录')
    handleLogout()
  } catch (e) {
    passwordError.value = e.response?.data?.error || e.response?.data?.msg || e.message || '修改失败'
  } finally {
    passwordSubmitting.value = false
  }
}

async function scrollToBottom() {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

function renderMarkdown(text) {
  if (!text) return ''
  return marked.parse(text)
}

async function loadDataModule(moduleId) {
  activeModule.value = moduleId
  showDataPanel.value = true
  await fetchData(moduleId)
}

async function fetchData(moduleId) {
  try {
    let res
    switch (moduleId) {
      case 'employees': res = await api.getEmployees({}); break
      case 'attendance': res = await api.getAttendance({}); break
      case 'leave': res = await api.getLeaves(); break
      case 'leaveBalances': res = await api.getAllLeaveBalances(); break
      case 'payroll': res = await api.getPayrollAll(); break
      case 'recruitment': res = await api.getRecruitments({}); break
      case 'interviews': res = await api.getInterviews({}); break
      case 'notifications': res = await api.getNotifications(50); break
      case 'audit': res = await api.getAuditLogs({}); break
    }
    dataRows.value = res?.data || []
  } catch (e) {
    console.error('fetchData error:', e)
    dataRows.value = []
  }
}

function refreshData() {
  if (activeModule.value) fetchData(activeModule.value)
}

function showAddForm() {
  formMode.value = 'add'
  formData.value = {}
  formVisible.value = true
}

function showEditForm(row) {
  formMode.value = 'edit'
  formData.value = { ...row }
  formVisible.value = true
}

async function submitForm() {
  try {
    const mod = activeModule.value
    const data = { ...formData.value }
    if (formMode.value === 'add') {
      // 新增
      switch (mod) {
        case 'employees': await api.createEmployee(data); break
        case 'attendance': await api.createAttendance(data); break
        case 'payroll': await api.createPayroll(data); break
        case 'recruitment': await api.createRecruitment(data); break
        case 'interviews': await api.scheduleInterview(data); break
        case 'leave': await api.submitLeave(data); break
      }
    } else {
      // 编辑
      const id = data.id || data.employee_code
      switch (mod) {
        case 'employees': await api.updateEmployee(data.employee_code, data); break
        case 'attendance': await api.updateAttendance(id, data); break
        case 'payroll': await api.updatePayroll(id, data); break
        case 'recruitment': await api.updateRecruitment(id, data); break
        case 'interviews': await api.updateInterview(id, data); break
        case 'leave': await api.updateLeave(id, data); break
      }
    }
    formVisible.value = false
    refreshData()
  } catch (e) {
    alert('保存失败: ' + (e.response?.data?.msg || e.message))
  }
}

async function deleteRow(row) {
  const mod = activeModule.value
  if (!confirm('确认删除此记录？')) return
  try {
    const id = row.id || row.employee_code
    switch (mod) {
      case 'employees': await api.deleteEmployee(row.employee_code); break
      case 'attendance': await api.deleteAttendance(id); break
      case 'payroll': await api.deletePayroll(id); break
      case 'recruitment': await api.deleteRecruitment(id); break
      case 'interviews': await api.deleteInterview(id); break
      case 'leave': await api.deleteLeave(id); break
    }
    refreshData()
  } catch (e) {
    alert('删除失败: ' + (e.response?.data?.msg || e.message))
  }
}

// ===== 通知 =====
async function fetchNotifications() {
  try {
    const res = await api.getUnreadNotifications()
    if (!showNotifPanel.value) {
      // 面板关闭时：更新列表和数字
      notifList.value = res.data || []
      unreadCount.value = (res.data || []).length
    }
    // 面板打开时：不覆盖列表（保持已显示的消息），也不更新数字（已清零）
  } catch (e) {
    // 静默失败
  }
}

function toggleNotifPanel() {
  showNotifPanel.value = !showNotifPanel.value
  if (showNotifPanel.value) {
    // 打开面板：拉取通知显示
    api.getUnreadNotifications().then(res => {
      notifList.value = res.data || []
      // 标记为已读，清除红色数字
      notifList.value.forEach(n => {
        api.markNotifRead(n.notif_id).catch(() => {})
      })
      unreadCount.value = 0
    })
  }
}

// 管理员审核
async function handleApprove(n, approved) {
  if (approved) {
    n.processing = true
    try {
      const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}')
      await api.approveLeave({
        leave_id: n.leave_id,
        approved: true,
        operator_code: userInfo.employee_code,
      })
      n.processed = true
      n.processedStatus = '通过'
      setTimeout(fetchNotifications, 500)
      // 强制刷新数据面板
      if (activeModule.value && showDataPanel.value) {
        await fetchData(activeModule.value)
      }
    } catch (e) {
      alert('操作失败: ' + e.message)
    } finally {
      n.processing = false
    }
  } else {
    n.showRejectInput = true
  }
}

async function submitReject(n) {
  if (!n.rejectReason || !n.rejectReason.trim()) {
    alert('请输入驳回原因')
    return
  }
  n.processing = true
  try {
    const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}')
    await api.approveLeave({
      leave_id: n.leave_id,
      approved: false,
      reason: n.rejectReason.trim(),
      operator_code: userInfo.employee_code,
    })
    n.processed = true
    n.processedStatus = '驳回'
    n.showRejectInput = false
    setTimeout(fetchNotifications, 500)
    // 强制刷新数据面板
    if (activeModule.value && showDataPanel.value) {
      await fetchData(activeModule.value)
    }
  } catch (e) {
    alert('操作失败: ' + e.message)
  } finally {
    n.processing = false
  }
}

// 员工查看后标记已读
async function markEmployeeNotifRead(n) {
  try {
    await api.markNotifRead(n.notif_id)
    setTimeout(fetchNotifications, 300)
  } catch (e) {
    // 静默
  }
}

// 每次发消息后刷新通知
function refreshNotif() {
  fetchNotifications()
}

function handleLogout() {
  userStore.logout()
  router.push('/login')
}

onMounted(() => {
  hydrateSessions()
  currentSessionId.value = generateSessionId()
  // 启动定时刷新（每15秒刷新通知+数据面板）
  fetchNotifications()
  notifTimer = setInterval(() => {
    fetchNotifications()
    // 管理端：数据面板打开时也刷新
    if (isAdmin.value && activeModule.value && showDataPanel.value) {
      fetchData(activeModule.value)
    }
  }, 15000)
})

onUnmounted(() => {
  if (notifTimer) clearInterval(notifTimer)
})

watch(employeeCode, () => {
  hydrateSessions()
  currentSessionId.value = generateSessionId()
  messages.value = []
  showDataPanel.value = false
})
</script>

<style scoped>
.chat-page { display: flex; height: 100vh; overflow: hidden; }

/* ===== 侧边栏 ===== */
.sidebar {
  width: 280px; min-width: 280px;
  background: linear-gradient(180deg, #fbfcff 0%, #f7f8fa 100%); border-right: 1px solid #eceef1;
  display: flex; flex-direction: column;
  height: 100vh; overflow-y: auto;
}
.sidebar-employee { width: 280px; }
.sidebar-header { padding: 14px; display: grid; gap: 10px; }
.new-chat-btn {
  width: 100%; height: 38px;
  background: linear-gradient(135deg, #165DFF 0%, #5b8cff 100%); color: #fff;
  border-radius: 8px; font-size: 14px; font-weight: 500;
  display: flex; align-items: center; justify-content: center; gap: 6px;
  transition: background 0.2s;
}
.new-chat-btn:hover { filter: brightness(0.96); }
.sidebar-action-btn {
  width: 100%; height: 38px;
  background: #fff; color: #1d2129;
  border: 1px solid #e5e6eb; border-radius: 8px;
  font-size: 14px; font-weight: 500;
  display: flex; align-items: center; justify-content: center; gap: 6px;
  transition: all 0.2s;
}
.sidebar-action-btn:hover { border-color: #165DFF; color: #165DFF; background: #f0f5ff; }

.chat-history { padding: 0 12px; flex: 1; overflow-y: auto; }
.history-title { font-size: 12px; color: #86909c; padding: 12px 8px 6px; }
.history-list { }
.history-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px; border-radius: 6px; cursor: pointer;
  font-size: 13px; color: #4e5969;
  transition: background 0.15s;
}
.history-item:hover { background: #f0f0f0; }
.history-item.active { background: #e8f3ff; color: #165DFF; }
.history-icon { font-size: 14px; }
.history-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.history-empty { font-size: 12px; color: #c9cdd4; text-align: center; padding: 20px 0; }

.nav-section { padding: 12px; border-top: 1px solid #eceef1; }
.nav-title { font-size: 12px; color: #86909c; padding: 8px 8px 6px; }
.nav-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px; border-radius: 6px; cursor: pointer;
  font-size: 13px; color: #4e5969;
  transition: background 0.15s;
}
.nav-item:hover { background: #f0f0f0; }
.nav-item.active { background: #e8f3ff; color: #165DFF; }
.nav-icon { font-size: 16px; }

/* ===== 主区域 ===== */
.main-area { flex: 1; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }

/* 顶部栏 */
.top-bar {
  height: 48px; min-height: 48px;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 20px; border-bottom: 1px solid #eceef1;
  background: rgba(255,255,255,0.92);
  backdrop-filter: blur(12px);
}
.top-bar-title { font-size: 15px; font-weight: 600; color: #1d2129; }
.top-bar-right { display: flex; align-items: center; gap: 12px; }
.user-info { display: flex; align-items: center; gap: 8px; }
.user-avatar {
  width: 32px; height: 32px; border-radius: 50%;
  background: #165DFF; color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 600;
}
.user-detail { }
.user-name { font-size: 13px; font-weight: 500; color: #1d2129; }
.user-role { font-size: 11px; color: #86909c; }
.logout-btn {
  width: 32px; height: 32px; border-radius: 6px;
  background: transparent; color: #86909c; font-size: 16px;
  display: flex; align-items: center; justify-content: center;
  transition: background 0.15s;
}
.logout-btn:hover { background: #fff2f0; color: #f53f3f; }
.notif-btn {
  background: transparent; font-size: 18px; padding: 6px 8px;
  color: #4e5969; border-radius: 8px; position: relative; transition: all 0.2s;
}
.notif-btn:hover { background: #f0f5ff; color: #165DFF; }
.notif-badge {
  position: absolute; top: 2px; right: 2px;
  background: #f53f3f; color: #fff; font-size: 10px; font-weight: 600;
  min-width: 16px; height: 16px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  padding: 0 4px; line-height: 1;
}
.notif-dropdown {
  position: absolute; top: 48px; right: 16px; width: 380px; max-width: 90vw;
  background: #fff; border-radius: 12px; box-shadow: 0 8px 40px rgba(0,0,0,0.12);
  z-index: 100; overflow: hidden;
}
.notif-dropdown-header {
  padding: 14px 16px; border-bottom: 1px solid #eceef1;
  display: flex; justify-content: space-between; align-items: center;
  font-weight: 600; font-size: 15px;
}
.notif-close { background: none; font-size: 16px; color: #86909c; }
.notif-dropdown-body { max-height: 400px; overflow-y: auto; }
.notif-empty { padding: 40px; text-align: center; color: #c9cdd4; font-size: 14px; }
.notif-item {
  padding: 12px 16px; border-bottom: 1px solid #f2f3f5;
  display: flex; gap: 10px; align-items: flex-start;
}
.notif-item:hover { background: #f7f8fa; }
.notif-item.notif-approval { background: #fffbe6; }
.notif-icon { font-size: 20px; flex-shrink: 0; }
.notif-content { flex: 1; min-width: 0; }
.notif-title { font-size: 14px; font-weight: 500; color: #1d2129; }
.notif-detail { font-size: 12px; color: #86909c; margin-top: 2px; }
.notif-time { font-size: 11px; color: #c9cdd4; margin-top: 4px; }
.notif-actions { display: flex; gap: 8px; margin-top: 8px; }
.notif-btn-approve {
  padding: 4px 14px; background: #00b42a; color: #fff;
  border-radius: 6px; font-size: 12px; font-weight: 500; transition: opacity 0.2s;
}
.notif-btn-approve:hover { opacity: 0.85; }
.notif-btn-approve:disabled { opacity: 0.5; }
.notif-btn-reject {
  padding: 4px 14px; background: #f53f3f; color: #fff;
  border-radius: 6px; font-size: 12px; font-weight: 500; transition: opacity 0.2s;
}
.notif-btn-reject:hover { opacity: 0.85; }
.notif-btn-reject:disabled { opacity: 0.5; }
.reject-reason-box { display: flex; gap: 6px; margin-top: 6px; }
.reject-reason-box input {
  flex: 1; height: 30px; border: 1px solid #d9d9d9; border-radius: 6px;
  padding: 0 8px; font-size: 12px;
}
.reject-reason-box input:focus { border-color: #165DFF; }
.notif-btn-confirm-reject {
  padding: 0 12px; background: #165DFF; color: #fff;
  border-radius: 6px; font-size: 12px; white-space: nowrap;
}
.notif-btn-confirm-reject:hover { background: #0e42d2; }
.notif-processed { font-size: 12px; color: #00b42a; margin-top: 6px; font-weight: 500; }

/* 内容区 */
.content-area { flex: 1; overflow: hidden; position: relative; }

/* 欢迎页 */
.welcome-page {
  height: 100%; display: flex; align-items: center; justify-content: center;
  overflow-y: auto;
}
.welcome-container { max-width: 680px; width: 100%; padding: 40px; text-align: center; }
.welcome-icon { font-size: 48px; margin-bottom: 16px; }
.welcome-title { font-size: 24px; font-weight: 600; color: #1d2129; margin-bottom: 8px; }
.welcome-subtitle { font-size: 14px; color: #86909c; margin-bottom: 32px; }
.welcome-cards { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.welcome-card {
  background: #f7f8fa; border: 1px solid #eceef1; border-radius: 12px;
  padding: 16px; display: flex; align-items: flex-start; gap: 12px;
  cursor: pointer; transition: all 0.2s; text-align: left;
}
.welcome-card:hover { border-color: #165DFF; background: #f0f5ff; }
.card-icon { width: 36px; height: 36px; border-radius: 8px; background: #e8f3ff; display: flex; align-items: center; justify-content: center; font-size: 18px; flex-shrink: 0; }
.card-body { flex: 1; }
.card-title { font-size: 14px; font-weight: 500; color: #1d2129; margin-bottom: 4px; }
.card-desc { font-size: 12px; color: #86909c; }

/* 聊天区域 */
.chat-area { height: 100%; display: flex; flex-direction: column; }
.messages-container { flex: 1; overflow-y: auto; padding: 20px 24px; }
.message-row { display: flex; gap: 12px; margin-bottom: 20px; }
.message-row.user { flex-direction: row-reverse; }
.message-avatar {
  width: 36px; height: 36px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 600; flex-shrink: 0;
}
.message-row.user .message-avatar { background: #165DFF; color: #fff; }
.message-row.assistant .message-avatar { background: #e8f3ff; }
.message-content { max-width: 70%; }
.message-role { font-size: 12px; color: #86909c; margin-bottom: 4px; }
.message-row.user .message-role { text-align: right; }
.message-text {
  background: #f7f8fa; border-radius: 12px; padding: 12px 16px;
  font-size: 14px; line-height: 1.6; color: #1d2129;
  word-break: break-word;
}
.message-row.user .message-text { background: #165DFF; color: #fff; }
.message-text.typing { color: #86909c; font-style: italic; }

/* 底部输入 */
.input-area { padding: 12px 24px 16px; border-top: 1px solid #eceef1; background: #fff; }
.quick-prompts { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.quick-tag {
  padding: 4px 12px; background: #f7f8fa; border: 1px solid #eceef1;
  border-radius: 16px; font-size: 12px; color: #4e5969;
  cursor: pointer; transition: all 0.15s;
}
.quick-tag:hover { border-color: #165DFF; color: #165DFF; background: #f0f5ff; }
.input-card {
  display: flex; align-items: center; gap: 8px;
  background: #f7f8fa; border: 1px solid #eceef1; border-radius: 12px;
  padding: 8px 12px;
}
.input-card input {
  flex: 1; border: none; background: transparent;
  font-size: 14px; padding: 8px 0;
}
.send-btn {
  padding: 8px 20px; background: #165DFF; color: #fff;
  border-radius: 8px; font-size: 14px; font-weight: 500;
  transition: background 0.2s;
}
.send-btn:hover { background: #0e42d2; }
.send-btn:disabled { background: #c9cdd4; cursor: not-allowed; }
.upload-btn {
  background: transparent; font-size: 20px; padding: 4px 8px;
  color: #86909c; border-radius: 6px; transition: all 0.2s; flex-shrink: 0;
}
.upload-btn:hover { background: #f0f5ff; color: #165DFF; }
.upload-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.password-modal { width: 420px; }
.password-hint {
  margin-top: 6px;
  font-size: 12px;
  color: #f53f3f;
}

/* 数据面板 */
.data-panel { height: 100%; display: flex; flex-direction: column; overflow: hidden; }
.data-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 24px; border-bottom: 1px solid #eceef1;
}
.data-header h3 { font-size: 16px; font-weight: 600; color: #1d2129; }
.data-actions { display: flex; gap: 8px; }
.data-btn {
  padding: 6px 14px; border: 1px solid #d9d9d9; border-radius: 6px;
  font-size: 13px; color: #4e5969; background: #fff;
  transition: all 0.15s;
}
.data-btn:hover { border-color: #165DFF; color: #165DFF; }
.data-btn.primary { background: #165DFF; color: #fff; border-color: #165DFF; }
.data-btn.primary:hover { background: #0e42d2; }

.data-table-wrapper { flex: 1; overflow: auto; padding: 16px 24px; }
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table th {
  background: #f7f8fa; padding: 10px 12px; text-align: left;
  font-weight: 500; color: #4e5969; border-bottom: 1px solid #eceef1;
  white-space: nowrap;
}
.data-table td {
  padding: 10px 12px; border-bottom: 1px solid #f0f0f0;
  color: #1d2129;
}
.data-table tr:hover td { background: #fafbfc; }
.action-cell { display: flex; gap: 6px; }
.row-btn {
  padding: 2px 10px; border: 1px solid #d9d9d9; border-radius: 4px;
  font-size: 12px; color: #4e5969; background: #fff;
}
.row-btn:hover { border-color: #165DFF; color: #165DFF; }
.row-btn.danger:hover { border-color: #f53f3f; color: #f53f3f; }
.data-empty { text-align: center; padding: 40px; color: #c9cdd4; font-size: 14px; }

/* 表单弹窗 */
.form-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.45);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.form-modal {
  background: #fff; border-radius: 12px; width: 480px; max-width: 90vw;
  max-height: 80vh; overflow-y: auto;
}
.form-header { padding: 16px 24px; border-bottom: 1px solid #eceef1; }
.form-header h3 { font-size: 16px; font-weight: 600; }
.form-body { padding: 20px 24px; }
.form-field { margin-bottom: 14px; }
.form-field label { display: block; font-size: 13px; color: #4e5969; margin-bottom: 6px; }
.form-field input {
  width: 100%; height: 38px; border: 1px solid #d9d9d9; border-radius: 6px;
  padding: 0 12px; font-size: 14px;
}
.form-field input:focus { border-color: #165DFF; }
.form-field select {
  width: 100%; height: 38px; border: 1px solid #d9d9d9; border-radius: 6px;
  padding: 0 12px; font-size: 14px; background: #fff;
}
.form-field select:focus { border-color: #165DFF; }
.form-footer {
  padding: 12px 24px; border-top: 1px solid #eceef1;
  display: flex; justify-content: flex-end; gap: 8px;
}

/* ===== Markdown 内容样式 ===== */
.message-text :deep(table) {
  width: 100%; border-collapse: collapse; margin: 8px 0;
  font-size: 13px; background: #fff;
}
.message-text :deep(th) {
  background: #f7f8fa; padding: 8px 12px; text-align: left;
  font-weight: 500; border: 1px solid #e5e6eb; white-space: nowrap;
}
.message-text :deep(td) {
  padding: 8px 12px; border: 1px solid #e5e6eb; color: #1d2129;
}
.message-text :deep(tr:nth-child(even)) { background: #fafbfc; }
.message-text :deep(tr:hover) { background: #f0f5ff; }
.message-text :deep(p) { margin: 4px 0; }
.message-text :deep(ul), .message-text :deep(ol) { margin: 4px 0; padding-left: 20px; }
.message-text :deep(li) { margin: 2px 0; }
.message-text :deep(strong) { font-weight: 600; }
.message-text :deep(code) {
  background: #f2f3f5; padding: 2px 6px; border-radius: 4px;
  font-size: 13px; font-family: "SF Mono", "Consolas", monospace;
}
.message-text :deep(blockquote) {
  border-left: 3px solid #165DFF; padding-left: 12px;
  margin: 8px 0; color: #86909c;
}
</style>
