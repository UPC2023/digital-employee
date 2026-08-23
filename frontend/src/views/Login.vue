<template>
  <div class="login-page">
    <div class="login-bg"></div>
    <div class="login-card">
      <!-- 左侧品牌区 -->
      <div class="login-left">
        <div class="brand">
          <div class="brand-icon">🏢</div>
          <div class="brand-title">HR 智能助手</div>
          <div class="brand-subtitle">企业 HR 数字员工</div>
        </div>
        <div class="features">
          <div class="feature-item">
            <span class="feature-icon">💼</span>
            <span>招聘咨询 · 简历解析</span>
          </div>
          <div class="feature-item">
            <span class="feature-icon">🕐</span>
            <span>考勤查询 · 请假管理</span>
          </div>
          <div class="feature-item">
            <span class="feature-icon">💰</span>
            <span>薪酬答疑 · 个税计算</span>
          </div>
          <div class="feature-item">
            <span class="feature-icon">📋</span>
            <span>入职离职 · 信息维护</span>
          </div>
        </div>
      </div>

      <!-- 右侧登录区 -->
      <div class="login-right">
        <div class="login-form">
          <div class="form-title">欢迎登录</div>
          <div class="form-subtitle">请输入您的工号和密码</div>

          <div class="input-group" :class="{ focus: codeFocus }">
            <span class="input-icon">👤</span>
            <input
              v-model="employeeCode"
              type="text"
              placeholder="工号"
              @focus="codeFocus = true"
              @blur="codeFocus = false"
              @keyup.enter="handleLogin"
            />
          </div>

          <div class="input-group" :class="{ focus: pwdFocus }">
            <span class="input-icon">🔒</span>
            <input
              v-model="password"
              :type="showPwd ? 'text' : 'password'"
              placeholder="密码"
              @focus="pwdFocus = true"
              @blur="pwdFocus = false"
              @keyup.enter="handleLogin"
            />
            <span class="pwd-toggle" @click="showPwd = !showPwd">
              {{ showPwd ? '🙈' : '👁' }}
            </span>
          </div>

          <div class="error-msg" v-if="errorMsg">{{ errorMsg }}</div>

          <button class="login-btn" :disabled="loading" @click="handleLogin">
            {{ loading ? '登录中...' : '登 录' }}
          </button>

          <div class="demo-accounts">
            <div class="demo-title">💡 演示账号</div>
            <div class="demo-item" @click="fillDemo('EMP001', '123456')">
              员工：EMP001 / 123456
            </div>
            <div class="demo-item" @click="fillDemo('EMP005', '123456')">
              管理员：EMP005 / 123456
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'

const router = useRouter()
const userStore = useUserStore()

const employeeCode = ref('')
const password = ref('')
const showPwd = ref(false)
const loading = ref(false)
const errorMsg = ref('')
const codeFocus = ref(false)
const pwdFocus = ref(false)

function fillDemo(code, pwd) {
  employeeCode.value = code
  password.value = pwd
  errorMsg.value = ''
}

async function handleLogin() {
  if (!employeeCode.value || !password.value) {
    errorMsg.value = '请输入工号和密码'
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    await userStore.login(employeeCode.value, password.value)
    router.push('/chat')
  } catch (e) {
    errorMsg.value = e.message || '登录失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  position: relative;
  overflow: hidden;
}
.login-bg {
  position: absolute;
  inset: 0;
  background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60"><circle cx="30" cy="30" r="1" fill="white" opacity="0.15"/></svg>');
}
.login-card {
  display: flex;
  width: 780px;
  max-width: 95vw;
  height: 460px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.3);
  overflow: hidden;
  z-index: 1;
}

/* 左侧品牌区 */
.login-left {
  flex: 1;
  background: linear-gradient(160deg, #4facfe 0%, #00f2fe 100%);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 40px;
  color: #fff;
}
.brand { text-align: center; margin-bottom: 40px; }
.brand-icon { font-size: 56px; margin-bottom: 12px; }
.brand-title { font-size: 24px; font-weight: 700; margin-bottom: 6px; }
.brand-subtitle { font-size: 14px; opacity: 0.85; }

.features { width: 100%; }
.feature-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0;
  font-size: 14px;
  opacity: 0.9;
}
.feature-icon { font-size: 18px; }

/* 右侧登录区 */
.login-right {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}
.login-form { width: 100%; max-width: 300px; }
.form-title { font-size: 22px; font-weight: 700; color: #1d2129; margin-bottom: 6px; }
.form-subtitle { font-size: 13px; color: #86909c; margin-bottom: 28px; }

.input-group {
  display: flex;
  align-items: center;
  border: 1px solid #d9d9d9;
  border-radius: 8px;
  padding: 0 12px;
  margin-bottom: 16px;
  transition: border-color 0.2s;
  background: #fff;
}
.input-group.focus { border-color: #4facfe; box-shadow: 0 0 0 3px rgba(79,172,254,0.1); }
.input-icon { font-size: 16px; color: #86909c; }
.input-group input {
  flex: 1;
  border: none;
  padding: 12px 8px;
  font-size: 14px;
  background: transparent;
}
.pwd-toggle { font-size: 16px; cursor: pointer; color: #86909c; }

.error-msg {
  color: #f53f3f;
  font-size: 12px;
  margin-bottom: 12px;
  text-align: center;
}

.login-btn {
  width: 100%;
  height: 42px;
  background: linear-gradient(135deg, #4facfe 0%, #00c6fb 100%);
  color: #fff;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
  transition: opacity 0.2s;
}
.login-btn:hover { opacity: 0.9; }
.login-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.demo-accounts {
  margin-top: 24px;
  padding: 12px;
  background: #f7f8fa;
  border-radius: 8px;
}
.demo-title { font-size: 12px; color: #4e5969; font-weight: 500; margin-bottom: 8px; }
.demo-item {
  font-size: 12px;
  color: #86909c;
  padding: 4px 0;
  cursor: pointer;
  transition: color 0.2s;
}
.demo-item:hover { color: #4facfe; }
</style>
