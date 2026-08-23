import { defineStore } from 'pinia'
import axios from 'axios'

export const useUserStore = defineStore('user', {
  state: () => ({
    userInfo: JSON.parse(localStorage.getItem('userInfo') || 'null'),
    token: localStorage.getItem('token') || '',
  }),
  getters: {
    isLoggedIn: (state) => !!state.userInfo,
    isAdmin: (state) => state.userInfo?.role === 'admin',
    displayName: (state) => state.userInfo?.name || '',
    employeeCode: (state) => state.userInfo?.employee_code || '',
  },
  actions: {
    async login(employeeCode, password) {
      const res = await axios.post('/api/login', { employee_code: employeeCode, password })
      if (res.data.ok) {
        this.userInfo = res.data.data
        this.token = res.data.data.token || employeeCode
        localStorage.setItem('userInfo', JSON.stringify(this.userInfo))
        localStorage.setItem('token', this.token)
        return true
      }
      throw new Error(res.data.error || '登录失败')
    },
    logout() {
      axios.post('/api/logout', { employee_code: this.employeeCode }).catch(() => {})
      this.userInfo = null
      this.token = ''
      localStorage.removeItem('userInfo')
      localStorage.removeItem('token')
    },
  },
})
