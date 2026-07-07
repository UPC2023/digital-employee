-- ============================================
-- HR Agent 数据库建表脚本
-- 数据库：SQLite
-- 包含：5张核心表 + 索引
-- ============================================

-- 员工信息表
CREATE TABLE IF NOT EXISTS employees (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_code   VARCHAR(20)  UNIQUE NOT NULL,       -- 工号，如 EMP001
    name            VARCHAR(50)  NOT NULL,               -- 姓名
    gender          VARCHAR(4)   DEFAULT '男',           -- 性别：男/女
    phone           VARCHAR(20),                         -- 手机号
    email           VARCHAR(100),                        -- 邮箱
    department      VARCHAR(100) NOT NULL,               -- 部门：技术部/市场部/财务部/人事部/运营部
    position        VARCHAR(100) NOT NULL,               -- 职位
    hire_date       DATE         NOT NULL,               -- 入职日期
    status          VARCHAR(20)  DEFAULT '在职',          -- 在职状态：在职/离职/试用期
    id_card         VARCHAR(18),                         -- 身份证号（用于个税）
    education       VARCHAR(50),                         -- 最高学历
    school          VARCHAR(100),                        -- 毕业院校
    major           VARCHAR(100),                        -- 专业
    address         TEXT,                                -- 住址
    emergency_contact VARCHAR(50),                       -- 紧急联系人
    emergency_phone   VARCHAR(20),                       -- 紧急联系电话
    created_at      DATETIME     DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_employees_code ON employees(employee_code);
CREATE INDEX IF NOT EXISTS idx_employees_dept ON employees(department);
CREATE INDEX IF NOT EXISTS idx_employees_status ON employees(status);

-- 考勤表
CREATE TABLE IF NOT EXISTS attendance (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_code   VARCHAR(20)  NOT NULL,               -- 工号
    date            DATE         NOT NULL,               -- 日期
    clock_in        DATETIME,                            -- 上班打卡时间
    clock_out       DATETIME,                            -- 下班打卡时间
    status          VARCHAR(20)  DEFAULT '正常',          -- 考勤状态：正常/迟到/早退/缺勤/请假
    overtime_hours  DECIMAL(4,1) DEFAULT 0,              -- 加班小时数
    remark          TEXT,                                -- 备注
    FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
);

CREATE INDEX IF NOT EXISTS idx_attendance_code ON attendance(employee_code);
CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date);

-- 请假表
CREATE TABLE IF NOT EXISTS leave_requests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_code   VARCHAR(20)  NOT NULL,               -- 工号
    leave_type      VARCHAR(30)  NOT NULL,               -- 请假类型：年假/事假/病假/婚假/产假/调休
    start_date      DATE         NOT NULL,               -- 开始日期
    end_date        DATE         NOT NULL,               -- 结束日期
    total_days      DECIMAL(3,1) NOT NULL,               -- 请假天数
    reason          TEXT,                                -- 请假原因
    status          VARCHAR(20)  DEFAULT '待审批',        -- 审批状态：待审批/已批准/已驳回
    approver        VARCHAR(50),                         -- 审批人
    approved_at     DATETIME,                            -- 审批时间
    created_at      DATETIME     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
);

CREATE INDEX IF NOT EXISTS idx_leave_code ON leave_requests(employee_code);
CREATE INDEX IF NOT EXISTS idx_leave_status ON leave_requests(status);

-- 薪酬表
CREATE TABLE IF NOT EXISTS payroll (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_code    VARCHAR(20)  NOT NULL,              -- 工号
    year             INTEGER      NOT NULL,              -- 年份
    month            INTEGER      NOT NULL,              -- 月份
    base_salary      DECIMAL(10,2) NOT NULL,             -- 基本工资
    performance      DECIMAL(10,2) DEFAULT 0,            -- 绩效工资
    subsidies        DECIMAL(10,2) DEFAULT 0,            -- 补贴（餐补+交通+通讯）
    overtime_pay     DECIMAL(10,2) DEFAULT 0,            -- 加班费
    gross_pay        DECIMAL(10,2) NOT NULL,             -- 应发合计
    social_insurance DECIMAL(10,2) DEFAULT 0,            -- 社保扣款
    housing_fund     DECIMAL(10,2) DEFAULT 0,            -- 公积金扣款
    tax              DECIMAL(10,2) DEFAULT 0,            -- 个人所得税
    other_deduction  DECIMAL(10,2) DEFAULT 0,            -- 其他扣款
    net_pay          DECIMAL(10,2) NOT NULL,             -- 实发工资
    pay_date         DATE,                               -- 发放日期
    FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
);

CREATE INDEX IF NOT EXISTS idx_payroll_code ON payroll(employee_code);
CREATE INDEX IF NOT EXISTS idx_payroll_ym ON payroll(year, month);

-- 招聘表
CREATE TABLE IF NOT EXISTS recruitment (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    position_name   VARCHAR(100) NOT NULL,               -- 招聘岗位
    department      VARCHAR(100) NOT NULL,               -- 所属部门
    candidate_name  VARCHAR(50),                         -- 候选人姓名
    candidate_phone VARCHAR(20),                         -- 候选人电话
    candidate_email VARCHAR(100),                        -- 候选人邮箱
    education       VARCHAR(50),                         -- 学历
    school          VARCHAR(100),                        -- 毕业院校
    years_of_exp    INTEGER,                             -- 工作年限
    skills          TEXT,                                -- 技能标签（逗号分隔）
    resume_path     VARCHAR(500),                        -- 简历文件路径
    resume_parsed   TEXT,                                -- 解析后的JSON文本
    status          VARCHAR(30)  DEFAULT '简历筛选',      -- 招聘状态
    interview_date  DATETIME,                            -- 面试时间
    interviewer     VARCHAR(50),                         -- 面试官
    remark          TEXT,                                -- 备注
    created_at      DATETIME     DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_recruitment_status ON recruitment(status);
CREATE INDEX IF NOT EXISTS idx_recruitment_dept ON recruitment(department);
