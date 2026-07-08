# -*- coding: utf-8 -*-
"""
企业 HR 数字员工 — 前端主应用（合并版）
豆包风格 AI 原生对话式工作台 + 数据管理 CRUD + 对话历史持久化

设计对标：豆包网页版浅色主题
核心理念：对话即工作台，左侧导航栏提供数据管理 CRUD 入口
技术栈：Gradio 6.x + Blocks + 自定义 CSS
"""

import os
import sys
import time
import uuid

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import gradio as gr
import pandas as pd

# ============================================================
# 导入后端 API 封装
# ============================================================
from frontend.utils import (
    run_agent, reset_session, _run_diagnostics,
    get_dashboard_summary, safe_call,
    DEPARTMENTS, LEAVE_TYPES, RECRUITMENT_STATUSES,
)

# 直接导入数据库 CRUD 函数
from src.database import (
    get_connection,
    query_employee, get_employee_by_code, update_employee,
    query_attendance,
    submit_leave, query_leave_history,
    query_payroll,
    query_recruitment, insert_recruitment, update_recruitment_status,
)

# 运行后端诊断
_run_diagnostics()


# ============================================================
# 一、CSS — 豆包风格视觉体系
# ============================================================

DOUBAO_CSS = """
/* ===== 基础重置 ===== */
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body {
    height: 100%;
    overflow: auto;
    font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", "Helvetica Neue", sans-serif;
}

/* 隐藏的触发按钮 — 不占空间但保留在DOM中供JS点击 */
.hidden-trigger {
    display: none !important;
    visibility: hidden !important;
    position: absolute !important;
    width: 0 !important;
    height: 0 !important;
    overflow: hidden !important;
}

/* 初始隐藏的页面（JS 控制显示/隐藏）*/
.initially-hidden {
    display: none !important;
}

/* ===== 全局清除 Gradio 默认边框/间距 ===== */
.component-wrapper,
.contain {
    border: none !important;
    gap: 0 !important;
}
#main-area > div,
#chat-area > div,
#welcome-page > div,
#data-page > div,
#input-wrapper > div {
    gap: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
    border: none !important;
    background: transparent !important;
    flex: 1 !important;
    display: flex !important;
    flex-direction: column !important;
    min-height: 0 !important;
    overflow: visible !important;
}
#chatbot .component-wrapper,
#chatbot > div {
    border: none !important;
    padding: 0 !important;
    background: transparent !important;
}

/* ===== Gradio 容器 ===== */
.gradio-container {
    max-width: 100% !important;
    width: 100vw !important;
    height: 100vh !important;
    padding: 0 !important;
    margin: 0 !important;
    background: #ffffff !important;
}
.gradio-container > .main {
    padding: 0 !important;
    gap: 0 !important;
    height: 100vh !important;
}

/* 隐藏 footer */
footer { display: none !important; }

/* ===== 根布局 ===== */
#app-root {
    display: flex !important;
    height: 100vh !important;
    gap: 0 !important;
    padding: 0 !important;
    width: 100% !important;
    max-width: 100% !important;
}
/* 确保 app-root 的父容器也不加 padding */
#main-area > div,
#main-area > .block,
#main-area > .svelte-1plpy97 {
    padding: 0 !important;
    margin: 0 !important;
    width: 100% !important;
    max-width: 100% !important;
}
/* gradio-container 内层也要撑满 */
.gradio-container > div,
.gradio-container > .main,
.gradio-container > .main > div,
.gradio-container > .wrap,
.gradio-container > .contain,
.gradio-container .svelte-zxu34v {
    padding: 0 !important;
    margin: 0 !important;
    width: 100% !important;
    max-width: 100% !important;
}

/* ===== 左侧边栏 ===== */
#sidebar {
    width: 260px !important;
    min-width: 260px !important;
    max-width: 260px !important;
    background: #f7f8fa !important;
    border-right: 1px solid #eceef1 !important;
    padding: 12px !important;
    height: 100vh !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    flex-shrink: 0 !important;
    gap: 0 !important;
    display: flex !important;
    flex-direction: column !important;
}
#sidebar > div { gap: 0 !important; }

/* 新建对话按钮 */
#new-chat-btn {
    width: 100% !important;
    height: 40px !important;
    background: #165DFF !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 10px !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    margin-bottom: 16px !important;
    cursor: pointer !important;
    transition: background 0.2s !important;
    flex-shrink: 0 !important;
}
#new-chat-btn:hover { background: #0e42d2 !important; }

/* 侧边栏分区标题 */
.sidebar-section-title {
    font-size: 12px !important;
    color: #86909c !important;
    padding: 12px 8px 6px 8px !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* 导航/列表项 */
.nav-item {
    height: 38px;
    padding: 0 12px;
    display: flex;
    align-items: center;
    gap: 10px;
    border-radius: 8px;
    font-size: 14px;
    color: #4e5969;
    cursor: pointer;
    margin-bottom: 2px;
    transition: background 0.15s;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
}
.nav-item:hover { background: #f2f3f5; }
.nav-item.active { background: #e8f3ff; color: #165DFF; font-weight: 500; }
.nav-item .nav-icon { font-size: 16px; flex-shrink: 0; }

/* 历史对话项 */
.history-item {
    height: 38px;
    padding: 0 8px 0 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-radius: 8px;
    font-size: 14px;
    color: #4e5969;
    cursor: pointer;
    margin-bottom: 2px;
    transition: background 0.15s;
    overflow: hidden;
    gap: 4px;
}
.history-item:hover { background: #f2f3f5; }
.history-item:hover .history-actions { opacity: 1; }
.history-item .history-title {
    flex: 1;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    min-width: 0;
}
.history-item .history-actions {
    display: flex;
    gap: 2px;
    opacity: 0;
    transition: opacity 0.15s;
    flex-shrink: 0;
}
.history-item .history-rename,
.history-item .history-delete {
    width: 22px;
    height: 22px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
    flex-shrink: 0;
}
.history-item .history-rename:hover { background: #e8f3ff; }
.history-item .history-delete:hover { background: #fff2f0; }
.history-item.active { background: #e8f3ff; color: #165DFF; font-weight: 500; }

/* 底部用户栏 */
.user-bar {
    margin-top: auto;
    padding: 12px 8px 4px 8px;
    border-top: 1px solid #eceef1;
    display: flex;
    align-items: center;
    gap: 10px;
    flex-shrink: 0;
}
.user-avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: linear-gradient(135deg, #165DFF, #4080FF);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    font-weight: 600;
    flex-shrink: 0;
}
.user-name { font-size: 14px; color: #1d2129; font-weight: 500; }
.user-role { font-size: 12px; color: #86909c; }

/* ===== 右侧主区 ===== */
#main-area {
    flex: 1 !important;
    background: #ffffff !important;
    height: 100vh !important;
    display: flex !important;
    flex-direction: column !important;
    padding: 0 !important;
    overflow: visible !important;
    gap: 0 !important;
    min-width: 400px !important;
    border: none !important;
    position: relative !important;
}
#main-area > div {
    gap: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
    border: none !important;
    background: transparent !important;
    flex: 1 !important;
    display: flex !important;
    flex-direction: column !important;
    min-height: 0 !important;
    overflow: visible !important;
}

/* 顶部栏 */
.top-bar {
    height: 48px;
    min-height: 48px;
    border-bottom: 1px solid #eceef1;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 24px;
    flex-shrink: 0;
    background: #ffffff;
}
.top-bar-title {
    font-size: 16px;
    font-weight: 500;
    color: #1d2129;
}
.top-bar-actions {
    display: flex;
    gap: 8px;
    align-items: center;
}
.top-bar-btn {
    width: 32px;
    height: 32px;
    border: none;
    background: transparent;
    border-radius: 8px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #4e5969;
    font-size: 16px;
    transition: background 0.15s;
}
.top-bar-btn:hover { background: #f2f3f5; }

/* ===== 欢迎页 ===== */
#welcome-page {
    position: absolute !important;
    top: 48px !important;
    left: 0 !important;
    right: 0 !important;
    bottom: 130px !important;
    height: auto !important;
    max-height: calc(100vh - 48px - 130px) !important;
    align-items: center !important;
    justify-content: center !important;
    overflow-y: auto !important;
    padding: 0 !important;
    background: #ffffff !important;
    border: none !important;
    z-index: 5 !important;
}
/* Gradio visible=False 时加 .hide 类，强制 display:none 生效 */
#welcome-page.hide {
    display: none !important;
}
#welcome-page > div,
#welcome-page .form,
#welcome-page .wrap {
    padding: 0 !important;
    margin: 0 !important;
    gap: 0 !important;
    border: none !important;
    background: transparent !important;
    width: 100% !important;
    max-width: 100% !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}

.welcome-container {
    max-width: 720px;
    width: 100%;
    padding: 40px;
    text-align: center;
}
.welcome-title {
    font-size: 28px;
    font-weight: 600;
    color: #1d2129;
    margin-bottom: 8px;
    line-height: 1.4;
}
.welcome-subtitle {
    font-size: 15px;
    color: #86909c;
    margin-bottom: 36px;
    line-height: 1.6;
}
.welcome-cards {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
}
.welcome-card {
    background: #f7f8fa;
    border: 1px solid #eceef1;
    border-radius: 12px;
    padding: 20px;
    text-align: left;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: flex-start;
    gap: 12px;
}
.welcome-card:hover {
    border-color: #165DFF;
    background: #f0f5ff;
    transform: translateY(-1px);
    box-shadow: 0 2px 12px rgba(22, 93, 255, 0.08);
}
.welcome-card-icon {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    flex-shrink: 0;
    background: #e8f3ff;
}
.welcome-card-body { flex: 1; min-width: 0; }
.welcome-card-title {
    font-size: 15px;
    font-weight: 500;
    color: #1d2129;
    margin-bottom: 4px;
}
.welcome-card-desc {
    font-size: 13px;
    color: #86909c;
    line-height: 1.5;
}

/* ===== 聊天区域 ===== */
#chat-area {
    position: absolute !important;
    top: 48px !important;
    left: 0 !important;
    right: 0 !important;
    bottom: 130px !important;
    height: auto !important;
    max-height: calc(100vh - 48px - 130px) !important;
    overflow: hidden !important;
    padding: 0 !important;
    flex-direction: column !important;
    gap: 0 !important;
    background: #ffffff !important;
    border: none !important;
    z-index: 5 !important;
    visibility: hidden !important;
    opacity: 0 !important;
}
#chat-area.chat-visible {
    visibility: visible !important;
    opacity: 1 !important;
}
/* Gradio visible=False 时加 .hide 类，强制 display:none 生效 */
#chat-area.hide {
    display: none !important;
}
#chat-area > div,
#chat-area .form,
#chat-area .wrap {
    padding: 0 !important;
    gap: 0 !important;
    margin: 0 !important;
    flex: 1 !important;
    display: flex !important;
    flex-direction: column !important;
    overflow: hidden !important;
    border: none !important;
    background: transparent !important;
    min-height: 0 !important;
}

#chatbot {
    flex: 1 !important;
    border: none !important;
    background: transparent !important;
    max-width: 100% !important;
    margin: 0 !important;
    width: 100% !important;
    padding: 8px 24px 8px 24px !important;
    height: 100% !important;
    min-height: 0 !important;
    overflow-y: auto !important;
}

/* 聊天气泡 */
#chatbot .message-row {
    margin-bottom: 20px !important;
    display: flex !important;
    padding: 0 12px !important;
    width: 100% !important;
}
/* 覆盖 Gradio 的 space-between，让消息从顶部开始排列 */
#chatbot .message-wrap {
    justify-content: flex-start !important;
    width: 100% !important;
    max-width: 100% !important;
}
#chatbot .message-row.user-row,
#chatbot .message-row.user { justify-content: flex-end !important; }
#chatbot .message-row.bot-row,
#chatbot .message-row.bot { justify-content: flex-start !important; }
/* 限制 message-wrap 内层为 50% */
#chatbot .message-row .message-wrap { max-width: 50% !important; }
/* message-row 本身也不超过 50% */
#chatbot .message-row.user-row .message-wrap { margin-left: auto !important; }

#chatbot .message {
    max-width: 100% !important;
    width: fit-content !important;
    padding: 12px 16px !important;
    border-radius: 16px !important;
    font-size: 15px !important;
    line-height: 1.6 !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04) !important;
    border: none !important;
}
/* 强制覆盖 Gradio 内联 max-width */
#chatbot .message-row .message,
#chatbot .message-wrap .message,
#chatbot .svelte-1nr59td.message,
#chatbot .user.message,
#chatbot .bot.message {
    max-width: 100% !important;
    width: fit-content !important;
}
/* Gradio 6.x 内层 message-content 不额外撑宽 */
#chatbot .message-content,
#chatbot .message .message,
#chatbot .message-wrap .message {
    max-width: 100% !important;
    width: auto !important;
}
/* 段落不额外撑宽 */
#chatbot .message p,
#chatbot .message-content p {
    margin: 0 !important;
    word-break: break-word !important;
}
#chatbot .user.message {
    background: #f7f8fa !important;
    color: #1d2129 !important;
    border-radius: 16px 16px 4px 16px !important;
}
#chatbot .bot.message,
#chatbot .message-row.bot-row .message {
    background: #f7f8fa !important;
    color: #1d2129 !important;
    border-radius: 16px 16px 16px 4px !important;
}
#chatbot .message .message,
#chatbot .message-content {
    background: transparent !important;
    padding: 0 !important;
    border-radius: 0 !important;
    box-shadow: none !important;
}

/* Markdown 样式 */
#chatbot .message p,
#chatbot .message-wrap p { margin-bottom: 8px !important; }
#chatbot .message p:last-child,
#chatbot .message-wrap p:last-child { margin-bottom: 0 !important; }
#chatbot .message ul, #chatbot .message ol,
#chatbot .message-wrap ul, #chatbot .message-wrap ol {
    padding-left: 20px !important; margin-bottom: 8px !important;
}
#chatbot .message li, #chatbot .message-wrap li { margin-bottom: 4px !important; }
#chatbot .message pre, #chatbot .message-wrap pre {
    background: #1d2129 !important; border-radius: 8px !important;
    padding: 12px !important; overflow-x: auto !important; margin: 8px 0 !important;
}
#chatbot .message code, #chatbot .message-wrap code {
    font-family: "SF Mono", "Fira Code", "Consolas", monospace !important; font-size: 13px !important;
}
#chatbot .message table, #chatbot .message-wrap table {
    border-collapse: collapse !important; margin: 8px 0 !important; width: 100% !important;
}
#chatbot .message th, #chatbot .message td,
#chatbot .message-wrap th, #chatbot .message-wrap td {
    border: 1px solid #eceef1 !important; padding: 6px 12px !important; font-size: 14px !important;
}
#chatbot .message th, #chatbot .message-wrap th {
    background: #f7f8fa !important; font-weight: 500 !important;
}

/* ===== 底部输入区（豆包风格：快捷提示+输入框一体化）===== */
#input-wrapper {
    position: absolute !important;
    bottom: 0 !important;
    left: 0 !important;
    right: 0 !important;
    flex-shrink: 0 !important;
    padding: 0 64px 16px 64px !important;
    max-width: 100% !important;
    width: 100% !important;
    margin: 0 !important;
    background: #ffffff !important;
    border: none !important;
    z-index: 20 !important;
}
/* 数据管理页时隐藏输入区 */
#input-wrapper.input-hidden {
    display: none !important;
}
#input-wrapper > div,
#input-wrapper .form,
#input-wrapper .wrap,
#input-wrapper .svelte-1plpy97 {
    gap: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
    border: none !important;
    background: transparent !important;
    display: flex !important;
    flex-direction: column !important;
    max-width: 100% !important;
    width: 100% !important;
}
#input-wrapper .input-card {
    max-width: 100% !important;
    width: 100% !important;
}

/* 快捷提示 — 紧贴输入框上方的小胶囊标签 */
.quick-prompts {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 10px;
    padding: 0 4px;
}
.quick-prompt-tag {
    padding: 4px 12px;
    background: #f7f8fa;
    border: 1px solid #eceef1;
    border-radius: 16px;
    font-size: 12px;
    color: #4e5969;
    cursor: pointer;
    transition: all 0.15s;
    user-select: none;
    line-height: 1.5;
}
.quick-prompt-tag:hover {
    border-color: #165DFF;
    color: #165DFF;
    background: #f0f5ff;
}

/* 输入卡片 — 豆包风格大圆角输入框 */
.input-card {
    background: #f7f8fa !important;
    border: 1px solid #eceef1 !important;
    border-radius: 22px !important;
    box-shadow: none !important;
    padding: 10px 16px !important;
    display: flex !important;
    align-items: center !important;
    gap: 8px !important;
    min-height: 56px !important;
    width: 100% !important;
}
/* 文件上传靠左 */
#file-upload {
    flex-shrink: 0 !important;
    margin-right: 4px !important;
}
/* 输入框撑满中间 */
#msg-input {
    flex: 1 1 auto !important;
    min-width: 0 !important;
}
/* 发送按钮靠最右 */
#send-btn {
    flex-shrink: 0 !important;
    margin-left: auto !important;
}

#msg-input {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    padding: 10px 4px !important;
    font-size: 15px !important;
    resize: none !important;
    overflow: visible !important;
    min-height: 56px !important;
}
#msg-input > div,
#msg-input .input-container,
#msg-input .svelte-1hguek3 {
    display: block !important;
    width: 100% !important;
}
#msg-input label { display: block !important; width: 100% !important; }
#msg-input .svelte-jdcl7l { display: none !important; }
#msg-input textarea {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    font-size: 15px !important;
    resize: none !important;
    padding: 4px 0 !important;
    width: 100% !important;
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    color: #1d2129 !important;
}
#msg-input textarea:focus { box-shadow: none !important; border: none !important; }

#send-btn {
    width: 40px !important;
    height: 40px !important;
    min-width: 40px !important;
    background: #165DFF !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 0 !important;
    font-size: 18px !important;
    cursor: pointer !important;
    flex-shrink: 0 !important;
    transition: background 0.2s !important;
}
#send-btn:hover { background: #0e42d2 !important; }
#send-btn:disabled { background: #c9cdd4 !important; cursor: not-allowed !important; }

/* 附件上传按钮 */
#file-upload {
    width: 36px !important; min-width: 36px !important; max-width: 36px !important;
    height: 36px !important; border: none !important;
    background: transparent !important; padding: 0 !important;
    flex-grow: 0 !important; overflow: visible !important;
}
#file-upload > div, #file-upload .wrap, #file-upload .svelte-1uj8rng { display: none !important; }
#file-upload label { display: none !important; }
#file-upload button {
    width: 36px !important; height: 36px !important; min-height: 36px !important;
    padding: 0 !important; background: transparent !important; border: none !important;
    border-radius: 8px !important; display: flex !important;
    align-items: center !important; justify-content: center !important; cursor: pointer !important;
}
#file-upload button:hover { background: #f2f3f5 !important; }
#file-upload button .wrap, #file-upload button .svelte-1vmd51o, #file-upload button > div { display: none !important; }
#file-upload button::after { content: "📎" !important; font-size: 20px !important; line-height: 1 !important; }
#file-upload button svg { display: none !important; }

/* ===== 数据管理页（HTML 容器）===== */
#data-page-container {
    position: absolute !important;
    top: 48px !important;
    left: 0 !important;
    right: 0 !important;
    bottom: 0 !important;
    height: calc(100vh - 48px) !important;
    max-height: calc(100vh - 48px) !important;
    overflow-y: auto !important;
    padding: 0 !important;
    background: #ffffff !important;
    border: none !important;
    z-index: 10 !important;
    visibility: hidden !important;  /* 初始隐藏，JS 改为 visible */
    opacity: 0 !important;
    transition: opacity 0.15s !important;
}
#data-page-container.data-visible {
    visibility: visible !important;
    opacity: 1 !important;
}
#data-page-container > div,
#data-page-container .form,
#data-page-container .wrap,
#data-page-container .html-container,
#data-page-container .prose {
    padding: 0 !important;
    margin: 0 !important;
    border: none !important;
    background: transparent !important;
    height: auto !important;
    max-width: 100% !important;
    display: block !important;
    overflow: visible !important;
}
#data-page-inner {
    height: auto !important;
    min-height: 100% !important;
    display: block !important;
}

.data-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 48px 12px 48px;
    flex-shrink: 0;
    gap: 12px;
}
.data-toolbar-left {
    display: flex;
    gap: 8px;
    align-items: center;
}
.data-toolbar-right {
    display: flex;
    gap: 8px;
    align-items: center;
}
.data-btn {
    height: 32px;
    padding: 0 16px;
    border: 1px solid #eceef1;
    background: #ffffff;
    border-radius: 8px;
    font-size: 13px;
    color: #4e5969;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 4px;
    transition: all 0.15s;
}
.data-btn:hover { border-color: #165DFF; color: #165DFF; background: #f0f5ff; }
.data-btn.primary {
    background: #165DFF;
    color: #ffffff;
    border-color: #165DFF;
}
.data-btn.primary:hover { background: #0e42d2; border-color: #0e42d2; color: #ffffff; }
.data-btn.danger:hover { border-color: #f53f3f; color: #f53f3f; background: #fff2f0; }
.data-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.data-search {
    height: 32px;
    padding: 0 12px;
    border: 1px solid #eceef1;
    background: #f7f8fa;
    border-radius: 8px;
    font-size: 13px;
    width: 200px;
    outline: none;
}
.data-search:focus { border-color: #165DFF; background: #ffffff; }

.data-table-wrapper {
    flex: 1 !important;
    overflow: auto !important;
    padding: 0 48px 24px 48px !important;
    min-height: 0 !important;
}

/* 原生 HTML 数据表格 */
.data-table {
    border-collapse: collapse !important;
    width: 100% !important;
    font-size: 13px !important;
    background: #ffffff !important;
    border: 1px solid #eceef1 !important;
    border-radius: 10px !important;
    overflow: hidden !important;
}
.data-table th {
    background: #f7f8fa !important;
    color: #4e5969 !important;
    font-weight: 500 !important;
    font-size: 13px !important;
    padding: 10px 12px !important;
    border-bottom: 1px solid #eceef1 !important;
    text-align: left !important;
    white-space: nowrap !important;
    position: sticky !important;
    top: 0 !important;
    z-index: 1 !important;
}
.data-table td {
    font-size: 13px !important;
    padding: 8px 12px !important;
    color: #1d2129 !important;
    border-bottom: 1px solid #f2f3f5 !important;
}
.data-table tbody tr {
    cursor: pointer !important;
    transition: background 0.15s !important;
}
.data-table tbody tr:hover td { background: #fafbfc !important; }
.data-table tbody tr.selected td { background: #e8f3ff !important; }
.data-empty-row { text-align: center !important; color: #86909c !important; padding: 24px !important; }
.data-empty { padding: 40px !important; text-align: center !important; color: #86909c !important; font-size: 14px !important; }

/* 行内操作按钮 */
.action-cell {
    text-align: center !important;
    white-space: nowrap !important;
    padding: 4px 6px !important;
    vertical-align: middle !important;
}
.row-action-btn {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 30px !important;
    height: 30px !important;
    border: 1px solid #eceef1 !important;
    background: #ffffff !important;
    border-radius: 6px !important;
    cursor: pointer !important;
    font-size: 14px !important;
    margin: 0 3px !important;
    padding: 0 !important;
    transition: all 0.15s !important;
    line-height: 1 !important;
}
.row-action-btn:hover {
    border-color: #165DFF !important;
    background: #f0f5ff !important;
    transform: translateY(-1px) !important;
}
.row-delete-btn:hover {
    border-color: #f53f3f !important;
    background: #fff2f0 !important;
    color: #f53f3f !important;
}

/* 数据表单弹窗 */
.form-overlay {
    position: fixed !important;
    top: 0 !important;
    left: 0 !important;
    right: 0 !important;
    bottom: 0 !important;
    background: rgba(0, 0, 0, 0.4) !important;
    z-index: 1000 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}
.form-modal {
    background: #ffffff !important;
    border-radius: 16px !important;
    padding: 28px !important;
    width: 520px !important;
    max-width: 90vw !important;
    max-height: 80vh !important;
    overflow-y: auto !important;
    box-shadow: 0 8px 32px rgba(0,0,0,0.12) !important;
}
.form-modal-title {
    font-size: 18px !important;
    font-weight: 600 !important;
    color: #1d2129 !important;
    margin-bottom: 20px !important;
}
.form-fields {
    display: grid !important;
    grid-template-columns: 1fr 1fr !important;
    gap: 14px !important;
}
.form-field {
    display: flex !important;
    flex-direction: column !important;
    gap: 4px !important;
}
.form-field label {
    font-size: 13px !important;
    color: #4e5969 !important;
    font-weight: 500 !important;
}
.form-field input,
.form-field select {
    padding: 8px 12px !important;
    border: 1px solid #d9d9d9 !important;
    border-radius: 8px !important;
    font-size: 14px !important;
    color: #1d2129 !important;
    outline: none !important;
}
.form-field input:focus,
.form-field select:focus {
    border-color: #165DFF !important;
}
.form-modal-actions {
    display: flex !important;
    justify-content: flex-end !important;
    gap: 8px !important;
    margin-top: 20px !important;
}
.data-btn.primary {
    background: #165DFF !important;
    color: #ffffff !important;
    border: none !important;
}

/* ===== 滚动条 ===== */
#sidebar::-webkit-scrollbar,
#chat-area::-webkit-scrollbar,
#data-page::-webkit-scrollbar,
.data-table-wrapper::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}
#sidebar::-webkit-scrollbar-thumb,
#chat-area::-webkit-scrollbar-thumb,
#data-page::-webkit-scrollbar-thumb,
.data-table-wrapper::-webkit-scrollbar-thumb {
    background: #c9cdd4;
    border-radius: 3px;
}
#sidebar::-webkit-scrollbar-track,
#chat-area::-webkit-scrollbar-track,
#data-page::-webkit-scrollbar-track,
.data-table-wrapper::-webkit-scrollbar-track {
    background: transparent;
}

/* ===== Gradio 默认元素清除 ===== */
.form {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    gap: 0 !important;
}
#chatbot label, #msg-input label, #send-btn label, #file-upload label {
    display: none !important;
}
.gradio-container .form { background: transparent !important; }
"""


