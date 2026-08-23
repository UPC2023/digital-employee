-- ============================================================
-- HR Agent 数据库建表脚本 v4.0
-- 数据库：SQLite
-- 包含：8张核心表 + 索引 + 外键约束
-- 更新日期：2026-07-09
-- ============================================================

-- ============================================================
-- 一、员工信息表（employees）— 修改：+password_hash, +role, +leave_date
-- ============================================================
CREATE TABLE IF NOT EXISTS employees (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_code     VARCHAR(20)  UNIQUE NOT NULL,         -- 工号，如 EMP001
    name              VARCHAR(50)  NOT NULL,                 -- 姓名
    gender            VARCHAR(4)   DEFAULT '男',             -- 性别：男/女
    password_hash     VARCHAR(128) NOT NULL DEFAULT '',      -- 🆕 SHA256密码哈希（初始密码123456）
    role              VARCHAR(20)  NOT NULL DEFAULT 'employee', -- 🆕 角色：employee / admin
    phone             VARCHAR(20),                           -- 手机号
    email             VARCHAR(100),                          -- 邮箱
    department        VARCHAR(100) NOT NULL,                 -- 部门
    position          VARCHAR(100) NOT NULL,                 -- 职位
    hire_date         DATE         NOT NULL,                 -- 入职日期
    leave_date        DATE,                                  -- 🆕 离职日期（离职时填写）
    status            VARCHAR(20)  DEFAULT '在职',            -- 在职状态：在职/离职/试用期
    id_card           VARCHAR(18),                           -- 身份证号（用于个税）
    education         VARCHAR(50),                           -- 最高学历
    school            VARCHAR(100),                          -- 毕业院校
    major             VARCHAR(100),                          -- 专业
    address           TEXT,                                  -- 住址
    emergency_contact VARCHAR(50),                           -- 紧急联系人
    emergency_phone   VARCHAR(20),                           -- 紧急联系电话
    created_at        DATETIME     DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME     DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_employees_code ON employees(employee_code);
CREATE INDEX IF NOT EXISTS idx_employees_dept ON employees(department);
CREATE INDEX IF NOT EXISTS idx_employees_status ON employees(status);
CREATE INDEX IF NOT EXISTS idx_employees_role ON employees(role);         -- 🆕 角色索引


-- ============================================================
-- 二、考勤表（attendance）— 不变
-- ============================================================
CREATE TABLE IF NOT EXISTS attendance (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_code   VARCHAR(20)  NOT NULL,                   -- 工号
    date            DATE         NOT NULL,                   -- 日期
    clock_in        DATETIME,                                -- 上班打卡时间
    clock_out       DATETIME,                                -- 下班打卡时间
    status          VARCHAR(20)  DEFAULT '正常',              -- 考勤状态：正常/迟到/早退/缺勤/请假
    overtime_hours  DECIMAL(4,1) DEFAULT 0,                  -- 加班小时数
    remark          TEXT,                                    -- 备注
    FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
);

CREATE INDEX IF NOT EXISTS idx_attendance_code ON attendance(employee_code);
CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date);


-- ============================================================
-- 三、请假表（leave_requests）— 确认审批字段
-- ============================================================
CREATE TABLE IF NOT EXISTS leave_requests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_code   VARCHAR(20)  NOT NULL,                   -- 工号
    leave_type      VARCHAR(30)  NOT NULL,                   -- 请假类型：年假/事假/病假/婚假/产假/调休
    start_date      DATE         NOT NULL,                   -- 开始日期
    end_date        DATE         NOT NULL,                   -- 结束日期
    total_days      DECIMAL(3,1) NOT NULL,                   -- 请假天数
    reason          TEXT,                                    -- 请假原因
    status          VARCHAR(20)  DEFAULT '待审批',            -- 审批状态：待审批/已批准/已驳回
    approver        VARCHAR(20),                             -- 审批人工号（关联 employees.employee_code）
    approved_at     DATETIME,                                -- 审批时间
    created_at      DATETIME     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
);

CREATE INDEX IF NOT EXISTS idx_leave_code ON leave_requests(employee_code);
CREATE INDEX IF NOT EXISTS idx_leave_status ON leave_requests(status);


-- ============================================================
-- 四、薪酬表（payroll）— 不变
-- ============================================================
CREATE TABLE IF NOT EXISTS payroll (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_code    VARCHAR(20)  NOT NULL,                  -- 工号
    year             INTEGER      NOT NULL,                  -- 年份
    month            INTEGER      NOT NULL,                  -- 月份
    base_salary      DECIMAL(10,2) NOT NULL,                 -- 基本工资
    performance      DECIMAL(10,2) DEFAULT 0,                -- 绩效工资（奖金）
    subsidies        DECIMAL(10,2) DEFAULT 0,                -- 补贴（餐补+交通+通讯）
    overtime_pay     DECIMAL(10,2) DEFAULT 0,                -- 加班费
    gross_pay        DECIMAL(10,2) NOT NULL,                 -- 应发合计 = base+performance+subsidies+overtime
    social_insurance DECIMAL(10,2) DEFAULT 0,                -- 社保扣款
    housing_fund     DECIMAL(10,2) DEFAULT 0,                -- 公积金扣款
    tax              DECIMAL(10,2) DEFAULT 0,                -- 个人所得税
    other_deduction  DECIMAL(10,2) DEFAULT 0,                -- 其他扣款
    net_pay          DECIMAL(10,2) NOT NULL,                 -- 实发工资 = gross - si - hf - tax - other
    pay_date         DATE,                                   -- 发放日期
    FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
);

