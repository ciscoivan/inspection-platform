# 网络自动化巡检平台 (Network Inspection Platform)

基于 Python FastAPI 的网络设备自动化巡检运维平台，支持 9 大厂商设备 SSH 信息采集、配置备份、批量 Ping/Traceroute、配置对比、配置推送、定时巡检调度、告警规则、自定义命令执行等运维功能。跨平台支持 Linux / Windows。

## 目录

- [架构概览](#架构概览)
- [平台功能矩阵](#平台功能矩阵)
- [功能模块](#功能模块)
- [目录结构](#目录结构)
- [环境要求](#环境要求)
- [快速启动](#快速启动)
- [Windows 部署](#windows-部署)
- [默认账号](#默认账号)
- [API 端点](#api-端点)
- [配置说明](#配置说明)
- [安全说明](#安全说明)

---

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    浏览器 (Browser)                      │
├─────────────────────────────────────────────────────────┤
│              FastAPI + Jinja2 (Web 前后端一体)             │
├──────────┬──────────┬──────────┬──────────┬─────────────┬─────────────┬─────────────┐
│  auth    │ devices  │ inspect  │  ping    │config_compare│config_push │ scheduler  │
│  认证模块  │ 设备管理  │ 巡检引擎  │ 网络诊断  │  配置对比     │  配置推送   │ 定时巡检   │
├──────────┼──────────┼──────────┼──────────┼─────────────┼─────────────┼─────────────┤
│  alerts  │ reports  │ subnet   │custom_cmd│  crypto      │            │            │
│  告警规则  │ 报告导出  │ 子网计算  │ 自定义命令 │  密码加密     │            │            │
├──────────┴──────────┴──────────┴──────────┴─────────────┴─────────────┴─────────────┤
│              SQLAlchemy ORM + SQLite                     │
├─────────────────────────────────────────────────────────┤
│         netmiko SSH → 网络设备 (9 厂商)                    │
└─────────────────────────────────────────────────────────┘
```

- **Web 框架**: FastAPI 0.136 + Jinja2 模板 (服务端渲染)
- **ORM**: SQLAlchemy 2.0 + SQLite
- **SSH 引擎**: Netmiko 4.7 (连接重试 2 次、超时 30s)
- **定时任务**: APScheduler 3.11 (每日 06:00 全量巡检)
- **密码加密**: cryptography (Fernet AES-128-CBC + HMAC)

---

## 平台功能矩阵

### 巡检采集能力一览

| 巡检类别 | Cisco IOS | Cisco XR | Cisco NX-OS | Juniper | Huawei | H3C | Fortinet | Arista | Ruijie |
|----------|:---------:|:--------:|:-----------:|:-------:|:------:|:---:|:--------:|:------:|:------:|
| **基本信息** |
| 版本/型号 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 硬件清单/序列号 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | — |
| 运行配置 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 设备序列号(ESN) | — | — | — | — | ✅ | — | — | — | — |
| **性能状态** |
| CPU 使用率 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 内存使用率 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 环境状态(电源/风扇/温度) | ✅ | ✅ | — | — | ✅ | ✅ | — | — | — |
| **接口状态** |
| IP 接口汇总 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 接口详情(错误/丢包) | ✅ | ✅ | ✅ | — | ✅ | ✅ | — | ✅ | ✅ |
| 接口描述 | ✅ | ✅ | ✅ | ✅ | — | — | — | ✅ | ✅ |
| HA 高可用状态 | — | — | — | — | — | — | ✅ | — | — |
| **光模块信息** |
| 光模块诊断(光功率/温度/电压) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **邻居信息** |
| CDP 邻居 | ✅ | — | ✅ | — | — | — | — | — | — |
| LLDP 邻居 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **日志与路由** |
| 系统日志 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ |
| 路由表摘要 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 会话统计 | — | — | — | — | — | — | ✅ | — | — |
| **配置自动备份** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

### 各平台执行的具体命令

#### Cisco IOS / IOS-XE (`cisco_ios`)

| 巡检类别 | 执行命令 | 采集指标 |
|----------|---------|---------|
| 基本信息 | `show version` | 版本、型号、运行时间 |
| | `show inventory` | 硬件序列号 |
| | `show running-config` | 运行配置 (自动备份) |
| 性能状态 | `show processes cpu sorted` | CPU 使用率 (5s 均值) |
| | `show processes memory sorted` | 内存使用率 (Processor Pool) |
| | `show environment` | 电源、风扇、温度状态 |
| 接口状态 | `show ip interface brief` | IP 接口汇总表 |
| | `show interfaces` | 接口详情 (错误/丢包计数) |
| | `show interfaces description` | 接口描述 |
| 光模块 | `show interfaces transceiver` | 光功率、温度、电压 |
| 邻居 | `show cdp neighbors detail` | CDP 邻居详情 |
| | `show lldp neighbors detail` | LLDP 邻居详情 |
| 日志路由 | `show logging` | 系统日志缓冲区 |
| | `show ip route summary` | 路由表摘要 |

#### Cisco IOS-XR (`cisco_xr`)

| 巡检类别 | 执行命令 | 采集指标 |
|----------|---------|---------|
| 基本信息 | `show version` | 版本、型号、运行时间 |
| | `show inventory` | 硬件序列号 |
| | `show running-config` | 运行配置 (自动备份) |
| 性能状态 | `show processes cpu` | CPU 使用率 (5s 均值) |
| | `show memory summary` | 物理内存使用率 |
| | `show environment all` | 电源、风扇、温度 |
| 接口状态 | `show ip interface brief` | IP 接口汇总 |
| | `show interfaces` | 接口详情 (错误/丢包) |
| | `show interfaces description` | 接口描述 |
| 光模块 | `show controllers optics all` | 光功率 (Port/Tx/Rx) |
| 邻居 | `show lldp neighbors` | LLDP 邻居 |
| 日志路由 | `show logging` | 系统日志 |
| | `show route summary` | 路由表摘要 |

#### Cisco NX-OS / Nexus (`cisco_nxos`)

| 巡检类别 | 执行命令 | 采集指标 |
|----------|---------|---------|
| 基本信息 | `show version` | 版本、型号、运行时间 |
| | `show inventory` | 硬件序列号 |
| | `show running-config` | 运行配置 (自动备份) |
| 性能状态 | `show system resources` | CPU + 内存 (单命令, 100%-idle) |
| 接口状态 | `show ip interface brief` | IP 接口汇总 |
| | `show interface` | 接口详情 (错误/丢包) |
| | `show interface description` | 接口描述 |
| 光模块 | `show interface transceiver details` | 光模块诊断 |
| 邻居 | `show cdp neighbors` | CDP 邻居 |
| | `show lldp neighbors` | LLDP 邻居 |
| 日志路由 | `show logging last 200` | 最近 200 条日志 |
| | `show ip route summary` | 路由表摘要 |

#### Juniper JunOS (`juniper`)

| 巡检类别 | 执行命令 | 采集指标 |
|----------|---------|---------|
| 基本信息 | `show version` | 版本、型号 (含 Hostname) |
| | `show system uptime` | 系统启动时间 |
| | `show chassis hardware` | 硬件清单/序列号 |
| | `show configuration \| display set` | 运行配置 (set 格式备份) |
| 性能状态 | `show chassis routing-engine` | CPU (100%-idle) + 内存 (单命令) |
| 接口状态 | `show interfaces terse` | IP 接口汇总 |
| | `show interfaces description` | 接口描述 |
| 光模块 | `show interfaces diagnostics optics` | 光模块诊断 |
| 邻居 | `show lldp neighbors` | LLDP 邻居 |
| 日志路由 | `show log messages \| last 200` | 最近 200 条日志 |
| | `show route summary` | 路由表摘要 |

#### Huawei VRP (`huawei`)

| 巡检类别 | 执行命令 | 采集指标 |
|----------|---------|---------|
| 基本信息 | `display version` | 版本、型号、运行时间 |
| | `display device` | 硬件清单 (板卡信息) |
| | `display esn` | 设备序列号 |
| | `display current-configuration` | 运行配置 (自动备份) |
| 性能状态 | `display cpu-usage` | CPU 使用率 |
| | `display memory-usage` | 内存使用率 |
| | `display health` | 电源、风扇、温度 |
| 接口状态 | `display ip interface brief` | IP 接口汇总 |
| | `display interface brief` | 接口简要状态 |
| | `display interface` | 接口详情 (错误/丢包) |
| 光模块 | `display transceiver verbose` | 光模块诊断 (光功率/温度/电压) |
| 邻居 | `display lldp neighbor brief` | LLDP 邻居 |
| 日志路由 | `display logbuffer` | 系统日志缓冲区 |
| | `display ip routing-table statistics` | 路由表统计 |

#### H3C Comware (`hp_comware`)

| 巡检类别 | 执行命令 | 采集指标 |
|----------|---------|---------|
| 基本信息 | `display version` | 版本、型号、运行时间 |
| | `display device manuinfo` | 硬件清单/序列号 |
| | `display current-configuration` | 运行配置 (自动备份) |
| 性能状态 | `display cpu-usage` | CPU 使用率 |
| | `display memory-usage` | 内存使用率 |
| | `display environment` | 电源、风扇、温度 |
| 接口状态 | `display ip interface brief` | IP 接口汇总 |
| | `display interface brief` | 接口简要状态 |
| | `display interface` | 接口详情 (错误/丢包) |
| 光模块 | `display transceiver verbose` | 光模块诊断 |
| 邻居 | `display lldp neighbor brief` | LLDP 邻居 |
| 日志路由 | `display logbuffer` | 系统日志缓冲区 |
| | `display ip routing-table statistics` | 路由表统计 |

#### Fortinet FortiOS (`fortinet`)

| 巡检类别 | 执行命令 | 采集指标 |
|----------|---------|---------|
| 基本信息 | `get system status` | 版本、型号、序列号、运行时间 |
| | `show full-configuration` | 完整配置 (自动备份) |
| 性能状态 | `get system performance status` | CPU + 内存 (单命令, 100%-idle) |
| 接口状态 | `get system interface physical` | 物理接口汇总 |
| | `get system ha status` | HA 高可用状态 |
| 光模块 | `get system interface transceiver` | 光模块诊断 |
| 邻居 | `get system lldp neighbors` | LLDP 邻居 |
| 日志路由 | `get router info routing-table all` | 路由表 |
| | `get system session status` | 会话统计 |

#### Arista EOS (`arista_eos`)

| 巡检类别 | 执行命令 | 采集指标 |
|----------|---------|---------|
| 基本信息 | `show version` | 版本、型号、运行时间 |
| | `show inventory` | 硬件序列号 |
| | `show running-config` | 运行配置 (自动备份) |
| 性能状态 | `show system resources` | CPU + 内存 (单命令) |
| 接口状态 | `show ip interface brief` | IP 接口汇总 |
| | `show interfaces` | 接口详情 (错误/丢包) |
| | `show interfaces description` | 接口描述 |
| 光模块 | `show interfaces transceiver` | 光模块诊断 |
| 邻居 | `show lldp neighbors` | LLDP 邻居 |
| 日志路由 | `show logging last 200` | 最近 200 条日志 |
| | `show ip route summary` | 路由表摘要 |

#### Ruijie RGOS (`ruijie_os`)

| 巡检类别 | 执行命令 | 采集指标 |
|----------|---------|---------|
| 基本信息 | `show version` | 版本、型号、运行时间 |
| | `show running-config` | 运行配置 (自动备份) |
| 性能状态 | `show cpu-usage` | CPU 使用率 |
| | `show memory-usage` | 内存使用率 |
| 接口状态 | `show ip interface brief` | IP 接口汇总 |
| | `show interfaces` | 接口详情 (错误/丢包) |
| | `show interfaces description` | 接口描述 |
| 光模块 | `show interfaces transceiver` | 光模块诊断 |
| 邻居 | `show lldp neighbors` | LLDP 邻居 |
| 日志路由 | `show logging` | 系统日志 |
| | `show ip route summary` | 路由表摘要 |

### CPU/内存解析策略

| 平台 | CPU 解析方式 | 内存解析方式 |
|------|-------------|-------------|
| Cisco IOS | 正则提取 `five seconds: N%` | Processor Pool Used/Total 比值 |
| Cisco XR | 正则提取 `five seconds: N%` | Physical Memory used/total 比值 |
| Cisco NX-OS | `100% - idle%` (从 `show system resources`) | Memory usage used/total 比值 |
| Juniper | `100% - idle%` (从 `show chassis routing-engine`) | Memory utilization 百分比直接提取 |
| Huawei | 正则提取 `CPU Usage: N%` | Memory using percentage 百分比提取 |
| H3C | 正则提取 `CPU Usage: N%` | Memory using percentage 百分比提取 |
| Fortinet | `100% - idle%` (从 `get system performance status`) | used(N%) 正则直接提取 |
| Arista | 正则提取 `CPU utilization: N%` | Memory utilization 百分比提取 |
| Ruijie | 正则匹配 `N% busy` / `CPU usage N%` | Memory usage/utilization 百分比提取 |

---

## 功能模块

### 1. 认证模块 (`routers/auth.py`)
- **用户**: 管理员 (admin)
- 基于 Cookie 的会话管理 (httponly, 7 天有效期)
- PBKDF2-SHA256 密码哈希 (600,000 迭代)
- 管理员可创建/删除普通用户
- 所有 API 端点强制认证

### 2. 设备管理 (`routers/devices.py`)
- **用户**: 管理员
- 设备增删改查 (Web 界面 + REST API)
- 支持字段: IP、设备类型、SSH 用户名/密码、端口
- 设备密码自动加密存储 (Fernet)

### 3. 巡检引擎 (`routers/inspect.py` + `engine/inspector.py` + `../inspection.py`)
- **用户**: 管理员
- 通过 Netmiko SSH 连接设备采集 6 大类巡检指标 (见 [平台功能矩阵](#平台功能矩阵))
- 运行配置自动备份到 `configs/` 目录
- 支持单设备巡检和批量巡检 (最大 10 并发, 单设备超时 300s)
- 进度面板实时显示每台设备状态 (CPU/内存/在线状态)
- 自定义命令嵌入巡检流程
- 设备状态标记 (connected / error / timeout / auth_failed / unknown)
- 定时巡检: 支持灵活调度 (一次性/每小时/每天/每月) 或默认每天 06:00
- SSH 连接重试 2 次, 间隔 3 秒

### 4. 网络诊断 (`routers/ping.py`)
- **用户**: 所有登录用户
- 批量 Ping (最大 100 个目标 IP, 50 并发, 超时 1000ms)
- 路由追踪 (Linux: MTR, Windows: Tracert)
- 持续 Ping 测试 (最大 100 次)
- 支持 IP 范围输入:
  - CIDR: `192.168.1.0/24`
  - 范围: `192.168.1.1-192.168.1.50`
  - 逗号/换行分隔: `10.0.0.1, 10.0.0.2`

### 5. 配置对比 (`routers/config_compare.py`)
- **用户**: 所有登录用户
- 粘贴或上传两份配置文件
- Unified Diff 行级对比
- HTML 并排可视化对比 (带行号高亮, 上下文 3 行)

### 6. 告警规则 (`routers/alerts.py`)
- **用户**: 管理员
- 基于 CPU/内存阈值创建告警规则
- 支持全局规则 (`device_id=NULL`) 和按设备规则
- 支持 `>` 和 `>=` 运算符
- 巡检时自动评估, 超标生成告警记录

### 7. 子网计算 (`routers/subnet_calc.py`)
- **用户**: 所有登录用户
- IPv4 子网信息: 网络地址、掩码、广播、可用 IP 范围、通配符掩码、二进制掩码
- IPv4 子网划分: 按新前缀长度拆分 (最多显示 128 个子网)
- IPv4 子网列举: 连续列出同大小子网 (最多 200 个)
- IPv6 子网信息: 压缩/展开地址、链路本地检测、hostmask
- 私有地址检测 (IPv4/IPv6)

### 8. 配置推送 (`routers/config_push.py`)
- **用户**: 管理员
- 向网络设备批量推送配置命令
- 支持粘贴命令文本或上传配置文件 (.txt/.cfg/.conf, 最大 2MB)
- 三步安全流程: 选择设备 → 预览确认 → 执行推送
- 使用 `netmiko.send_config_set()` 自动进入/退出配置模式
- 逐设备串行推送，完成后一次性展示全部结果（成功/失败 + 详细输出）
- 推送结果自动保存到巡检报告 (`InspectionRun`)
- 支持 `#` 注释行过滤

### 9. 自定义命令 (`routers/custom_cmds.py`)
- **用户**: 管理员
- 按设备平台配置自定义命令
- 三种执行模式: 单命令快速执行、单设备批量执行（保存报告）、多设备批量执行（每设备独立报告）
- 支持 `all` 平台通配符 (对所有设备生效)
- 命令可启用/禁用
- 支持的平台标签: `all`, `cisco_ios`, `cisco_xr`, `cisco_nxos`, `juniper`, `huawei`, `hp_comware`, `fortinet`, `arista_eos`, `ruijie_os`

### 10. 定时巡检调度 (`routers/scheduler.py`)
- **用户**: 管理员
- 4 种调度类型: 一次性 (指定日期时间) / 每小时 (间隔 N 小时) / 每天 (指定时间) / 每月 (指定日期+时间)
- 每个定时任务可选指定巡检设备（不选 = 全设备，最多 10 并发）
- 动态 APScheduler 管理: 新增/修改/删除/启停即时生效，无需重启
- 一次性任务执行后自动禁用，过期自动顺延至次日
- 支持「立即执行」按钮 + 实时进度面板（AJAX + 轮询）
- 「立即执行」返回 JSON 驱动进度面板，无需页面跳转
- 无 DB 定时任务时回退到默认每日 06:00

### 11. 报告模块 (`routers/reports.py`)
- **用户**: 所有登录用户
- 巡检历史记录列表 (最近 50 条)
- 单次巡检详情查看 (原始命令输出, JSON 格式)
- CSV 导出 (最近 500 条: ID/时间/IP/主机名/CPU/内存/运行时间/状态)
- HTML 报告导出 (含 CSS 样式的完整页面)

---

## 目录结构

```
/home/ivan/network-inspection/
├── inspection.py                   # 核心巡检引擎 (netmiko SSH 采集 + 解析 + HTML 报告生成)
├── inspection.db                   # SQLite 数据库
├── devices.csv                     # CSV 格式设备清单 (批量导入用)
├── inspection-platform/            # Web 平台
│   ├── .encryption_key             # 密码加密密钥 (600 权限, 首次启动自动生成)
│   └── backend/
│       ├── main.py                 # FastAPI 入口, LoginMiddleware, 定时巡检, Dashboard
│       ├── database.py             # SQLAlchemy 引擎 & Session 工厂
│       ├── models.py               # ORM 模型 (Device/User/InspectionRun/AlertRule/CustomCommand)
│       ├── schemas.py              # Pydantic 请求/响应模型
│       ├── crypto.py               # 密码加密/解密工具 (Fernet AES-128-CBC + HMAC)
│       ├── templating.py           # Jinja2 模板引擎实例
│       ├── engine/
│       │   └── inspector.py        # 巡检引擎封装 (调用 inspection.py)
│       ├── routers/
│       │   ├── auth.py             # 认证路由 (登录/登出/用户管理/Session)
│       │   ├── devices.py          # 设备 CRUD (Web + API)
│       │   ├── inspect.py          # 巡检触发 & 进度追踪
│       │   ├── ping.py             # Ping / Traceroute / MTR
│       │   ├── config_compare.py   # 配置文件对比 (粘贴/上传)
│       │   ├── alerts.py           # 告警规则管理
│       │   ├── subnet_calc.py      # IPv4/IPv6 子网计算 & 划分
│       │   ├── config_push.py     # 配置推送 (命令/文件上传)
│       │   ├── custom_cmds.py      # 自定义命令管理 & 实时执行
│       │   ├── scheduler.py        # 定时巡检调度 (APScheduler 动态管理)
│       │   └── reports.py          # 巡检报告查看 & 导出
│       ├── templates/              # Jinja2 HTML 模板 (15 个页面)
│       │   ├── base.html           # 基础布局 (导航栏)
│       │   ├── login.html          # 登录页
│       │   ├── dashboard.html      # 仪表盘 (设备状态概览)
│       │   ├── devices.html        # 设备管理页
│       │   ├── users.html          # 用户管理页
│       │   ├── alerts.html         # 告警规则配置页
│       │   ├── config_push.html   # 配置推送页 (选择/预览/结果)
│       │   ├── custom_cmds.html    # 自定义命令管理 & 执行页
│       │   ├── scheduler.html      # 定时巡检调度管理页
│       │   ├── ping.html           # 网络诊断页
│       │   ├── subnet.html         # 子网计算页
│       │   ├── config_compare.html # 配置对比页
│       │   ├── compare.html        # 配置对比结果页
│       │   ├── reports.html        # 报告列表页
│       │   ├── report.html         # 单次巡检详情页
│       │   └── adhoc.html          # 即时巡检页
│       └── static/
│           └── app.css             # 全局样式
├── configs/                        # 设备配置备份目录 (*.cfg)
└── reports/                        # HTML 报告输出目录
```

---

## 环境要求

| 依赖 | 版本 | 用途 |
|------|------|------|
| Python | ≥ 3.10 | 运行环境 |
| FastAPI | 0.136 | Web 框架 |
| Uvicorn | 0.49 | ASGI 服务器 |
| SQLAlchemy | 2.0 | ORM |
| Netmiko | 4.7 | SSH 连接 & 命令执行 |
| APScheduler | 3.11 | 定时巡检 |
| cryptography | 41.0 | Fernet 密码加密 |
| Jinja2 | 3.1 | 模板渲染 |
| python-multipart | 0.0.32 | 文件上传解析 |

完整安装命令:

```bash
pip install fastapi uvicorn sqlalchemy netmiko apscheduler cryptography jinja2 python-multipart
```

---

## 快速启动

### 开发模式

```bash
cd /home/ivan/network-inspection/inspection-platform
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

访问 `http://<服务器IP>:8000`

API 文档: `http://<服务器IP>:8000/docs`

### 生产模式 (systemd)

服务文件: `/etc/systemd/system/network-inspect.service`

```ini
[Unit]
Description=Network Inspection Platform
After=network.target

[Service]
Type=simple
User=ivan
Group=ivan
WorkingDirectory=/home/ivan/network-inspection/inspection-platform
ExecStart=/usr/bin/python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
StandardOutput=append:/home/ivan/inspect.log
StandardError=append:/home/ivan/inspect.log

[Install]
WantedBy=multi-user.target
```

管理命令:

```bash
# 启动 / 停止 / 重启
sudo systemctl start network-inspect
sudo systemctl stop network-inspect
sudo systemctl restart network-inspect

# 查看状态
sudo systemctl status network-inspect

# 实时日志
journalctl -u network-inspect -f
tail -f /home/ivan/inspect.log

# 开机自启
sudo systemctl enable network-inspect
```

---

## 默认账号

| 用户名 | 密码 | 角色 |
|--------|------|------|
| `admin` | `123.com` | 管理员 (可管理用户/设备/告警) |

> ⚠️ **首次登录后请立即修改默认密码。**

---

## API 端点

> 所有 `/api` 端点需要认证 (Cookie: `inspect_session`)。  
> 未认证的 API 请求由 LoginMiddleware 拦截并返回 HTTP 303 重定向到登录页。

### 设备管理

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|:----:|
| GET | `/devices` | 设备管理页面 | ✅ |
| GET | `/devices/api` | 设备列表 (JSON) | ✅ |
| POST | `/devices/api` | 创建设备 (JSON) | ✅ |
| POST | `/devices/add` | 创建设备 (表单) | ✅ |
| PUT | `/devices/api/{id}` | 更新设备 | ✅ |
| DELETE | `/devices/api/{id}` | 删除设备 | ✅ |

### 巡检

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|:----:|
| POST | `/inspect` | 触发巡检 (`?device_id=N` 单设备) | ✅ |
| GET | `/inspect/status/{run_id}` | 查询巡检进度 (轮询) | ✅ |

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/login` | 登录页面 |
| POST | `/login` | 登录提交 (Form: username, password, next) |
| GET | `/logout` | 登出 |
| GET | `/users` | 用户管理页面 (管理员) |
| POST | `/users/add` | 添加用户 |
| POST | `/users/delete/{id}` | 删除用户 |

### 网络诊断

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/ping` | Ping 工具页面 |
| POST | `/ping` | 执行 Ping/Traceroute/MTR |

### 配置对比

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/config-compare` | 配置对比页面 |
| POST | `/config-compare` | 提交对比 (粘贴或上传文件) |

### 配置推送

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|:----:|
| GET | `/config-push` | 配置推送页面 | ✅ |
| POST | `/config-push/preview` | 预览推送内容 (选择设备 + 命令预览) | ✅ |
| POST | `/config-push/execute` | 执行推送 (逐设备 send_config_set) | ✅ |

### 告警

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|:----:|
| GET | `/alerts` | 告警规则页面 | ✅ |
| POST | `/alerts/add` | 添加告警规则 | ✅ |
| DELETE | `/alerts/api/{id}` | 删除告警规则 | ✅ |

### 子网计算

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/subnet` | 子网计算页面 |
| POST | `/subnet` | 计算子网 (IPv4/IPv6/子网划分/子网列举) |

### 自定义命令

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|:----:|
| GET | `/custom-commands` | 命令管理页面 | ✅ |
| POST | `/custom-commands/add` | 添加命令 | ✅ |
| POST | `/custom-commands/execute` | 在设备上执行命令 | ✅ |
| POST | `/custom-commands/delete/{id}` | 删除命令 | ✅ |
| POST | `/custom-commands/toggle/{id}` | 启用/禁用命令 | ✅ |

### 定时巡检调度

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|:----:|
| GET | `/scheduler` | 定时任务管理页面 | ✅ |
| POST | `/scheduler/add` | 添加定时任务 | ✅ |
| POST | `/scheduler/run-now/{id}` | 立即执行 (支持 JSON 响应) | ✅ |
| POST | `/scheduler/toggle/{id}` | 启用/禁用定时任务 | ✅ |
| POST | `/scheduler/delete/{id}` | 删除定时任务 | ✅ |

### 报告

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|:----:|
| GET | `/reports` | 报告列表页面 | ✅ |
| GET | `/reports/api` | 报告列表 (JSON) | ✅ |
| GET | `/reports/{run_id}` | 单次巡检详情 | ✅ |
| GET | `/reports/{run_id}/export` | 导出 HTML 报告 | ✅ |
| GET | `/reports/export/csv` | 导出 CSV | ✅ |
| DELETE | `/reports/api/{run_id}` | 删除报告 | ✅ |

### 其他

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 重定向 → `/dashboard` |
| GET | `/dashboard` | 仪表盘 (设备数/在线数/离线数/最新巡检) |
| GET | `/docs` | Swagger API 文档 (无需认证) |
| GET | `/openapi.json` | OpenAPI Schema (无需认证) |

---

## 配置说明

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `INSPECT_SECRET_KEY` | Fernet 加密密钥 (Base64 编码) | 自动生成到 `.encryption_key` 文件 |

### 加密密钥

- 密钥文件: `inspection-platform/.encryption_key`
- 算法: Fernet (AES-128-CBC + HMAC-SHA256)
- 权限: `600` (仅 owner 可读写)
- 首次启动自动生成，后续启动复用
- **请备份此文件** — 丢失后无法解密已存储的设备密码

### 数据库

- 类型: SQLite
- 位置: `/home/ivan/network-inspection/inspection.db`
- 表: `users`, `devices`, `inspection_runs`, `alert_rules`, `custom_commands`
- 表结构首次启动自动创建 (SQLAlchemy `Base.metadata.create_all`)
- 明文密码首次启动自动迁移为加密存储

### 定时巡检

- 默认调度: 每天 06:00
- 配置位置: `backend/main.py` 第 89 行
  ```python
  scheduler.add_job(scheduled_inspection, CronTrigger(hour=6, minute=0), id="daily", name="daily")
  ```

### 巡检并发参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `MAX_WORKERS` | 10 | 巡检最大并发数 |
| `CONN_TIMEOUT` | 30s | SSH 连接超时 |
| `CMD_TIMEOUT` | 60s | 单命令执行超时 |
| `CONN_RETRIES` | 2 | SSH 连接重试次数 |
| `RETRY_DELAY` | 3s | 重试间隔 |

---

## Windows 部署

本项目完全支持 Windows 部署，核心代码使用纯 Python 跨平台库（FastAPI / SQLAlchemy / Netmiko / APScheduler）。

### Windows 特殊适配

| 功能 | Linux | Windows | 处理方式 |
|------|-------|---------|---------|
| Ping | `ping -c 4 -W 1000` | `ping -n 4 -w 1000` | `ping.py` 自动检测 `sys.platform` |
| 路由追踪 | MTR (`mtr --report`) | Tracert (`tracert -d`) | `ping.py` 自动切换命令 |
| 文件权限 | `os.chmod(0o600)` | 不支持 POSIX chmod | `crypto.py` 用 try/except 安全跳过 |
| 进程管理 | systemd (`systemctl`) | NSSM / Windows Service / 直接运行 | 见下方 |

### Windows 启动方式

**方式一: 直接运行 (开发/测试)**

```powershell
cd C:\network-inspection\inspection-platform
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**方式二: NSSM 注册为 Windows 服务 (生产)**

```powershell
# 安装 NSSM
winget install NSSM.NSSM

# 注册服务
nssm install NetworkInspect python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
nssm set NetworkInspect AppDirectory C:\network-inspection\inspection-platform
nssm set NetworkInspect AppStdout C:\network-inspection\inspect.log
nssm set NetworkInspect AppStderr C:\network-inspection\inspect.log
nssm start NetworkInspect
```

**方式三: 任务计划程序 (Task Scheduler)**

创建"系统启动时"触发的任务，执行:
```
程序: python
参数: -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
起始目录: C:\network-inspection\inspection-platform
```

### 路径调整

从 Linux 迁移到 Windows 时只需修改:

```python
# database.py — 将相对路径改为绝对路径
DATABASE_URL = "sqlite:///C:/network-inspection/inspection.db"
```

其他所有路径使用 `pathlib.Path`，自动适配系统分隔符。

### 依赖安装 (Windows)

```powershell
pip install fastapi uvicorn sqlalchemy netmiko apscheduler cryptography jinja2 python-multipart
```

> ⚠️ Netmiko 在 Windows 上需要安装 PyCryptodome: `pip install pycryptodome`

---

## 安全说明

- ✅ 设备密码使用 Fernet (AES-128-CBC + HMAC) 加密存储
- ✅ 用户密码使用 PBKDF2-SHA256 (600,000 迭代) 哈希
- ✅ Session Cookie 设置 `httponly` 标志 (防 XSS 窃取)
- ✅ 所有 API 端点强制认证 (`require_auth` 依赖注入)
- ✅ 加密密钥文件权限 600
- ✅ 旧格式 SHA256 密码自动兼容 (登录时检测)
- ⚠️ 生产环境建议:
  - 修改默认 admin 密码
  - 使用环境变量 `INSPECT_SECRET_KEY` 替代密钥文件
  - 配置 HTTPS 反向代理 (Nginx/Caddy)
  - 定期备份 `inspection.db` 和 `.encryption_key`
  - 为设备账号使用只读权限 (最小权限原则)