# ============================================================
# 二、常量与配置
# ============================================================

WELCOME_PROMPTS = [
    {"icon": "👤", "title": "查询员工信息", "desc": "按工号、姓名或部门查询员工", "prompt": "查询技术部所有员工"},
    {"icon": "🕐", "title": "查看考勤记录", "desc": "查询员工打卡、请假记录", "prompt": "查询EMP001上个月的考勤记录"},
    {"icon": "💰", "title": "薪酬个税查询", "desc": "工资明细、个税计算", "prompt": "月薪18000元交多少税？"},
    {"icon": "📚", "title": "制度知识问答", "desc": "员工手册、考勤制度等", "prompt": "员工手册中关于迟到的规定是什么？"},
]

QUICK_PROMPTS = [
    "查看公司员工概览",
    "月薪18000交多少税?",
    "年假有几天?",
    "查看招聘进度",
]

# 左侧导航栏 — 数据管理模块
NAV_ITEMS = [
    {"id": "employees",   "icon": "👤", "label": "员工管理"},
    {"id": "attendance",  "icon": "🕐", "label": "考勤管理"},
    {"id": "leave",       "icon": "🏖️", "label": "请假管理"},
    {"id": "payroll",     "icon": "💰", "label": "薪酬管理"},
    {"id": "recruitment", "icon": "📋", "label": "招聘管理"},
]