CREATE INDEX IF NOT EXISTS idx_payroll_code ON payroll(employee_code);
CREATE INDEX IF NOT EXISTS idx_payroll_ym ON payroll(year, month);


-- ============================================================
-- 五、招聘表（recruitment）— 保留面试快照字段
-- ============================================================
CREATE TABLE IF NOT EXISTS recruitment (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    position_name   VARCHAR(100) NOT NULL,                   -- 招聘岗位
    department      VARCHAR(100) NOT NULL,                   -- 所属部门
    candidate_name  VARCHAR(50),                             -- 候选人姓名
    candidate_phone VARCHAR(20),                             -- 候选人电话
    candidate_email VARCHAR(100),                            -- 候选人邮箱
    education       VARCHAR(50),                             -- 学历
    school          VARCHAR(100),                            -- 毕业院校
    years_of_exp    INTEGER,                                 -- 工作年限
    skills          TEXT,                                    -- 技能标签（逗号分隔）
    resume_path     VARCHAR(500),                            -- 简历文件路径
    resume_parsed   TEXT,                                    -- 解析后的JSON文本
    status          VARCHAR(30)  DEFAULT '简历筛选',          -- 招聘状态
    interview_date  DATETIME,                                -- 最新面试时间（快照，详细记录见interviews表）
    interviewer     VARCHAR(20),                             -- 最新面试官工号（快照）
    remark          TEXT,                                    -- 备注
    created_at      DATETIME     DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_recruitment_status ON recruitment(status);
CREATE INDEX IF NOT EXISTS idx_recruitment_dept ON recruitment(department);


-- ============================================================
-- 六、🆕 面试记录表（interviews）— 支持多轮面试
-- ============================================================
CREATE TABLE IF NOT EXISTS interviews (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    recruitment_id     INTEGER NOT NULL,                    -- 关联 recruitment.id
    round              VARCHAR(20) NOT NULL,                -- 面试轮次：初试/复试/终试
    interview_date     DATETIME,                            -- 面试时间
    interviewer_code   VARCHAR(20),                         -- 面试官工号（关联 employees）
    location           VARCHAR(200),                        -- 面试地点（或线上链接）
    notes              TEXT,                                -- 面试备注/提醒事项
    result             VARCHAR(50),                         -- 面试结果：通过/待定/淘汰
    status             VARCHAR(20) DEFAULT '待面试',        -- 状态：待面试/已完成/已取消
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (recruitment_id) REFERENCES recruitment(id),
    FOREIGN KEY (interviewer_code) REFERENCES employees(employee_code)
);

CREATE INDEX IF NOT EXISTS idx_interviews_rec ON interviews(recruitment_id);
CREATE INDEX IF NOT EXISTS idx_interviews_date ON interviews(interview_date);
CREATE INDEX IF NOT EXISTS idx_interviews_status ON interviews(status);


-- ============================================================
-- 七、🆕 通知日志表（notification_log）— 邮件/企微推送追踪
-- ============================================================
CREATE TABLE IF NOT EXISTS notification_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    type          VARCHAR(20) NOT NULL,                     -- 类型：email / dingtalk / wecom
    recipient     VARCHAR(200) NOT NULL,                    -- 收件人邮箱 或 群聊名称
    subject       VARCHAR(300),                             -- 邮件主题 或 推送标题
    content       TEXT,                                     -- 内容摘要（前500字）
    status        VARCHAR(20) DEFAULT 'sent',               -- 状态：sent / failed
    error_msg     TEXT,                                     -- 失败时的错误信息
    sent_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notif_type ON notification_log(type);
CREATE INDEX IF NOT EXISTS idx_notif_time ON notification_log(sent_at);


-- ============================================================
-- 八、🆕 入职任务跟踪表（onboarding_tasks）
-- ============================================================
CREATE TABLE IF NOT EXISTS onboarding_tasks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_code   VARCHAR(20) NOT NULL,                   -- 新员工工号
    task_name       VARCHAR(100) NOT NULL,                  -- 任务名称
    category        VARCHAR(50),                            -- 分类：材料/设备/账号/培训
    status          VARCHAR(20) DEFAULT '未完成',            -- 状态：未完成/已完成
    completed_at    DATETIME,                               -- 完成时间
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
);

CREATE INDEX IF NOT EXISTS idx_otasks_emp ON onboarding_tasks(employee_code);
CREATE INDEX IF NOT EXISTS idx_otasks_status ON onboarding_tasks(status);


-- ============================================================
-- 九、🆕 操作审计日志表（audit_log）— 数据安全第6条
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    operator_code   VARCHAR(20),                               -- 操作人工号（关联 employees）
    action          VARCHAR(50) NOT NULL,                      -- 操作类型：login/logout/query/create/update/delete/approve/export/backup
    target_table    VARCHAR(50),                               -- 操作的目标表名
    target_id       VARCHAR(50),                               -- 操作记录的ID
    detail          TEXT,                                      -- 操作详情（JSON字符串）
    ip_address      VARCHAR(50),                               -- 客户端IP
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_operator ON audit_log(operator_code);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_log(created_at);
