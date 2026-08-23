import axios from 'axios'
import router from '../router'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

function clearAuthStorage() {
  localStorage.removeItem('userInfo')
  localStorage.removeItem('token')
}

function readUserInfo() {
  try {
    return JSON.parse(localStorage.getItem('userInfo') || 'null')
  } catch {
    clearAuthStorage()
    return null
  }
}

api.interceptors.request.use((config) => {
  const userInfo = readUserInfo()
  if (userInfo) {
    config.headers['X-User-Code'] = userInfo.employee_code
    config.headers['X-User-Role'] = userInfo.role
  }
  return config
})

api.interceptors.response.use(
  (res) => res.data,
  (err) => {
    if (err.response?.status === 401) {
      clearAuthStorage()
      if (router.currentRoute.value.path !== '/login') {
        router.replace('/login').catch(() => {})
      }
    }
    return Promise.reject(err)
  }
)

export default {
  // 员工
  getEmployees: (params) => api.get('/employees', { params }),
  getEmployee: (code) => api.get(`/employees/${code}`),
  createEmployee: (data) => api.post('/employees', data),
  updateEmployee: (code, data) => api.put(`/employees/${code}`, data),
  deleteEmployee: (code) => api.delete(`/employees/${code}`),
  getDepartments: () => api.get('/departments'),
  getDepartmentMembers: (dept) => api.get(`/departments/${dept}/members`),

  // 考勤
  getAttendance: (params) => api.get('/attendance', { params }),
  getAttendanceSummary: (params) => api.get('/attendance/summary', { params }),
  getAttendanceAnomalies: (params) => api.get('/attendance/anomalies', { params }),
  createAttendance: (data) => api.post('/attendance', data),
  updateAttendance: (id, data) => api.put(`/attendance/${id}`, data),
  deleteAttendance: (id) => api.delete(`/attendance/${id}`),

  // 请假
  submitLeave: (data) => api.post('/leave/submit', data),
  approveLeave: (data) => api.post('/leave/approve', data),
  cancelLeave: (data) => api.post('/leave/cancel', data),
  getLeaveBalance: (code) => api.get(`/leave/balance/${code}`),
  getLeaveHistory: (code) => api.get(`/leave/history/${code}`),
  getPendingLeaves: () => api.get('/leave/pending'),
  getLeaves: () => api.get('/leave/all'),
  getAllLeaveBalances: () => api.get('/leave/balances'),
  updateLeave: (id, data) => api.put(`/leave/${id}`, data),
  deleteLeave: (id) => api.delete(`/leave/${id}`),

  // 薪酬
  getPayroll: (code) => api.get(`/payroll/${code}`),
  getPayrollAll: () => api.get('/payroll'),
  createPayroll: (data) => api.post('/payroll', data),
  updatePayroll: (id, data) => api.put(`/payroll/${id}`, data),
  deletePayroll: (id) => api.delete(`/payroll/${id}`),

  // 招聘
  getRecruitment: (params) => api.get('/recruitment', { params }),
  getRecruitments: (params) => api.get('/recruitment', { params }),
  createRecruitment: (data) => api.post('/recruitment', data),
  updateRecruitmentStatus: (id, data) => api.put(`/recruitment/${id}/status`, data),
  updateRecruitment: (id, data) => api.put(`/recruitment/${id}`, data),
  deleteRecruitment: (id) => api.delete(`/recruitment/${id}`),
  getRecruitmentPipeline: () => api.get('/recruitment/pipeline'),

  // 面试
  getInterviews: (params) => api.get('/interviews', { params }),
  scheduleInterview: (data) => api.post('/interviews', data),
  updateInterviewResult: (id, data) => api.put(`/interviews/${id}/result`, data),
  updateInterview: (id, data) => api.put(`/interviews/${id}`, data),
  deleteInterview: (id) => api.delete(`/interviews/${id}`),

  // 通知
  getNotifications: (limit) => api.get('/notifications', { params: { limit } }),
  getUnreadNotifications: () => api.get('/notifications/unread'),
  markNotifRead: (notifId) => api.post('/notifications/read', { notif_id: notifId }),

  // 审计
  getAuditLogs: (params) => api.get('/audit', { params }),

  // 入职任务
  getOnboardingTasks: (code) => api.get(`/onboarding/${code}`),
  getOnboardingProgress: (code) => api.get(`/onboarding/${code}/progress`),
  updateOnboardingTask: (id, data) => api.put(`/onboarding/tasks/${id}`, data),

  // 文件上传（简历）
  uploadFile: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  parseResume: (filePath) => api.post('/parse_resume', { file_path: filePath }),
  downloadFile: (path) => api.get('/download', { params: { path }, responseType: 'blob' }),

  // Agent — 带用户身份
  chat: (message, sessionId) => {
    const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}')
    return api.post('/chat', {
      message,
      session_id: sessionId,
      user_info: {
        role: userInfo.role || 'employee',
        employee_code: userInfo.employee_code || '',
        name: userInfo.name || '',
        department: userInfo.department || '',
      },
    })
  },
  resetSession: (sid) => api.post('/chat/reset', { session_id: sid }),

  // Dashboard
  getDashboard: () => api.get('/dashboard'),

  // 修改密码
  changePassword: (data) => api.post('/change_password', data),

  // 备份
  backup: () => api.post('/backup'),
  getBackups: () => api.get('/backups'),
}