# 每个数据模块的列配置（用于表格展示和表单）
# 注意：列名必须与数据库实际字段名一致
DATA_CONFIG = {
    "employees": {
        "title": "员工管理",
        "table": "employees",
        "columns": ["employee_code", "name", "gender", "department", "position", "phone", "email", "hire_date", "status"],
        "labels": {
            "employee_code": "工号", "name": "姓名", "gender": "性别",
            "department": "部门", "position": "职位", "phone": "手机号",
            "email": "邮箱", "hire_date": "入职日期", "status": "状态",
        },
        "id_field": "employee_code",
        "form_fields": [
            {"key": "employee_code", "label": "工号", "type": "text", "placeholder": "如 EMP001"},
            {"key": "name", "label": "姓名", "type": "text", "placeholder": "员工姓名"},
            {"key": "gender", "label": "性别", "type": "select", "options": ["男", "女"]},
            {"key": "department", "label": "部门", "type": "select", "options": ["技术部", "市场部", "财务部", "人事部", "运营部"]},
            {"key": "position", "label": "职位", "type": "text", "placeholder": "如 初级工程师"},
            {"key": "phone", "label": "手机号", "type": "text", "placeholder": "手机号码"},
            {"key": "email", "label": "邮箱", "type": "text", "placeholder": "邮箱地址"},
            {"key": "hire_date", "label": "入职日期", "type": "date"},
            {"key": "status", "label": "状态", "type": "select", "options": ["在职", "离职", "试用期"]},
        ],
    },
    "attendance": {
        "title": "考勤管理",
        "table": "attendance",
        "columns": ["id", "employee_code", "date", "clock_in", "clock_out", "status", "overtime_hours"],
        "labels": {
            "id": "ID", "employee_code": "工号", "date": "日期",
            "clock_in": "上班时间", "clock_out": "下班时间",
            "status": "状态", "overtime_hours": "工时",
        },
        "id_field": "id",
        "form_fields": [
            {"key": "employee_code", "label": "工号", "type": "text", "placeholder": "如 EMP001"},
            {"key": "date", "label": "日期", "type": "date"},
            {"key": "clock_in", "label": "上班时间", "type": "text", "placeholder": "如 09:00"},
            {"key": "clock_out", "label": "下班时间", "type": "text", "placeholder": "如 18:00"},
            {"key": "status", "label": "状态", "type": "select", "options": ["正常", "迟到", "早退", "缺勤", "加班"]},
            {"key": "overtime_hours", "label": "工时", "type": "number", "placeholder": "如 8"},
        ],
    },
    "leave": {
        "title": "请假管理",
        "table": "leave_requests",
        "columns": ["id", "employee_code", "leave_type", "start_date", "end_date", "total_days", "reason", "status"],
        "labels": {
            "id": "ID", "employee_code": "工号", "leave_type": "请假类型",
            "start_date": "开始日期", "end_date": "结束日期",
            "total_days": "天数", "reason": "原因", "status": "状态",
        },
        "id_field": "id",
        "form_fields": [
            {"key": "employee_code", "label": "工号", "type": "text", "placeholder": "如 EMP001"},
            {"key": "leave_type", "label": "请假类型", "type": "select", "options": ["年假", "事假", "病假", "调休", "婚假", "产假"]},
            {"key": "start_date", "label": "开始日期", "type": "date"},
            {"key": "end_date", "label": "结束日期", "type": "date"},
            {"key": "total_days", "label": "天数", "type": "number", "placeholder": "如 3"},
            {"key": "reason", "label": "原因", "type": "text", "placeholder": "请假原因"},
            {"key": "status", "label": "状态", "type": "select", "options": ["待审批", "已批准", "已拒绝"]},
        ],
    },
    "payroll": {
        "title": "薪酬管理",
        "table": "payroll",
        "columns": ["id", "employee_code", "year", "month", "base_salary", "performance", "other_deduction", "net_pay"],
        "labels": {
            "id": "ID", "employee_code": "工号", "year": "年", "month": "月",
            "base_salary": "基本工资", "performance": "奖金",
            "other_deduction": "扣款", "net_pay": "实发工资",
        },
        "id_field": "id",
        "form_fields": [
            {"key": "employee_code", "label": "工号", "type": "text", "placeholder": "如 EMP001"},
            {"key": "year", "label": "年", "type": "number", "placeholder": "如 2026"},
            {"key": "month", "label": "月", "type": "number", "placeholder": "如 7"},
            {"key": "base_salary", "label": "基本工资", "type": "number", "placeholder": "如 10000"},
            {"key": "performance", "label": "奖金", "type": "number", "placeholder": "如 2000"},
            {"key": "other_deduction", "label": "扣款", "type": "number", "placeholder": "如 500"},
            {"key": "net_pay", "label": "实发工资", "type": "number", "placeholder": "如 11500"},
        ],
    },
    "recruitment": {
        "title": "招聘管理",
        "table": "recruitment",
        "columns": ["id", "position_name", "department", "candidate_name", "candidate_phone", "education", "years_of_exp", "status"],
        "labels": {
            "id": "ID", "position_name": "职位", "department": "部门",
            "candidate_name": "候选人", "candidate_phone": "电话",
            "education": "学历", "years_of_exp": "工作年限", "status": "状态",
        },
        "id_field": "id",
        "form_fields": [
            {"key": "position_name", "label": "职位", "type": "text", "placeholder": "如 高级工程师"},
            {"key": "department", "label": "部门", "type": "select", "options": ["技术部", "市场部", "财务部", "人事部", "运营部"]},
            {"key": "candidate_name", "label": "候选人", "type": "text", "placeholder": "候选人姓名"},
            {"key": "candidate_phone", "label": "电话", "type": "text", "placeholder": "联系电话"},
            {"key": "education", "label": "学历", "type": "select", "options": ["大专", "本科", "硕士", "博士"]},
            {"key": "years_of_exp", "label": "工作年限", "type": "number", "placeholder": "如 3"},
            {"key": "status", "label": "状态", "type": "select", "options": ["简历筛选", "初试", "复试", "Offer", "入职", "淘汰"]},
        ],
    },
}


