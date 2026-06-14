<img width="200" height="200" alt="ivan-logo-mini" src="https://github.com/user-attachments/assets/8514f584-9f3f-49ca-8920-9c84cdcb4ac0" />

# 网络自动化巡检平台 (Network Inspection Platform)

基于 Python FastAPI 的网络设备与服务器自动化巡检运维平台，支持 9 大网络厂商 + 5 大服务器 BMC 平台的 SSH 信息采集、配置备份、批量 Ping/Traceroute、配置对比、配置推送、定时巡检调度、告警系统（升级/静默/确认/历史）、自定义命令执行、报告导出（PDF/Word/CSV/HTML）等运维功能。跨平台支持 Linux / Windows。支持中英文界面切换。

## 目录

- [架构概览](#架构概览)
- [平台功能矩阵](#平台功能矩阵)
- [功能模块](#功能模块)
- [目录结构](#目录结构)
- [环境要求](#环境要求)
- [快速启动](#快速启动)
- [Docker 部署](#docker-部署)
- [Windows 部署](#windows-部署)
- [默认账号](#默认账号)
- [API 端点](#api-端点)
- [配置说明](#配置说明)
  - [数据库](#数据库)
  - [配置备份去重](#配置备份去重)
- [性能优化](#性能优化)
- [路由表验证与自动回退](#路由表验证与自动回退)
- [语言切换](#语言切换)
- [安全说明](#安全说明)
- [优化记录](#优化记录-2026-06)

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
│  alerts  │ reports  │ subnet   │custom_cmd│  crypto      │  topology  │  helpers   │
│  告警系统  │ 报告导出  │ 子网计算  │ 自定义命令 │  密码加密     │  网络拓扑   │  共享工具   │
├──────────┼──────────┼──────────┼──────────┼─────────────┼─────────────┼─────────────┤
│ constants │          │          │          │             │            │            │
│  共享常量  │          │          │          │             │            │            │
├──────────┴──────────┴──────────┴──────────┴─────────────┴─────────────┴─────────────┤
│              SQLAlchemy ORM + SQLite                     │
├─────────────────────────────────────────────────────────┤
│         netmiko SSH → 网络设备 (9 厂商)                    │
└─────────────────────────────────────────────────────────┘
```

- **Web 框架**: FastAPI 0.136 + Jinja2 模板 (服务端渲染) + BackgroundTasks (异步任务)
- **ORM**: SQLAlchemy 2.0 + SQLite WAL \u6a21\u5f0f (Write-Ahead Logging, \u8bfb\u5199\u5e76\u53d1\u6027\u80fd\u63d0\u5347 3-5x)
- **连接池**: pool_pre_ping + pool_recycle (3600s) + pool_size=5 + max_overflow=10
- **SSH 引擎**: Netmiko 4.7 (连接重试 2 次、超时 30s, 180+ 设备类型注册表分发)
- **定时任务**: APScheduler 3.11 + BackgroundScheduler (定时巡检 + 数据自动清理)
- **密码加密**: cryptography (Fernet AES-128-CBC + HMAC, 三级密钥查找: 环境变量 2192 /etc/inspection/ 2192 自动生成)
- **日志系统**: 结构化 logging + 敏感字段脱敏过滤器 (password/secret/token/key)
- **配置备份**: SHA256 去重 (内容不变跳过写入) + 自动轮转 (每设备保留最新 5 版)

---



---

## 技术方案对比（行业调研）

> 基于 2026-06 深度研究：5 角度搜索 -> 23 来源 -> 81 声明 -> 对抗性验证(3票制) -> 4 项高置信结论

### 开源 vs 自研 vs 商业 总览

| 维度 | 本平台 (自研) | LibreNMS + Oxidized | Netshot | SolarWinds NPM |
|------|:---:|:---:|:---:|:---:|
| **架构** | FastAPI + Netmiko | PHP + SNMP Poller | Java + React 19 | Windows + .NET |
| **部署** | 单文件 / pip | LAMP 栈 | Docker Compose / K8s | Windows Server + SQL Server |
| **SSH 巡检** | 14 厂商 | 需配合 Oxidized | 7 厂商 Java 驱动 | 支持 |
| **SNMP 监控** | 不支持 | LibreNMS | 不支持 | 支持 |
| **配置备份** | SHA256 去重 + 轮转 | Git (Oxidized) | SHA256 + PostgreSQL | 支持 |
| **合规检查** | 计划中 | 不支持 | 软/硬/配置三级 | 支持 |
| **告警系统** | 升级/静默/确认 | LibreNMS | 不支持 | 支持 |
| **拓扑发现** | CDP/LLDP | LibreNMS | 不支持 | 支持 |
| **gNMI 遥测** | 不支持 | 不支持 | 不支持 | 不支持 |
| **许可证** | 免费 | 免费 | 免费 | 元素授权付费 |
| **厂商覆盖** | 14 平台 | 130+ OS (Oxidized) | 约7厂商 | 广泛 |

### 行业架构共识

1. **Agentless + Pull 是主导模式**: LibreNMS、Prometheus SNMP Exporter、Nagios Core 均采用无代理轮询；差异在告警/可视化是委托(Grafana/Alertmanager)还是内置
2. **Oxidized (130+ OS) 大幅领先 RANCID (约35, Cisco中心)**: 华为/H3C/Fortinet/Palo Alto 仅 Oxidized 原生支持，RANCID 已进入维护模式
3. **Netshot 是功能集成度最高的开源配置管理平台**: 6合1(备份+资产+软件合规+硬件合规+配置合规+变更自动化)，React 19 + TypeScript 前端开发极活跃(2026-05/06 每日提交)，但新前端尚未包含在发布版中(pom.xml 注释: Exclude new WebUI files until release)
4. **商业工具存在架构天花板**: rConfig V8 仅支持 5 种传统连接方式(无 NETCONF/RESTCONF/gNMI)；SolarWinds 超 12000 元素需额外 Polling Engine + SQL Server Enterprise

### 本平台差异化定位

| 能力 | 开源工具局限 | 本平台优势 |
|------|:--:|:--:|
| CLI 深度信息采集 | SNMP 只能拿 OID，无法获取硬件序列号/光模块诊断 | SSH 执行任意命令 + 专用解析器 |
| 多 BMC 统一管理 | 无工具同时覆盖 Dell/HP/Lenovo/Huawei/Inspur | 5 平台统一 Command Map |
| 路由表日志污染检测 | 无自动检测 | validate_routing_output() + 自动回退 |
| 中英文双语 | 多数工具仅英文 | i18n Cookie 持久化 |

### Netshot 前端进展（追踪至 2026-06-06）

| 日期 | 动态 |
|------|------|
| 2026-06-06 | fix(web): 调整 padding/margin; feat(web): 前端改进 |
| 2026-05-31 | feat(web): 重写查询构建器; refactor(web): 重命名页面 |
| 2026-05-29/30 | 合规视图增强、树形显示改进、诊断视图增强 |
| 2026-05-23 | feat(web): 合规规则建议功能(新核心功能) |
| 2026-02-16 | v0.24.0 发布(新前端 webui/** 被 pom.xml 排除) |

> **结论**: Netshot 新前端(React 19 + Chakra UI v3 + TanStack + Vite)开发极活跃但尚未发布，预计 2026 Q4 可能进入 RC。本平台继续独立发展，可参考其技术栈。

---


---

## 技术方案对比（行业调研）

> 基于 2026-06 深度研究：5 角度搜索 → 23 来源 → 81 声明 → 对抗性验证（3 票制）→ 4 项高置信结论

### 开源 vs 自研 vs 商业 总览

| 维度 | 本平台 (自研) | LibreNMS + Oxidized | Netshot | SolarWinds NPM |
|------|:---:|:---:|:---:|:---:|
| **架构** | FastAPI + Netmiko | PHP + SNMP Poller | Java + React 19 | Windows + .NET |
| **部署** | 单文件 / pip | LAMP 栈 | Docker Compose / K8s | Windows Server + SQL Server |
| **SSH 巡检** | ✅ 14 厂商 | ❌ (需 Oxidized) | ✅ 7 厂商 Java 驱动 | ✅ |
| **SNMP 监控** | ❌ | ✅ (LibreNMS) | ❌ | ✅ |
| **配置备份** | SHA256 去重 + 轮转 | Git (Oxidized) | SHA256 + PostgreSQL | ✅ |
| **合规检查** | ❌ (计划中) | ❌ | ✅ 软件/硬件/配置三级 | ✅ |
| **告警系统** | ✅ 升级/静默/确认 | ✅ (LibreNMS) | ❌ | ✅ |
| **拓扑发现** | ✅ CDP/LLDP | ✅ (LibreNMS) | ❌ | ✅ |
| **gNMI/流式遥测** | ❌ | ❌ | ❌ | ❌ |
| **许可证费用** | 免费 | 免费 | 免费 | 117$ (元素授权) |
| **厂商覆盖** | 14 平台 | 130+ OS (Oxidized) | ~7 厂商 | 广泛 |
| **社区活跃度** | 自维护 | ⭐⭐⭐⭐⭐ (Oxidized 活跃) | ⭐⭐⭐ (快速迭代中) | ⭐⭐⭐⭐ |

### 行业架构共识

1. **Agentless + Pull 是主导模式**：LibreNMS、Prometheus SNMP Exporter、Nagios Core 均采用无代理轮询架构，差异仅在处理链路（告警/可视化委托 vs 内置）
2. **Oxidized (130+ OS) 大幅领先 RANCID (~35，Cisco 中心)**：华为/H3C/Fortinet/Palo Alto 仅 Oxidized 原生支持，RANCID 已进入维护模式
3. **Netshot 是功能集成度最高的开源配置管理平台**：6 合 1（备份+资产+软件合规+硬件合规+配置合规+变更自动化），React 19 + TypeScript 前端开发极活跃（2026-05/06 每日提交），但新前端尚未包含在发布版本中
4. **商业工具存在架构天花板**：rConfig V8 仅支持 5 种传统连接方式（无 NETCONF/RESTCONF/gNMI），SolarWinds 超 12000 元素需额外 Polling Engine + SQL Server Enterprise

### 本平台差异化定位

| 能力 | 开源工具做不到 | 本平台做到 |
|------|:--:|:--:|
| CLI 深度信息采集 | SNMP 只能拿 OID，无法获取硬件序列号/光模块诊断 | SSH 执行任意命令解析 |
| 多 BMC 统一管理 | 无工具同时覆盖 Dell/HP/Lenovo/Huawei/Inspur | 5 平台统一 Command Map |
| 路由表日志污染检测 | 无自动检测机制 | + 自动回退 |
| 中英文双语 | 多数工具仅英文 | i18n Cookie 持久化 |

### 对标 Netshot 前端进展（追踪）

| 日期 | 动态 |
|------|------|
| 2026-06-06 | |
| 2026-05-31 | |
| 2026-05-29/30 | 合规视图增强、树形显示改进、诊断视图增强 |
| 2026-05-23 | — 新核心功能 |
| 2026-02-16 | v0.24.0 发布（新前端 被 排除：Exclude new WebUI files until release） |

> **结论**：Netshot 新前端（React 19 + Chakra UI v3 + TanStack + Vite）开发极活跃但尚未可发布，预计 2026 Q4 可能进入 RC。本平台继续独立发展，可参考其技术栈选型。

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
| **路由回退** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
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
| | `show chassis environment` | 电源、风扇、温度 |
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
| | `show interface status` | 接口状态汇总 |
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
| | \ | 电源、风扇、温度 |
| 接口状态 | `show interfaces terse` | IP 接口汇总 |
| | `show interfaces description` | 接口描述 |
| | `show interfaces detail` | 接口详情 (错误/丢包) |
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
| 日志路由 | `execute log display` | 系统日志 (最近) |
| | `get router info routing-table all` | 路由表 |
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
| | `show version | include System` | 设备型号/启动时间 |
| | `show running-config` | 运行配置 (自动备份) |
| 性能状态 | `show cpu-usage` | CPU 使用率 (支持 5 种输出格式) |
| | `show memory-usage` | 内存使用率 (支持 4 种输出格式) |
| 接口状态 | `show ip interface brief` | IP 接口汇总 |
| | `show interfaces` | 接口详情 (错误/丢包) |
| | `show interfaces description` | 接口描述 |
| 光模块 | `show interfaces transceiver` | 光模块诊断 |
| 邻居 | `show lldp neighbors` | LLDP 邻居 |
| 日志路由 | `show logging` | 系统日志 |
| | `show ip route summary` | 路由表摘要 (异常时自动回退 `show ip route`) |

### CPU/内存解析策略

| 平台 | CPU 解析方式 | 内存解析方式 |
|------|-------------|-------------|
| Cisco IOS | `five seconds` / `one minute` / 通用 CPU utilization 回退 | Processor Pool Used/Total 比值 |
| Cisco XR | 正则提取 `five seconds: N%` | Physical Memory used/total 比值 |
| Cisco NX-OS | `100% - idle%` (从 `show system resources`) | Memory usage used/total 比值 |
| Juniper | `100% - idle%` / User percent / 通用回退 | Memory utilization 百分比直接提取 |
| Huawei | 正则提取 `CPU Usage: N%` | Memory using percentage 百分比提取 |
| H3C | 正则提取 `CPU Usage: N%` | Memory using percentage 百分比提取 |
| Fortinet | `100% - idle%` (从 `get system performance status`) | used(N%) 正则直接提取 |
| Arista | 正则提取 `CPU utilization: N%` | Memory utilization 百分比提取 |
| Ruijie | 5 层回退匹配 (RGOS/Cisco/通用格式) | 4 层回退匹配 (RGOS/通用格式) |

### 服务器 BMC 平台 (5 种)

| 平台标识 | 厂商 | 连接 | 命令工具 |
|------|------|:--:|------|
| `dell_idrac` | Dell 服务器 | SSH :22 | `racadm` CLI |
| `hp_ilo` | HP 服务器 | SSH :22 | iLO `show /system1/...` CLI |
| `lenovo_xcc` | Lenovo 服务器 | SSH :22 | `syshealth` / `sysinfo` CLI |
| `huawei_ibmc` | Huawei 服务器 | SSH :22 | `ipmcget -d ...` CLI |
| `inspur_bmc` | Inspur 浪潮 | SSH :22 | `fru` / `sdr` / `sel` CLI |

#### 服务器统一采集能力

| 采集类别 | 采集指标 | Dell | HP | Lenovo | Huawei | Inspur |
|---------|---------|:--:|:--:|:--:|:--:|:--:|
| 基本信息 | 型号 / 序列号 / 固件 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 处理器 | CPU 型号 / 频率 / 健康 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 内存 | 容量 / 类型 / 频率 / 健康 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 传感器 | 风扇转速 / 温度 / 电压 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 电源 | 功率 / 健康 / 冗余 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 网络 | MAC / 链路状态 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 存储 | RAID 控制器 / 物理硬盘 / 逻辑驱动器 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 硬件日志 | 系统事件日志 (SEL) | ✅ | ✅ | ✅ | ✅ | ✅ |
| PCIe/显卡 | GPU/PCIe 设备清单 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 健康总览 | 整体健康状态判定 | ✅ | ✅ | ✅ | ✅ | ✅ |

> 所有服务器 BMC 通过标准 SSH (端口 22) 连接，Netmiko 使用 `generic` 驱动兼容。健康状态自动判定：全部绿灯 → Healthy，有 Warning → Warning，有 Critical/Error → Critical。
> 
> **硬件摘要**：巡检报告"基本信息"顶部自动生成硬件摘要，包含 CPU 型号/数量、内存型号/容量、网卡型号/数量、RAID 控制器型号、硬盘型号/容量、电源型号/状态。Dell iDRAC 使用专用解析器（`racadm hwinventory`），其它平台使用通用解析器（自动匹配 `Model`/`Size`/`Cores` 等关键字段）。

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
- 支持单设备巡检和批量巡检 (最大 100 并发, 单设备超时 300s)
- 进度面板实时显示每台设备状态 (CPU/内存/在线状态)
- 自定义命令嵌入巡检流程
- 设备状态标记 (connected / error / timeout / auth_failed / unknown)
- 定时巡检: 支持灵活调度 (一次性/每小时/每天/每月) 或默认每天 06:00
- 主机名三层回退提取: 常规命令 → 平台专用快速命令 → 设备提示符
- 混合命令执行:  默认（提示符等待），大配置自动切换  长超时
- SSH 连接重试 2 次, 间隔 3 秒

### 4. 网络诊断 (`routers/ping.py`)
- **用户**: 所有登录用户
- 批量 Ping (最大 100 个目标 IP, 50 并发, 可配超时 500-5000ms)
- **设备快速选择**: 下拉菜单从设备列表选 IP 填入目标
- 路由追踪 (Linux: MTR, Windows: Tracert)
- 持续 Ping 测试 (最大 100 次)
- 支持 IP 范围输入:
  - CIDR: `192.168.1.0/24`
  - 范围: `192.168.1.1-192.168.1.50`
  - 逗号/换行分隔: `10.0.0.1, 10.0.0.2`

### 5. 配置对比 (`routers/config_compare.py`)
- **用户**: 所有登录用户
- 粘贴、上传或**从设备加载**两份配置文件
- 设备下拉菜单一键加载最新配置备份
- 一键 Swap 交换 A/B 配置、Clear 清空
- 可调差异上下文行数 (0/1/3/5/8/All)
- Unified Diff 行级对比 + 颜色语法高亮 (+绿/-红/@@蓝)
- HTML 并排可视化对比

### 6. 告警系统 (`routers/alerts.py` + `routers/inspect.py`)
- **用户**: 管理员 (规则管理) / 所有用户 (查看 & 确认)
- **告警规则**: 基于 CPU/内存阈值创建规则，支持全局和按设备
- **告警级别**: Warning / Critical / Info，支持 `>` `>=` `==` 运算符
- **告警升级**: 连续触发 N 次自动从 Warning 升级为 Critical (可配置 escalation_count)
- **告警静默**: 支持按小时静默告警规则 (Silence)，静默期内不触发
- **告警确认**: 支持 Ack 确认告警，跟踪已处理/未处理
- **告警历史**: 独立历史页面，按时间倒序展示最近 200 条告警记录，支持 Ack 确认和 Clear All/ Clear Acknowledged 批量清除
- **仪表盘告警面板**: 首页展示最近告警列表 + 活跃告警数统计卡片 (红色脉冲动画)
- 巡检时自动评估所有启用规则，超标的生成 AlertHistory 记录

### 7. 子网计算 (`routers/subnet_calc.py`)
- **用户**: 所有登录用户
- IPv4 子网信息: 网络地址、掩码、广播、可用 IP 范围、通配符掩码、二进制掩码
- IPv4 **VLSM**: 输入主机数 -> 自动最优方案 | **路由聚合**: 多网段 -> 最小超网 | 子网划分: 等长子网 (最多256) | 子网列举: 3列显示 (最多500)
- IPv6 子网信息: 压缩/展开地址、链路本地检测、hostmask
- 私有地址检测 (IPv4/IPv6)

### 8. 配置推送 (`routers/config_push.py`)
- **用户**: 管理员
- 向网络设备批量推送配置命令
- 支持粘贴命令文本或上传配置文件 (.txt/.cfg/.conf, 最大 2MB)
- 并行推送: ThreadPoolExecutor 10 路并发, 120s 超时保护, 耗时统计
- 推送结果自动保存到巡检报告
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
- **调度器**: BackgroundScheduler (线程调度, 不依赖 asyncio event loop)
- **时区**: 所有定时任务使用 CST (UTC+8)，确保北京时间准时触发
- 4 种调度类型: 一次性 (指定日期时间) / 每小时 (间隔 N 小时) / 每天 (指定时间) / 每月 (指定日期+时间)
- 每个定时任务可选指定巡检设备（不选 = 全设备，最多 100 并发）
- 动态 APScheduler 管理: 新增/修改/删除/启停即时生效，无需重启
- 一次性任务执行后自动禁用，过期自动顺延至次日
- 支持「立即执行」按钮 + 实时进度面板（AJAX + 轮询）
- 「立即执行」返回 JSON 驱动进度面板，无需页面跳转
- 无 DB 定时任务时回退到默认每日 06:00 CST

### 11. 网络拓扑 ( + )
- **用户**: 所有登录用户
- 基于 CDP/LLDP 邻居信息自动生成交互式拓扑图
- 使用 vis.js 力导向布局，支持拖拽节点、滚轮缩放、点击查看详情
- **自动角色识别**: Core（核心）/ Distribution（汇聚）/ Access（接入），按连接数分级
- **路径追踪**: 选择两台设备，BFS 最短路径高亮，标注跳数
- **告警集成**: 触发告警的设备红色边框闪烁
- **跨协议 IP 匹配合并**: CDP 和 LLDP 发现的同一设备自动去重
- 设备按 /24 子网自动分组，层级排列
- 连线按端口速率着色（GE/10G 绿色，FE 橙色），悬停显示全部端口
- 点击节点弹出设备详情（IP/CPU/内存/邻居/角色/告警）
- 点击连线显示两端设备和端口信息
- 搜索定位 + 自动刷新

### 12. 报告模块 (`routers/reports.py`)
- **用户**: 所有登录用户
- **批量删除**: 复选框多选 + 一键批量删除巡检报告
- **PDF 导出**: 完整巡检报告 PDF，含页眉/页脚/页码/统计卡片。字体系统：英文标题 Helvetica-Bold、代码 Courier、中文 DroidSansFallback
- **Word 导出**: `.docx` 格式，含标题/统计卡片/灰色背景代码块/彩色状态标签
- **HTML 导出**: 含 CSS 样式的完整页面 (暗色主题，打印友好)
- **CSV 导出**: 最近 500 条批量导出 (ID/时间/IP/主机名/CPU/内存/运行时间/状态)
- 报告列表每行直接导出 HTML/Word
- 巡检历史记录列表 (最近 200 条, 设备筛选下拉菜单)
- 统计概览 (总计/成功/失败)
- 单次巡检详情查看 (原始命令输出, JSON 格式)

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
│       ├── models.py               # ORM 模型 (Device/User/InspectionRun/AlertRule/AlertHistory/CustomCommand/InspectionSchedule)
│       ├── schemas.py              # Pydantic 请求/响应模型
│       ├── crypto.py               # 密码加密/解密工具 (Fernet AES-128-CBC + HMAC)
│       ├── constants.py            # 共享常量 (SERVER_PLATFORMS)
│       ├── helpers.py              # 共享辅助函数 (save_inspection_run)
│       ├── templating.py           # Jinja2 模板引擎实例
│       ├── engine/
│       │   └── inspector.py        # 巡检引擎封装 (调用 inspection.py)
│       ├── routers/
│       │   ├── auth.py             # 认证路由 (登录/登出/用户管理/Session)
│       │   ├── devices.py          # 设备 CRUD (Web + API)
│       │   ├── inspect.py          # 巡检触发 & 进度追踪
│       │   ├── ping.py             # Ping / Traceroute / MTR
│       │   ├── config_compare.py   # 配置文件对比 (粘贴/上传/设备加载)
│       │   ├── alerts.py           # 告警规则管理
│       │   ├── subnet_calc.py      # IPv4/IPv6 子网计算 & 划分
│       │   ├── config_push.py     # 配置推送 (命令/文件上传)
│       │   ├── custom_cmds.py      # 自定义命令管理 & 实时执行
│       │   ├── scheduler.py        # 定时巡检调度 (APScheduler 动态管理)
│       │   └── topology.py         # 网络拓扑 (vis.js 交互图)
│       │   └── reports.py          # 巡检报告查看 & 导出
│       ├── templates/              # Jinja2 HTML 模板 (15 个页面)
│       │   ├── base.html           # 基础布局 (导航栏)
│       │   ├── login.html          # 登录页
│       │   ├── dashboard.html      # 仪表盘 (设备状态 + 告警面板 + CPU/内存趋势)
│       │   ├── devices.html        # 设备管理页
│       │   ├── users.html          # 用户管理页
│       │   ├── alerts.html         # 告警规则配置 & 历史记录页
│       │   ├── config_push.html   # 配置推送页 (选择/预览/结果)
│       │   ├── custom_cmds.html    # 自定义命令管理 & 执行页
│       │   ├── scheduler.html      # 定时巡检调度管理页
│       │   └── topology.html       # 网络拓扑页 (CDP/LLDP 可视化)
│       │   ├── ping.html           # 网络诊断页
│       │   ├── subnet.html         # 子网计算页
│       │   ├── config_compare.html # 配置对比页 (输入+结果一体化)
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
| GET | `/ping` | Ping 工具页面 (含设备快速选择下拉菜单) |
| POST | `/ping` | 执行 Ping/Traceroute/MTR |

### 配置对比

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/config-compare` | 配置对比页面 (含设备选择下拉菜单) |
| POST | `/config-compare` | 提交对比 (粘贴/上传/设备加载) |
| GET | `/config-compare/load-config?device_id=N` | 加载设备最新配置备份 (JSON) |

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
| GET | `/alerts/history` | 告警历史页面 | ✅ |
| POST | `/alerts/add` | 添加告警规则 (支持 severity/escalation_count) | ✅ |
| POST | `/alerts/silence/{rule_id}` | 静默告警规则 (hours=N) | ✅ |
| POST | `/alerts/ack/{history_id}` | 确认告警 | ✅ |
| DELETE | `/alerts/api/{rule_id}` | 删除告警规则 | ✅ |

### 子网计算

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/subnet` | 子网计算页面 (5 个 Tab: IPv4/划分/VLSM/聚合/IPv6) |
| POST | `/subnet` | 计算子网 (IPv4/IPv6/VLSM/路由聚合/子网列举) |

### 自定义命令

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|:----:|
| GET | `/custom-commands` | 命令管理页面 | ✅ |
| POST | `/custom-commands/add` | 添加命令 | ✅ |
| POST | `/custom-commands/execute` | 在设备上执行命令 (结果自动保存) |
| POST | `/custom-commands/execute-multi` | 多设备并行执行 (ThreadPool, 120s 超时) | ✅ |
| POST | `/custom-commands/delete/{id}` | 删除命令 | ✅ |
| POST | `/custom-commands/toggle/{id}` | 启用/禁用命令 | ✅ |

### 网络拓扑

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|:----:|
| GET | `/topology` | 网络拓扑页面 (vis.js 交互图, Fit/Export(JSON下载)/Auto-refresh 60s) | ✅ |
| GET | `/topology/data` | 拓扑数据 JSON (nodes + edges + groups + roles + alerts) | ✅ |

### 定时巡检调度

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|:----:|
| GET | `/scheduler` | 定时任务管理页面 | ✅ |
| POST | `/scheduler/add` | 添加定时任务 |
| POST | `/scheduler/edit/{id}` | 编辑定时任务 |
| POST | `/scheduler/batch-delete` | 批量删除定时任务 | ✅ |
| POST | `/scheduler/run-now/{id}` | 立即执行 (支持 JSON 响应) | ✅ |
| POST | `/scheduler/toggle/{id}` | 启用/禁用定时任务 | ✅ |
| POST | `/scheduler/delete/{id}` | 删除定时任务 | ✅ |

### 报告

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|:----:|
| GET | `/reports` | 报告列表页面 (支持 ?device_id=N 设备筛选, 统计概览) | ✅ |
| GET | `/reports/api` | 报告列表 (JSON) | ✅ |
| POST | `/reports/api/batch-delete` | 批量删除报告 (JSON: [id1,id2,...]) | ✅ |
| GET | `/reports/{run_id}` | 单次巡检详情 | ✅ |
| GET | `/reports/{run_id}/export` | 导出 HTML 报告 | ✅ |
| GET | `/reports/{run_id}/export/docx` | 导出 Word 报告 (.docx) | ✅ |
| GET | `/reports/{run_id}/export/pdf` | 导出 PDF 报告 | ✅ |
| GET | `/reports/export/csv` | 导出 CSV | ✅ |
| DELETE | `/reports/api/{run_id}` | 删除单条报告 | ✅ |

### 其他

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 重定向 → `/dashboard` |
| GET | `/dashboard` | 仪表盘 (设备统计 + 活跃告警 + 最近告警面板 + CPU/内存趋势柱状图) |
| GET | `/docs` | Swagger API 文档 (无需认证) |
| GET | `/openapi.json` | OpenAPI Schema (无需认证) |

---



---

## 当前运行状态

> 数据更新时间: 2026-06-12

### 数据库统计

| 表 | 记录数 | 说明 |
|---|:---:|------|
| devices | 8 | 已纳管设备 |
| inspection_runs | 8 | 历史巡检记录 |
| alert_history | 13 | 告警历史(含升级测试数据) |
| inspection_schedules | 3 | 活跃定时巡检任务 |
| custom_commands | 3 | 自定义命令模板 |

### 配置备份概况

configs/ 目录: 100+ 个 .cfg 备份文件

覆盖设备 IP: 172.16.1.1, 172.16.1.5, 172.16.1.55, 192.168.10.1,
192.168.10.3, 192.168.10.47, 192.168.55.2, 192.168.100.63, 192.168.100.105

最新备份: 2026-06-12 05:22 (今日凌晨定时巡检正常执行)

### 最近活动

- 2026-06-12 05:22: 定时巡检执行 (192.168.55.2 配置备份)
- 2026-06-11 13:57: 验证测试通过 (test_verify.py)
- 2026-06-11 13:57: 告警升级测试完成 (172.16.1.5, 3轮)

### Git 状态

- 分支: master
- 最近提交: 05978d2 feat: comprehensive platform optimization (2026-06)
- 未跟踪: 大量 .bak 备份文件 + 新配置文件
- 已删除: 旧版配置备份(定时轮转清理)

---


---

## 当前运行状态

> 数据更新时间: 2026-06-12

### 数据库统计

| 表 | 记录数 | 说明 |
|---|:---:|------|
| | 8 | 已纳管设备 |
| | 8 | 历史巡检记录 |
| | 13 | 告警历史（含升级测试数据） |
| | 3 | 活跃定时巡检任务 |
| | 3 | 自定义命令模板 |

### 配置备份



### 最近活动



### Git 状态



---

## 配置说明

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `INSPECT_SECRET_KEY` | Fernet 加密密钥 (Base64 编码) | 自动生成到 `.encryption_key` 文件 |
| `INSPECT_DB_PATH` | SQLite 数据库文件路径 | `/home/ivan/network-inspection/inspection.db` |

### 加密密钥

- 密钥文件 (推荐): `/etc/inspection/.encryption_key` (非 Web 可访问目录)
- 密钥文件 (旧位置): `inspection-platform/.encryption_key` (启动时自动迁移到新位置)
- 环境变量: `INSPECT_SECRET_KEY` (最高优先级)
- 算法: Fernet (AES-128-CBC + HMAC-SHA256)
- 权限: `600` (仅 owner 可读写)
- 首次启动自动生成，后续启动复用
- **请备份此文件** — 丢失后无法解密已存储的设备密码

### 数据库

- 类型: SQLite (WAL 模式)
- 位置: 默认 `/home/ivan/network-inspection/inspection.db`，可通过 `INSPECT_DB_PATH` 环境变量覆盖
- 表: `users`, `devices`, `inspection_runs`, `alert_rules`, `alert_history`, `inspection_schedules`, `custom_commands`
- 表结构首次启动自动创建 (SQLAlchemy `Base.metadata.create_all`)
- 明文密码首次启动自动迁移为加密存储
- **WAL 模式**: 读写不互锁，并发性能提升 3-5 倍
- **连接池**: `pool_size=5` + `max_overflow=10` + `pool_pre_ping=True` (自动检测断开连接)
- **连接回收**: `pool_recycle=3600` (1 小时)
- **忙等超时**: `busy_timeout=5000ms` (避免 "database is locked" 错误)
- **外键约束**: 强制开启 `foreign_keys=ON`
- **自动清理**: 每日 03:00 CST 清理 >30 天巡检记录和 >90 天已确认告警

### 配置备份去重

- SHA256 哈希对比: 与上一次备份内容对比，内容不变则跳过写入
- 自动轮转: 每设备保留最新 5 个备份版本，自动清理旧版本
- 存储位置: `configs/` 目录，文件命名格式 `{ip}_{timestamp}.cfg`

### 定时巡检

- 默认调度: 每天 06:00
- 配置位置: `backend/main.py` 第 89 行
  ```python
  scheduler.add_job(scheduled_inspection, CronTrigger(hour=6, minute=0), id="daily", name="daily")
  ```

### 巡检并发参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `MAX_WORKERS` (Web) | `min(os.cpu_count() * 2, 50)` | 动态调整，上限 50 |
| `MAX_WORKERS` (CLI) | 10 | CLI 脚本并发数 |
| `CONN_TIMEOUT` | 30s | SSH 连接超时 |
| `CMD_TIMEOUT` | 60s | 单命令执行超时 |
| `CONN_RETRIES` | 2 | SSH 连接重试次数 |
| `RETRY_DELAY` | 3s | 重试间隔 |
| 单设备超时 | 300s | 5 分钟保护，防止阻塞 |
| 进度保留 | 10s | 巡检完成后保留 10s 供前端轮询 |

---


## Docker 部署

### 镜像信息

| 项目 | 详情 |
|------|------|
| 镜像名 | `network-inspection:latest` |
| 基础镜像 | `python:3.12-slim` |
| 暴露端口 | `8000` (Web 平台) |
| 工作目录 | `/app/inspection-platform` |
| 运行用户 | `inspect` (非 root) |
### 从docker-hub仓库拉取（推荐）
```bash
# 公开镜像，无需登录即可拉取

docker pull ivanliyang/network1-inspection:latest

```
### 从阿里云镜像仓库拉取（推荐）

```bash
# 公开镜像，无需登录即可拉取
docker pull crpi-onapv500ctq06zb5.cn-hangzhou.personal.cr.aliyuncs.com/ivannetwrok/networkauto:latest
docker pull ivanliyang/network1-inspection:latest

# 打本地标签（可选）
docker tag crpi-onapv500ctq06zb5.cn-hangzhou.personal.cr.aliyuncs.com/ivannetwrok/networkauto:latest   network-inspection:latest
```

### 快速启动

```bash
# 1. 加载镜像（如果使用 tar 文件）
docker load -i network-inspection.tar
# 或者直接拉取（如果已推送至仓库）
docker pull crpi-onapv500ctq06zb5.cn-hangzhou.personal.cr.aliyuncs.com/ivannetwrok/networkauto:latest
docker pull https://hub.docker.com/r/ivanliyang/network1-inspection

# 2. 创建数据目录
mkdir -p configs reports logs
touch inspection.db
chmod 666 inspection.db

# 3. 启动容器 (端口 8001)
docker run -d --name network-inspection --restart unless-stopped   -p 8001:8000   -v ./configs:/app/configs   -v ./reports:/app/reports   -v ./logs:/app/logs   network-inspection:latest

# 4. 验证
curl http://localhost:8001/dashboard
```

### 使用 docker-compose (推荐)

```yaml
# docker-compose.yml
# 使用本地镜像:
#   image: network-inspection:latest
# 使用阿里云仓库镜像:
#   image: crpi-onapv500ctq06zb5.cn-hangzhou.personal.cr.aliyuncs.com/ivannetwrok/networkauto:latest
services:
  inspection:
    image: network-inspection:latest
    container_name: network-inspection
    restart: unless-stopped
    ports:
      - "8001:8000"
    environment:
      - INSPECT_SECRET_KEY=${INSPECT_SECRET_KEY:-}
      - INSPECT_DB_PATH=/app/inspection.db
      - PYTHONUNBUFFERED=1
    volumes:
      - ./configs:/app/configs
      - ./reports:/app/reports
      - ./logs:/app/logs
      - ./inspection.db:/app/inspection.db
```

```bash
# 启动
docker-compose up -d

# 停止
docker-compose down

# 查看日志
docker logs -f network-inspection
```

### 构建镜像

```bash
# 在项目根目录
cd /home/ivan/network-inspection

# 构建 (需要 Dockerfile, requirements.txt, .dockerignore)
sudo docker build -t network-inspection:latest .

# 导出镜像
sudo docker save network-inspection:latest -o network-inspection.tar

# 传输到其他服务器
scp network-inspection.tar docker-compose.yml root@target-server:/opt/
```

### 跨服务器部署流程

```
源服务器 (192.168.26.53)              目标服务器 (172.16.1.177)
─────────────────────────            ─────────────────────────
docker build -t network-inspection
docker save -o network-inspection.tar
                                       ↓ scp 传输
                                    docker load -i network-inspection.tar
                                    docker-compose up -d
```

### 容器内路径映射

| 宿主机 | 容器内 | 用途 |
|--------|--------|------|
| `./configs/` | `/app/configs/` | 设备配置备份 |
| `./reports/` | `/app/reports/` | 巡检 HTML 报告 |
| `./logs/` | `/app/logs/` | 系统日志文件 |
| `./inspection.db` | `/app/inspection.db` | 数据库 (可选挂载) |

### 常用管理命令

```bash
# 查看状态
docker ps | grep network-inspection

# 查看日志
docker logs --tail 50 network-inspection

# 进入容器
docker exec -it network-inspection /bin/bash

# 重启
docker restart network-inspection

# 更新: 重新构建镜像后
docker-compose down
docker load -i network-inspection.tar
docker-compose up -d
```

### Docker 网络不通的解决方案

如果服务器到 Docker Hub / PyPI 网络不通，Dockerfile 已配置阿里云镜像加速：

```dockerfile
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/
```

对于 apt 源也可替换为阿里云：

```dockerfile
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources
```

详细文档见 `dockerivan.MD`。

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

## Git 版本控制

项目已初始化 Git 仓库，支持 git status/diff/commit/log/checkout。

## 语言切换

导航栏右侧提供 **EN / 中文** 切换按钮。使用 / 属性 + JavaScript Cookie 实现：
- 默认中文显示所有导航标签
- 点击 EN 切换为英文界面（Dashboard, Devices, Reports 等）
- 语言偏好通过 Cookie 持久化（1 年有效期），刷新后保持
- 不影响设备数据、巡检报告等内容语言

---
---

## 路由表验证与自动回退

巡检平台内置路由表输出验证机制，自动检测命令返回数据是否为日志污染而非路由信息。

**工作原理：**
1. 执行路由表命令（如 `display ip routing-table statistics`）
2. 验证器 `_validate_routing_output()` 检测输出是否包含日志特征（`FIREWALLATCK`、`%%01ATK` 等）
3. 若检测到日志污染，自动回退到备用命令（如 `display ip routing-table`）
4. 再次验证回退命令的输出，确保数据正确

**各厂商路由命令及回退：**

| 厂商 | 主命令 | 回退命令 |
|------|--------|----------|
| Cisco IOS | `show ip route summary` | `show ip route` |
| Cisco XR | `show route summary` | `show route` |
| Cisco NX-OS | `show ip route summary` | `show ip route` |
| Juniper | `show route summary` | `show route` |
| Huawei | `display ip routing-table statistics` | `display ip routing-table` |
| H3C | `display ip routing-table statistics` | `display ip routing-table` |
| Fortinet | `get router info routing-table all` | `get router info routing-table static` |
| Arista | `show ip route summary` | `show ip route` |
| Ruijie | `show ip route summary` | `show ip route` |




---

## 已知问题与改进方向

### 安全性 (优先级: 高)

| # | 问题 | 影响 | 改进方案 |
|---|------|------|----------|
| 1 | 用户密码使用弱哈希 | 安全风险 | 已升级为 PBKDF2-SHA256 (600K迭代) |
| 2 | CLI脚本 inspection.py 从 CSV 读明文密码 | 密码泄露风险 | 复用 crypto.py Fernet 加密或从 Web 数据库读取 |
| 3 | devices.csv 密码列明文存储 | 文件权限泄露风险 | 迁入 Web 数据库(已加密) |

### 代码质量 (优先级: 中)

| # | 问题 | 影响 | 改进方案 |
|---|------|------|----------|
| 1 | 19+ 个 .bak/.bak_* 文件散落 | 代码库混乱 | 统一清理，保留最近版本 |
| 2 | H3C_COMMANDS 第138行和196行重复定义 | 后者覆盖前者 | 合并为单一定义 |
| 3 | inspection.db-wal 6.6MB | 磁盘占用 | PRAGMA wal_checkpoint(TRUNCATE) |

### 功能增强 (优先级: 低-中)

| # | 方向 | 参考方案 | 优先级 |
|---|------|----------|:---:|
| 1 | 补充 SNMP 性能采集 | LibreNMS / Prometheus SNMP Exporter | 中 |
| 2 | 配置备份集成 Git | Oxidized Git 模型 | 中 |
| 3 | 合规检查引擎 | Netshot 策略引擎 | 低 |
| 4 | 容器化部署 | Netshot compose.yaml 参考 | 低 |
| 5 | gNMI 流式遥测调研 | OpenConfig 厂商支持矩阵 | 低 |
| 6 | 密码哈希升级 bcrypt/argon2 | OWASP 推荐 | 中 |

### 项目清理命令

```
rm -f inspection.py.bak* inspection-platform/README.md.bak*
rm -f inspection-platform/README.md.readme*
rm -f inspection-platform/backend/**/*.bak*
sqlite3 inspection.db "PRAGMA wal_checkpoint(TRUNCATE);"
git add -A && git commit -m "chore: cleanup backup files and update docs"
```

---


---

## 已知问题与改进方向

### 安全性（优先级：高）

| # | 问题 | 影响 | 改进方案 |
|---|------|------|----------|
| 1 | 用户密码使用 MD5 哈希 | 弱哈希，易被彩虹表破解 | 已升级为 PBKDF2-SHA256 (600K 迭代) |
| 2 | CLI 脚本 从 CSV 读取明文密码 | 密码泄露风险 | 复用 Fernet 加密或从 Web 数据库读取 |
| 3 | 密码列明文存储 | 文件权限泄露风险 | 迁入 Web 数据库（已加密）或使用环境变量 |

### 代码质量（优先级：中）

| # | 问题 | 影响 | 改进方案 |
|---|------|------|----------|
| 1 | 19 个 / 文件散落项目中 | 代码库混乱，增加维护成本 | 统一清理，保留最近 1 个版本 |
| 2 | 第 138 行和 196 行 重复定义 | 后者覆盖前者，逻辑不明确 | 合并为单一定义 |
| 3 | 6.6MB，WAL 文件过大 | 磁盘占用 | 执行 |

### 功能增强（优先级：低-中）

| # | 方向 | 参考方案 | 优先级 |
|---|------|----------|:---:|
| 1 | 补充 SNMP 性能采集（带宽/错误计数/CPU趋势） | LibreNMS / Prometheus SNMP Exporter | 🟡 |
| 2 | 配置备份集成 Git 版本控制 | Oxidized Git 模型 | 🟡 |
| 3 | 增加合规检查引擎（配置审计规则） | Netshot regex/JS/Python 策略引擎 | 🟢 |
| 4 | 容器化部署（Docker Compose） | Netshot compose.yaml 参考 | 🟢 |
| 5 | 调研 gNMI 流式遥测协议就绪度 | OpenConfig / 厂商支持矩阵 | 🟢 |
| 6 | 密码哈希升级为 bcrypt/argon2 | OWASP 推荐 | 🟡 |

### 项目清理

0|-1|-1

---

## 安全说明

- ✅ 设备密码使用 Fernet (AES-128-CBC + HMAC) 加密存储
- ✅ 用户密码使用 PBKDF2-SHA256 (600,000 迭代) 哈希
- ✅ Session Cookie 设置 `httponly` 标志 (防 XSS 窃取)
- ✅ 所有 API 端点强制认证 (`require_auth` 依赖注入)
- ✅ 告警规则运算符服务端验证 (仅允许 `>` `>=` `==`，非法运算符返回 400)
- ✅ 密码加密存储 (Fernet AES-128-CBC + HMAC)
- ✅ 日志系统敏感字段脱敏: password/secret/token/key 自动替换为 `***MASKED***`
- ✅ 支持明文密码自动迁移: 启动时检测并加密旧密码
- ✅ 加密密钥文件权限 600
- ✅ 旧格式 SHA256 密码自动兼容 — 登录时检测并自动升级为 PBKDF2-SHA256

### 数据保护
- ✅ SQLite WAL 模式: 读写并发安全
- ✅ 外键约束强制开启
- ✅ 配置备份 SHA256 去重 + 自动轮转 (最新 5 版)
- ✅ 自动数据清理: >30 天巡检记录 + >90 天已确认告警
- ⚠️ 生产环境建议:
  - 修改默认 admin 密码
  - 使用环境变量 `INSPECT_SECRET_KEY` 替代密钥文件
  - 配置 HTTPS 反向代理 (Nginx/Caddy)
  - 定期备份 `inspection.db` 和 `.encryption_key`
  - 为设备账号使用只读权限 (最小权限原则)

---

## 优化记录 (2026-06)

| 模块 | 优化内容 |
|------|----------|
| **前端交互** | HTMX 渐进增强 — 仪表盘 /api/dashboard/stats 轻量端点 (30s 刷新)、告警/报告行内操作、去除 deleteOne 死代码 |
| **IOS-XR 巡检** | 命令矩阵 6→8 类别 (新增系统冗余/环境状态/告警与日志), 12→21 命令, 告警自动回退, 日志大小写过滤 |
| **代码质量** | 提取 SERVER_PLATFORMS→constants.py, save_inspection_run→helpers.py, topology N+1 修复, H3C_COMMANDS 去重 |
| **安全加固** | PBKDF2 自动升级旧哈希, devices.csv 安全警告, config_push 预配置备份持久化, INSPECT_DB_PATH 环境变量 |
| **巡检引擎** | 路由表验证与自动回退 (9厂商), 华为 USG 防火墙兼容, Juniper/NX-OS 环境监控, Arista 路由回退, Ruijie 增强 |
| **服务器 BMC** | 5 大 BMC 独立系统日志类别 (Dell getsel, HP iML, Lenovo eventlog, Huawei sel, Inspur sel) |
| **数据库** | SQLite WAL 模式, 连接池 (pool_pre_ping/pool_recycle), Context Manager |
| **安全** | 三级密钥查找 (环境变量→/etc/inspection/→自动生成), 日志敏感脱敏, SHA256 备份去重 |
| **告警** | Clear All / Clear Acknowledged 批量清除 |
| **配置对比** | 设备配置加载 API, Swap/Clear 按钮, 可调上下文行数 |
| **配置推送** | ThreadPoolExecutor 并行推送 (10路, 120s超时), 耗时统计 |
| **自定义命令** | 并行多设备执行, 单命令执行结果自动保存 |
| **Ping** | 设备快速选择下拉菜单, 可配超时 (500ms-5000ms) |
| **巡检报告** | 设备筛选下拉菜单, 统计概览 (总计/成功/失败), Word 导出按钮 |
| **定时任务** | 编辑任务弹窗, 批量删除, Run-now last_run 时间戳修复 |
| **子网计算** | IPv6 is_global/is_unique_local, IPv6 子网列表, Tab 切换 JS |
| **网络拓扑** | Fit 缩放, JSON 导出, 60s 自动刷新 |
| **日志系统** | 结构化 logging + SensitiveMaskFilter 敏感字段脱敏 |
| **CLI 脚本** | devices.csv 模板自动生成, SHA256 配置备份去重+轮转 |
| **Ruijie RGOS** | 增强命令矩阵, 5 层 CPU/4 层内存/3 层 uptime 解析器 |
| **技术调研** | 深度研究行业方案对比 (LibreNMS/Oxidized/Netshot/SolarWinds), Netshot 前端进展追踪 |
| **文档** | README 新增技术方案对比、运行状态、已知问题与改进方向 |
| **安全性** | 识别 MD5 弱哈希风险、CSV 明文密码问题、H3C_COMMANDS 重复定义 |
| **技术调研** | 深度研究行业方案对比(LibreNMS/Oxidized/Netshot/SolarWinds), Netshot 前端进展追踪 |
| **文档** | README 新增技术方案对比、运行状态、已知问题与改进方向 |
| **代码审查** | 识别 H3C_COMMANDS 重复定义、WAL 膨胀、.bak 文件清理等改进点 |
| **解析器** | Cisco IOS CPU 3 层回退, Juniper CPU 4 层回退 |


-----如果您支持我可以请问喝一杯咖啡--------------
<img width="628" height="701" alt="image" src="https://github.com/user-attachments/assets/503b3532-8109-4bd2-945d-061272a2a5f6" />

<img width="571" height="643" alt="image" src="https://github.com/user-attachments/assets/a05c8081-2e49-4e58-8aba-d100daa1066d" />