# ============================================================
# 三、工具函数
# ============================================================

def generate_session_id():
    return str(uuid.uuid4())[:8]


def _chat_content_to_text(content) -> str:
    """把聊天内容统一转成可读文本，兼容字符串、列表和字典。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        if "text" in content:
            return _chat_content_to_text(content.get("text"))
        if "content" in content:
            return _chat_content_to_text(content.get("content"))
        return str(content)
    if isinstance(content, list):
        parts = [_chat_content_to_text(item) for item in content]
        return "".join(part for part in parts if part)
    return str(content)


def _extract_chat_title(history: list) -> str:
    """从对话历史提取标题：取第一条用户消息的前 20 字"""
    for msg in history:
        if msg.get("role") == "user":
            content = _chat_content_to_text(msg.get("content", ""))
            if content.startswith("📎"):
                continue
            return content[:20] + ("…" if len(content) > 20 else "")
    return "新对话"


def save_chat_session(history: list, session_id: str, chat_histories: dict, chat_sessions: list) -> tuple[dict, list]:
    """将当前对话保存到历史记录"""
    if not history or len(history) == 0:
        return chat_histories, chat_sessions
    existing_ids = [s["id"] for s in chat_sessions]
    if session_id in existing_ids:
        chat_histories[session_id] = {
            "history": history,
            "title": _extract_chat_title(history),
            "updated_at": time.time(),
        }
        return chat_histories, chat_sessions

    title = _extract_chat_title(history)
    chat_histories[session_id] = {
        "history": history,
        "title": title,
        "updated_at": time.time(),
    }
    chat_sessions.insert(0, {"id": session_id, "title": title})
    if len(chat_sessions) > 50:
        removed = chat_sessions.pop()
        chat_histories.pop(removed["id"], None)
    return chat_histories, chat_sessions


def delete_chat_session(session_id: str, chat_histories: dict, chat_sessions: list) -> tuple[dict, list]:
    """删除指定历史对话"""
    chat_histories.pop(session_id, None)
    chat_sessions = [s for s in chat_sessions if s["id"] != session_id]
    return chat_histories, chat_sessions


def rename_chat_session(session_id: str, new_title: str, chat_histories: dict, chat_sessions: list) -> tuple[dict, list]:
    """重命名指定历史对话"""
    if session_id in chat_histories:
        chat_histories[session_id]["title"] = new_title
        chat_histories[session_id]["updated_at"] = time.time()
    for s in chat_sessions:
        if s["id"] == session_id:
            s["title"] = new_title
            break
    return chat_histories, chat_sessions


# ============================================================
# 四、数据库查询函数（供数据管理页使用）
# ============================================================

def fetch_all_records(table_name: str) -> list[dict]:
    """获取指定表的全部记录"""
    with get_connection() as conn:
        rows = conn.execute(f"SELECT * FROM {table_name} ORDER BY 1").fetchall()
        return [dict(r) for r in rows]


def delete_record(table_name: str, id_field: str, record_id: str) -> bool:
    """删除指定记录"""
    with get_connection() as conn:
        conn.execute(f"DELETE FROM {table_name} WHERE {id_field} = ?", (record_id,))
    return True


def insert_record(table_name: str, data: dict) -> bool:
    """插入记录（通用）"""
    cols = ", ".join(data.keys())
    placeholders = ", ".join("?" for _ in data)
    values = list(data.values())
    with get_connection() as conn:
        conn.execute(f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})", values)
    return True


def update_record(table_name: str, id_field: str, record_id: str, data: dict) -> bool:
    """更新记录（通用）"""
    set_clause = ", ".join(f"{k} = ?" for k in data)
    values = list(data.values()) + [record_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE {table_name} SET {set_clause} WHERE {id_field} = ?", values)
    return True


def load_table_data(module_id: str):
    """加载数据表 → 返回 HTML 表格字符串（每行末尾带编辑/删除按钮）"""
    if module_id not in DATA_CONFIG:
        return "<div class='data-empty'>请从左侧选择一个数据模块</div>"
    config = DATA_CONFIG[module_id]
    table_map = {
        "employees": "employees",
        "attendance": "attendance",
        "leave": "leave_requests",
        "payroll": "payroll",
        "recruitment": "recruitment",
    }
    records = fetch_all_records(table_map[module_id])
    cols = config["columns"]
    labels = config["labels"]
    total_cols = len(cols) + 1  # +1 for 操作列

    html = "<div class='data-table-wrapper'>"
    html += "<table class='data-table'>"
    html += "<thead><tr>"
    for c in cols:
        html += f"<th>{labels[c]}</th>"
    html += "<th style='width:120px;text-align:center;'>操作</th>"
    html += "</tr></thead>"
    if not records:
        html += f"<tbody><tr><td colspan='{total_cols}' class='data-empty-row'>暂无数据</td></tr></tbody>"
    else:
        html += "<tbody>"
        for r in records:
            row_id = str(r.get(config["id_field"], ""))
            html += f"<tr data-id='{row_id}' data-module='{module_id}'>"
            for c in cols:
                val = r.get(c, "")
                html += f"<td>{val}</td>"
            html += (
                f"<td class='action-cell'>"
                f"<button class='row-action-btn row-edit-btn' data-id='{row_id}' data-module='{module_id}' title='编辑'>✏️</button>"
                f"<button class='row-action-btn row-delete-btn' data-id='{row_id}' data-module='{module_id}' title='删除'>🗑️</button>"
                f"</td>"
            )
            html += "</tr>"
        html += "</tbody>"
    html += "</table></div>"
    return html


def load_table_df(module_id: str):
    """加载数据表 → 返回 DataFrame（用于搜索过滤）"""
    if module_id not in DATA_CONFIG:
        return pd.DataFrame()
    config = DATA_CONFIG[module_id]
    table_map = {
        "employees": "employees",
        "attendance": "attendance",
        "leave": "leave_requests",
        "payroll": "payroll",
        "recruitment": "recruitment",
    }
    records = fetch_all_records(table_map[module_id])
    if not records:
        return pd.DataFrame(columns=[config["labels"][c] for c in config["columns"]])
    cols = config["columns"]
    rows = []
    for r in records:
        row = {}
        for c in cols:
            row[config["labels"][c]] = r.get(c, "")
        rows.append(row)
    return pd.DataFrame(rows)


# ============================================================
# 五、聊天与消息处理
# ============================================================

def chat_respond_stream(message, history, session_id):
    """流式输出对话回复 — 打字机效果"""
    if not message or not message.strip():
        yield history, ""
        return

    history = history + [{"role": "user", "content": message}]
    history = history + [{"role": "assistant", "content": "正在思考中..."}]
    yield history, ""

    try:
        result = run_agent(message, session_id=session_id)
        response = result.get("response", "处理失败，请稍后重试")
        tool_used = result.get("tool_used", "none")

        full_response = response
        if tool_used and tool_used != "none":
            full_response += f"\n\n---\n🔧 调用工具: `{tool_used}`"
    except Exception as e:
        full_response = f"处理失败: {str(e)}"

    history[-1]["content"] = ""
    chunk_size = 8
    for i in range(0, len(full_response), chunk_size):
        history[-1]["content"] = full_response[:i + chunk_size]
        yield history, ""
        time.sleep(0.015)

    history[-1]["content"] = full_response
    yield history, ""


def send_message_handler(message, history, session_id):
    """发送消息 — 隐藏欢迎页 → 显示聊天区 → 流式回复"""
    if not message or not message.strip():
        yield history, "", gr.update(), gr.update(), gr.update()
        return

    yield history, "", gr.update(visible=False), gr.update(visible=True), gr.update()

    for h, m in chat_respond_stream(message, history, session_id):
        yield h, m, gr.update(visible=False), gr.update(visible=True), gr.update()


def handle_new_chat(history, session_id, chat_histories, chat_sessions):
    """新建对话 — 保存旧对话到历史列表，回到欢迎页"""
    if history and len(history) > 0:
        chat_histories, chat_sessions = save_chat_session(
            history, session_id, chat_histories, chat_sessions
        )
    try:
        reset_session(session_id)
    except Exception:
        pass
    new_sid = generate_session_id()
    return (
        [], new_sid, gr.update(visible=True), gr.update(visible=False), gr.update(),
        gr.update(value=render_sidebar(chat_sessions)), chat_histories, chat_sessions,
    )


def handle_load_chat(session_id_to_load: str, chat_histories: dict):
    """加载历史对话到聊天区"""
    session = chat_histories.get(session_id_to_load, {})
    history = session.get("history", [])
    return (
        history, session_id_to_load,
        gr.update(visible=False), gr.update(visible=True), gr.update(),
    )


def handle_file_upload(file, history, session_id):
    """文件上传 — 直接解析简历，不走 Agent（避免文件路径传递问题）"""
    if file is None:
        yield history, "", gr.update(), gr.update(), gr.update(), gr.update()
        return

    file_path = file.name if hasattr(file, "name") else str(file)
    file_name = os.path.basename(file_path)

    history = history + [{"role": "user", "content": f"📎 已上传简历文件：{file_name}"}]
    history = history + [{"role": "assistant", "content": "正在解析简历..."}]
    yield history, "", gr.update(visible=False), gr.update(visible=True), gr.update(), gr.update(value=None)

    try:
        from src.resume_parser import parse_resume
        result = parse_resume(file_path)
        if isinstance(result, dict) and result.get("success"):
            d = result.get("data", {})
            lines = ["✅ **简历解析成功**\n"]
            lines.append(f"**姓名**: {d.get('name', '未识别')}")
            lines.append(f"**电话**: {d.get('phone', '未识别')}")
            lines.append(f"**邮箱**: {d.get('email', '未识别')}")
            edu = d.get("education", [])
            if edu:
                lines.append("\n**教育经历**:")
                for e in edu:
                    lines.append(f"- {e.get('school', '')} | {e.get('major', '')} | {e.get('degree', '')}")
            work = d.get("work_experience", [])
            if work:
                lines.append("\n**工作经历**:")
                for w in work:
                    lines.append(f"- {w.get('company', '')} | {w.get('position', '')} ({w.get('start_date', '')}~{w.get('end_date', '')})")
            skills = d.get("skills", [])
            if skills:
                lines.append(f"\n**技能标签**: {', '.join(skills)}")

            try:
                from src.database import get_connection
                with get_connection() as conn:
                    conn.execute(
                        "INSERT INTO recruitment (position_name, department, candidate_name, candidate_phone, education, status, remark) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (d.get("target_position", ""), "待分配", d.get("name", ""), d.get("phone", ""), d.get("education", [{}])[0].get("degree", "") if edu else "", "简历筛选", f"邮箱: {d.get('email', '')}")
                    )
                lines.append("\n✅ 候选人信息已存入招聘库")
            except Exception:
                pass

            full_response = "\n".join(lines)
        else:
            error = result.get("error", "未知错误") if isinstance(result, dict) else str(result)
            full_response = f"❌ 简历解析失败：{error}\n\n请确认文件格式为 PDF 或 Word，且文件内容可正常读取。"
    except Exception as e:
        full_response = f"❌ 简历解析出错：{str(e)}"

    history[-1]["content"] = ""
    chunk_size = 12
    for i in range(0, len(full_response), chunk_size):
        history[-1]["content"] = full_response[:i + chunk_size]
        yield history, "", gr.update(visible=False), gr.update(visible=True), gr.update(), gr.update(value=None)
        time.sleep(0.02)

    history[-1]["content"] = full_response
    yield history, "", gr.update(visible=False), gr.update(visible=True), gr.update(), gr.update(value=None)


# ============================================================
# 六、数据管理页处理函数
# ============================================================

def show_data_page(module_id):
    """切换到数据管理页 — 返回完整 HTML（工具栏 + 表格）"""
    if module_id not in DATA_CONFIG:
        module_id = "employees"
    table_html = load_table_data(module_id)
    toolbar_html = render_data_toolbar(module_id)
    full_html = f"<div id='data-page-inner'>{toolbar_html}{table_html}</div>"
    return (
        gr.update(visible=False),  # welcome
        gr.update(visible=False),  # chat
        gr.update(value=full_html), # data HTML
        module_id,
    )


def refresh_data_table(module_id):
    """刷新数据表 — 返回完整 HTML"""
    if module_id not in DATA_CONFIG:
        return gr.update(value="<div id='data-page-inner'></div>")
    table_html = load_table_data(module_id)
    toolbar_html = render_data_toolbar(module_id)
    full_html = f"<div id='data-page-inner'>{toolbar_html}{table_html}</div>"
    return gr.update(value=full_html)


def delete_selected(module_id, selected_id):
    """删除选中的行（selected_id 来自 CSS 隐藏的 Textbox）"""
    if not selected_id or str(selected_id).strip() == "":
        gr.Warning("请先选择一条记录再删除")
        return refresh_data_table(module_id), ""

    if module_id not in DATA_CONFIG:
        return refresh_data_table(module_id), ""

    config = DATA_CONFIG[module_id]
    table_map = {
        "employees": "employees",
        "attendance": "attendance",
        "leave": "leave_requests",
        "payroll": "payroll",
        "recruitment": "recruitment",
    }
    try:
        delete_record(table_map[module_id], config["id_field"], str(selected_id))
        gr.Info(f"已删除记录: {selected_id}")
    except Exception as e:
        gr.Warning(f"删除失败: {e}")

    return refresh_data_table(module_id), ""


def search_records(module_id, keyword):
    """搜索过滤 → 返回完整 HTML（含行内操作按钮）"""
    if module_id not in DATA_CONFIG:
        return gr.update(value="<div id='data-page-inner'></div>")
    config = DATA_CONFIG[module_id]
    table_map = {
        "employees": "employees",
        "attendance": "attendance",
        "leave": "leave_requests",
        "payroll": "payroll",
        "recruitment": "recruitment",
    }
    records = fetch_all_records(table_map[module_id])

    if keyword and keyword.strip():
        kw = keyword.strip().lower()
        records = [r for r in records if any(kw in str(r.get(c, "")).lower() for c in config["columns"])]

    cols = config["columns"]
    labels = config["labels"]
    total_cols = len(cols) + 1
    html = "<div class='data-table-wrapper'>"
    html += "<table class='data-table'>"
    html += "<thead><tr>"
    for c in cols:
        html += f"<th>{labels[c]}</th>"
    html += "<th style='width:120px;text-align:center;'>操作</th>"
    html += "</tr></thead>"
    if not records:
        html += f"<tbody><tr><td colspan='{total_cols}' class='data-empty-row'>无匹配结果</td></tr></tbody>"
    else:
        html += "<tbody>"
        for r in records:
            row_id = str(r.get(config["id_field"], ""))
            html += f"<tr data-id='{row_id}' data-module='{module_id}'>"
            for c in cols:
                val = r.get(c, "")
                html += f"<td>{val}</td>"
            html += (
                f"<td class='action-cell'>"
                f"<button class='row-action-btn row-edit-btn' data-id='{row_id}' data-module='{module_id}' title='编辑'>✏️</button>"
                f"<button class='row-action-btn row-delete-btn' data-id='{row_id}' data-module='{module_id}' title='删除'>🗑️</button>"
                f"</td>"
            )
            html += "</tr>"
        html += "</tbody>"
    html += "</table></div>"
    toolbar_html = render_data_toolbar(module_id)
    full_html = f"<div id='data-page-inner'>{toolbar_html}{html}</div>"
    return gr.update(value=full_html)


def get_record_by_id(module_id: str, record_id: str) -> dict | None:
    """根据模块和记录ID获取单条记录数据（用于编辑表单预填充）"""
    if module_id not in DATA_CONFIG:
        return None
    config = DATA_CONFIG[module_id]
    table_map = {
        "employees": "employees",
        "attendance": "attendance",
        "leave": "leave_requests",
        "payroll": "payroll",
        "recruitment": "recruitment",
    }
    records = fetch_all_records(table_map[module_id])
    id_field = config["id_field"]
    for r in records:
        if str(r.get(id_field, "")) == str(record_id):
            return r
    return None


def show_form(module_id, mode="add", record_id=""):
    """显示新增/编辑表单 — 编辑模式自动预填充当前记录数据"""
    if module_id not in DATA_CONFIG:
        return gr.update()
    record_data = None
    if mode == "edit" and record_id:
        record_data = get_record_by_id(module_id, record_id)
    table_html = load_table_data(module_id)
    toolbar_html = render_data_toolbar(module_id)
    form_html = render_form_html(module_id, mode, record_id, record_data)
    full_html = f"<div id='data-page-inner'>{toolbar_html}{table_html}{form_html}</div>"
    return gr.update(value=full_html)


def render_form_html(module_id, mode="add", record_id="", record_data=None):
    """渲染新增/编辑表单 HTML — 编辑模式自动预填充字段值"""
    if module_id not in DATA_CONFIG:
        return ""
    config = DATA_CONFIG[module_id]
    fields = config["form_fields"]
    title = "编辑记录" if mode == "edit" else "新增记录"

    html = f"<div id='data-form-overlay' class='form-overlay'>"
    html += f"<div id='data-form-modal' class='form-modal'>"
    html += f"<div class='form-modal-title'>{title} — {config['title']}</div>"
    html += "<div class='form-fields'>"
    for f in fields:
        key = f["key"]
        label = f["label"]
        ftype = f["type"]
        placeholder = f.get("placeholder", "")
        current_val = ""
        if mode == "edit" and record_data:
            raw = record_data.get(key, "")
            current_val = str(raw) if raw is not None else ""
        if ftype == "select":
            opts = ""
            for o in f["options"]:
                selected = ' selected' if (mode == "edit" and str(o) == current_val) else ''
                opts += f"<option value='{o}'{selected}>{o}</option>"
            html += f"<div class='form-field'><label>{label}</label><select name='{key}'>{opts}</select></div>"
        elif ftype == "date":
            html += f"<div class='form-field'><label>{label}</label><input type='date' name='{key}' value='{current_val}' placeholder='{placeholder}' /></div>"
        elif ftype == "number":
            html += f"<div class='form-field'><label>{label}</label><input type='number' name='{key}' value='{current_val}' placeholder='{placeholder}' /></div>"
        else:
            html += f"<div class='form-field'><label>{label}</label><input type='text' name='{key}' value='{current_val}' placeholder='{placeholder}' /></div>"
    html += "</div>"
    html += "<div class='form-modal-actions'>"
    html += f"<button id='form-cancel-btn' class='data-btn'>取消</button>"
    html += f"<button id='form-submit-btn' class='data-btn primary' data-mode='{mode}' data-module='{module_id}' data-record-id='{record_id}'>确定</button>"
    html += "</div>"
    html += "</div></div>"
    return html


def handle_form_submit(module_id, mode, record_id, form_json):
    """处理表单提交 — 新增或编辑"""
    if module_id not in DATA_CONFIG:
        return refresh_data_table(module_id), ""
    import json
    try:
        data = json.loads(form_json) if isinstance(form_json, str) else form_json
    except Exception:
        data = {}

    data = {k: v for k, v in data.items() if v is not None and str(v).strip() != ""}

    config = DATA_CONFIG[module_id]
    table_name = config["table"]

    try:
        if mode == "edit" and record_id:
            update_record(table_name, config["id_field"], record_id, data)
            gr.Info(f"已更新记录: {record_id}")
        else:
            insert_record(table_name, data)
            gr.Info("新增记录成功")
    except Exception as e:
        gr.Warning(f"操作失败: {e}")

    return refresh_data_table(module_id), ""


# ============================================================
# 七、HTML 渲染函数
# ============================================================

def render_welcome_page():
    cards_html = ""
    for p in WELCOME_PROMPTS:
        cards_html += f"""
        <div class="welcome-card" data-prompt="{p['prompt']}">
            <div class="welcome-card-icon">{p['icon']}</div>
            <div class="welcome-card-body">
                <div class="welcome-card-title">{p['title']}</div>
                <div class="welcome-card-desc">{p['desc']}</div>
            </div>
        </div>
        """
    return f"""
    <div class="welcome-container">
        <div class="welcome-title">你好，我是 HR 数字员工 👋</div>
        <div class="welcome-subtitle">我可以帮你查询员工信息、考勤记录、薪酬个税，解析简历，办理入离职，回答制度问题等。</div>
        <div class="welcome-cards">
            {cards_html}
        </div>
    </div>
    """


def render_sidebar(chat_sessions: list = None):
    """渲染侧边栏 — 含导航、历史对话列表"""
    nav_html = ""
    for item in NAV_ITEMS:
        nav_html += f'<div class="nav-item" data-module="{item["id"]}"><span class="nav-icon">{item["icon"]}</span>{item["label"]}</div>'

    history_html = ""
    if chat_sessions:
        for sess in chat_sessions:
            sid = sess.get("id", "")
            title = sess.get("title", "新对话")
            history_html += f'''<div class="history-item" data-session-id="{sid}">
                <span class="history-title" title="双击重命名">{title}</span>
                <span class="history-actions">
                    <span class="history-rename" title="重命名">✏️</span>
                    <span class="history-delete" title="删除">🗑️</span>
                </span>
            </div>'''

    return f"""
    <div class="sidebar-section-title">对话</div>
    <div class="nav-item active" data-module="chat"><span class="nav-icon">💬</span>新对话</div>
    {history_html}
    <div class="sidebar-section-title">数据管理</div>
    {nav_html}
    <div class="user-bar">
        <div class="user-avatar">HR</div>
        <div>
            <div class="user-name">HR 管理员</div>
            <div class="user-role">数字员工 · 在线</div>
        </div>
    </div>
    """


def render_top_bar():
    return """
    <div class="top-bar">
        <div class="top-bar-title">HR 数字员工</div>
        <div class="top-bar-actions">
            <button class="top-bar-btn" id="clear-chat-btn" title="清空对话">🗑️</button>
        </div>
    </div>
    """


def render_quick_prompts():
    tags_html = ""
    for p in QUICK_PROMPTS:
        tags_html += f'<span class="quick-prompt-tag" data-prompt="{p}">{p}</span>'
    return f'<div class="quick-prompts">{tags_html}</div>'


def render_data_toolbar(module_id):
    """渲染数据管理工具栏"""
    config = DATA_CONFIG[module_id]
    return f"""
    <div class="data-toolbar">
        <div class="data-toolbar-left">
            <span style="font-size:18px;font-weight:600;color:#1d2129;">{config['title']}</span>
            <span style="font-size:13px;color:#86909c;margin-left:8px;">共 <span id="data-count">-</span> 条记录</span>
        </div>
        <div class="data-toolbar-right">
            <input type="text" class="data-search" id="data-search-input" placeholder="搜索..." />
            <button class="data-btn" id="data-refresh-btn">🔄 刷新</button>
            <button class="data-btn" id="data-add-btn">➕ 新增</button>
        </div>
    </div>
    """


# ============================================================
# 八、界面构建
# ============================================================

def create_app():
    """构建 Gradio 应用"""

    with gr.Blocks(
        title="HR 数字员工",
        analytics_enabled=False,
    ) as app:

        # ===== 状态 =====
        session_state = gr.State(value=generate_session_id())
        current_module = gr.State(value="employees")
        # 对话历史持久化
        chat_histories = gr.State(value={})
        chat_sessions = gr.State(value=[])
        # CSS 隐藏的 Textbox 用于传递选中行 ID（Gradio visible=False 不渲染 DOM）
        selected_record_id = gr.Textbox(value="", elem_id="selected-record-id", elem_classes="hidden-trigger")

        with gr.Row(elem_id="app-root", equal_height=False):

            # ===== 左侧边栏 =====
            sidebar_col = gr.Column(elem_id="sidebar", scale=0, min_width=260)
            with sidebar_col:
                new_chat_btn = gr.Button("+ 新建对话", elem_id="new-chat-btn", variant="primary")
                sidebar_html = gr.HTML(value=render_sidebar([]))

            # ===== 右侧主区 =====
            main_col = gr.Column(elem_id="main-area", scale=1, min_width=400)
            with main_col:
                top_bar_html = gr.HTML(value=render_top_bar())

                # 欢迎页（默认可见）
                welcome_col = gr.Column(elem_id="welcome-page", visible=True)
                with welcome_col:
                    welcome_html = gr.HTML(value=render_welcome_page())

                # 聊天区（初始用 CSS 隐藏）
                chat_col = gr.Column(elem_id="chat-area", elem_classes="initially-hidden")
                with chat_col:
                    chatbot = gr.Chatbot(
                        elem_id="chatbot",
                        show_label=False,
                        height=None,
                        render_markdown=True,
                        latex_delimiters=[],
                    )

                # 数据管理页 — 用 HTML 组件直接渲染
                data_col = gr.HTML(value="<div id='data-page-inner'></div>", elem_id="data-page-container")
                data_table = data_col

                # 底部输入区
                input_col = gr.Column(elem_id="input-wrapper")
                with input_col:
                    quick_prompts_html = gr.HTML(value=render_quick_prompts())
                    with gr.Row(equal_height=False, elem_classes="input-card"):
                        file_upload = gr.File(
                            elem_id="file-upload",
                            label="",
                            file_types=[".pdf", ".doc", ".docx"],
                            show_label=False,
                            scale=0,
                            min_width=36,
                        )
                        msg_input = gr.Textbox(
                            elem_id="msg-input",
                            placeholder="输入消息，Enter 发送",
                            show_label=False,
                            lines=2,
                            max_lines=4,
                            scale=1,
                        )
                        send_btn = gr.Button("➤", elem_id="send-btn", variant="primary", scale=0, min_width=36)

        # ============================================================
        # 九、隐藏触发器
        # ============================================================

        # 每个数据模块一个导航触发器
        nav_triggers = {}
        for mod_id in DATA_CONFIG:
            btn = gr.Button(elem_id=f"nav-trigger-{mod_id}", elem_classes="hidden-trigger")
            btn.click(
                fn=lambda mid=mod_id: show_data_page(mid),
                inputs=None,
                outputs=[welcome_col, chat_col, data_col, current_module],
            )
            nav_triggers[mod_id] = btn

        # 聊天页导航触发器（新建对话）
        chat_nav_trigger = gr.Button(elem_id="chat-nav-trigger", elem_classes="hidden-trigger")
        chat_nav_trigger.click(
            handle_new_chat,
            inputs=[chatbot, session_state, chat_histories, chat_sessions],
            outputs=[chatbot, session_state, welcome_col, chat_col, data_col, sidebar_html, chat_histories, chat_sessions],
        )

        # 历史对话加载/删除/重命名
        history_session_id_input = gr.Textbox(value="", elem_id="history-session-id", elem_classes="hidden-trigger")
        history_new_title_input = gr.Textbox(value="", elem_id="history-new-title", elem_classes="hidden-trigger")

        load_history_trigger = gr.Button(elem_id="load-history-trigger", elem_classes="hidden-trigger")
        load_history_trigger.click(
            handle_load_chat,
            inputs=[history_session_id_input, chat_histories],
            outputs=[chatbot, session_state, welcome_col, chat_col, data_col],
        )

        def _on_delete_history(sid, hs, ss):
            hs, ss = delete_chat_session(sid, hs, ss)
            return hs, ss, gr.update(value=render_sidebar(ss))

        delete_history_trigger = gr.Button(elem_id="delete-history-trigger", elem_classes="hidden-trigger")
        delete_history_trigger.click(
            fn=_on_delete_history,
            inputs=[history_session_id_input, chat_histories, chat_sessions],
            outputs=[chat_histories, chat_sessions, sidebar_html],
        )

        def _on_rename_history(sid, title, hs, ss):
            hs, ss = rename_chat_session(sid, title, hs, ss)
            return hs, ss, gr.update(value=render_sidebar(ss))

        rename_history_trigger = gr.Button(elem_id="rename-history-trigger", elem_classes="hidden-trigger")
        rename_history_trigger.click(
            fn=_on_rename_history,
            inputs=[history_session_id_input, history_new_title_input, chat_histories, chat_sessions],
            outputs=[chat_histories, chat_sessions, sidebar_html],
        )

        # 刷新数据触发器
        refresh_trigger = gr.Button(elem_id="data-refresh-trigger", elem_classes="hidden-trigger")
        refresh_trigger.click(
            refresh_data_table,
            inputs=[current_module],
            outputs=[data_col],
        )

        # 删除触发器
        delete_trigger = gr.Button(elem_id="data-delete-trigger", elem_classes="hidden-trigger")
        delete_trigger.click(
            delete_selected,
            inputs=[current_module, selected_record_id],
            outputs=[data_col, selected_record_id],
        )

        # 搜索触发器
        search_kw_input = gr.Textbox(value="", elem_id="search-kw-input", elem_classes="hidden-trigger")
        search_trigger = gr.Button(elem_id="data-search-trigger", elem_classes="hidden-trigger")
        search_trigger.click(
            fn=lambda kw, mod: search_records(mod, kw),
            inputs=[search_kw_input, current_module],
            outputs=[data_col],
        )

        # 新增触发器
        add_trigger = gr.Button(elem_id="data-add-trigger", elem_classes="hidden-trigger")
        add_trigger.click(
            fn=lambda mod: show_form(mod, "add", ""),
            inputs=[current_module],
            outputs=[data_col],
        )

        # 编辑触发器
        edit_trigger = gr.Button(elem_id="data-edit-trigger", elem_classes="hidden-trigger")
        edit_trigger.click(
            fn=lambda mod, rid: show_form(mod, "edit", rid),
            inputs=[current_module, selected_record_id],
            outputs=[data_col],
        )

        # 表单提交触发器
        form_data_input = gr.Textbox(value="", elem_id="form-data-input", elem_classes="hidden-trigger")
        form_mode_input = gr.Textbox(value="", elem_id="form-mode-input", elem_classes="hidden-trigger")
        form_record_id_input = gr.Textbox(value="", elem_id="form-record-id-input", elem_classes="hidden-trigger")
        form_submit_trigger = gr.Button(elem_id="form-submit-trigger", elem_classes="hidden-trigger")
        form_submit_trigger.click(
            handle_form_submit,
            inputs=[current_module, form_mode_input, form_record_id_input, form_data_input],
            outputs=[data_col, selected_record_id],
        )

        # ============================================================
        # 十、事件处理
        # ============================================================

        # --- 发送消息（按钮点击）---
        send_btn.click(
            send_message_handler,
            inputs=[msg_input, chatbot, session_state],
            outputs=[chatbot, msg_input, welcome_col, chat_col, data_col],
        )

        # --- 发送消息（Enter键）---
        msg_input.submit(
            send_message_handler,
            inputs=[msg_input, chatbot, session_state],
            outputs=[chatbot, msg_input, welcome_col, chat_col, data_col],
        )

        # --- 文件上传 ---
        file_upload.change(
            fn=None,
            inputs=[file_upload],
            js="""(file) => {
                if (file && file.path) {
                    const wp = document.querySelector('#welcome-page');
                    const ca = document.querySelector('#chat-area');
                    const dp = document.querySelector('#data-page-container');
                    const iw = document.querySelector('#input-wrapper');
                    if (wp) wp.style.display = 'none';
                    if (ca) ca.classList.add('chat-visible');
                    if (dp) dp.classList.remove('data-visible');
                    if (iw) iw.classList.remove('input-hidden');
                    setTimeout(() => {
                        const btn = document.querySelector('#file-process-trigger');
                        if (btn) btn.click();
                    }, 300);
                }
            }""",
        )

        file_process_trigger = gr.Button(elem_id="file-process-trigger", elem_classes="hidden-trigger")
        file_process_trigger.click(
            fn=handle_file_upload,
            inputs=[file_upload, chatbot, session_state],
            outputs=[chatbot, msg_input, welcome_col, chat_col, data_col, file_upload],
        )

        # ============================================================
        # 十一、页面加载 JavaScript — 交互逻辑
        # ============================================================
        app.load(
            fn=None,
            js="""
            () => {
                setTimeout(() => {

                function fillInput(prompt) {
                    const input = document.querySelector('#msg-input textarea');
                    if (input) {
                        input.value = prompt;
                        input.dispatchEvent(new Event('input', {bubbles: true}));
                        input.focus();
                    }
                }

                function triggerHidden(id) {
                    const btn = document.querySelector('#' + id);
                    if (btn) btn.click();
                }

                function setHiddenValue(id, value) {
                    const ta = document.querySelector('#' + id + ' textarea');
                    if (ta) {
                        ta.value = value;
                        ta.dispatchEvent(new Event('input', {bubbles: true}));
                    }
                }

                // 欢迎页卡片点击
                document.querySelectorAll('.welcome-card').forEach(card => {
                    card.addEventListener('click', () => {
                        fillInput(card.getAttribute('data-prompt'));
                    });
                });

                // 快捷提示标签点击
                document.querySelectorAll('.quick-prompt-tag').forEach(tag => {
                    tag.addEventListener('click', () => {
                        fillInput(tag.getAttribute('data-prompt'));
                    });
                });

                // 侧边栏导航
                document.querySelectorAll('.nav-item[data-module]').forEach(item => {
                    item.addEventListener('click', () => {
                        const moduleId = item.getAttribute('data-module');
                        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
                        item.classList.add('active');

                        if (moduleId === 'chat') {
                            document.querySelector('#welcome-page').style.display = '';
                            document.querySelector('#chat-area').classList.add('chat-visible');
                            document.querySelector('#input-wrapper').classList.remove('input-hidden');
                            document.querySelector('#data-page-container').classList.remove('data-visible');
                            triggerHidden('chat-nav-trigger');
                        } else {
                            document.querySelector('#welcome-page').style.display = 'none';
                            document.querySelector('#chat-area').classList.remove('chat-visible');
                            document.querySelector('#input-wrapper').classList.add('input-hidden');
                            const dp = document.querySelector('#data-page-container');
                            dp.classList.add('data-visible');
                            dp.style.overflowY = 'auto';
                            dp.style.setProperty('overflow-y', 'auto', 'important');
                            triggerHidden('nav-trigger-' + moduleId);
                        }
                    });
                });

                // 新建对话按钮
                const newChatBtn = document.querySelector('#new-chat-btn');
                if (newChatBtn) {
                    newChatBtn.addEventListener('click', () => {
                        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
                        const chatNav = document.querySelector('.nav-item[data-module="chat"]');
                        if (chatNav) chatNav.classList.add('active');
                        document.querySelector('#welcome-page').style.display = '';
                        document.querySelector('#chat-area').classList.remove('chat-visible');
                        document.querySelector('#input-wrapper').classList.remove('input-hidden');
                        document.querySelector('#data-page-container').classList.remove('data-visible');
                        triggerHidden('chat-nav-trigger');
                    });
                }

                // 顶栏清空对话
                const clearBtn = document.querySelector('#clear-chat-btn');
                if (clearBtn) {
                    clearBtn.addEventListener('click', () => {
                        document.querySelector('#welcome-page').style.display = '';
                        document.querySelector('#chat-area').classList.remove('chat-visible');
                        document.querySelector('#input-wrapper').classList.remove('input-hidden');
                        document.querySelector('#data-page-container').classList.remove('data-visible');
                        triggerHidden('chat-nav-trigger');
                    });
                }

                // 历史对话、数据操作（事件委托）
                document.addEventListener('click', (e) => {
                    // 加载历史对话
                    const historyItem = e.target.closest('.history-item');
                    if (historyItem && !e.target.closest('.history-delete') && !e.target.closest('.history-rename')) {
                        e.preventDefault();
                        const sid = historyItem.getAttribute('data-session-id');
                        setHiddenValue('history-session-id', sid);
                        document.querySelector('#welcome-page').style.display = 'none';
                        document.querySelector('#chat-area').classList.add('chat-visible');
                        document.querySelector('#input-wrapper').classList.remove('input-hidden');
                        document.querySelector('#data-page-container').classList.remove('data-visible');
                        document.querySelectorAll('.history-item').forEach(h => h.classList.remove('active'));
                        historyItem.classList.add('active');
                        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
                        triggerHidden('load-history-trigger');
                    }
                    // 删除历史对话
                    if (e.target.closest('.history-delete')) {
                        e.preventDefault();
                        e.stopPropagation();
                        const item = e.target.closest('.history-item');
                        const sid = item.getAttribute('data-session-id');
                        if (confirm('确定要删除这条对话记录吗？')) {
                            setHiddenValue('history-session-id', sid);
                            triggerHidden('delete-history-trigger');
                        }
                    }
                    // 重命名历史对话
                    if (e.target.closest('.history-rename')) {
                        e.preventDefault();
                        e.stopPropagation();
                        const item = e.target.closest('.history-item');
                        const sid = item.getAttribute('data-session-id');
                        const titleEl = item.querySelector('.history-title');
                        const newTitle = prompt('请输入新的对话名称：', titleEl ? titleEl.textContent : '');
                        if (newTitle && newTitle.trim()) {
                            setHiddenValue('history-session-id', sid);
                            setHiddenValue('history-new-title', newTitle.trim());
                            triggerHidden('rename-history-trigger');
                        }
                    }
                    // 刷新按钮
                    if (e.target.closest('#data-refresh-btn')) {
                        e.preventDefault();
                        triggerHidden('data-refresh-trigger');
                    }
                    // 新增按钮
                    if (e.target.closest('#data-add-btn')) {
                        e.preventDefault();
                        triggerHidden('data-add-trigger');
                    }
                    // 行内编辑按钮
                    if (e.target.closest('.row-edit-btn')) {
                        e.preventDefault();
                        e.stopPropagation();
                        const btn = e.target.closest('.row-edit-btn');
                        const rid = btn.getAttribute('data-id');
                        setHiddenValue('selected-record-id', rid);
                        document.querySelectorAll('.data-table tr.selected').forEach(r => r.classList.remove('selected'));
                        const row = btn.closest('tr');
                        if (row) row.classList.add('selected');
                        setTimeout(() => triggerHidden('data-edit-trigger'), 100);
                    }
                    // 行内删除按钮
                    if (e.target.closest('.row-delete-btn')) {
                        e.preventDefault();
                        e.stopPropagation();
                        const btn = e.target.closest('.row-delete-btn');
                        const rid = btn.getAttribute('data-id');
                        if (confirm('确定要删除该记录吗？此操作不可撤销。')) {
                            setHiddenValue('selected-record-id', rid);
                            setTimeout(() => triggerHidden('data-delete-trigger'), 100);
                        }
                    }
                    // 表单取消
                    if (e.target.closest('#form-cancel-btn')) {
                        e.preventDefault();
                        const overlay = document.querySelector('#data-form-overlay');
                        if (overlay) overlay.remove();
                    }
                    // 表单提交
                    if (e.target.closest('#form-submit-btn')) {
                        e.preventDefault();
                        const btn = e.target.closest('#form-submit-btn');
                        const mode = btn.getAttribute('data-mode');
                        const mod = btn.getAttribute('data-module');
                        const rid = btn.getAttribute('data-record-id');
                        const formEl = document.querySelector('#data-form-modal');
                        const inputs = formEl.querySelectorAll('input, select');
                        const data = {};
                        inputs.forEach(inp => {
                            if (inp.name) data[inp.name] = inp.value;
                        });
                        setHiddenValue('form-data-input', JSON.stringify(data));
                        setHiddenValue('form-mode-input', mode);
                        setHiddenValue('form-record-id-input', rid || '');
                        setTimeout(() => {
                            triggerHidden('form-submit-trigger');
                            const overlay = document.querySelector('#data-form-overlay');
                            if (overlay) overlay.remove();
                        }, 200);
                    }
                    // 表格行点击高亮
                    const row = e.target.closest('.data-table tbody tr');
                    if (row && !e.target.closest('.row-edit-btn') && !e.target.closest('.row-delete-btn')) {
                        document.querySelectorAll('.data-table tr.selected').forEach(r => r.classList.remove('selected'));
                        row.classList.add('selected');
                        setHiddenValue('selected-record-id', row.getAttribute('data-id'));
                    }
                });

                // 搜索框回车
                document.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' && e.target && e.target.id === 'data-search-input') {
                        e.preventDefault();
                        const kw = document.querySelector('#data-search-input')?.value || '';
                        setHiddenValue('search-kw-input', kw);
                        setTimeout(() => triggerHidden('data-search-trigger'), 200);
                    }
                });

                // 输入框自适应高度 + Enter发送
                const textarea = document.querySelector('#msg-input textarea');
                if (textarea) {
                    textarea.style.resize = 'none';
                    textarea.addEventListener('input', () => {
                        textarea.style.height = 'auto';
                        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
                    });
                    textarea.addEventListener('keydown', (e) => {
                        if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey) {
                            e.preventDefault();
                            const sendBtn = document.querySelector('#send-btn');
                            if (sendBtn) sendBtn.click();
                            document.querySelector('#welcome-page').style.display = 'none';
                            document.querySelector('#chat-area').classList.add('chat-visible');
                        }
                    });
                }

                // 发送按钮点击
                const sendBtn = document.querySelector('#send-btn');
                if (sendBtn) {
                    sendBtn.addEventListener('click', () => {
                        document.querySelector('#welcome-page').style.display = 'none';
                        document.querySelector('#chat-area').classList.add('chat-visible');
                    });
                }

                // MutationObserver 限制消息气泡宽度
                const chatbotEl = document.querySelector('#chatbot');
                if (chatbotEl) {
                    const observer = new MutationObserver(() => {
                        chatbotEl.querySelectorAll('.message-wrap').forEach(w => {
                            w.style.setProperty('max-width', '50%', 'important');
                        });
                        chatbotEl.querySelectorAll('.message').forEach(m => {
                            m.style.setProperty('max-width', '100%', 'important');
                            m.style.setProperty('width', 'fit-content', 'important');
                        });
                    });
                    observer.observe(chatbotEl, {childList: true, subtree: true, attributes: true, attributeFilter: ['style', 'class']});
                }

                }, 1500);
            }
            """,
        )

    return app


# ============================================================
# 十二、启动
# ============================================================

if __name__ == "__main__":
    import gradio as gr

    app = create_app()
    app.queue()
    app.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        show_error=True,
        css=DOUBAO_CSS,
        theme=gr.themes.Default(
            font=['-apple-system', 'BlinkMacSystemFont', 'PingFang SC', 'Microsoft YaHei', 'sans-serif'],
            primary_hue=gr.themes.colors.blue,
            neutral_hue=gr.themes.colors.gray,
            radius_size=gr.themes.sizes.radius_md,
        ),
    )
