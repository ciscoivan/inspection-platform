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
│  alerts  │ reports  │ subnet   │custom_cmd│config_backup│  topology  │  helpers   │
│  告警系统  │ 报告导出  │ 子网计算  │ 自定义命令 │  配置备份管理  │  网络拓扑   │  共享工具   │
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


---

## 平台功能矩阵


- **BOM匹配验证**: 上传项目BOM文件(≤20MB)与巡检报告匹配验证设备是否按单配置 — 网络设备按 Product#↔PID 精确匹配; Dell 等无 PID 输出的服务器按 Description 提取的 Model/CPU/内存/磁盘/RAID/网卡/电源与硬件摘要词级匹配;结果三态(成功/未匹配/配置异常)标色,可剔除行后导出 Excel 报告
- **CA证书服务器**: 内置PKI系统，支持创建根CA、签发终端证书、CSR签名、PEM/PKCS#12导出、证书吊销。CRL 以数据库为唯一真相源重建（文件为可重建缓存），原子写入 + 线程锁，杜绝损坏/并发导致吊销记录丢失
- **Case 管理**: 按项目/案件归档巡检报告、设备文档、照片;可配置类别(设置页增删改,非空不可删);多文件上传(≤50MB,有界读取防 OOM,中途失败回滚防孤儿)、下载、在线查看(图片/PDF 内联;HTML 等强制下载防存储型 XSS);预览 URL 带 HMAC 签名+6h 过期;扁平存储+DB 类别标签;文件名净化+路径防穿越;新建重名(大小写不敏感)拒绝并提示
- **LLM VRAM计算器**: 根据模型参数量和量化精度估算推理/训练/多GPU部署所需显存，支持10种预设模型和8种量化精度对比表
- **AI 助手**: 对话式设备巡检/配置 — 支持 Kimi/DeepSeek/GLM/本地 OpenAI 兼容模型 (全局+个人双轨配置, key Fernet 加密); 工具栏下拉可按会话选择/切换模型, 会话可删除 (软删除, 记录保留); 只读命令直接执行, 配置变更逐条全文展示人工确认后才下发; 全量审计 (对话/命令/输出/确认人)

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
> **硬件摘要**：巡检报告"基本信息"顶部自动生成硬件摘要，包含 CPU 型号/数量、内存型号/容量、网卡型号/数量、RAID 控制器型号、硬盘型号/容量、电源型号/状态。Dell iDRAC 使用专用解析器（`racadm hwinventory`），其它平台使用通用解析器（自动匹配 `Model`/`Size`/`Cores` 等关键字段）。存储解析覆盖 PERC 背板盘（`Disk.Bay.*`）与 BOSS 卡及其直插 M.2 NVMe（`BOSS.SL.*` / `Disk.Direct.*`），背板/电池等非控制器部件不会误计入 RAID 列表。

---

## 功能模块

### 1. 认证模块 (`routers/auth.py`)
- **用户**: 管理员 (admin)
- 基于 Cookie 的会话管理 (httponly + samesite=lax, 7 天有效期)
- PBKDF2-SHA256 密码哈希 (600,000 迭代), 旧 SHA256 格式登录时自动升级
- 统一密码策略: ≥8 位 / ≤128 位 / 非纯空白 (添加/修改/重置同一校验)
- 自助修改密码页 `/change-password` (验旧密码 + 两次确认)
- 管理员可创建/删除用户、重置用户密码 (不可在用户页重置自己, 防误锁)
- 改密/重置/删除用户后自动吊销该用户全部会话 (强制重新登录)
- 管理员接口统一 `require_admin` 依赖 (非管理员返回 403)
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

### 13. BOM 匹配模块 (`routers/bom.py` + `bom_matcher.py` + `templates/bom_match.html`)
- **用户**: 所有登录用户
- 上传项目 BOM 文件 (.xlsx/.xls, ≤20MB 有界读取防 OOM), 自动定位 `Product#` 表头行, 解析 Product#/Description/Vendor/QTY 列
- 与选定的巡检记录匹配, 验证到货设备是否按单配置:
  - **网络设备**: BOM `Product#` 与巡检数据「硬件清单」中的 PID 精确匹配
  - **服务器** (Dell iDRAC 等无 PID 输出的 BMC): 从 Description 提取 Model/CPU/内存/磁盘/RAID/网卡/电源关键词, 与巡检「硬件摘要」做词级匹配 — 容忍 (R)/(TM) 商标符号; `BROADCOM XXXX` 自动归一化为 `BCMXXXX`; CPU `24C/48T` 只取核心数 `24C`
- 匹配结果三态: 匹配成功 / 未匹配 / 配置异常 (服务器逐项列出配置检查明细, 标出缺失项)
- 结果行可勾选剔除 (导出前清理误配行)
- 导出 Excel 匹配报告 (状态色标: 绿=成功 / 黄=未匹配 / 红=配置异常; RFC 6266 中文安全文件名)
- BOM 数据按会话在服务端内存缓存 (会话级隔离, 互不可见)

### 14. Case 系统 (`routers/cases.py` + `templates/case*.html`)
- **用户**: 所有登录用户 (类别管理: 管理员)
- 按项目/案件归档巡检报告、设备文档、照片; 每 Case 一个独立目录
- **重名校验**: 新建 Case 名称与现有 Case 重复时 (大小写不敏感, 自动去首尾空格) 拒绝创建并回显错误横幅, 被拒绝的创建不触发 QC webhook (Case 名即 T1 订单号, 重名会让质检链接指向不明)
- 类别可配置 (默认 巡检报告/设备文档/照片): 增删改, 改名查重, 非空类别不可删
- **搜索**: 列表页跨表搜索 Case 名称/备注/文件名 (LIKE 通配符已转义), 匹配文件内联展示; 详情页文件名实时过滤
- 多文件上传 (单文件 ≤50MB): 有界读取防 OOM, 文件名净化+uuid 防碰撞+路径防穿越, 中途失败回滚已写磁盘文件
- **在线查看**: 图片/PDF 内联, HTML 等其余类型强制下载 (杜绝存储型 XSS), 统一 `X-Content-Type-Options: nosniff`
- 预览 URL 带 HMAC 签名 + 6h 过期 (先验签后查库, 不可伪造/不可穷举)
- 下载 FileResponse 流式 + RFC 6266 中文文件名
- 删除 Case 级联删除全部文件与目录
- **QC 联动**: 内容变更 (新建/上传/删文件/删 Case) 自动 webhook 通知 T1 质检系统 (见 `qc_webhook.py`)

### 15. CA 证书服务器 (`routers/ca_server.py` + `ca_engine.py`)
- **用户**: 所有登录用户
- 根 CA 创建 (RSA-2048/4096, ECC P-256/P-384, 有效期可配) 与根证书下载
- 终端证书签发 (Common Name + SAN, RSA/ECC); 支持**外部 CSR 签名** (服务端不持有私钥)
- 证书吊销: **DB 为唯一真相源**, CRL 文件为可重建缓存 — 原子写入 + 线程锁, 杜绝损坏/并发导致吊销记录丢失
- 已吊销证书**仅到期后可删除** (防止序列号提前移出 CRL 被静默"解吊销")
- 导出: PEM zip (证书+私钥+CA 链) / 裸 .crt / PKCS#12 (自定义密码; CSR 签发的证书无私钥, 仅可下 .crt)
- 全部下载走 RFC 6266 编码 (中文证书名不崩溃)

### 16. 配置备份管理 (`routers/config_backup.py` + `../inspection.py`)
- **用户**: 所有登录用户
- 备份列表浏览 (按设备 IP 筛选, 显示大小/时间)
- 在线查看 (inline) / 下载 `.cfg` (RFC 6266 文件名)
- 手动触发单台设备备份 (netmiko; SHA256 去重, 可强制)
- 批量导出 ZIP (按设备筛选) / 批量删除 (仅限备份目录内 .cfg, 路径校验)
- 轮转: 手动备份每设备保留最新 10 份; 巡检自动备份去重后保留 5 版

### 17. LLM VRAM 计算器 (`routers/vram_calc.py`)
- **用户**: 所有登录用户
- 10 种预设模型 (LLaMA 3 / Qwen 2.5 / DeepSeek V3 / R1 / Mistral / Gemma / ChatGLM / Yi) + 自定义参数量
- 8 种量化精度对比表 (FP32 / FP16 / BF16 / INT8 / FP8 / INT4 / GPTQ / AWQ)
- 三种场景估算: 推理 (参数量×字节×1.2) / 训练 (×4) / 多 GPU 部署 (TP 开销 ×1.05, PP ×1.02)
- 纯计算工具, 无数据存储

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
│       │   ├── config_backup.py   # 配置备份管理 (浏览/下载/手动备份/批量导出)
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
│       │   ├── config_backup.html # 配置备份管理页 (列表/下载/手动备份/ZIP导出)
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
| `admin` | 首次启动自动生成随机密码 | 管理员 (可管理用户/设备/告警) |

> 初始密码生成后写入 `/tmp/inspect_initial_admin_password` (权限 0600, 请立即保存并删除该文件), 或用环境变量 `INSPECT_INITIAL_ADMIN_PASSWORD` 预设。
> ⚠️ **首次登录后请立即通过「修改密码」页修改初始密码。**

---

## API 端点


- `/bom-match` — BOM匹配验证页面
- `/ca-server` — CA证书管理页面
- **CA证书服务器**: 内置PKI系统，支持创建根CA、签发终端证书、CSR签名、PEM/PKCS#12导出、证书吊销。CRL 以数据库为唯一真相源重建（文件为可重建缓存），原子写入 + 线程锁，杜绝损坏/并发导致吊销记录丢失
- `/vram-calc` — LLM VRAM计算器页面

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
| GET | `/change-password` | 修改密码页面 |
| POST | `/change-password` | 提交修改密码 (Form: old_password, new_password, confirm_password) |
| GET | `/users` | 用户管理页面 (管理员) |
| POST | `/users/add` | 添加用户 (管理员, 密码≥8位) |
| POST | `/users/reset-password/{id}` | 重置用户密码 (管理员, 不可重置自己) |
| POST | `/users/delete/{id}` | 删除用户 (管理员) |

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

### BOM 匹配

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/bom-match` | BOM 匹配页面 (列出最近 50 条巡检记录) |
| POST | `/bom-match/api/upload` | 上传并解析 BOM xlsx (≤20MB, 返回统计片段) |
| POST | `/bom-match/api/match` | 对选定巡检记录执行匹配 (返回结果表) |
| POST | `/bom-match/api/remove` | 按行号剔除结果行 |
| GET | `/bom-match/api/export` | 导出 Excel 匹配报告 |

### Case 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/cases` | Case 列表 (`?q=` 跨表搜索名称/备注/文件名) |
| POST | `/cases/create` | 新建 Case (重名拒绝并回显错误) |
| GET | `/cases/{id}` | Case 详情 (含签名预览 URL) |
| POST | `/cases/{id}/upload` | 多文件上传 (≤50MB/文件) |
| GET | `/cases/{id}/files/{fid}/download` | 下载文件 |
| GET | `/cases/{id}/files/{fid}/view` | 在线查看页 |
| GET | `/cases/{id}/files/{fid}/raw` | 内联/下载原始文件 |
| GET | `/cases/preview/{id}/{stored}` | 签名预览 (公开, 需有效 exp+sig) |
| POST | `/cases/{id}/files/{fid}/delete` | 删除文件 |
| POST | `/cases/{id}/delete` | 删除 Case (级联) |
| GET | `/cases/categories` | 类别管理页 (管理员) |
| POST | `/cases/categories/add` | 新增类别 (管理员) |
| POST | `/cases/categories/{id}/rename` | 类别改名 (管理员) |
| POST | `/cases/categories/{id}/delete` | 删除空类别 (管理员) |

### CA 证书

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/ca-server` | CA 管理页面 |
| POST | `/ca-server/api/root/create` | 创建根 CA |
| GET | `/ca-server/api/root/{id}/download` | 下载根证书 |
| POST | `/ca-server/api/cert/issue` | 签发终端证书 |
| POST | `/ca-server/api/csr/sign` | 签名外部 CSR |
| POST | `/ca-server/api/cert/{id}/revoke` | 吊销证书 (重建 CRL) |
| POST | `/ca-server/api/cert/{id}/delete` | 删除已吊销且已过期的证书 |
| GET | `/ca-server/api/cert/{id}/download/pem` | 下载 PEM zip (证书+私钥+CA) |
| GET | `/ca-server/api/cert/{id}/download/crt` | 下载裸证书 |
| POST | `/ca-server/api/cert/{id}/download/p12` | 下载 PKCS#12 (Form: password) |

### 配置备份

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/config-backup` | 备份管理页面 |
| GET | `/config-backup/api/list` | 备份列表 (`?device_ip=` 筛选) |
| GET | `/config-backup/api/download/{filename}` | 下载 (`?view=1` 在线查看) |
| POST | `/config-backup/api/backup-now` | 手动备份单台设备 |
| GET | `/config-backup/api/export-zip` | 批量导出 ZIP |
| POST | `/config-backup/api/batch-delete` | 批量删除备份 |

### VRAM 计算

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/vram-calc` | 计算器页面 |
| POST | `/vram-calc` | 计算 (Form: model/custom_params/quant/scenario/gpu_count/strategy) |

### 其他

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 重定向 → `/dashboard` |
| GET | `/dashboard` | 仪表盘 (设备统计 + 活跃告警 + 最近告警面板 + CPU/内存趋势柱状图) |
| GET | `/docs` | Swagger API 文档 (需登录) |
| GET | `/openapi.json` | OpenAPI Schema (需登录) |

---



---

## 当前运行状态

> 数据更新时间: 2026-06-16

### 数据库统计

| 表 | 记录数 | 说明 |
|---|:---:|------|
| devices | 7 | 已纳管设备 |
| inspection_runs | 7 | 历史巡检记录 |
| alert_history | 2 | 告警历史(含升级测试数据) |
| inspection_schedules | 3 | 活跃定时巡检任务 |
| custom_commands | 3 | 自定义命令模板 |
| users | 3 | 平台用户 |

> ⚠️ 2026-06-16: 数据库曾发生损坏（已修复），预防措施已部署：单例锁 + 启动完整性检查 + systemd 崩溃循环保护 + WAL 定期 checkpoint
>
> ✅ 2026-06-16 07:22: 全模块验证通过 (16/16)，零新错误（WAL 14MB 膨胀 + 多进程并发写入），已通过 dump→重建恢复。3 条 inspection_runs 因页损坏丢失。预防措施已部署（见下方安全说明）。

### 配置备份概况

configs/ 目录: 100+ 个 .cfg 备份文件

覆盖设备 IP: 172.16.1.1, 172.16.1.5, 172.16.1.55, 192.168.10.1,
192.168.10.3, 192.168.10.47, 192.168.55.2, 192.168.100.63, 192.168.100.105

最新备份: 2026-06-12 05:22 (今日凌晨定时巡检正常执行)

### 最近活动

- 2026-06-16 07:22: WAL checkpoint 机制部署 + 全模块验证 (16/16 PASS)
- 2026-06-16 04:42: 服务恢复运行，全部 13 模块验证通过
- 2026-06-16 03:29: 数据库损坏恢复（dump→重建，18/21 inspection_runs 保留）
- 2026-06-16: 部署单例锁 + 启动完整性检查 + systemd 崩溃循环保护
- 2026-06-14 12:17: 安全修复验证通过（登录/登出/认证/备份/时间戳 全部正常）
- 2026-06-11 13:57: 验证测试通过 (test_verify.py)
- 2026-06-11 13:57: 告警升级测试完成 (172.16.1.5, 3轮)

### Git 状态

- 分支: master
- 最近提交: bf51a1f fix: prevent DB corruption - singleton lock, integrity check, crash-loop protection
- 清理: .bak 备份文件已删除，configs/ 纳入版本控制
- 未跟踪: 大量 .bak 备份文件 + 新配置文件
- 已删除: 旧版配置备份(定时轮转清理)

---


---


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
| 当前镜像 | `network-inspection:v5` (= `latest`, 2026-08-13 构建, 代码基线 git `e714245`) |
| 历史镜像 | `v4` / `v3` 保留在服务器本地, 可回滚 |
| 基础镜像 | `python:3.12-slim` |
| 暴露端口 | `8000` (容器内), 宿主机默认映射 `9001` |
| 工作目录 | `/app/inspection-platform` |
| 运行用户 | `inspect` (非 root, uid 1000) |

> 完整手册: 仓库根 `dockerivan.MD` (零基础版); 精简 runbook 见
> `docs/docker-compose-runbook-2026-08-13.md`; Dockerfile 逐行解析见
> `docs/dockerfile-explained-2026-08-13.md`; v5 构建与验证记录见
> `docs/docker-build-v5-verify-2026-08-13.md`。

### 快速启动 (新服务器)

仓库根目录自带 `setup.sh`, 首次运行前执行一次即可完成全部预创建
(.env / 空 inspection.db / 数据目录 / Fernet 密钥 / 属主 uid 1000):

```bash
cd /home/ivan/network-inspection   # 或你的部署目录 (需含 Dockerfile 同级全套文件)
./setup.sh                         # 一次性初始化
sudo docker compose up -d          # 启动
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:9001/login   # 期望 200
```

手工预创建清单 (不用 setup.sh 时): `.env` (含 `INSPECT_SECRET_KEY`)、
**空文件** `inspection.db` (必须 touch, 否则 Docker 建成同名目录)、
`configs/ reports/ logs/ data/cases/ data/ca/`, 属主均为 uid 1000。

### docker-compose.yml (当前版本)

```yaml
services:
  inspection:
    image: network-inspection:v5
    container_name: network-inspect
    restart: unless-stopped
    ports:
      - "${PORT:-9001}:8000"
    environment:
      - INSPECT_SECRET_KEY=${INSPECT_SECRET_KEY:?run setup.sh first}
      - INSPECT_DB_PATH=/app/inspection.db
      - INSPECT_READONLY_TOKEN=${INSPECT_READONLY_TOKEN:-}
      - PYTHONUNBUFFERED=1
      - TZ=Asia/Shanghai
    volumes:
      - ./inspection.db:/app/inspection.db
      - ./configs:/app/configs
      - ./reports:/app/reports
      - ./logs:/app/logs
      - ./data/cases:/app/inspection-platform/backend/data
      - ./data/ca:/app/inspection-platform/data
    command: >
      sh -c "touch /app/inspection.db &&
             python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000"
```

> 注意: `INSPECT_SECRET_KEY` 一旦使用不能换 (换了库里设备密码全部无法解密);
> 从旧服务器迁移时先把旧密钥填进 `.env` 再跑 setup.sh。

### 初始管理员密码 (全新库首启)

挂载已有 DB 时密码不变; **全新库**首启生成 22 位随机密码写入容器内文件:

```bash
sudo docker exec network-inspect cat /tmp/inspect_initial_admin_password
# 或在 .env 预设 INSPECT_INITIAL_ADMIN_PASSWORD=<密码> 再首启 (不生成文件)
```

登录改密后删除: `sudo docker exec network-inspect rm /tmp/inspect_initial_admin_password`

### 构建镜像

```bash
cd /home/ivan/network-inspection     # 必须在此目录 (构建上下文)
sudo docker build -t network-inspection:v6 -t network-inspection:latest .
sudo docker save network-inspection:v6 -o network-inspection-v6.tar   # 导出分发
```

依赖层与代码层分离, 改代码重建约 3 秒 (pip 层 135MB 命中缓存)。

### 跨服务器部署流程

```
源服务器 (192.168.26.53)              目标服务器
─────────────────────────            ─────────────────────────
docker build -t network-inspection:v6
docker save -o network-inspection-v6.tar
                                       ↓ scp 传输 (镜像 + compose + setup.sh + .env.example)
                                    docker load -i network-inspection-v6.tar
                                    ./setup.sh && docker compose up -d
```

### 容器内路径映射

| 宿主机 | 容器内 | 用途 |
|--------|--------|------|
| `./inspection.db` | `/app/inspection.db` | SQLite 数据库 (WAL) |
| `./configs/` | `/app/configs/` | 设备配置备份 |
| `./reports/` | `/app/reports/` | 巡检报告 |
| `./logs/` | `/app/logs/` | 日志文件 |
| `./data/cases/` | `/app/inspection-platform/backend/data/` | Case 附件 |
| `./data/ca/` | `/app/inspection-platform/data/` | CA 证书材料 |

### 常用管理命令

```bash
sudo docker compose ps                     # 状态
sudo docker compose logs -f                # 日志
sudo docker compose restart                # 重启
sudo docker compose down                   # 停止
sudo docker exec -it network-inspect /bin/bash   # 进入容器

# 更新: 构建新标签 → 改 compose 的 image: →
sudo docker compose up -d
```

### 从阿里云镜像仓库拉取 (备选)

```bash
docker pull crpi-onapv500ctq06zb5.cn-hangzhou.personal.cr.aliyuncs.com/ivannetwrok/networkauto:latest
```

> 注意: 仓库镜像可能落后于本地 v5, 以构建记录文档中的标签为准。

### Docker 网络不通的解决方案

Dockerfile 已配置阿里云 PyPI 镜像。apt 源也可替换:

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


---

---

## 安全修复记录 (2026-06-14)

基于全项目代码审查修复的 8 项安全问题：

| # | 文件 | 修复内容 |
|---|------|----------|
| 1 |  | 路径穿越防护：拒绝  和路径分隔符，校验父目录，添加  认证 |
| 2 |  | 添加  响应头 |
| 3 |  | 修复镜像名为 ，挂载  防止密钥丢失 |
| 4 |  |  字典写入添加  锁保护，消除并发竞态 |
| 5 |  |  中  添加  锁保护 |
| 6 |  | Session Cookie 添加  和  属性 |
| 7 |  | 修复旧格式 SHA256 密码验证路径：PBKDF2 仅匹配 64 位 hex salt，旧格式可正常升级 |
| 8 |  | 添加  注释说明不可加  后缀（会破坏已有加密密码） |

| 9 | inspection.py | 5处 datetime.now() 改为 datetime.now(CST_TZ)，备份文件名和报告时间使用北京时间 |
| 10 | config_backup.py | backup_now 和 export_zip 使用 now_cst()，list_backups 显示 fromtimestamp(tz=CST) |
| 11 | models.py | 修复 salt 长度检查 64->32（16 bytes hex = 32 chars），恢复 PBKDF2 密码验证 |
| 12 | auth.py | 移除 secure=True，应用运行在 HTTP 上不需要 HTTPS cookie |

> 验证通过 (2026-06-14 12:17 CST): 登录/登出/认证/备份时间/文件名时间戳 全部正常。

---

## 数据库损坏事件与恢复 (2026-06-16)

### 事件时间线

| 时间 | 事件 |
|---|---|
| Jun 11 09:03 | 首次崩溃：两个 uvicorn 进程同时写入 inspection.db，WAL 文件开始膨胀 |
| Jun 11 09:03 ~ Jun 16 03:29 | 1472 次崩溃循环（systemd Restart=always + RestartSec=5 紧循环） |
| Jun 16 03:29 | systemd 手动重启停止循环 |
| Jun 16 12:30 | 用户报告 Dashboard Internal Server Error |
| Jun 16 12:34 | 诊断确认：database disk image is malformed |
| Jun 16 12:38 | 修复：.dump → 修改 ROLLBACK→COMMIT → Python executescript 重建 |
| Jun 16 12:42 | 全部 13 模块验证通过 |

### 根因

**两个 uvicorn 进程并发写入同一 SQLite 数据库：**

- PID 300863：手动 `python3 -m uvicorn --reload` 启动，运行 2+ 天
- PID 353870：systemd `network-inspect` 服务

SQLite WAL 模式支持多读单写，两个进程同时写入导致：
- Freelist 大小不匹配（实际 4183 ≠ 应有 4675）
- Tree 6 (inspection_runs) overflow list 长度错误
- 重复页引用 (page 3624)
- 90+ 个孤儿页
- WAL 文件膨胀至 14 MB（正常应 < 1 MB）

### 恢复结果

| 表 | 恢复前 | 恢复后 | 丢失 |
|---|:---:|:---:|:---:|
| devices | 7 | 7 | 0 |
| users | 3 | 3 | 0 |
| inspection_runs | 21 | 18 | 3 |
| alert_rules | 2 | 2 | 0 |
| alert_history | 2 | 4 | 0 |
| inspection_schedules | 3 | 3 | 0 |
| custom_commands | 3 | 3 | 0 |

**完整性检查: ok**

### 预防措施

| 层级 | 措施 | 文件 |
|---|---|---|
| Python 应用层 | `flock` 单例锁 (`/tmp/network-inspect.lock`)，启动时获取排他锁 | `main.py` |
| Python 应用层 | `PRAGMA integrity_check` 启动检查，损坏时 FATAL 退出 | `main.py` |
| systemd | `Restart=on-failure`（替代 `always`），避免无差别重启 | `network-inspect.service` |
| systemd | `StartLimitBurst=5` + `StartLimitIntervalSec=120`，2 分钟内最多 5 次重启 | `network-inspect.service` |
| systemd | `RestartSec=10`（替代 `5`），给 WAL checkpoint 留足时间 | `network-inspect.service` |
| 运维规范 | 永远使用 `systemctl restart network-inspect`，禁止手动 `uvicorn --reload` | CLAUDE.md |

## 只读 Token 免密访问 (T1 集成)

供 T1 等外部系统嵌入链接 / 免登录查看的**固定只读 Token**。携带有效 Token 的访客无需账号即可浏览各页面, 但**只能查看, 不能做任何增删改**, 且配置备份、拓扑等敏感数据区对其封闭。

### 配置 (token 不入 git)

Token 值只写在 systemd unit 里, 仓库中不出现:

```ini
# /etc/systemd/system/network-inspect.service  [Service] 段
Environment="INSPECT_READONLY_TOKEN=<token 值>"
```

改后 `sudo systemctl daemon-reload && sudo systemctl restart network-inspect`。**置空 = 整个功能关闭**。

### 使用方式

```
http://<服务器>:8000/cases/2?token=<token 值>     # T1 嵌入链接 (任意页面都可带)
curl -H "X-Readonly-Token: <token 值>" ...        # 程序调用
```

首次带 `?token=` 访问后, 服务端自动种下 `inspect_rt` Cookie (httponly, 30 天), 之后站内点击跳转、下载文件无需再带参数。

### 权限约束 (中间件 + 路由双层强制, 不依赖各路由自觉)

| 请求 | 结果 |
|---|---|
| GET/HEAD 浏览页面、Case 文件下载、CA 公开证书 (crt/root) | 200 正常 |
| 任何 POST/PUT/PATCH/DELETE | 403 (中间件层) |
| `/users*`、`/change-password*` | 403 (中间件层) |
| CA 私钥材料下载 (`/download/pem`、`/download/p12`) | 403 (中间件层) |
| 配置备份 (`/config-backup*` 页面/列表/下载/导出 ZIP) | 403 (路由层 `require_full_user`) |
| 网络拓扑 (`/topology` 页面 + `/topology/data`) | 403 (路由层 `require_full_user`) |

- Token 校验用 `hmac.compare_digest` 常量时间比对 (防时序侧信道)
- 通过 query 参数使用 token 的访问会记日志 (`read-only token access: <path> from <ip>`)
- 合成访客身份 `T1访客(只读)`: `is_admin=False`, 可通过 `require_auth`; 但涉及敏感数据的接口用 `require_full_user` 将其排除 (配置备份含设备凭据材料, 拓扑数据含各设备完整 raw_data)
- 持有 token = 可见系统内全部数据, 仅发可信方; 公网场景务必配合 HTTPS (否则 token 明文出现在 URL)

## 安全说明

- ✅ 设备密码使用 Fernet (AES-128-CBC + HMAC) 加密存储
- ✅ 用户密码使用 PBKDF2-SHA256 (600,000 迭代) 哈希
- ✅ Session Cookie 设置 `httponly` + `samesite=lax` 标志 (防 XSS 窃取 / CSRF)
- ✅ 统一密码策略: ≥8 位 / ≤128 位 / 非纯空白, 添加/修改/重置三入口同一校验
- ✅ 改密/重置/删除用户后自动吊销该用户全部会话 (被盗会话随旧密码失效)
- ✅ 管理员接口统一 `require_admin` 依赖 (非管理员 403)
- ✅ 只读 Token 免密访问 (T1 集成): 中间件强制仅 GET/HEAD + 敏感路径黑名单, token 仅存 systemd unit 不入 git, 常量时间比对 (详见「只读 Token 免密访问」节)
- ✅ 登录失败统一提示 + 虚拟哈希时序均衡 (防用户名枚举)
- ✅ 所有 API 端点强制认证 (`require_auth` 依赖注入)
- ✅ 告警规则运算符服务端验证 (仅允许 `>` `>=` `==`，非法运算符返回 400)
- ✅ 密码加密存储 (Fernet AES-128-CBC + HMAC)
- ✅ 日志系统敏感字段脱敏: password/secret/token/key 自动替换为 `***MASKED***`
- ✅ 支持明文密码自动迁移: 启动时检测并加密旧密码
- ✅ 加密密钥文件权限 600
- ✅ 旧格式 SHA256 密码自动兼容 — 登录时检测并自动升级为 PBKDF2-SHA256
- ✅ 单例锁 (flock): 阻止多个 uvicorn 实例同时运行，防止多进程并发写入损坏 SQLite
- ✅ 启动数据库完整性检查 (PRAGMA integrity_check): 发现损坏立即退出并打印恢复指引
- ✅ systemd 崩溃循环保护: Restart=on-failure, StartLimitBurst=5, StartLimitIntervalSec=120
- ✅ WAL 定期 checkpoint: 每日清理任务执行 PRAGMA wal_checkpoint(TRUNCATE), 防止 WAL 文件无限膨胀

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

## 优化记录
### 热修: 批量巡检 0/7 冻死 — T1 搬迁残留越界相对导入 — 2026-08-24

- 现象: W3 部署后手动批量巡检, 进度面板永远停在「巡检中 0/7」, 7 张卡片全部冻结在初始 等待中/CPU=… 状态, DB 无任何新结果行
- 根因: T1 把 `_inspect_one` 从 `routers/inspect.py` (包层级 `backend.routers`, `..engine` = `backend.engine` 合法) 上搬到 `backend/inspection_runs.py` (包层级 `backend`, 顶层包), 函数体内的惰性 import `from ..engine.inspector import run_single_device` 未随层级改点 — `..` 越出顶层包, 7 个 worker 一进来就 ImportError, 异常发生在任何 `_bump_done` 之前 → done 永不推进; `import backend.main` 启动探针抓不到函数体内的惰性 import, 今早 06:00 定时巡检跑的还是旧代码, 直到用户手动触发才暴露
- 修复: 该行改单点 `from .engine.inspector import run_single_device` (backend.engine 同包子模块)
- 部署流程补强: 部署探针新增「惰性 import 运行时探针」— 在模块上下文 exec 函数体内的 import 语句, 此类「启动探针漏网、运行即炸」的层级错误今后在部署时即被拦截
- 验证: 服务器端先复现 ImportError (确认根因) → 部署后探针全绿 → admin 触发 7 台全量: 15.3s 4/7 → 18.4s 6/7 → 142.7s 7/7 全部 connected, DB 新增 7 行 (id 161-167); 附带量化: 192.168.10.47 单台 ~124s (慢尾设备), 其余 6 台 15s 内完成 — 修复后整批 ~2.5 分钟属正常, 面板恢复实时跳动 (⏳→✓)

### 全项目 /code-review 修复 W4: 索引/效率 5 项 — 2026-08-24

- E1 `routers/config_backup.py` export_zip: ZIP 先落临时文件再分块流式回传, BackgroundTask 收尾清理 — 此前整个 ZIP 在内存 BytesIO 里攒齐才回第一个字节, 内存峰值 = 全部 .cfg 之和, 且 StreamingResponse 包已成型缓冲并不流式
- E3 `ai_engine.py` 限流等待: 按算出的等待时长整段分片睡, 睡满回循环复查一次 — 此前每 1s 重查一次限流计数, 一次 60s 等待最多 75 次 DB 聚合查询+锁往返; 切片 (≤5s) 保持等待期间的会话删除响应
- E4 `main.py` LoginMiddleware + `routers/auth.py`: 会话校验只查内存 _sessions 表 (不再为它开 DB 会话 + PK SELECT), user_id 挂 request.state 由 get_current_user 复用 — 每请求从「中间件查一次 + 路由再查一次」降为整请求一次 SELECT; validate_session (唯一调用方即中间件) 随之删除
- E5 `routers/ping.py`: 扫描两段式探测 (先 1 探判活, 活主机再 4 探取时延统计) — /24 扫描从 254×4 包/子进程降为 254×1 + 活主机×4, 不可达段每台少烧 3/4 探测时间; ping_one 增 count 形参
- E6 `models.py` + 一次性 DDL: ai_messages(session_id,seq) / ai_actions(session_id,executed_at) 复合索引 — 限流计数与消息序号是每条 AI 工具命令的热点查询, 此前全表 SCAN + 临时 B-TREE; create_all 只给新建表带索引, 已有表停服窗口显式 CREATE INDEX IF NOT EXISTS, 现 _next_seq 走 COVERING INDEX、recent_exec_rows 走 INDEX SEARCH

部署: 6 文件 trickle+md5+AST+import 探针全绿, 重启两次 (代码波 + 建索引停/启); live 验证 PASS (未登录 303 → 登录全页面 200 / stats 片段 / ping 两段式 2/2 Up / export-zip 200 且 12 条 .cfg zip 完整 / /tmp 无残留 cfgbak_*)。

### 全项目 /code-review 修复 W3: 重复收敛 17 项 (R/S/T 三组) — 2026-08-24

**R 组 (重复定义单点化)**

- R1 `custom_cmds.py`: PLATFORM_TYPES 平台目录 (14 项) 单点定义 + platform_types() 统一读取, 各处手抄目录收敛
- R2 `routers/ai_assistant.py`: 14 处 `_api_404` 手抄块 → 共享助手
- R3 `routers/config_compare.py`: CONFIG_DIR 改引引擎 `inspection.CONFIG_DIR` (模块级 sys.path 注入), 不再手抄路径常量
- R4 `routers/devices.py` + `templates/devices.html`: 设备页平台下拉由 PLATFORM_TYPES 注入渲染 (此前 14 项模板硬编码, 自定义命令页加平台而本下拉漏加)
- R5 `routers/reports.py`: 新增 `_load_run` — 4 处 run+raw_data 加载重复收敛, 顺带 404 语义一致
- R6 `main.py`: 新增 `_dashboard_core` — dashboard 与 /api/stats 两处统计口径单点

**S 组 (引擎解析单点化)**

- S1 `inspection.py`: 新增 `_find_output(sections, cats, min_len, match, require_kw)` — cpu/mem×2/power×2/raid/disk/nic 六处扫描循环单点; 此前六份内联手抄且 ERROR 守卫已漂移 (raid/disk/mem 二遍没挡, 长错误串 len>100 被当磁盘/RAID 清单喂进解析器产出幻觉数据)
- S2 `inspection.py`: PSU_OK_WORDS (补 healthy) + `_psu_status_fallback` + `_dimm_summary` — PSU 好词表与 DIMM 汇总此前 parse_server_* 与 parse_idrac_* 两份手抄且已漂移 (hp_ilo/lenovo "Healthy" 电源曾被计为故障)
- S3 `routers/reports.py` export_html: 段落输出 `_coerce_section_output` 归一 + 超 300 行截断标记 (此前超长输出全量塞单格)
- S5 `routers/vram_calc.py` + `_vram_result.html`: BASE_OVERHEAD/SCENARIO_MULTIPLIERS 单源, 对照表逐档直接调 calc_vram, 公式行经 context 引用 (此前三处各抄一份, 调参即静默分叉)
- S6 `routers/vram_calc.py`: calc_vram 惰性形参 (multi_gpu 分支恒真) 移除, 乘数改返字段

**T 组 (跨模块私有引用收敛)**

- T1 新建 `backend/inspection_runs.py` (~380 行): _progress 注册表/_inspect_one worker (原 routers/inspect.py) 与 _init_progress/_light_device_rows/_run_batch (原 routers/scheduler.py) 全部落位 — 两个路由模块靠函数级延迟 import 互取对方私有名的双向耦合消除, 引用方向单一化 (routers+main → inspection_runs)
- T3 `constants.py` PENDING_STATUS + `templating.py` Jinja 全局 + `base.html` 引用 — 「等待中」魔串单点 (constants 为叶子模块, 不引入循环)
- T4 `routers/ca_server.py` PRIVATE_KEY_DOWNLOAD_SUFFIXES + `main.py` _readonly_blocked 改 endswith 锚定 — 只读黑名单后缀与路由定义同源, 路由改名不再静默漏拦
- T5 `routers/auth.py` _ensure_full_user — require_full_user 与 change-password 双生路由的只读拒绝判定单点
- T6 `inspection.py` CMD_SYNTAX_ERRORS (9 种) 单点 — 引擎告警/回退两站点与 ai_engine 纠正提示 (惰性 import) 共用; 此前四处各抄且已漂移 (AI 侧只认 2 种, "% Ambiguous" 类拒绝得不到纠正提示连续盲猜)
- T2 (403 detail 常量) 核查后确认 W1 已落, 无需改动

部署: 21 文件 (18 py + 3 html) trickle+md5+AST + `import backend.main` 循环导入探针 + 引擎函数探针全绿, 重启一次; live 验证全 PASS (login/dashboard 等待中图标渲染/devices 平台下拉 14 项/config-compare/vram POST 公式行 ×1.2×4/inspect 404/只读 pem 403·crt 200/七页面 200)。

### 全项目 /code-review 修复 W2: 次级正确性 8 项 — 2026-08-24

- B6 `database.py`: PRAGMA busy_timeout 5000→30000, 与 connect_args 的 timeout:30 对齐 (此前 PRAGMA 后执行悄悄把「等锁 30s」覆盖成 5s, 并发写提前抛 locked); auth.py 用户管理四个写点 (改密/建用户/重置/删除) 裸 commit 换共享 commit_with_locked_retry 重放闭包, 失败友好回显不再 500
- C4 `custom_cmds.py`: execute / execute-batch 单设备执行入库改 commit=False + 重试闭包 (与 execute_multi 同策), 失败降级 persist_error 页面提示 (复用既有模板槽); 渲染列表查询换 query_or_empty 降级; 无调用方的 _save_inspection_run 包装删除
- C5 `config_push.py /preview`: device_ids 改 list[str] 容错解析 (空勾选字段整体缺失时 list[int]=Form(...) 抛裸 422, 走不到「请至少选择一台设备」提示) — live 验证 200 友好页
- A1 `inspect.py`: 新增 _bump_done — done 递增与身份守卫同临界区, 并发 worker 的 read-modify-write 丢更新会让 done 永远追不上 total (前端轮询卡死); 两调用点迁移
- A2 `engine/topology.py`: parse_cdp 的 Port ID 行 re.match→re.search, IOS 合并行 "Interface: Gi0/1,  Port ID (outgoing port): Gi0/24" 的 remote_port 此前行首锚定永不命中
- A5 `engine/topology.py`: 新增 _summary_neighbors 表头驱动摘要解析 (2+ 空格分列, 按列名取值) — NX-OS CDP 摘要表头曾被 detail 解析器当邻居产出垃圾; XR/Arista/Ruijie/Juniper 的 LLDP 摘要此前整段丢不开或掉进华为位置兜底把主机名当 local_port; detail 与华为 brief 路径回归不破 (探针 7 例全过)
- A6 `scheduler.py`: once 空日期的「今天」改按 CST 取 — 服务器 UTC 时 naive now() 在 CST 0~8 点给出昨天, 用户约今天被判过去 (+1 天顺移甚至 PastDateError)
- A4 `inspection.py parse_idrac_power`: InstanceID 块型门控 (in_psu_block) — System.Embedded.1 块的 Model=PowerEdge R740 / Power Capacity 此前混入 psus 显示幽灵电源 ("PowerEdge" 含 "power" 连关键字过滤都拦不住); getsensorinfo 无 InstanceID 路径保持原行为

部署: 8 文件 trickle+md5+AST, 重启一次; 无写验证 22 项全 PASS (结构 8 + 函数探针 11 + live 3), journal 零 Traceback。

### 全项目 /code-review 修复 W1: 正确性 10 项 — 2026-08-24

8 角度 41 候选 → 31 CONFIRMED / 9 PLAUSIBLE, 分 4 波修复; 本波为正确性 10 项:

- C1 `alerts.py /alerts/add`: device_id 改 str 容错解析 (空串/非数字 → None=全局规则), 修复「All 设备」勾空框提交 422、全局告警规则从 UI 不可达 (已验证: 三形态 POST 303 落库, 测试行建后即删、计数复原)
- C2 `custom_cmds.py execute_multi`: as_completed 换 config_push 同款 wait+deadline 轮询 (并发 min(10, 设备数)), 挂死线程不再永久阻塞请求; 超预算结果标记「结果未知请人工核对」
- B2 `main.py` 单例锁: O_CREAT|O_NOFOLLOW (win32 豁免) 替代裸 open("w"), /tmp 符号链接劫持不再截断/伪造锁 (探针: ELOOP 拒绝且目标文件未动)
- B3 `main.py` 未登录重定向: quote(request.url.path) 编码 CJK 路径, 修复 latin-1 响应头 500 (live: /网络网络 → 303, next 参数已百分号编码)
- A3 `inspection.py parse_server_mem`: 显式捕获 MB|GB 单位, 512 MB 不再按 GB 虚增 (探针: 512MB+256GB+无单位512 = 768GB, 旧代码 1280GB)
- E2 `inspection.py` 命令循环: prompt 异常后置 prompt_bad 粘性标记, 后续命令直接走 send_command_timing, 不再逐条重试双超时
- B4 `ca_engine.py get_pem_zip`: CN 消毒为安全文件名 (非法字符→_, 去头尾 ./_), 堵 zip-slip 路径穿越 (探针: ../../tmp/evil → tmp_evil.crt/key)
- C3 `config_backup.py backup_now`: finally 兜底 conn.disconnect(), 对端不回显时不再泄漏 SSH 连接
- B5 `ca_server.py create_root/issue_cert`: 异常 rollback + 已落盘密钥/证书 unlink 善后 + 模板错误条回显 (探针: 非法请求 200+错误条, 不再 500 或留孤儿密钥)
- S4 `topology.py` 告警联动: 补 silence_until 静默判断与 operator 映射 (此前静默规则仍标红)

部署: 10 文件 trickle+md5+AST 校验, 重启一次; journal/应用日志零 Traceback/ERROR。



### 低优先级清理波: 重复代码收敛 + 死代码清扫 (13 项) — 2026-08-24

多轮评审累积的低优先级清理项一次收敛, 以零行为变化为原则 (两处语义对齐已注明):

1. **「密码解密失败(密钥不匹配)」7 处手抄 → `crypto.DECRYPT_FAIL_MSG` 常量** — raise 方 (ai_session.DeviceSessionPool) 与 config_backup / config_push / custom_cmds / inspect / ai_assistant 的失败结果与翻译表全部引用单一定义, 消除 UI 提示、审计存储、翻译表三处各自漂移的风险。
2. **AI 限流计数双份过滤条件 → `ai_engine.recent_exec_rows`** — `_rate_wait` (show 路径) 与 `confirm_action` 复检共用同一查询口径 (executed_at 窗口 + executed/confirmed/failed 三态); 此前两份手抄过滤条件, 改其一不改其二会让两个限流器口径分裂。
3. **DOCX/PDF 导出双份转换/截断块 → `reports._coerce_section_output` / `_trunc_marker`** — H7 类型强制转换与 H4 截断标记的两份手抄收敛为共享助手。
4. **mtr 子进程调用双份 → `ping._run_mtr`** — do_trace 与 ping_post 的命令行拼装、每轮 ~1s+20s 超时、stdout+stderr 合并口径单点化。
5. **手动巡检执行器双副本删除, 并入 `scheduler._run_batch`** — `_run_inspection_sync` 整套手抄 (线程池 + _inspect_one + 每设备 300s + 退休清理) 删除; trigger_inspection 改用 `_light_device_rows` 轻量行 (id/ip, 不再物化含加密密码列的全量 ORM 行) 并复用 _run_batch; 线程池上限两套 (定时 100 / 手动 MAX_WORKERS) 统一为 inspect.MAX_WORKERS (2*cpu 封顶 50); 起止日志统一在 _run_batch (手动/定时/run-now 三条触发路径运维痕迹一致)。
6. **run_now 双写 last_run → 单一写入点** — 请求线程的预写 (裸 commit + 整段兜底) 删除, 工作线程跑完后统一回写, 与定时路径同语义 (last_run 记完成时刻), 也消除了两线程对同一字段的并发写。
7. **`_classify_403` 字符串等值耦合 → `auth.ADMIN_REQUIRED_DETAIL` / `READONLY_DETAIL` 常量** — raise 点 (require_admin / require_full_user / 改密双路由) 与 main 的分类比较共用; detail 改文案不再让浏览器友好 403 页错类渲染、T1 监控标记挂错。
8. **StaticCache / Lang 两个简单中间件转纯 ASGI** — 直接包装 send/receive, 不再经 BaseHTTPMiddleware 的每请求 anyio 任务 + 内存流 (各省一层任务开销); LoginMiddleware (重度依赖 call_next) 保持不动。
9. **`backup_host_prefix` 双定义收敛到引擎** — 定义点移入仓库根 inspection.py (引擎是更底层, 不能反向导入 backend), backend/helpers 延迟 import 转发; 此前「逐字节相同的手抄副本」同步义务消除。
10. **topology showNode 局部 `badge` 字符串遮蔽全局 `badge(n)` 图标函数** — 改名 statusBadge; 弹层内未来再调 badge(...) 会按字符串调用抛 TypeError 的潜在陷阱排除。
11. **pyflakes 全树清扫 16 处死代码** — 死导入: auth.SessionLocal、bom.json、config_compare.HTMLResponse、config_push.RedirectResponse、custom_cmds.OperationalError、inspect.datetime+SessionLocal+ThreadPoolExecutor、reports.Query/Inches/Emu/TA_LEFT/TA_RIGHT/KeepTogether、scheduler._json+HTTPException、engine/topology.json; 死变量: custom_cmds.start_time、reports.r4/mem_color/PDF 侧 GRAY100+GREEN+RED、vram_calc.multiplier+vram、main 与 inspection 的未用 except 绑定。main._logger_setup (副作用导入, 已注明) 有意保留。
12. (有意不动) ai_engine._exec_show 等待循环的 1Hz 分片 sleep + db.refresh — 注释明确记录为「等待期保持删除响应性」的设计, 非浪费。

**验证 (38 断言全绿)**: 结构断言 17 项 (各单点定义/常量引用文件清单/中间件继承关系/双副本删除确认) + 21 页 200 且零 BOM + `/static` 响应 `Cache-Control: no-cache` (纯 ASGI 生效) + en 模式标题切换 (LangMiddleware 纯 ASGI 生效) + mtr 真跑 200 带 hops 表 (_run_mtr 单点) + config-backup 200 (helpers→引擎 sanitize 转发生效) + 只读 token 三页零写按钮 + **单台真机巡检 (vpn 172.16.1.1) 走合并后 _run_batch 全链路 connected** (InspectionRun 落库 connected|39%|55.8%, 统一起止日志 start=1/done=1) + journal 零 Traceback + 应用日志零 ERROR + Playwright 8 个改动关联页零 pageerror。

### 全库评审甄别修复（7 项，误报与有意设计项除外）— 2026-08-23

多轮全库 code review 产出的发现逐条本机核实后分三类处置：**误报**（`_parse_mtr` 正则实际 9 组/9 名/7 列正确；`_exec_show` 等待期设备删除被 ORM expire_on_commit 天然拦截；esc 竞态已由 d70e16b 修复）、**有意设计**（qc_webhook http 出站策略、p12 密码默认值移除、/reports/api 去 raw_data、每日 6 点兜底条件等，均有文档）、**证实修复**（本条目）：

1. **config_push 超时路径 CancelledError 500** — 全局超时后 `cancel_futures` 取消的任务 `done()` 也为真，先进 `_harvest` 导致 `f.result()` 抛 `CancelledError`（BaseException，逃逸 `except Exception`）→ 整个 execute 500、已收集结果丢弃、剩余设备无审计；"未执行 (可安全重试)" 分支为死代码。`cancelled()` 改为先于 `done()` 判断。
2. **ping IPv6 CIDR → 500** — `ip_network` 接受 IPv6，展开的 v6 串在 per-part try 之外被 `IPv4Address` 排序键抛 ValueError。排序键容错（v4 → v6 → 字符串三级）。
3. **11 个模板 UTF-8 BOM 剥离** — adhoc/alerts/cases/case_categories/ca_server/config_compare/ping/scheduler/vram_calc/_ca_certs/_ca_roots 每次渲染响应头多 EF BB BF，htmx fragment 交换往 DOM 注入零宽字符。字节级剥离后全目录零 BOM。
4. **三页按钮门控**（与 H1 同类）— devices 的 添加/编辑/删除、custom-commands 全部写表单、ca-server 签发/吊销/删除/PEM/P12：对应端点此前已升 require_admin/require_full_user，但按钮对非管理员照常渲染（点击 403 且表单输入丢失）。路由补传 `user`（含 7 处 htmx fragment 再渲染点，管理员操作后按钮不消失），模板按 `user.is_admin` 门控；CRT/根证书下载为 require_auth 保持可见。
5. **subnet 分割模式回显** — POST 渲染上下文缺 `split_mode`/`new_prefix`，按数量分割后下拉弹回"按前缀"、输入框清空，下次提交会在无感知下按前缀分割。上下文补齐两字段。
6. **reports.html 本地 triggerInspect 死代码删除** — base.html chrome 块的共享版（更完善）恒覆盖本地副本，且本地版错误提取只有单键 `detail` 已漂移。
7. **export_csv 补 `defer(raw_data)`** — 此前 500 行全量物化（每行原始巡检 JSON 可达数百 KB）只为写 8 列 CSV，与同文件 list_runs/reports_page 对齐。

**验证**：页面响应字节级零 BOM（8 页）+ admin/只读 token 双视角门控（devices/custom-commands/ca-server 共 6 断言）+ subnet count 模式回显与输入保留 + POST /ping `2001:db8::/126` 200（不再 500）+ export_csv 表头 + config_push cancelled/elif-done 结构断言 + journal 零 Traceback + 21 页冒烟全 200。

### base.html 共享 JS 助手上移 head（esc 竞态，全模块健康检查发现的真实 bug）— 2026-08-22

`esc`/`apiErrorText`/`alertOnErr`/`toggleAll` 四个共享纯函数此前定义在 body 末尾的 `{% block chrome %}`（渲染在 `{% block content %}` **之后**），而部分页面的 content 脚本在 HTML 解析期就发起 fetch（config_backup 的 `loadBackups()`、ai 页的 `loadDevices()`/`loadSessions()` 等），其异步 continuation 在暖连接下先于 chrome 块脚本执行——`esc` 尚未定义 → `ReferenceError: esc is not defined`（unhandled rejection）→ 备份表/会话列表**静默不渲染**，用户只能靠手动筛选或刷新碰运气。

生产复现（Playwright 每页 8 次加载）：/config-backup **8/8** 全中、/ai 8 次共 **309 个** pageerror（会话轮询每 tick 都失败）；/adhoc 同类风险当时未触发。此前未暴露是因为冷连接下 chrome 脚本恰好先解析完——纯时序运气。

**修复**：四个函数上移 `<head>`（`t()` 旁，head 脚本本就承诺「chrome 块脚本早于 body 末尾执行」的更早位置），chrome 块只留巡检面板/轮询等 DOM 相关脚本。单文件改动，各函数仍仅一处定义。

**验证**：修复后 /config-backup、/adhoc、/ai 各 8 次加载 **0 pageerror**；21 页冒烟全 200；全量健康检查（服务/journal/应用日志/磁盘/SQLite quick_check/业务数据/APScheduler/21 页/JSON API/只读 token/浏览器零 pageerror）除本提交前的工作区未提交项外全绿。

### 巡检报告模块评审修复 (H1-H7) — 2026-08-22

1. **H1 删除端点权限加固 + 按钮门控** — `DELETE /reports/api/{id}` 与 `batch-delete` 从 `require_auth` 升 `require_full_user`（只读 token 的写请求本就被 LoginMiddleware 拦截，此为与 F 波先例一致的纵深加固，零行为变化）；列表页删除按钮/批量删除按钮此前对只读访客可见（点击才 403），现按 `user.id` 门控不渲染，`updateSelection` 相应加 null 守卫。
2. **H2 详情页内存分级与导出器统一口径（显示 bug）** — report.html 此前用 `|float` 手判（"N/A" 得 0.0 → 错显绿色 ok），是 `_mem_color` docstring「不再各自手判」漏网的第 4 个手判。现路由侧用共享 `_mem_color` 算好 `mem_class` 传入，与 HTML/DOCX/PDF 三导出器同一语义（N/A → 灰色 info）。
3. **H3 不存在的 run 统一 404** — `report_detail` 此前渲染 base.html 空骨架且状态 200，与导出端点 `raise 404` 不一致。
4. **H4 DOCX/PDF 截断标记** — 输出超 300 行截断此前无任何标记（与配置比较 P1 同类），现附「… (截断, 剩余 N 行)」标记行（随请求语言）。
5. **H5 列表页设备下拉窄列** — 全列 `query(Device)`（含加密密码列）改 id/ip/hostname 窄列。
6. **H6 小清理** — 单条删除的 `hx-confirm` 英文硬编码改为页面加载时按语言用 `t()` 设置；删 PDF 导出三连注释头迭代残留。
7. **H7 推送审计 run 导出 500（验证中新发现，真实 bug）** — Config Push 段的 `Success` 是 bool，DOCX/PDF 导出对它 `.split`/`.splitlines` 直接 AttributeError 500——所有推送审计 run 的 Word/PDF 导出一直必崩（HTML 导出本就有 `str()` 不受影响）。现非字符串值先转文本（bool/int → str，dict/list → JSON 串）。

**验证**：结构探针 + HTTP（admin 列表页按钮在 / 不存在 run 404 / N/A 内存 run #138 详情页 info 卡片 / run #138 DOCX 含截断标记且 PDF 200 = H4+H7 同测 / run 130 详情与三种导出回归）+ 只读 token 视角（页面 200 零删除按钮、DELETE 中间件 403）+ Playwright（hx-confirm 中英切换、零 pageerror）+ 21 页冒烟全 200。

### 配置推送模块评审修复 (G1-G6) — 2026-08-22

1. **G1 textarea 占位符 i18n 误用（真实 bug）** — 命令输入框此前用 `data-zh`/`data-en` 属性对，base.html applyI18n 对这对属性写 textContent，而 textarea 的 textContent 即实际内容：切换语言后说明/示例文字会变成输入框真实内容，用户不清空就预览会把这些文字当命令真正推送到设备。改用占位符专用对 `data-zh-ph`/`data-en-ph`（配置比较波在 base.html 新增的机制，第二个使用方）。
2. **G2 恢复配置抓取按平台取命令** — 推送前抓恢复参考此前硬编码 `show running-config`，非 Cisco 平台（Huawei 等）静默抓空 = 出问题时无恢复参考。现按 `DEVICE_PROFILES[device_type].backup_cmd` 取（与 config_backup 同款），无 profile 回退原值。
3. **G3 错误消息双语** — `_render_input` 9 处英文错误串改走 `T()`。
4. **G4 import 收敛** — netmiko 异常 import 提顶部；删 execute 内重复的 `import logging`/`getLogger`。
5. **G5 展示查询窄列** — 输入页/预览页/结果页的 4 处全列 `query(Device)`（含加密密码列）改 `_display_devices` 窄列；execute 保留全列（解密密码 + ORM 入库需要）。
6. **G6 文件/文本切换残留** — 选了文件再切回「粘贴命令」，残留文件仍随表单提交且服务端优先采用（用户以为推的是文本、实际推旧文件）。`toggleInputMode` 切回文本时清空 file input。

**验证**：结构探针 + HTTP 双语（zh/en 错误分支）+ Playwright（zh/en 占位符且 textarea 内容恒为空 = G1 修复证明；选文件切模式后文件清空 = G6）+ 真机推送回环（设备 1 推 `interface Loopback100 + description G2Verify` 成功、审计 raw_data 含非空 RecoveryConfig = G2 生效证明、随即 `no interface Loopback100` 回滚成功）+ 21 页冒烟全 200。

### 配置备份模块评审修复 (F1-F6) — 2026-08-22

1. **F1 手动备份改走共享写入** — `backup_now` 的 force 路径此前是第三套写入实现：无 chmod（含凭据的配置文件按 umask 644 世界可读）+ 轮换 bare unlink（删旧文件失败会在写入成功后误报「备份失败」）。现在与巡检备份共用 `inspection.write_config_backup`（命名/写盘/chmod 600/容错轮换单点），全平台只剩这一套写入语义。
2. **F2 import 收敛** — netmiko 异常 import 提模块顶部；删 `backup_now` 函数内重复的 `import inspection`（模块顶已有 `_insp`）。
3. **F3 筛选防抖 + 序号守卫** — 筛选输入原每按键发一次全量列表请求，现 300ms 防抖；快速输入时在途响应乱序到达会显示过时筛选结果，加序号守卫只接受最后一次响应。
4. **F4 设备列表 fetch 容错** — `/devices/api` 失败原静默（导出功能悄悄不可用），现提示「设备列表加载失败, 导出功能可能不可用」（双语）。
5. **F5 死代码** — 删除无调用的 `onDeviceSelect` 及其 onchange 属性。
6. **F6 防双击** — 立即备份按钮在途禁用（try/finally 恢复），双击不再并发触发同设备备份（同秒文件名会互相覆盖）。

**验证**：服务器函数探针（tmp 目录 `write_config_backup` 写盘+chmod 600 / 轮换 13→10 保最新 / `backup_config` 去重回归）+ HTTP（页面模板锚点 / 列表 API）+ 真机 backup-now 设备 1（32KB 新文件 stat 600、列表可见）+ Playwright en 模式按钮/占位 textContent、零 pageerror + 21 页冒烟全 200。

### 配置比较模块评审修复 (P1-P6) — 2026-08-22

1. **P1 静默截断警告** — 此前每侧配置截断到 2MB/5000 行无任何提示：两侧同点截断、差异在截断点之后时会误报 +0/-0「无差异」。现在截断发生时结果区显示警告横幅（「配置 A 过大， 仅比较前 5000 行」，双语），比较逻辑本身不变。
2. **P2 页面双语补全** — error 消息改走 `T()`；模板 `-- 从设备加载 --` / `或上传:` / `上下文:` / `比较结果` / `并排对比` / 行数单位补齐 data-zh/data-en；placeholder 经 base.html 新增的 `data-zh-ph`/`data-en-ph` 属性对双语化（与既有 title/aria 属性对同机制，config_compare 为首个使用方）。
3. **P3 设备下拉窄列** — GET/POST 两处 `query(Device)` 全列物化（含加密密码列）改为只取 id/ip/hostname/device_type，与 config_backup 页同款处理。
4. **P4 `_page_ctx(db)` 助手** — GET/POST 逐字重复的「设备 + 备份列表」页面上下文收敛单点。
5. **P5 `context_lines` clamp** — 下拉只给 0/1/3/5/8/999，构造 POST 可传负数/巨值，现 clamp 到 [0, 999]。
6. **P6 `import json` 提顶部** — 删 load_device_config 函数内导入。

**验证**：HTTP 实测 16 项（基本比较计数 / 无截断不显示警告 / 6000 行截断横幅 / 负数与巨值 clamp 不崩 / error 中文 / load-config 回归 / Playwright zh+en 双模式下拉占位与 placeholder textContent / 零 pageerror）+ base.html 共享变更后 21 页冒烟全 200。

### 巡检模块评审修复 (A1: 自定义命令复用巡检 SSH 连接) — 2026-08-22

**动机**：此前巡检主流程建连→采集→断开后，`run_commands_on_device` 对同一台设备**再开第二条 SSH 连接**执行自定义命令——每台启用自定义命令的设备每轮巡检付两次连接+认证开销（约 2-5s/台）。

**改动**（3 文件）：
1. `inspection.py` — `inspect_device` 新增可选 `extra_commands=[(label, command)]` 纯数据参数（engine 保持 DB 无关），自定义命令在主命令循环后随同一连接执行；逐命令容错语义与旧路径一致（`send_command_timing` read_timeout=30 delay_factor=2，失败 `[Error]`），section 追加在全部 profile 类别之后（报告展示位置不变）。
2. `engine/inspector.py` — `run_single_device` 透传该参数。
3. `routers/inspect.py` — `_inspect_one` 改用 `custom_cmds._cmd_pairs` 归一化（标签规则仍唯一定义处）后传入，删除第二段 SSH 与二次序列化（raw_data 由 engine 统一序列化）；「存储键不翻译」策略注释随 section 键移入 engine 侧。

**验证**：
- mock 连接探针 11 项（零写入）：全程仅一次连接 / 自定义命令在同连接按序执行 / 输出与 `[Error]` 语义 / section 居末位 / engine raw_data 含 section / 不传参兼容性。
- 真机 A/B 11 项：设备 1 (172.16.1.1) 新路径 run 128 vs 旧路径基线 run 124 — 自定义命令键集合一致、3 条命令输出逐条同类（成功/错误归类一致）、profile sections 集合一致、主 section 内容同类。
- 21 页冒烟全 200。（轮询中一次 RemoteDisconnected 为瞬断，服务无崩溃，run 正常完成。）

### 巡检模块评审修复 (A2/A3/C2) — 2026-08-22

1. **A2 `parse_idrac_nic` 删死循环** — 函数内原有两遍遍历：第一遍状态机（~30 行）的结果被 `nic_models.clear()` 显式丢弃后重跑第二遍。删除第一遍，行为零变化（合成 hwinventory 探针：NIC 聚合计数 / SSD 不误计 / FC HBA 按卡计一次 / 空输入 N/A 四例）。
2. **A3 `backup_config` size 快速路径** — 去重判断前先比文件大小：尺寸不同必已变化，跳过整文件读 + SHA256；尺寸相同仍走 hash 确认（同尺寸 ≠ 同内容）。Windows CLI 写文件有 `\n→\r\n` 转换，尺寸不可比，门控退回旧路径。tmp 目录探针 5 例：首写 / 相同去重 / 同尺寸异内容判变 / 异尺寸判变 / 判变后再次去重。
3. **C2 `version_output` 选取改写** — 原「预读 DESC_VERSION + 双重循环」逻辑改写为 `_first_long` + `or` 链，三分支语义显式化（基本信息长输出 → DESC_VERSION 短值回落 → 处理器类别）。新旧算法 8 例矩阵逐分支等价探针（含短值优先于处理器、20 字符边界等陷阱例）。

**验证**：服务器函数探针 14 项全过 + 21 页冒烟全 200。（探针过程中发现：同秒时间戳下 backup_config 同名覆盖属既有行为，与本次改动无关，未动。）

### 巡检模块评审修复 (B1/B2/B3) — 2026-08-22

1. **B1 备份保留策略统一** — 巡检引擎 (`inspection.py`) 原保留 5 份、手动备份 (`config_backup.py`) 原保留 10 份，同一 `configs/` 目录两个写入者互相截断。新增 `inspection.BACKUP_KEEP = 10` 常量，手动备份路径经 `_insp.BACKUP_KEEP` 共用，两路径策略一致（统一为用户选定的 10 份；去重机制下未变化配置不占份数）。
2. **B2 `_validate_routing_output` 删死参** — `device_type` 参数定义以来从未被函数体引用，两个调用点同步精简；路由输出验证行为不变（合法输出/日志垃圾/错误回显三例探针实证）。
3. **B3 `parse_idrac_power` 输出确定性** — `", ".join(set(statuses))` 集合迭代序不稳定导致同一设备相邻两轮 power 字符串不同序（报告显示抖动），改 `sorted(set(...))`；顺带删除累计后从未使用的 `total_watts` 死变量。

**验证**：服务器函数探针 12 项（BACKUP_KEEP 常量两路径共用 / 单参数签名 / 路由验证三例行为不变 / power 解析同输入两次输出一致 + 多状态有序拼接 `[Ok, Warning]`）+ 21 页冒烟全 200 + config_backup 列表 API 正常。

### 评审 cap 外清理 (5 项落地 + 1 项实证跳过) — 2026-08-22

**零影响清理，每项附实证**：

1. **topology.html 删本地 `esc` 拷贝** — 与 base.html canonical 同字符集；engine/topology.py 保证节点 id/label/ip/devicetype/status 全部非空（`String(s||'')` 与 `String(s)` 差异不可达）；esc 调用全在 fetch 回调/事件里，chrome 块 script 届时已定义。三重实证零影响，消除并行拷贝遮蔽未来全局加强的隐患。
2. **`alertOnErr` 入 base.html 共享** — alerts.html 两处逐字相同的 `resp.ok` 守卫收敛为 `if(await alertOnErr(r))return;`。（评审 finder 称 5 份拷贝为过时信息：config_backup/adhoc 的变体走不同显示通道——showStatus 双语前缀 / 带前缀 alert，非逐字重复，保留。）
3. **bom_matcher.py `import time` 提顶部** — 删 2 处函数内 `import time as _t`；模块级 identity 探针实证 `bm.time is time`。
4. **scheduler once 触发器单一比较点改写** — `dt < now - 1天 → PastDateError`；`dt < now → +1天`。与旧双重守卫逐例等价（例表探针 4 例：未来不变 / 今天过时顺移明天 / 昨天 24h 内顺移不抛 / 前天抛 PastDateError）。
5. **config_backup BMC 注释移位** — 从 decrypt 块上方移到 `netmiko_connect(...)` 正上方（注释描述的是驱动映射，与解密无关）。
6. **pool deleted-check 集中化 — 实证后跳过** — pool 层按设计是 DB 无关的，两个调用点需要不同响应（410 JSON vs LLM 提示文本），集中化会引入分层反转，非零影响，如实记录不做。

**验证**：服务器函数探针 7/7（once 例表 4 例 + bom 模块级 time + cache 写读清）；Playwright 11/11（21 页冒烟 200、topology vis 画布渲染 + 节点弹窗 esc 渲染路径 + 弹窗无 undefined/null 文本、alerts 页 `typeof alertOnErr === 'function'`、全程零 pageerror）。

- 2026-08-22: **评审深度修复 (review_diff_head2, 6 项, 需重启)** — /code-review (8 finder × 29 候选, 对照 HEAD 逐条实证: 4 项 77c8721 已修 / 3 项证伪 / 10 项上报) 后修复当前仍存 6 项: ①confirm_action S7 已删会话 410 分支不回滚 — 原子认领已提交 confirmed 后 db.refresh 见 deleted 返回 410, 卡片永久卡 confirmed (从未执行却审计 confirmed, 后续 confirm 一律 400 已处理); 修复: 回滚为 rejected 终态 + 审计留痕「会话已删除, 取消下发」+ confirmed_by/executed_at 清空 (会话已删卡片不可能再执行, rejected 诚实终态而非 pending 僵尸)。②config_compare load_device_config 的 read_text 裸奔 — mtime_safe 只修了排序键竞态, glob 与读取之间并发轮换/批删 unlink 仍 FileNotFoundError 直通 500; 修复: OSError 捕获按无备份回落巡检 run 配置。③delete_run 空 200 破坏 README 文档化的公开 API 契约 — 外部脚本 resp.json() 空体 JSONDecodeError 把成功误报失败; 修复: HX-Request 头分流 (htmx 空 200 保 outerHTML swap 契约, 非 htmx 返回 {"ok": true})。④改密 POST 只靠中间件按路径名黑名单 (GET 早有显式守卫) — 路由改名即静默暴露真实改密端点; 修复: POST 补同一 READONLY_VIEWER 403 守卫。⑤_PAST_DATE_MSG 字符串相等分类 — 抛出点与分类器靠消息文本耦合, 文案漂移即误分类; 修复: PastDateError(ValueError) 类型化, except 子类优先, 注册路径 except ValueError 兼容不变。⑥form_int 机制困在 scheduler.py — 提入 helpers 单点 (docstring 注明钳位语义不适用越界须报错的端口字段), scheduler 两处调用与注释切换; devices 端口归一化收敛为单次 port_s (保留越界报错语义不用钳位)。验证: 服务器函数探针 11 项 (悬挂软链复现 read_text 竞态不抛异常+真实备份阳性对照/只读身份直调改密 POST 403/过期 once 中英透传不冠前缀+真格式错误仍冠前缀+PastDateError 子类兼容/form_int 行为+scheduler 单点); HTTP 14 项 (delete_run 双契约/过期 once 303 闪现不落库/interval=abc 303 非 422/21 页全模块冒烟/只读 6 项); S7 竞态窗口函数级复现 5 项 (410+rejected+留痕+清空; 注: HTTP 先删后确认命中既有 404 早卫属正确行为, S7 窗口只能函数级复现); Playwright 8 页零 pageerror。

- 2026-08-21: **AI 助手: 降级协议文本落库修复 + 限流等待前端可见 (需重启)** — 复审模块又闭环两项: ①降级协议 (无 function-calling 模型走 ```run 块) 的 assistant 解释文本曾只在内存追加不落库 (configs 分支早已落库, shows 分支漏) — 刷新页面模型的话消失, 下一轮从 DB 重建的历史也缺这段, 模型看不到自己之前说过什么; 修复: shows 分支执行命令前先 _save_msg assistant 文本。②限流等待前端可见 — 上一波服务端等待重试上线后, 触发 6 条/分钟限流时用户端最长静默 ~60s 以为卡死; 修复: _exec_show 进入等待即 emit tool_wait 事件 (emit-only 不落库, 双语, 含倒计时秒数), 前端 handleSseEvent 新增分支复用思考提示条显示「命令频率限制 (6 条/分钟), 约 N 秒后自动执行」。验证: 生产探针 6 项 — 降级 run 块一轮后 assistant 文本+工具结果双双落库; 种子 6 条动作填满窗口后首个事件为 tool_wait (文案「约 11 秒后自动执行」), 等 10.1s 透明执行成功; 探针数据自清。

- 2026-08-21: **AI 助手三项优化: 轮次耗尽部分总结 / 厂商命令速查 / 语法错误纠正提示 (需重启)** — 继限流等待修复后对会话 57 剩余两根因与尾部失败的治理: ①轮次耗尽不再裸报错 — 8 轮用满后自动追加一条「轮次已达上限」指令并禁用工具再调一次 LLM, 模型基于已收集命令输出写出部分总结 (要求自标不完整), 经打字机推送并落库 assistant 消息, 流以 done 正常结束; 仅总结调用失败才回落原「工具调用轮次超限」错误。②系统提示词 (中英双模板逐条等意) 新增重试纪律 (命令报错/被拒绝不立即重试, 先 display ? / show ? 探查) 与分平台常用命令速查 (cisco_ios / huawei VRP / huawei USG 防火墙含 display security-policy rule all — 会话 57 连猜错 2 条的正确语法)。③_exec_show 检测 Unrecognized command / % Invalid input 输出时在返回文本尾部固定中文追加纠正提示 (随工具结果落库, 审计 AIAction.output 仍只存设备原始输出), 引擎层兜底不依赖提示词自觉。顺带: 打字机推送抽 _stream_text 助手去重。验证: 生产探针 11 项 — 双模板渲染含速查; Unrecognized 输出附提示/正常输出不附; 模拟 8 轮工具调用后第 9 次 LLM 调用 use_tools=False、总结推送+落库、无 error 事件; 探针数据自清。

- 2026-08-21: **AI 助手限流不再烧工具轮次 (需重启)** — 用户报「工具调用轮次超限, 已停止」; 会话 57 取证: 模型对 USG 防火墙 (ICI-FW, huawei) 猜错 2 条命令语法后探索 4 条, 触发 6 条/分钟限流, 「[被拒绝] 命令频率超限」文本返回后模型立即重试同一命令 4 次 — 每次拒绝都白烧一轮, 8 轮 MAX_TOOL_ROUNDS 耗尽空手停止, 而限流窗口过后同一命令 (display security-policy rule all) 实际成功取出 8 条安全策略。修复: _rate_ok→_rate_wait (返回距窗口放行的秒数, 计数策略不变仍按 executed_at 与 confirm 复检同口径), _exec_show 限流时服务端分片 sleep 等窗口放行后透明执行 — 拒绝不再返回给模型、不消耗工具轮次; 等待期间逐秒 db.refresh 保持删除响应, 75s 兜底返回原拒绝文本防异常自旋。验证: 生产探针 (种子 6 条 AIAction 填满窗口, 最早 50s 前) — 第 7 条等 10.2s 窗口放行后透明执行成功, 占位审计行正常落库, 探针数据自清。

- 2026-08-21: **评审修复 (6e700d9 回归审查, 6 项, 需重启)** — 对 1cd30ac+6e700d9 再做 /code-review (实际范围 e3ea8d3..HEAD, 本地 cr_sync_full 与 HEAD 逐哈希核对后直读实证; 5 CONFIRMED + 1 PLAUSIBLE): ①save_inspection_run dev=None 回归 — R10 统一入口后裸解 dev.id, inspect._inspect_one 设备查询失败路径 (K4 兜底) 的失败 run 永远落不了库; 修复: helper 新增 device_id 参数容忍 dev=None (旧码 device_id=dev_id + if dev 守卫语义回归), _persist 传入 dev_id。②过期 once 残留 stale next_run — B4 拒收只挡新增, 存量过期 once 启动注册失败 / toggle 先提交 enabled=1 再注册失败两条路径都留下过去的 next_run, 「启用但 next_run 为空」徽标被旧值骗过永不浮面; 修复: _register_and_persist 失败分支清空 next_run 另行提交, load_all_schedules 单条失败同步清空。③巡检按钮全站门控 — POST /inspect 升 require_admin 后 dashboard/devices/reports/_stat_cards/adhoc 五处触发按钮仍是全员可见的必 403 按钮 (与 alerts 同类的治理漏网); 修复: 五路由补传 user (dashboard/dashboard_stats/devices/reports/adhoc), 六模板按 user.is_admin 门控, 只读 adhoc 给「巡检需管理员权限」提示; 轮询片段 /api/dashboard/stats 同样门控 (hx-swap 不会把已门控卡片换回带 onclick 版)。④_PAST_DATE_MSG 裸中文 — en UI 闪现中文 (兄弟错误全走 T); 修复: 透传分支接 T() 双语, 常量仍作比较键。⑤_mtime_safe 双拷贝 (config_backup 闭包 + config_compare 模块级) 收敛 helpers.mtime_safe 单点。⑥alerts 规则表操作列只门控 td 内容没门控 td 本身 — 非管理员 6 头 7 格; 修复: 整个 td 进门控。验证: 服务器探针 (dev=None run 落库字段正确自清 / 过期 once 注册失败 next_run=None 且 job 未注册自清); HTTP 23+5 项 (按钮门控按 onclick 标记断言 — 首跑误匹配 base.html 函数定义与 confirm 文案字面量, 修正后全过; en/zh 双语闪现各证; config-compare/config-backup helpers.mtime_safe 路径 200; alerts 只读 6=6/admin 7=7 头格对齐); Playwright 双上下文 5 页零 pageerror + 只读 adhoc 提示可见

- 2026-08-21: **once 过去日期错误文案修复 (/verify 探针发现, 需重启)** — B4 拒收功能正确但文案自相矛盾: _schedule_config_to_trigger 抛的「计划时间已过去」被 _build_schedule_config 的统一 except ValueError 冠上「计划时间格式无效: 」前缀, 用户看到「计划时间格式无效: 计划时间已过去」。修复: _PAST_DATE_MSG 常量单点定义, 语义错误原样透传不冠前缀。验证: 生产复测 error 闪现 = 「计划时间已过去 (once 日期早于今天)」无前缀, 拒收零写入不变

- 2026-08-21: **评审修复 (e3ea8d3 全项目 /code-review, 47 候选收敛 34 项, 需重启)** — 8 finder (47 候选) → 去重 38 → 5 验证代理 → 34 项 (30 CONFIRMED + 4 PLAUSIBLE) 全部处理, 3 驳回 (reports 导出授权=README 声明的刻意设计; topology 下拉注入经实证 id 恒为 DB 整数; apiErrorText Chrome 拦截论不成立)。**权限修正 (对齐 README 权限表)**: CA 写端点权限倒挂修复 — create_root/issue_cert/delete/revoke/sign_csr 从 require_full_user 升 require_admin (此前普通登录用户可签发/吊销证书); CA 公开证书下载 (root.crt/单张 crt) 降 require_auth (只读 token 可下载公开证书, 中间件本就放行 GET); POST /inspect 升 require_admin; 告警写端点 add/silence/delete/clear 升 require_admin (ack 保持 require_auth —「所有用户查看&确认」); config_backup backup-now/batch-delete 升 require_full_user; alerts 两页写控件按 user.is_admin 模板门控 (只读/普通用户不再看见必失败的按钮)。**Bug 修复**: batch_delete_backups 裸 list[str] 无 Body() 恒 422 → Body(...); PDF 导出 run.error/cat/desc 未 html.escape 遇特殊字符 500; reports delete_run 改返回空 200 (htmx 契约 — 非空 {"ok":true} 会被 outerHTML swap 成裸 JSON 文本); scheduler once 计划时间已过去拒收 + _build_schedule_config 统一 add/edit 配置构建; devices 表单 port 字符串容错解析 (裸 int Form 遇非数字抛 422 丢整表); BOM network 分支补 matched_summary (此前硬件摘要列恒 '—'); BOM 缓存加 7 天 TTL + 64 条上限 (此前永不过期无界增长); 配置备份/比较 glob getmtime 竞态 _mtime_safe 兜底; AI confirm 认领后下发前复查会话软删除 (410 取消下发, 与 _exec_show 每命令 db.refresh 同策略); adhoc 多设备改单次 POST /inspect?device_id=N&device_id=M (后端改收列表 — 此前每设备一 POST 互相覆盖 localStorage, 面板只跟踪最后一个 run); topology esc() 强化为全字符集 &<>"' 且 from_port/to_port (LLDP/CDP 设备侧可控字符串) 拼 modal innerHTML 前转义。**重构**: helpers.netmiko_connect 统一入口 (SERVER_PLATFORMS→generic 驱动映射 + 超时单点, 4 处调用各自硬编码收敛); models.check_password 返回 'pbkdf2'/'legacy'/None, verify_password 纯 bool 包装 ('upgrade:' 双形态返回删除); i18n.py 删死代码 _translations/t(); 路由级 set_lang(get_lang(request)) 清零 (LangMiddleware 唯一设置点, 9 文件 30 处); get_current_user_sync 别名删除; main.py 首页/告警 N+1 (joinedload/defer raw_data); subnet_calc 7 份 try/except 收敛 _parse_v4/_parse_v6; base.html 新增共享 toggleAll(master, selector) — adhoc/config_backup/config_push/custom_cmds/reports/scheduler/_bom_result 七页逐字拷贝收敛, esc() 三页副本删除 (统一 base canonical); app.css 死规则删除 (.status-ok/.status-err 选择器臂/.alert-info/.device-progress/.text-warn, 全库零引用)。**记录在案不修**: E4 中间件+路由双 User SELECT (中间件缓存的 ORM 对象跨 session 有 detached 变异风险, 大于一次 PK 查询收益); R2 backup_now force=False 分支 (外部自动化契约保留)。验证: 本地 py_compile 22 py + jinja2 解析 11 tpl 全过; 服务器 TMPDIR=/tmp/_ick 导入检查过; 生产 HTTP 43 项 (只读 token 全写端点 403 / admin 写路径端到端增删自清 / batch-delete JSON 体 200 / 多设备单 POST 单 run_id / PDF·DOCX 导出 200 / CA 公开证书只读下载 200); Playwright 13 项 (admin+只读双上下文, 共享 toggleAll 三页实证, en 语言, 零 JS console 错误)

- 2026-08-21: **品牌双语补漏 (导航品牌名 en 模式仍中文, 纯模板免重启)** — /verify 生产终验 (5a52b90) 发现的最后一个双语盲区: base.html 导航品牌 `ivan网络巡检运维平台` 未接 data-zh/data-en (页签标题 26 页与登录页 h1 此前已双语, 仅此一处遗漏)。修复: 品牌文本包 span 接入 applyI18n (span 而非 a — applyI18n 的 textContent 替换会清掉 a 内的 logo img), 英文取 "ivan NetOps Platform" (与全站 title_en 后缀一致, 且更短, 缓解导航拥挤)。记录在案不修: 文件上传的原生「选择文件」按钮文案由浏览器 UI 语言决定 (英文浏览器自动显示 Choose File), 非应用层可达。验证 (生产 Edge): en 品牌 ivan NetOps Platform + 无中文 + logo img 存活 + 页签标题英文; zh 品牌中文 + devices h1 回归; 未登录 login 页 h1 英文不受影响; 零 pageerror

- 2026-08-21: **评审修复 (3340418 回归审查, 32 候选收敛 7 主线, 需重启)** — 对上一波评审修复提交 3340418 再做 /code-review (8 finder + 跨会话转发 → 去重 32 候选, 1 驳回: tmp.innerHTML XSS 经实证当前无未转义用户标记到达) 全部处理: ①BOM 上传区重构 — form 移出 htmx swap 目标 #bom-info (成功/错误片段不再销毁文件输入框, 曾上传成功后必须整页刷新才能再传); htmx:responseError 处理从 bom_match.html 页内监听上提为 base.html 全局监听 (全站 400/413/500 错误渲染进请求目标区域顶部: apiErrorText 提取 JSON error/detail + DOMParser inert 解析 HTML 片段 + textContent 防注入 + 不清空目标, 下次成功 swap 自动清除错误条); ②AI 标题哨兵根除 — 哨兵 ('{label} 对话/Chat') 随语言/hostname 漂移已连续三波修漂移, 改为创建时 title 存空串 + 首条非空白消息命名 (空标题永不与用户标题相等, 识别不依赖创建时刻任何状态; 前端 ai.html 已有 '会话 N' 回退), _default_title_variants(hostname, ip) 具名参数仅识别 2026-08 之前存量会话的旧默认标题; 命名不再受 seq 门控 (空白首条消息不再永久锁死后续改名); ③403 显式分类 — _classify_403: 只读 token 身份 (readonly_token_ok) 优先于 detail 文案 (只读 token 命中 require_admin 时永远按只读拒绝渲染, T1 监控标记不漏报), detail 精确匹配两个常量, 其余 generic 兜底 (三分支文案各异, 稳定标记只在只读拒绝出现); ④BOM 翻译/效率 — config_checks 不再存 'actual' 显示串 (它是 match 布尔的纯函数, 双表示可漂移), 渲染时 translate_config_checks 推导 (找到/未找到) 且 copy-on-write (无改动条目复用原 dict); 状态表与固定串表形状统一 key→(zh,en) + _bilingual() 访问器 + status_labels() 直出 (STATUS_KEYS 与 routers._bilingual_labels 再包装删除); _kw_match 的 summary.upper() 提升为每 run 一次 (曾每关键字重算 KB 级文本); _extract_config_keywords 每件 BOM 提一次 (曾每件两遍 + 非匹配 run 白跑); extract_run_facts 单次 json.loads 同取 PID 集合与硬件摘要 (曾两函数各解析一遍); ⑤ai_engine 落库残留 T() 清零 — _exec_show/_propose_config 返回值与 assistant 兜底共 10 处 ([已停止]/[被拒绝]×2/截断后缀/steps 错误×4/[已生成确认卡片]/[提示] 分轮/未知工具) 改固定中文 (经 _save_msg 落库 AIMessage, 存储值不翻译); ⑥注释收敛 —「固定中文不翻译」现场注释 10+ 份逐点复制收敛为 ai_engine/ai_session/custom_cmds 模块头语言政策段 (新增落库点不再靠抄注释维持防线); ⑦confirm_action 显示侧 — 审计改固定中文后 UI 响应仍直返 str(e) (英文 UI 显示中文错误, 显示回归), 新增 _display_err 前缀表显示侧翻译 (保存失败/配置下发失败/设备连接失败/密码解密失败), 审计字段保持固定中文。验证 (生产): bom 页结构探针 (form 在目标外/全局监听就位/页内监听移除) + 无 BOM match 400 双语 + 非法格式 400 双语 + 只读 token 403 双客户端形态 (API 纯文本稳定标记/浏览器双语友好页+注释标记) + admin /users 200; 服务器侧探针: actual 推导 zh/en + 存储串翻译 + copy-on-write 同一对象 + status_labels 双语 + extract_run_facts 单解析 + _kw_match 双态 + _display_err zh/en/未知透传 + 标题变体识别与命名条件四态 + _classify_403 三分支+标记隔离 + ai_engine 落库零 T() grep; 重启后 /login 200

- 2026-08-21: **评审修复 (6ccb60b 回归审查, 10 项, 需重启)** — 对上一波评审修复提交 6ccb60b 再做 /code-review (8 finder → 逐候选验证, 10 报告项) 全部处理: ①custom_cmds 密钥不匹配/任务提交失败/SSH 连接失败/SSH 执行超时 5 处错误串仍包 T() 经 save_inspection_run 落库 (与上波在 config_push/inspect 修好的同类缺陷一致但被漏) → 全部固定中文; ②ai_session RuntimeError/SaveFailedError/ConfigExecError 消息 T() 经 confirm_action 兜底 except 与 _exec_show 落库进 AIAction.output 审计与 AIMessage 聊天历史 → 全部固定中文 (T 导入移除), ai_engine [执行失败] 返回值固定中文; ③只读 token 403 友好页误伤 — _friendly_403 异常处理器对所有 Accept: text/html 的 403 一律返回只读 token 专用页+稳定标记, require_admin 的 'Admin required' 403 (已登录非管理员) 文案误导且标记误报; 修复: _friendly_403_html(detail) 按 detail 区分, 仅只读拒绝嵌标记, 其他 403 显示「需要管理员权限」; ④BOM config_checks 的 actual 存英文 found/not found 且 _CONFIG_CHECK_STRINGS 未覆盖 → 改规范中文 '找到'/'未找到' 存储 + 补译 (zh 未找到/en not found); ⑤AI 标题哨兵 hostname 漂移 — 哨兵按当前 hostname or ip 重组, 建会话时 hostname 为 NULL 后被巡检回填则比较不命中; 修复: _default_title_variants(hostname, ip) 2 label × 2 语言共 4 变体都认; ⑥放宽的哨兵可覆盖手动同名标题 → 自动改名限定首条消息 (seq_last is None), 后续消息不再触碰标题; ⑦bom 上传 413/400/500 对 htmx 用户不可见 (htmx 默认不 swap 非 2xx 且无 responseError 处理) → bom_match.html 加 htmx:responseError 监听 (JSON detail 与 HTML 片段都渲染进目标区域, textContent 防注入), 413 detail 顺带双语化; ⑧STATUS_LABELS 派生表值无人读取 (唯一消费者只迭代键) + 注释过时 → 删除派生表, 改出 STATUS_KEYS 键元组; ⑨subnet.html 两处 yn 元组是全库仅剩的裸 lang cookie 嗅探 → 改用模板全局 T('是','Yes')/T('否','No'), 模板 cookie 嗅探清零; ⑩默认标题后缀字面量创建/比较两处重复 → _TITLE_SUFFIXES 常量 + helper 单一来源。验证 (生产): 部署代码 grep 各存储点零 T() + ai_session 无 T 导入; 403 三形态 (只读页含标记/Admin 页无标记且文案为管理员权限/只读 token POST 实拦 403+标记); 标题哨兵 4 变体 + en 建会话 zh 首条自动改名 + 第二条消息不覆盖实测; BOM translate_config_checks zh/en/原列表不变三探针; subnet en Yes/No + zh 是/否 + lang=fr 回退中文; 413 双语确认; 服务重启后 /login 200

- 2026-08-20: **评审修复 (双语 Wave 1+2 后回归审查, 9 项 + 附加 6 项, 需重启)** — 对双语系列提交 (9556383→22cfcd5 + 未提交终验修复) 的 /code-review (8 finder → 对抗验证, 9 报告项) 全部处理: ①AI 会话默认标题哨兵跨语言失配 — 创建按当时语言存 'X 对话'/'X Chat', chat() 却按当前语言重建哨兵比较, 切语言后首条消息自动改名永久失效; 修复: 哨兵双语都认 (存储值不翻译, 只放宽比较); ②持久化字段回退固定中文 (落实自定「存储值与比较键不翻译」规则) — AIAction.output 审计标记 ([过期自动拒绝]/[执行输出]/[保存失败]/[执行失败])、AI 配置变更 goal、InspectionRun.error (密钥不匹配)、config-push 审计 error (解密失败/队列取消/疑似挂死) 全部撤掉 T(); ③raw_data section 键固定 '自定义命令' (曾随触发者语言在 自定义命令/Custom Commands 间漂移, 存储 schema 依赖语言); ④cases webhook 备注固定中文 — notify_case_change 发外部 T1/QC 通道的备注曾随操作者 UI 语言中英漂移 (顺带消掉英文变体 'and N in total' 的计数重复); ⑤BOM config_checks 存规范中文 + 渲染时翻译 — 曾把匹配时刻的语言烘进跨请求缓存 _last_results, 切语言后 remove-rows/export 同行混排; 新增 translate_config_checks() 与 bom.py _render_results 渲染副本 (缓存不动), STATUS_LABELS 改从双语表派生 (单一来源), build_export_excel 去掉与路由重复的 lang 参数/set_lang; ⑥只读 token 403 稳定标记 — 终验修复把浏览器 403 从纯文本改为双语友好页后, 带浏览器 Accept 的机器客户端丢失固定 'Forbidden: read-only token...' 标记; 友好页尾部嵌入该 ASCII 标记 (HTML 注释), API 路径 (无 html Accept) 保持纯文本原样; ⑦get_lang 统一 — 19 处 set_lang(request.cookies.get(...)) 手写拷贝全部收敛为 set_lang(get_lang(request)) (8 文件 + LangMiddleware); ⑧实证驳回项 (记录在案): 评审认为 4 个 router 的同步路由缺手工 set_lang 会恒出中文 — 前提不成立 (LangMiddleware 在 call_next 前设置 + anyio.to_thread.run_sync 复制 contextvar, 同步端点天然可达; 生产实测 custom-commands 平台下拉与 scheduler flash 在无手工 set_lang 下仍正确双语), 既有手工 set_lang 保留为无害显式兜底, ai_assistant.py 里陈述错误前提的注释已修正; ⑨附加确认项 — bom.py 上传 413 被兜底 except 吞成 500「解析失败」 (补 except HTTPException: raise)、scheduler run-now 'Schedule not found' 单语英文改双语、chat worker 对会话/设备/用户并发删除的 None 解引用加防御 (优雅双语报错替代 Internal error: NoneType)、ai_engine 历史循环内 T() 表头提升循环外、base.html switchLang 用未归一的原始 cookie 判断 (lang=fr 时点语言钮首击无变化) 改复用 head 已归一的 i18nLang + 删 body 末尾死变量、main.py _MWHTML 重复别名删除、custom_cmds PLATFORM_TYPES 死 'all' 条目删除。验证 (生产): custom-commands en All Platforms / zh 所有平台; scheduler run-now 双语 flash; 只读 403 en/zh 双语页 + 稳定标记 + API 纯文本原样; AI en 建会话 'vpn Chat' → zh 首条消息自动改名命中; 改密双语回归; BOM translate_config_checks 服务器侧 en/zh 直探; 部署代码 grep 各存储点零 T(); lang=fr 渲染中文且语言钮首击即英文; 零 pageerror。已知残余 (记录在案): 持久化/外发字符串 (审计标记/推送 error/webhook 备注) 在英文 UI 下显示中文 (存储优先于显示, 显示层翻译留待后续); custom_cmds 独立执行存 'Custom Commands' 键与巡检存 '自定义命令' 键的既有不一致未动 (历史数据兼容)

- 2026-08-20: **双语终验修复 (lang 白名单前后端对齐 + 只读 token 403 双语友好页)** — /verify 终验 (17 项探针) 抓出两项边角: ①lang=fr 这类非法 cookie 值时前端 JS 只判 `==='zh'` 按英文渲染而后端白名单兜底中文 → 页面中英混排; 修复: base.html 的 i18nLang 归一白名单 (非 en 一律 zh, 与后端 set_lang 同向), body 末尾脚本直接复用 head 已归一的 window.i18nLang; ②只读 token 访问受限页 (/users 等) 被 LoginMiddleware 拦截时返回纯文本英文 Forbidden, 与路由层 403 的双语友好页风格不一; 修复: 友好页 HTML 抽成 _friendly_403_html() 两处共用, 中间件对 Accept: text/html 的拦截同样返回双语友好页 (API 调用无 html Accept 保持纯文本)。验证 (生产): lang=fr 时后端片段中文 + 前端整页中文 (h1/页签/导航, 不再混排) + 语言钮显示 EN; 只读 token /users 在 lang=en/zh 下分别返回 403 Access Denied / 403 无权访问 友好页; API 路径纯文本不变; en/zh 正常切换回归; 零 pageerror

- 2026-08-20: **双语盲区全修 Wave 2 (后端字符串双语, 需重启)** — 应「修复全部」清掉最后一类盲区: 后端 .py 直出中文字符串 (此前机制够不到)。①i18n 基础设施 — i18n.py 新增 T(zh,en) + contextvar (与前端 t() 同构), main.py 新增 LangMiddleware (每请求把 lang cookie 写入 contextvar, 最后 add=最外层, 403 处理器等早期路径也覆盖), templating.py 注册 Jinja 全局 T; 同步 def 路由跑线程池 contextvar 不传播 — 相关路由入口显式 set_lang(request.cookies.get(...)), 其中 5 个原本无 request 参数的路由补加 Request 形参 (FastAPI 自动注入); ②改造规模 (~80 处用户可见字符串, 日志/docstring/注释保持中文): bom.py 全部 htmx 片段文案 + STATUS_LABELS 双语化 (_bilingual_labels, 模板按键查不变) + Excel 导出 (表头/状态/BOM匹配报告 build_export_excel 加 lang 参数); auth 密码策略/改密/重置全部错误 + T1访客(只读) 用户名改 @property; ai_assistant 全部 JSON error + 会话标题「对话」; ai_engine RuntimeError/SSE 事件文本; ai_tools 工具 description 改 build_tools() 函数 (模块级常量 import 时会冻结为 zh) + **新增完整英文系统提示词** SYSTEM_PROMPT_TEMPLATE_EN 与降级协议 FALLBACK_SUFFIX_EN (英文模式下 LLM 用英文提示词应答); ai_session/crypto 异常消息; devices/subnet/vram/cases/config_backup 错误消息; 403 页面 HTML; ③worker 线程 lang 传递链 — 巡检 (trigger_inspection→BackgroundTasks→_inspect_one), run-now (run_now→_run_scheduled→_run_batch→_inspect_one), 多设备命令 (execute_multi→_run_cmds_with_lang), 入口统一 get_lang(request) 传入, worker 内 set_lang 后 T() 生效; APScheduler 定时路径默认 zh 不变; ④跳过项 (记录在案): 存储值/比较键不翻译 (scheduler「等待中」状态值、设备 raw_data 解析键「硬件清单/序列号」), 历史报告/历史巡检记录中的存量中文不回溯。验证 (生产): 服务器 TMPDIR 隔离锁 import 检查通过后重启, BOM 空上传/未上传匹配/subnet 非法地址/vram 空参与非法参数量/改密不一致/AI 建会话设备不存在 七组 API 探针 en/zh 双向全部命中预期语言, 全 20 页 × lang=en 遍历 200 + 零 pageerror

- 2026-08-20: **双语盲区全修 Wave 1 (默认亮色主题 + 页签标题/tooltip 双语, 纯模板免重启)** — 应「默认主题亮色 + 修复全部」: ①默认主题暗→亮 — base.html 预绘脚本与 switchTheme 的缺省值 dark 改 light (已有 theme=dark cookie 的老用户不受影响, 新访客首次访问即亮色); ②页签标题双语 — base.html title 标签改 `<title data-zh="{{ self.title() }}" data-en="{% block title_en %}{{ self.title() }}{% endblock %}">` 复用 applyI18n 机制, 26 个页面模板各加 title_en block (品牌后缀统一 "ivan NetOps Platform", 含 {{ }} 动态标题只翻静态部分, 不定义 title_en 回落中文); ③tooltip/aria 双语 — applyI18n 新增 data-zh-title/data-en-title 与 data-zh-aria/data-en-aria 属性对处理, 全站 13 处此前保留中文的 title/aria-label 全部接入 (topology 缩放三键/bom 清除钮/_ca_certs P12 提示/ai 三个 select 的 aria/scheduler 四个 title)。验证 (生产 Edge): 全新访客 (无 cookie) 登录页 data-theme=light + body rgb(241,245,249); theme=dark cookie 用户保持 rgb(2,6,23); 亮色点切换→暗色+标签翻转 ☾ 暗色/☀ 亮色; lang=en 页签标题 Subnet/Devices 英文 + lang=zh 回中文; topology tooltip 双语往返; 控制台零错误。部署注: 网络路径突发丢包导致两次部署失败, 诊断为大包间歇被丢 (1400/1800 字节失败而 2000 成功, 非硬 MTU), 部署脚本升级为断点续传 (md5 比对跳过已新文件) + 1KB 块 + 每块 30 次重试后一次通过

- 2026-08-20: **全站内容双语 (模块内容英文化, 30 个模板 575 处标注)** — 继 UI 统一 Wave 4 (只覆盖导航+标题/按钮) 之后, 应「模块内容也显示英文」要求把双语覆盖到全部页面内容 (纯模板, 免重启): ①base.html 机制扩展 — applyI18n 抽出 _i18nSet 助手, 带 placeholder 属性的元素替换 placeholder、input[type=submit/button] 替换 value (此前只换 textContent, 表单占位符无法翻译); i18nLang 与 t() 定义前移到 head 预绘脚本 (chrome 块巡检面板脚本早于 body 末尾 i18n 脚本执行, 此前面板 JS 字符串无法用 t()); 巡检进度面板全部硬编码中文 (巡检进度/登录已过期/巡检完成/巡检中/巡检超时/请求失败/确认提示/刷新按钮) 改 t(); ②30 个模板全量标注 — 全站可见静态文案 (h1/h3/label/button/th/option/空态/副标题/模态框) 575 处 data-zh/data-en, 模板内 JS 动态字符串 (alert/confirm/innerHTML 拼接/textContent) ~90 处改 t(), 术语表全站统一 (巡检 Inspection/在线 Online/超时 Timeout/暂无数据 No data 等); 默认渲染中文, data-zh 存中文原文, 切 EN 整页内容变英文; ③Jinja 内联中文处理 — `{{ '成功' if x else '失败' }}` 类表达式约 10 处 (服务端渲染, JS 机制够不到): 徽标类改 {% if %} 分支包双语 span (custom_cmds/config_push/case_detail/scheduler), subnet 的 6 处 是/否 用 request.cookies 判 lang 的 yn 元组; ④中英语序差异句子拆 span 重排 (如「N 个子网, 每子网 M 个可用 IP」英文为 "N subnets, M usable IPs each"), 纯量词「个/台/条」span 的 data-en 置空串消隐。验证 (生产 Edge): lang=en 全 20 页遍历零中文残留 (高频词探针: 添加/保存/取消/删除/编辑/状态/操作/加载中/暂无 全部 0 命中) + devices 表单 placeholder 英文生效 + 控制台零错误; 回切 lang=zh 逐页复核全部 data-zh 元素显示中文 (初版 zh 探针在 7 个原生英文为主页面上假 FAIL, 定向复核确认全部正常); 32/32 模板 Jinja 编译通过。如实记录的机制边界 (未覆盖, 留待后续): title/aria-label 属性 (约 8 处 tooltip 英文模式仍中文) / block title 页签标题 / 服务端 .py 直出字符串 (设备状态 等待中、bom.py 片段文案、巡检结果文本) — 最后一类需改后端重启, 本轮明确出范围

- 2026-08-20: **全站 UI 统一 Wave 4 (双语补全 + htmx 片段双语钩子 + 全站双主题终回归)** — 系列第四波 (纯模板, 免重启): ①base.html i18n 机制补两个洞 — 初始化逻辑抽成 applyI18n(root) 并注册 htmx:afterSwap 监听 (此前 htmx 局部刷新插入的片段不会被翻译, 初始化只在首绘跑一遍); 新增 t(zh,en) 助手供 JS 动态文案按当前语言二选一; ②英文页面接入 data-zh/data-en 双语 — ca_server + _ca_roots/_ca_certs (CA 证书管理/根 CA/签发外部 CSR/签发证书/证书列表/全部表单标签/按钮/表头), alerts (清空全部/清除已确认/确认/添加/静默 2h/删除/空态), ping (网络诊断标题), config_compare (配置比较标题+比较/互换/清空按钮), vram_calc 空态提示句; 默认中文, 切 EN 后这些页面同步变英文 (机制与导航一致); ③终回归 — 生产 Edge 全 20 个页面 × 暗/亮双主题遍历: 全部 200、每页 h1/card 结构在位、暗色下无任何"岛白"背景元素 (card/th/table 探针)、控制台零错误; 双语验证: lang=en 下 ca/ping/config_compare 标题与 alerts 按钮变英文、applyI18n 对 swap 片段生效、回 zh 全部恢复。如实记录: 内联 style 计数 527 vs 基线 523 基本持平 — 本系列收敛的是私有样式块/硬编码颜色/重复组件 (设计系统层), 未逐页清扫存量内联布局属性 (subnet 等页的表单布局内联留待后续)

- 2026-08-20: **全站 UI 统一 Wave 3 (页面骨架/空态/模态框统一 + compare 孤儿模板发现)** — 系列第三波 (纯模板/CSS, 免重启): ①compare.html (巡检对比) 毛坯页收编 — card 包裹 + table-wrapper + 状态徽标 + .empty-state; **注意: 全库 grep 确认没有任何路由渲染 compare.html 也没有任何页面链接 /compare — 该模板是孤儿 (死代码), 本次只做结构化收编, 是否接线/删除待用户决策**; ②config_backup.html — 全站唯一用 h2 当页面标题的页面改 h1 + .page-header; 删私有 .backup-table/.btn-backup/.status-msg 三套轮子 → 共享 table/.toolbar/btn 族/.alert 族 (showStatus 改用 alert-success/alert-error); JS 拼表格行同步 (无引号属性修正、冲突标注 #EF4444 → .text-err、空态行用 .empty-state); 死代码 r["new"] ? "ok" : "ok" 清理; ③alerts.html — severity 徽标内联拼色 (#EF4444/rgba 硬编码) → 令牌化 .alert-sev 类; 页头规则/历史 tab 移入 .page-header; 'No alert history' → .empty-state; ④4 份手写模态框外壳 (devices/scheduler/topology/ai, 逐字重复的 position:fixed+rgba(0,0,0,0.7)) 收编为 .modal-overlay/.modal 共享类, ai.html 保留 .ai-modal-mask/.ai-modal 布局钩子; ⑤空态/副标题统一 — cases/scheduler 的手写居中段落 → .empty-state, adhoc/cases/case_categories/scheduler 的副标题内联 → .page-desc; ⑥潜伏 bug 修复 — scheduler.html 在用 status-badge info-badge 修饰类但 app.css 从未定义 (徽标一直无底色), 补 .status-badge.info/.info-badge 定义。验证 (生产 Edge): alerts severity 徽标颜色与 --*-text 令牌动态比对一致 / 告警历史页正常 / 配置备份 h1+toolbar+共享表格 22 行数据渲染 / devices 编辑模态暗色内层 #0F172A+亮色纯白+遮罩 rgba(0,0,0,0.6) / scheduler 页面正常+info-badge 蓝色生效 / 拓扑画布渲染无回归 / 控制台零错误

- 2026-08-20: **全站 UI 统一 Wave 2 (共享类入库 + 消灭 bom/ca/vram 三个亮色孤岛)** — 系列第二波 (纯模板/CSS, 免重启): ①app.css 共享类入库 — 从全库 523 处内联 style 收敛出 .page-header/.page-desc/.form-row/.form-group/.modal-overlay/.modal/.btn-outline/.btn-outline-danger/.btn-block/tr.row-ok/row-warn/.status-badge.warn/.page-narrow/.page-wide/.flex/.mb-16/.text-ok/.text-err; 注意 .btn-outline 此前被 case 系列页和 _ca_roots/_ca_certs 使用但 app.css 从未定义 (一直渲染成裸按钮), 现已补定义; ②删除全局 input/select/textarea 的 margin:0 6px 6px 0 (内联 margin 泛滥的诱因); ③三个"亮色孤岛"页面消灭 — bom_match (~75 行私有亮色 <style> 全删)、ca_server (19 行, 且**未加作用域重定义全局 .btn/.btn-primary/.btn-danger/.btn-sm**, 在该页打开期间污染共享按钮)、vram_calc (23 行, 私有重定义 .card/.alert-error 覆盖共享类); 硬编码 #fff/#2563eb/#f1f5f9/#eff6ff/#bbf7d0 等清零, 私有表格 (.bom-table/.ca-table)/徽章 (.badge-active)/按钮 (.btn-export/.btn-calc) 全部映射共享类; ④bom.py 路由以 HTMLResponse 字符串直出的类 (btn-clear/upload-error/match-error) 在 app.css 保留令牌化别名 — 改 .py 需要重启, 收编留待后续波次; ⑤主题切换按钮文案随当前主题翻转 (暗色下显示 ☀ 亮色, 亮色下显示 ☾ 暗色)。验证 (生产 Edge): 三岛暗色主题下无岛白背景/亮色主题下卡片纯白+页面底 #F1F5F9 层次成立/ca 页按钮回归共享 Fira Code 字体 (私有覆盖已除)/vram 计算 htmx swap 出结果表 (38.4 GB)/bom 共享卡片+空态就位/全局 margin 移除后 subnet+devices+adhoc+config_push 抽查截图无布局挤压/控制台零错误

- 2026-08-20: **全站 UI 统一 Wave 1 (设计令牌层 + 亮色主题 + 导航高亮 + 登录页去导航 + htmx 本地化)** — 「优化全部模块 UI」系列第一波 (纯模板/CSS/静态资源, 免重启): ①令牌补齐 — :root 新增语义令牌族 (alert/徽标文字色 --*-text、实底按钮文字 --*-contrast、语义边框 --*-border、中性底色 --muted-glow), app.css 内全部硬编码颜色 (alert 文字 #FCA5A5 系、alert 边框 rgba、.btn-success 的 #020617、.alert-sev 三色、.result-card 边框、.status-badge.unknown 背景) 收敛为 var() 引用, 删除死令牌 --bg-elevated; ②亮色主题 — 新增 [data-theme="light"] 覆盖块 (亮白底 #F1F5F9/卡片纯白/语义色降档保对比度/阴影减轻), 导航条加 ☀ 切换 (cookie theme=light 持久化, 与 lang 同构 reload 切换), head 内 3 行预绘脚本防暗色闪烁; ③导航 active 高亮 — .nav-links a.active 样式存在两年但从未被设置, 现纯 JS location.pathname 前缀匹配 (详情页归入列表页; 实测发现 / 会 303 到 /dashboard, 两者都算仪表盘); 退出链接内联 #EF4444 改 .nav-danger 类; ④登录页不再渲染完整导航栏和巡检进度浮层 — base.html 的 nav/巡检面板包进 {% block nav %}/{% block chrome %}, login.html 空覆盖 (此前未登录用户看到全部 21 个菜单+退出链接), i18n 脚本对缺失的 #lang-switch 加防御; ⑤htmx 1.9.10 从 unpkg CDN 本地化到 static/htmx.min.js (内网隔离部署不再失效, 版本钉死不升 2.x); ⑥顺手修 badge bug — .status-badge.timeout/.auth_failed 的 ::before 圆点无颜色规则 (圆点不可见)。验证 (生产 Edge): 暗色零回归 (body rgb(2,6,23)) / 亮色切换往返 (dataset.theme+cookie+body rgb(241,245,249)+卡片纯白+正文深色) / 导航高亮 /devices·/·/cases 三态 / 登录页无 navbar 无巡检浮层 / htmx 本地加载 typeof htmx 定义 / timeout 徽标圆点红色 / 控制台零错误

- 2026-08-20: **子网计算优化 (IPv4/IPv6 划分 + 修一个同名字段覆盖的真实表单 bug)** — ①斜杠前缀被拒: 划分输入框 placeholder 引导用户输入 "/26" 带斜杠形式, 旧实现 int('/26') 直接报错, 现 _resolve_prefix 统一 strip().lstrip('/') 解析; ②新增按数量划分模式 (split_mode=count): 输入想要的子网数量 (如 4 或 100), 自动换算能容纳该数量的最小新前缀 (数量向上取整到 2 的幂, /24+4→/26, /24+5→/27, v6 /32+100→/39), IPv4 划分卡片与 IPv6 划分卡片各加 按前缀/按数量 下拉; ③大数格式化 _fmt_pow2: /32→/48 的子网数从 65536 裸数字改显 2^16 (65,536), v6 每子网地址数同样 2^80 (...) 形式; ④相同前缀/更小前缀给出明确错误 (新前缀与当前相同, 无需划分) 而非静默空结果; ⑤VLSM 容量不足不再静默 break 丢弃剩余需求 — 记录 unallocated 列表并页面 alert-warn 明示「以下主机数需求未能分配」; ⑥v6 ULA 检测修复: Python 3.11 的 IPv6Network 无 is_unique_local 属性, 旧 getattr 兜底恒 False, 改显式按 fc00::/7 网段判断; v6 卡片补地址属性行 (全球单播/ULA/链路本地/组播 + 展开形式); ⑦全部结果卡片包 error 分支 — 此前计算错误只返回 {"error": ...} 而模板无判断, 渲染成空白卡片, 现统一 alert-error 红条; ⑧**同名字段覆盖 bug (生产浏览器实测抓出)**: IPv6 面板内基本信息/子网划分两张卡片共用 name="ipv6_addr", Starlette 对重名字段取最后出现的值 — 在基本信息卡片填地址点「计算」, 后面划分卡片的空输入把值覆盖成空串, 服务端回「Enter an IPv4 or IPv6 address」; prepareSubmit 增加去重规则: 禁用可见面板内靠后的空重复字段 (保留用户实际填的那份); ⑨v4 可用主机数/总 IP 数与 v6 总 IP 数加千分位 (16,777,214); ⑩清理: 路由层 int() try/except 死代码删除 (_resolve_prefix 接管), IPv6 分支重复的死 list 分支删除, 模板重复的 switchTab 定义去重。验证: 本地 8 项行为断言 (斜杠/纯数字/数量取整/2^N 格式化/同前缀错误/VLSM 未分配/ULA 两态) 全过 + 生产 Edge 真用户流程 (点 tab 切页签填表点按钮) 9/9 PASS: v4 '/26' 与 '26' 均出 4 子网、数量 5→/27 出 8 子网含 192.168.1.224/27、v6 /48 显 2^16 (65,536)、v6 数量 100→/39、同前缀错误条、VLSM 未分配横幅、ULA fd00::/8 识别、非法地址错误卡、/8 基本计算回归 (千分位在位)

- 2026-08-20: **静态资源缓存修复 (用户浏览器旧 CSS 把 logo 渲染成 200px 原图)** — Starlette StaticFiles 默认不带 Cache-Control, 浏览器按启发式缓存 (约文件年龄的 10%), 部署新版 app.css 后用户浏览器滞留旧 CSS: 新 HTML 引用了 logo 图但旧 CSS 没有 .brand img 26px 约束, 且还留着 ⚡ ::before。修复: ①StaticCacheMiddleware — /static 响应统一加 Cache-Control: no-cache (浏览器每次重验证, StaticFiles 自带 ETag 命中走 304, 开销极小); ②app.css 与 logo.png 引用加 ?v= 版本号, 强制已缓存旧 CSS 的浏览器立即拉新版。验证: 生产响应头 Cache-Control: no-cache + ETag 在位, Edge 实测品牌图标渲染 26×26

- 2026-08-20: **全站启用正式 Logo (ivanioc.png)** — /home/ivan/ivanioc.png (200×200 网络节点图形, 深蓝底与主题一致) 复制为 backend/static/logo.png 并应用到三处品牌位: ①导航栏品牌 — 替换 CSS ::before 的 ⚡ 字符, .brand 改 flex + 26px 圆角图标; ②浏览器页签 favicon — 替换前一日加的内联 SVG data-URI, 改指 /static/logo.png; ③登录页 — h1 的 ⚡ 替换为 96px 大 logo 图。验证: 生产 Edge 截图确认登录页大 logo + 导航栏图标渲染正常, /static/logo.png 200, 控制台零错误

- 2026-08-20: **Traceroute/MTR 修复 + 优化 (修一个从未生效的解析器)** — 实证发现 Linux 上 Trace 的解析表格**从未渲染过**: mtr 0.95 输出 hop 号是 `1.|--` 连写, 旧 _parse_mtr 的 `parts[0].isdigit()` 永远为假逐行跳过, 页面只剩 details 里的 raw 文本; 且 mtr 对 100% 丢包省略 % 号 (列宽对齐), 纯 `([\d.]+)%` 正则会漏掉全丢包跳。重写为逐行正则解析 (hop/IP/Loss/Snt/Last/Avg/Best/Wrst/StDev 全列, % 可选), 用服务器真实 mtr 样本做单测。优化: ①Trace 与 MTR 两个表单统一渲染全列统计表 (Jinja macro 共享, Windows tracert 降级为 times 文本行), 丢包配色徽标 (0% 绿 / >0 橙 / 100% 或 ??? 红), 标题带 N hops · M cycles 汇总, raw 输出保留在折叠 details; ②两个表单的 mtr 采样轮数可选 (5/10/20/30, _cycles 白名单钳位 1-30, subprocess 超时随轮数自适应 cycles*2+20); ③目标主机白名单 _clean_host — subprocess 虽是 list 形式无 shell 注入, 但 `--help` 这类目标会被 mtr/ping 解析为选项 (选项注入), 现拒绝并页面提示 invalid target; ④Continuous ping 的 Linux -W 同步修正为秒 (与批量路径同款单位 bug)。验证 (生产 HTTP + Edge 截图): Trace 网关 1 跳表格渲染 / Trace 223.5.5.5 cycles=10 得 17 跳含 13 个 * 跳 + 40% 丢包跳橙色徽标 / MTR 表单出表格 + raw 折叠保留 / `--help` 被拦截 / 批量与 Continuous 回归正常

- 2026-08-20: **Ping 模块支持完整 /24 (254 台) + 截断提示 + 接通超时控件** — 批量 ping 上限 MAX_HOSTS 100→254 (worker 50→64): 此前输入 /24 被静默截断到前 100 台且页面无任何提示 (实测 198.51.100.0/24 只返回 100 行, 用户会误以为扫了整个子网); 现 expand_targets 返回 (ips, truncated) 标志, 超限时结果页显示 alert-warn 横幅「仅 ping 前 254 个地址, 其余已截断未测」。顺带修复同页两个潜伏问题: ①超时下拉框 (500/1000/2000/5000ms) 是死控件 — ping_post 从未接收 timeout_ms 参数, 现已接通到 ping_one (非法值回落默认 1000ms); ②Linux ping -W 单位是秒 (Windows -w 才是毫秒), 原先把 1000 毫秒值直传 = 每包等 1000 秒, 不可达主机实际靠 subprocess timeout=6 兜底, 现按平台换算 (Linux 秒/Windows 毫秒), subprocess 超时按 4 包 × 超时 + 3s 余量自适应。验证 (生产 HTTP): /24 整网段 254 行结果 17s 完成无截断提示; /23 (510 台) 截断到 254 并显示横幅; 超时控件实测生效 (500ms→4.2s / 5000ms→8.2s 响应时间差); Continuous Ping 与范围形式回归正常

- 2026-08-20: **拓扑页 /verify 探针修复 (4 项 UX/显示问题)** — 对美化波次 (4c95b1b..61ad932) 的生产 /verify (Playwright 驱动真页交互探针) 发现并修复: ①缩放百分比读数在按钮缩放后失步 — vis 的 zoom 事件只在滚轮/捏合缩放时触发, zoomBy/fitAll/Trace 的编程式 moveTo/fit 不触发, 点 + 后画布放大了读数仍停 58% (与 README「实时缩放百分比」宣称不符); 修复: 收敛 syncZoomPct 助手, 编程式缩放挂 network.once('animationFinished') 回调同步 (滚轮路径仍走 zoom 事件); ②Trace 的 hop 计数与 Clear 的清空占用 #last-update, Updated 时间戳被覆盖/抹掉要等下次刷新才回来 — 拆出独立 #path-status 状态位, last-update 只表更新时间; ③跨连通分量的 Trace 弹原生 alert('No path found') (生产拓扑数据实为 3 个连通分量: core 13 节点/office-sw1 11 节点/ICI-FW 2 节点 — LLDP 采集现状非缺陷, 但意味着该提示会常被撞到), 改为 #path-status 内联「No path (节点不连通)」; ④favicon 404 控制台噪音 — base.html 补内联 SVG data-URI 图标 (⚡, 零外部资源)。验证 (生产 Edge 真页): 按钮缩放 58%→75%、Fit 75%→56% 读数同步; Trace 'Path: 2 hops' 入 path-status 且 Updated 时间戳保持; 不连通对无 dialog 弹窗、内联提示; Clear 清空 path-status; 控制台零错误 (favicon 404 消除); pageerror 为零

- 2026-08-19: **网络拓扑页美化 (视觉升级 + 修一个定时器泄漏)** — 拓扑页整页视觉重做, engine 层仅动外部节点标签一行: ①节点图标化 — ASCII 字符 (`*` `<>` `^`) 替换为内联 SVG 徽章 (vis image shape + data-URI, 零外部资源): 形状=设备类型 (交换机/路由器/防火墙/WLC/服务器/外部主机, 按 devicetype+主机名启发式归类), 类型强调色着色, 外环+底部色条=状态 (在线/异常/未知), 外部节点虚线描边; ②确定性分层布局 — 角色已有 core/distribution/access/external 分级, 改为固定分层 (核心居顶、逐层向下, 同层按子网+名称排序分行), physics 关闭 — 原先初始摆位后交给 forceAtlas2 重排, 每次刷新整图重新散开; ③边标注降噪 — 每条边的 8px 端口对常驻画布改为仅悬停提示 (title), 画布只保留「N 链路」聚合标注与速率配色 (GE/10G 绿 / FE 橙), 边箭头移除 (无向图误导); ④节点双行标签 (主机名 + 第二行 IP 小字), 外部 Unknown 节点改以 IP 作标签 (engine: 名字缺失/Unknown 时回落 IP — 原先图上一排 "Unknown" 毫无区分度, 生产 26 节点中 0 个 Unknown 剩余); ⑤告警表现升级 + 修泄漏 — 边框宽度闪烁改为红色阴影呼吸脉冲, 且原实现每个告警节点一个 setInterval、每次 loadTopo (自动刷新 60s) 叠加永不回收 — 改为单一共享定时器 + 重载先清旧; ⑥画布精修 — 细点阵网格背景 + 内阴影, 右下角 +/−/Fit 悬浮缩放控件与实时缩放百分比; ⑦图例面板化 — 左下角浮动卡: 在线/异常/外部/告警带实时计数, 可点击过滤 (暗掉非匹配节点), 链路色带说明; ⑧弹窗 CPU/内存改迷你进度条 (>85% 红 / >65% 橙), 邻居区显示计数。验证: 页面 11/11 关键标记 + /topology/data Unknown 清零 (外部节点样例全部有区分标签) + devices/dashboard 无回归; 布局稳定性由 physics:false 保证 (刷新不再重排)。未做 (评估后否决): 子网背景框 (vis 无原生支持且视觉易乱 — 以图例过滤替代)

- 2026-08-19: **拓扑页美化补充修复 (生产报错 Cannot set properties of null (textContent))** — 美化版上线后浏览器打开即报错。根因 (线上 vis-network.min.js 9.1.2 源码实证): `Network._create()` 开头即 `for(;container.hasChildNodes();) container.removeChild(...)` — **vis 构造时会清空容器的全部子节点**; 美化版把图例面板/缩放控件放进了 `#topo` 容器内, `new vis.Network()` 一执行控件连同 `#zoom-pct` 被当场删除, 下一行 `getElementById('zoom-pct').textContent=...` 即 null → catch 渲染报错 (旧版可用恰因容器为空)。修复: ①恢复「vis 容器必须为空」结构 — 图例/缩放控件/错误层全部改为容器外兄弟节点 (wrapper 内绝对定位), 并在标记处注释该坑防再犯; ②错误路径改写专用 `#topo-error` 兄弟覆盖层, 不再核平 vis 容器 (原 catch 改写容器 innerHTML 会把控件一并删掉, 一次瞬时错误放大为后续所有刷新的 null 崩溃); ③全部 `textContent` 赋值走 setTxt 守卫助手。验证: node --check 语法 + **生产环境 headless Edge 真实渲染验证** (管理员会话开 /topology 真页, 生产 /topology/data 真实数据): 截图确认画布渲染 (26 节点徽章+连线分层布局)、图例计数 (在线7/异常0/外部19/告警2 与数据吻合)、缩放控件与实时百分比 (58%)、Updated 时间戳刷新、#topo-error 覆盖层保持隐藏、pageerror 为零 (原报错消失)。教训记录: vis-network 容器是库的私有领地 (9.x 构造即清空), 叠加层一律做兄弟节点

- 2026-08-18: **评审修复第十七轮 (第十六轮后回归审查, 7 正确性 + 14 清理全修)** — 对第十六轮提交 (e1136d4→38b8d42) 的复审 (8 finder → 26 候选 → 3 验证者 → 7/7 全 CONFIRMED; 其中 5 条系上轮自己引入的回归/过修, 坦白记录): ①ai_engine allowed_hosts 重开 rebinding — 允许集含原始主机名, 跳回原主机名的重定向保留凭据而该跳 urllib 重新解析 DNS (钉住时刻答 loopback、此刻答公网的 resolver 收下明文 key; 改动前 old_host 是钉住的数字地址恰好会剥), 修复: 重定向目标主机名再钉住 (req.pinned_hosts 逐跳传递, netloc 换回钉住地址, 该跳不经 resolver); ②qc_webhook 拒发 http://localhost (五角度收敛回归) — _is_private_host 的 localhost 分支按「唯一调用方」前提删除、同轮被 webhook 这个第二调用方证伪, 修复: 恢复 localhost 域分支 (解析验证 loopback), docstring 如实改写两个消费方; ③inspect ad-hoc 慢 worker 结果丢弃 — Timer(10) 无条件退休 × 严格守卫, SSH 合计略超 300s 预算的健康设备完成时条目已退休 → 真实结果整个丢弃而 status 已 done:true (守卫注释「退休只发生在全部 worker 结束后」对此路径为假), 修复: ad-hoc 退休延窗对齐 max(N*60,10)s 且带 expected 身份守卫 (与定时路径同款); ④config_backup '::1' 完整地址被 ≥2 段门槛误杀 (单 hextet 完整地址只有一段, 孤儿过滤 0 行), 修复: q_addr 可解析的完整地址放行; ⑤阴性 TTL 期文案把 resolver 打嗝报成「必须使用 https」配置违规 (用户直接看到原文), 修复: localhost 域拒绝文案区分「无法解析」+ 失败路径留服务端告警日志; ⑥_form_int 静默回落 (修 422 时造出的第三条错误通道: 填 abc 得到间隔 1 的计划无反馈落库, edit 模态 JS submit() 绕过浏览器校验), 修复: 无效返回 None 走 ?error= 闪现拒绝 — /verify 又抓到空串绕过 (FastAPI 把提交的空串替换成 default, default="1" 时清空数字框经 HTTP 静默变 1 落库, 探针意外建了 3 个 hourly 测试计划已确认删除), 修复: default 改 "" 让 缺席/清空 两路都收敛到闪现; ⑦碰撞标注混入 ip 数据字段 (exportSelected 精确匹配对碰撞组永远「未找到匹配设备」、过滤命中散文), 修复: ip 保持纯值 + conflict 另立字段 (记录碰撞另一方), 模板按字段渲染徽章; ⑧清理: _current_entry 守卫谓词收敛 (手写四份两变体→一个命名助手, 单元外冗余预检删除 — helper 对非 locked 首次即抛, 单元内检查完全等价); _rollback_and_log 收敛三份逐字 except 体; apiErrorText 上移 base.html 三页共用; query_or_empty 删死 callable 分支; custom_cmds 设备选择器窄化五列; 判定按 host 前缀记忆化 (N 文件→D 设备); 容量护栏简化 (超限直接清空); 死端口 try/except 与死空查询守卫删除。验证 38/38 (temp-DB: 再钉住三跳/localhost 四态/文案区分+日志/容量护栏/守卫收敛三态/重试窗口丢弃/::1 六形/冲突纯值+另立字段/闪现四形含空串/收敛源码断言) + 生产 HTTP 复探 (空串/缺席/abc 三路闪现, 列表 3 个真实计划, adhoc 共享函数无内联残留)。部署链: 本轮网络路径对突发流量严重断连, 部署脚本加涓流 (2KB/0.5s) + 8 次重连。记录在案不改: devs_snapshot 显式 origin 参数 (未来给 APScheduler 加快照会让 once 永久重火) / 出站策略完整上提 egress 模块。另: 部署中断排查发现 ps 显示 uvicorn 起于文件落盘同秒的时序问题已由「上传→重启」顺序+线上行为双重证据覆盖

- 2026-08-18: **评审修复第十六轮 (第十五轮后回归审查, 12 CONFIRMED + 2 PLAUSIBLE 全修)** — 对第十五轮提交 (e1136d4) 的复审 (8 finder → 37 候选 → 去重 14 正确性 + 15 清理 → 4 验证者对抗核实, 两条线上抓包/实测复现); 评审锚定服务器导出的 e1136d4 原始树 (本地镜像含未部署的后续迭代, 经审计后采纳为基底 + 补齐缺口一并部署): ①ai_engine 出站链三连 — Host 头此前用原始 netloc, URL userinfo (http://user:pass@…) 凭据被明文写进发往对端的请求头并落网关访问日志 (线上复现), 改按 主机名+端口 重建; 手工 Host 头在重定向后原样存活 (_SafeRedirect 只剥 Authorization, 内部 vhost 名泄露给重定向目标并错误路由, 线上复现), 改为按请求跟踪允许主机集 ({原始主机} ∪ {各钉住地址}, 逐跳传递), 出集的跳转 Authorization 与 Host 都剥、集内保留 (回原始主机名的良性重定向不再被剥成匿名 401); 单地址钉住破坏 getaddrinfo 多地址回退 (双栈 localhost + 网关只听 ::1: 改动前能连、钉死后拒连且 key 明文送到 127.0.0.1 上的无关服务), 改钉候选地址列表 (IPv4 在前) + _call_llm 拒连/连接重置时按序回退备用地址 (超时/解析失败不回退, 防止 120s 超时成倍放大); ②阴性解析结果带 60s 短 TTL 缓存 (阳性 300s + 256 项容量护栏) — 黑洞 resolver (getaddrinfo 阻塞数秒到数十秒, 不受 LLM_TIMEOUT 覆盖) 此前每个新轮次拖一次且无服务端日志, 完全不缓存又回到「一次性故障关死 provider 到重启」; ③inspect 僵尸守卫两处补全 — 条目被退休 (非替换) 时苏醒线程照常入库 (ad-hoc 路径 Timer(10) 无条件退休 + uuid 键永不复用, 超 300s 仅 10s 即无守卫), 守卫改严格 (活跃条目非本轮实例即丢弃, 含 None); 身份预检不在 _persist 重试窗口内复查 (预检通过后 ~5s locked 退避期间新一轮重建同键条目, 旧 worker 末次重试照样落库 — 预检被自家重试助手击穿, 而重试后的进度字典写反而有守卫), _persist 内每次重放先复查, 被取代则抛 _StaleRunError 由调用点捕获丢弃 (进度也不推进: done 份额属于新一轮); ④run_now 的 last_run 戳记 — 只挡 locked 时删行抛 StaleDataError 穿透 (线程已启动却 500, 「启动后假失败→隐形运行」正是上轮要消灭的; 重试窗口变体抛 ObjectDeletedError), 且重试在请求线程里最坏 ~20s 同步阻塞 (3×busy_timeout + 纯睡, 而纯 APScheduler 路径 worker 完成时本就再写一次); 改单次尝试 + 全量兜底, 失败只记日志; ⑤once 计划自动停用不分手动/定时路径 — 管理员「立即执行」冒烟测试未来日期的一次性计划会把它永久禁用 (真正的定时触发永不发生), 改为仅在纯 APScheduler 路径 (devs_snapshot is None) 停用, 且禁用独立成重试单元 + finally 摘 job (last_run 失败不得把禁用整段跳过, 否则到点重火); ⑥config_backup 过滤 — 冒号垃圾 fail-open (':' sanitize 成 '_' 匹配一切带时间戳前缀, 注释自称 fail-closed 只对无冒号垃圾成立), 兜底通道改双重准入: sanitize 后须含字母数字 且 冒号形须 ≥2 个非空十六进制段 (':1'→'_1' 会子串命中 '_16_1_1' 类, 有界但过宽); 大小写归一 + IPv6 压缩/展开形按地址相等比对 + 匹配器工厂 (查询派生值循环外算一次, 不再每文件 re.sub); 前缀碰撞不再静默归一边 (标记「前缀冲突」显示); ⑦scheduler 页其余表单端点 — 非法类型静默 303、时间解析失败裸 400 JSON (普通输入即可触达, 全局处理器只软化 403), 全部改 ?error= 闪现; 错误横幅换标准 .alert alert-error 模式 (此前手搓 card+内联样式且引用不存在的 --red 令牌); /verify 阶段又抓到同类的相邻路径: 整型字段 (schedule_day/interval_hours) 的 `int = Form()` 对非数字输入 (数字框清空/填 abc) 抛裸 422 验证 JSON — int 默认值只在键缺席时生效, 改 str 接收 + _form_int 容错解析 (无效回落默认并钳位), 月日/间隔/类型/时间四类非法输入全部闪现; ⑧qc_webhook 出站策略 (altitude) — payload 携带 QC token 而 QC_WEBHOOK_URL 是 env 可配, http 公网一次误配即 token 明文出网, _post 前按与 ai_engine 同源的 _is_private_host 校验 (https 恒放行 / http 仅内网), 拒绝则记日志跳过不触网; ⑨顺带清理: _normalize_host 单一来源 (校验/判定两份归一, _is_private_host 死 localhost 分支删除); wants_json 共享 Accept 谓词; _reject 薄包装恢复 (错误站点不再共享魔键协议); helpers exc_info=err 替手搓三元组; query_or_empty 直收 Query 对象 (四处 lambda 包装消除); 调用方重复耗尽日志收敛 (what 携带上下文); scheduler_page/backup_page 窄列 (不再物化加密密码); {% set is_admin %} 单次定义; adhoc.html 守卫补双键 (落后的第三份拷贝); _light_device_rows 提取共用。验证 42/42 (temp-DB: 钉住三态/阴性 TTL 三步/Host 重建/拒连回退/重定向双向/重试窗口取代丢弃/退休条目丢弃/once 分路径/StaleDataError 兜底/单次戳记/冒号双重准入六形/出站策略五态/窄列渲染) + 生产 HTTP 全绿 (横幅渲染/三端点 ?error= 闪现非裸 400/冒号垃圾 0 行/双角色门控/adhoc 双键/只读 403)。记录在案不改: 出站策略整体上提独立 egress 模块 (qc_webhook 已按同源复用, 完整迁移待后续) / devs_snapshot 语义拆分为显式 origin 标记

- 2026-08-18: **评审修复第十五轮 (第十四轮后回归审查, 16 项全确认 + 顺带 6 清理)** — 对第十四轮提交 (bd38745) 的复审 (8 finder → 30 候选 → 去重 16 正确性 → 5 验证者对抗核实: 15 CONFIRMED + 1 PLAUSIBLE + 0 驳回) 并全部修复: ①ai_engine 钉住分支三条高危 — 纯 IPv6 loopback (::1-only) 主机被无条件钉到 127.0.0.1 (连接导向另一个 socket: 拒连, 或更糟明文 Bearer key 落到 127.0.0.1:port 的无关服务), 改为钉到实际解析出的 loopback 地址 (IPv4 优先, IPv6 以 [::1] 形式进 netloc); 裸 localhost 被豁免出钉住分支 (_is_private_host 零解析直接放行, 上轮声称关闭的 rebinding TOCTOU 在最常见的主机名上依然敞开), 与 *.localhost 同走解析+钉住; u.port 对非法端口 (:abc/:99999) 抛裸 ValueError 且 _check_base_url 在 _call_llm 的 try 之外被调用 (穿透 run_agent_turn 的 RuntimeError 捕获网, 每轮对话给用户吐「内部错误: Port could not be cast…」), 包成「端口非法」RuntimeError; ②阴性解析结果永久缓存 (一次性 resolver 故障或先配 provider 后加 hosts 条目, 该 provider 被拒到进程重启) — 只缓存阳性 (主机名→钉住地址, 钉住后连接不经 resolver, 永久安全), 阴性每次重查; ③钉住后 Host 头变成 127.0.0.1 (本机网关按 Host 做 vhost 路由的部署全打默认 vhost 404) — _call_llm 在 netloc 被改写时显式保留原 Host; ④inspect 僵尸线程的持久化副作用无守卫 (上轮的 entry 身份守卫只护两处 _progress 字典写, _persist 单元 — InspectionRun 落库/Device.status 覆写/AlertHistory 插入 — 在守卫之前无条件执行, 挂死 SSH 线程苏醒后陈旧结果按当前时间落库且毫无痕迹) — 入库前加身份检查: 活跃条目已换成新一轮实例则整个丢弃过期结果并告警 (条目已退休 None 时保持原行为, 只挡新旧交替); ⑤run_now 的 last_run 裸 commit 漏出重试收敛 (线程与进度条目已建后遇 locked → 500, 管理员看到失败不再轮询, 巡检在后台隐形跑完) — 走共享重试, 耗尽只记日志 (last_run 是展示字段); ⑥scheduler 页全选复选框漏出 is_admin 门控 (#batch-del-btn 已门控, showBatchBtn 裸解引用 null → 只读用户点全选必抛 TypeError) — 复选框入门控 + JS null 守卫双保险; ⑦config_backup 孤儿 IPv6 过滤回归 (上轮改真实 IP 反查后, 设备已删的备份退回 '2001.db8..1' 有损还原, 冒号形查询永远匹配不上) — 含冒号的查询退回与文件名同编码的 sanitize 前缀比对 (仅限冒号形, 垃圾值 '%' 仍 fail-closed); 反查 order_by(Device.id) 定序 (碰撞归一不再跨请求飘移) + 只取 ip 列 (不再物化加密密码); ⑧_json_or_redirect 泛化收敛 (run_now 成功路径的第五份 Accept 嗅探一并收编), 重定向分支带 ?error= 闪现到列表页错误横幅 (此前表单 POST 出错被静默弹回, 与本轮修的 AJAX 静默失败同类); ⑨_run_scheduled 计划侧 TOCTOU (设备快照修了设备侧, 但线程内重查 sched.enabled: 校验→线程启动之间计划被停用/删除仍产出 done:true/progress:null 假完成墓碑) — 快照路径视为已校验的一次性请求照跑, sched 缺失仅跳过 last_run 回写; ⑩顺带: _run_batch 异常兜底退休补 expected=entry 身份守卫 (同函数 _clean 线程有兜底没有); helpers 重试耗尽日志补 traceback (旧 logger.exception 的堆栈在收敛时丢了, next_run 为 NULL 只剩一行无堆栈 error) + 退避加 jitter (N 线程 locked 齐步重试再相撞); base.html triggerInspect 守卫补 err.error 双键 (与 scheduler.html 的漂移消除 — {error} 形状的 400 曾只显示裸「HTTP 400」); 渲染降级收敛 helpers.query_or_empty (custom_cmds 记日志/ping 静默吞统一为记日志, 且逐查询独立降级) + ping 页查询窄化三列; scheduler.html 失效注释修正。记录在案不改: localhost 策略归 ipnorm 模块/只读门控统一机制/crypto priority-3 icacls 拷贝/commit 重试契约收敛等独立清理项 (下轮评审候选)。验证 31/31 (temp-DB: 钉住四态+端口守卫+缓存阴阳+Host 保留/耗尽 traceback/快照 TOCTOU 停用+删除/_json_or_redirect 三形态/僵尸线程入库守卫/冒号查询双命中+fail-closed/降级助手) + 生产 HTTP 全绿 (双角色门控精确标记重探/表单 303→?error=→横幅渲染/AJAX 错误形状/只读 token 403/fail-closed 探针)

- 2026-08-17: **评审修复第十四轮 (第十三轮后回归审查, 6 报告项 + 7 迟到项)** — 对第十三轮修复提交 (9920f1d) 的复审 (8 finder + 内联对抗验证, 6 报告; 迟到的 finder 代理补 7 项, 去重后全部收录) 并修复: ①scheduler.html 的 runSchedulerNow 漏跟第十二轮 ⑩ 的 resp.ok 守卫 — run-now 提为 require_admin 后, 非 admin 用户点击得到 403 {detail} (无 error 键), 前端把字符串 "undefined" 写入 localStorage 并轮询 /inspect/status/undefined, 且 base.html 的 resume 逻辑每次页面加载重放假轮询 (与 base.html 当年 bug 同类的孪生副本); 补 resp.ok 拦截, 错误文案 err.error || err.detail 双键兼容; ②execute_multi 的降级两条泄漏路: 只 catch OperationalError — 执行期间设备被删时 commit 抛 StaleDataError/FK IntegrityError 穿透成 500 (验证实测复现 StaleDataError); 且降级后的渲染查询仍在可能已死的会话上执行 (rollback 被 except-pass 吞掉的场景), 照样 500 — 非 locked 异常同样降级 + 渲染查询失败空列表兜底, 已完成的整批 SSH 结果两条路都不再丢; ③*.localhost 的 loopback 校验只在配置检查时刻做一次, urllib 连接时重新解析 DNS — rebinding TOCTOU 可让 Bearer key 明文离机; _check_base_url 改为返回钉住后的 URL (*.localhost 验证全 loopback 后替换为 127.0.0.1, 连接不再经过 resolver), 顺带修复带 scope IPv6 (fe80::1%eth0) 的 ValueError 崩溃 (新引入的崩溃类别), 解析结果按主机名缓存 (_check_base_url 每个 LLM 轮次都跑, 慢 resolver 下重复 getaddrinfo 会拖垮对话); ④_backup_host_prefix 的「唯一定义处」名不副实 — 真正的备份写入方 (仓库根 inspection.py) 保留内联副本; 助手移入 helpers.py 单一来源 (config_backup 三处 + config_compare 共用), docstring 如实标注外部写入方须同步; ⑤第三份手写 SQLite-locked 重试单元 (inspect._persist / execute_multi._persist_all / load_all_schedules) 收敛为 helpers.commit_with_locked_retry — rollback 会丢弃暂存对象必须重放整单元的微妙点 (第十二轮 MULTI-2 实证写错国一次) 不再要每个写入方重新推导; load_all_schedules 内层 per-schedule except 不再吞 OperationalError (rollback 过期对象的惰性刷新遇 locked 曾被误分类为单条注册失败, 空提交成功即 break — 计划永不注册且 next_run 为 NULL); ⑥run_now 函数内四份 Accept 嗅探 + 局部 import JSONResponse 收敛为 _reject 助手; ⑦迟到项: run_now 把已校验非空的设备快照直接交给工作线程 (消除「校验→线程再查」之间设备被删的空设备假完成墓碑 TOCTOU); _run_scheduled 纯 APScheduler 路径空设备分支补告警日志 (第十三轮 ⑪ 只补了异常路径); _inspect_one 加 entry 身份守卫 (周期任务复用 sch_{job_id} 键 + 线程池 wait=False, 上一轮挂死 SSH 线程苏醒后曾把 done+=1 和结果写进新一轮条目); scheduler 页六个写控件 is_admin 门控 (非 admin 真只读, 不再点得到按钮却整页跳 403 JSON; devices 页同类项维持第十二轮缓议); crypto priority-3 迁移路径的 chmod 与写文件同 try (priority-4 同款问题的同源拷贝) 拆为 else 仅告警; ping _render 的设备查询失败降级空列表 (子进程结果优先) 且 ping_page 复用 _render; config_backup 列表改用设备表反查真实 IP — 前端 exportSelected 的有损还原匹配落空让 IPv6 备份导出从唯一 UI 入口够不着 (第十三轮 ⑥ 只修了服务端), 列表 IPv6 乱码列与垃圾过滤值 fail-open 一并修复。记录在案不改: sanitize 前缀碰撞 (1.2.3.4 与 1:2:3:4 同映射 1_2_3_4) — 碰撞在磁盘文件名层面, 写入方在未检入的 inspection.py, 单方改字符集会让已有备份孤儿化。验证 30/30 (temp-DB 直连: 共享助手三态/快照 TOCTOU/重试重放/StaleDataError 降级/死会话渲染兜底/entry 身份守卫/localhost 钉住+缓存+scope 守卫/迁移 chmod/真实 IP 反查+fail-closed) + 14/14 (生产 HTTP 回归) + 线上表面 /verify PASS (双角色门控/四种错误形状/mtr 渲染/零生产写入探测)

- 2026-08-17: **评审修复第十三轮 (第十二轮后回归审查, 11 项 = 10 修复 + 1 顺带)** — 对第十二轮修复提交 (321620f) 的复审 (基线→当前累积 diff, 27 文件, 8 finder + 逐条对抗验证, 10 确认/存疑取 10) 并全部修复: ①scheduler 六个写端点 (add/toggle/delete/run-now/edit/batch-delete) 仍是 require_auth — README 权限矩阵声明定时任务为管理员模块, 普通登录用户可增删改/立即执行任意巡检计划 (第七轮曾统一提升设备/命令/推送模块, 此模块漏网); 全部提为 require_admin (页面 GET 保持 require_auth 只读可看); ②execute_multi 末尾 commit 三次重试仍 locked 时 raise db_error 原样上抛 — SSH 工作已全部完成, 一个 500 把成功的整批结果 (所有设备的输出) 从用户眼前丢掉, 只有日志可见; 改为降级渲染: 结果照常展示 + 页面顶部「未保存到巡检记录」横幅 (与 inspect.py 的 db_error 降级同策略); ③巡检中途设备 IP 被编辑时, _inspect_one 用实时 dev.ip 覆盖进度键快照 — 旧键条目留在 devices 里无人更新, 前端出现永远「等待中」的幽灵卡片, 新键不在进度里结果也不可见; dev_key 改为快照优先 (None 才取实时值); ④run_now 对绑定设备已全部删除的计划照常返回 200 + run_id, 工作线程立即退休进度, 前端轮询看到 done:true/progress:null 的假完成墓碑 (零设备且无错误); 端点前置 400「该计划没有可巡检的设备」; ⑤load_all_schedules 启动路径批量注册 + 单次 commit 遇 SQLite locked (与备份/清理任务并发) 无重试 — job 已在 APScheduler, next_run 却永远 NULL 且无任何页面提示 (第十轮的批量化把第八轮的逐条容错一并简掉); 补 3 次 locked 重试 (rollback 会丢弃暂存的 next_run 赋值, 重试重放整个注册+提交单元, _register_schedule 幂等), 仍失败则整体 rollback 记日志, 计划页对「启用但 next_run 为空」补警示徽标; ⑥配置备份文件名 host 前缀两套写法漂移: 备份写入用全字符集 sanitize (re.sub), export_zip/列表过滤/config_compare 却用 ip.replace('.','_') 只替换点号 — IPv6 设备 (含 ':') 的备份文件导出 ZIP 漏选、按设备过滤匹配不到、对比页加载不到; 收敛为 config_backup._backup_host_prefix 单一定义四处共用; ⑦ping_post 在请求开头就查全部设备, 随后 mtr/tracert 子进程最长 35s — ORM 结果集连着 Session/连接被整个子进程期间占住, 小连接池下并发几个 trace 即可耗尽; devices 查询收敛进 _render 助手, 渲染时才查; ⑧_is_private_host 对 *.localhost 主机名不解析直接放行明文 http — RFC 6761 规定 localhost 域应解析回本机但依赖 resolver 配置, 「evil.localhost」若被指向公网, Bearer key 随之明文发出; 现仅 localhost 本身直接放行, *.localhost 要求 getaddrinfo 全部结果为 loopback; ⑨crypto 密钥自举 (priority 4) 的权限加固 (chmod/icacls) 与写文件在同一个 try 里 — 加固失败会触发 fallback 把同一把新 key 再写一份到 legacy 位置 (两处残留), 日志还谎称「falling back to legacy」; 重构为仅 mkdir/write 失败才走 legacy fallback, 加固失败只告警; ⑩P12 下载表单密码无前端约束 — 短密码 (<8) 提交后被后端 422 拒绝, target=_blank 的新标签页显示裸 JSON 错误; 输入框补 minlength=8 + 提示文案 (后端校验不变, 双保险); ⑪顺带 (复审中另一个恢复的旧评审代理发现): _run_scheduled 外层兜底在纯 APScheduler 路径 (run_id=None) 下整段静默 — 定时巡检的设备/计划查询失败会没有任何日志痕迹; except 分支改为恒记日志, run_id 守卫只管退休进度。验证 26/26 (temp-DB 直连: require_admin 计数/空设备 400 无进度/locked 重试重放后 next_run 真实落库+job 注册/入库全失败降级渲染不 500/IPv6 前缀导出+过滤+对比加载/localhost 解析四向/chmod 失败不双写 legacy/minlength 表单/恒记日志顺序) + 14/14 (生产 HTTP 回归)

- 2026-08-17: **评审修复第十二轮 (第八至十一轮累积复审, 10 项)** — 对 2026-08-12 基线至 2026-08-17 累积 diff (26 文件) 的复审 (8 finder + 逐条对抗验证, 12 确认取 10, 另 2 项轻微 UX 残留缓议) 并全部修复: ①_is_private_host 用 ipaddress.is_private 判定过宽 — TEST-NET (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24)、benchmark 198.18.0.0/15、192.0.0.0/29 均被判私网而放行明文 http, 解密后的 Bearer key 会发到非 RFC1918 地址; 改显式 _ALLOWED_HTTP_NETS 网段表 (RFC1918 + loopback + IPv6 ULA); ②_exec_show 的占位审计行 (status=executed) 提交在前、`dev = session.device` 解析在后且在 try 外 — 解析抛错 (如会话被并发删除后的懒加载失败) 会留下一条永不执行却记为已执行的假审计且限流槽位不释放; 设备解析移到占位提交之前; ③execute_multi 第八轮把逐台 commit 收敛为末尾单次 commit 却没带 inspect.py 同款的 locked 重试 — 与定时巡检并发写入时 SQLite locked 会让整批 (全部设备的 InspectionRun + Device.status) 一次 500 全丢; 补 3 次重试, 且因 rollback 会丢弃已 add 的暂存对象, 重试必须重放整个「入库+commit」单元 (首轮修复只重试 commit 本身, 被验证抓出: 重试成功却零行落库); ④_run_batch 的退休清理线程睡 len(设备)*60 秒后无条件 retire_progress — 周期任务复用 sch_{job_id} 键, 休眠超过任务间隔 (如 100 台设备的 hourly 任务睡 6000s > 3600s) 时上一轮的 sleeper 会把下一轮在途运行墓碑化 (设备明细全丢、状态页误报完成); retire_progress 增加 expected 身份参数, 锁内确认条目仍是本 run 创建的实例才退休; ⑤dashboard 与 /api/dashboard/stats 的 last_time 对 timestamp 无 NULL 守卫 — 该列可空 (第九轮 RunResponse 改 Optional 已承认此类行存在), 全 NULL 场景 strftime 抛 AttributeError 全站 500; 两处补判空 (注意 SQLite DESC 排序 NULL 在最后, 混合行不受影响); ⑥_rate_ok (show 路径) 按 created_at 计数而 confirm 复检按 executed_at — 陈旧卡片确认后的执行对 show 限流不可见, 两限流器各放 6 条实际可达 12 条/分钟, 同分钟提议+确认又被双计; _rate_ok 统一改按 executed_at, 与注释「两限流器必须一致」落到实处; ⑦ConfigExecError 用 getattr(ex, 'output', '') 取部分输出 — .output 是 subprocess.CalledProcessError 的属性, netmiko 4.x 全版本异常均无此属性 (已核对 4.2/4.7 源码), 部分生效的配置下发永远拿不到设备输出, 该类的存在意义落空; 改为异常后 read_channel() 尽力读回通道残余; ⑧execute_multi 的 pool.submit 字典推导中途抛错 (线程池损坏/资源耗尽) 会让已提交设备的 SSH 执行结果与全部审计随 500 丢弃; 改逐台 try, 单台记「任务提交失败」继续整批; ⑨run_now 对停用计划仍返回 200 + run_id, 工作线程毫秒级退休进度, 前端轮询看到 done:true/progress:null 的假完成墓碑 (用户的手动执行实际从未发生且无任何提示); 端点前置 400「计划任务已停用」; ⑩base.html 共享 triggerInspect (devices/dashboard/_stat_cards 页沿用) 漏跟第七轮 K5 的 404 语义更新 — 只查 data.error 不查 resp.ok, 零设备时点巡检会把字符串 "undefined" 写进 localStorage 并轮询 /inspect/status/undefined, 真实错误「没有可巡检的设备」被吞; 补 resp.ok 拦截。缓议 (轻微 UX 残留): P12 短密码裸 422 JSON 页、非 admin 用户的设备页表单无 is_admin 门控 (提交才 403)。验证 18/18 (temp-DB 直连: 网段表双向/executed_at 计数两向/dev 解析顺序/read_channel 部分输出/submit 失败整批保留/locked 重试真实落库/expected 身份退休/全 NULL dashboard/停用 400/base.html 拦截) + 14/14 (生产 HTTP 回归)

- 2026-08-17: **验证修复第十一轮 (生产实击发现, 1 项)** — /verify 驱动生产 HTTP 表面时发现: 启用中的计划 next_run 恒显「—」, 生产库该字段为 NULL, 应用日志每次重启都有 `注册计划任务失败 id=3 / AttributeError: 'Job' object has no attribute 'next_run_time'` — main.py 的 load_all_schedules() 在 scheduler.start() 之前运行, pending job 没有 next_run_time 属性, 该启动路径自第七轮 S1 引入 next_run 字段起从未成功 (历次 temp-DB 验证全部漏掉: 测试进程 import backend.main 时调度器已启动, 与生产启动顺序不同; 调度功能本身不受影响, 仅展示字段为空)。修复: _register_schedule 在 job 无 next_run_time (pending) 时直接用 trigger.get_next_fire_time 计算下次触发, 不再依赖已调度 job。验证 6/6 (temp-DB 复现生产启动序: 未启动调度器下 load_all_schedules 持久化 next_run=次日 06:00 / 已启动调度器主路径回归且与 APScheduler 自算一致) + 生产实查: DB next_run=2026-08-18 06:00:00, 计划页「day」行渲染 08-18 06:00, 重启日志无新增注册失败

- 2026-08-17: **评审修复第十轮 (第九轮后回归审查, 4 项)** — 复审在第九轮提交 (f2b1de9) 上确认 4 项新发现并全部修复: ①设备在巡检中途被删除 (或 Device 查询遇 SQLite locked) 时, 第八轮为消幽灵数字键把失败路径的 per-device 写入整个跳过 — done 照常递增, 该设备卡片却永远停在「等待中」, 失败在 UI 完全不可见, 操作员会把不完整结果当完整结果信任; 现 _inspect_one 增加 ip_hint 参数 (调用方在初始化进度时已知 id→ip 快照, 经 _run_inspection_sync 与 scheduler._run_batch 两条批量路径传入), 设备加载失败时把「设备已被删除」错误写到真实 ip 条目; ②confirm 路径限流复检仍只计 executed/confirmed, 与第八轮收紧后的 _rate_ok (show 路径, 含 failed) 策略分叉 — confirmed 卡片执行翻成 failed 后会释放 confirm 侧槽位却仍占 show 侧, 失败爆发时 confirm 密集操作可超出设备保护速率; 现两处限流同策略计入 failed; ③load_all_schedules 第八轮改为逐条 _register_and_persist (每条一次 commit), 而 expire_on_commit 默认开 — 每次 commit 过期会话内全部 ORM 对象, 后续迭代的属性读取被迫惰性重 SELECT (N 条计划 = N commit + N-1 次刷新, 注册本就相互独立无事务收益); 启动路径恢复批量注册 + 单次 commit (注册异常仍按条隔离, commit 失败整体 rollback), 端点路径保留 _register_and_persist 单条即时持久化语义; ④save_inspection_run 的 commit 标志曾翻转返回类型 (True→None / False→run) 且唯一的 commit=False 调用方并不使用返回值 — 双形态是死通用性也是误用陷阱, 现统一始终返回 run 对象。验证 11/11 (temp-DB 直连: 删除设备写真实 ip 错误条目/无 hint 不产生幽灵键/key_map 两条批量路径接线/failed 占 confirm 槽位/单次 commit/next_run 持久化/rollback 回归/双路径返回 run) + 14/14 (生产 HTTP 回归)

- 2026-08-14: **评审修复第九轮 (第八轮回归审查, 10 项 = 9 修复 + 1 记录在案)** — 对第八轮修复提交 (c88d6f1) 的复审 (8 角度, 10 确认) 并全部处理: ①_register_and_persist 吞 commit 失败却不 rollback — load_all_schedules 单会话循环里一次失败 (SQLite locked) 会毒化会话, 后续全部计划连锁失败, 且 job 已注册进 APScheduler (「未注册」徽标不会提示) 而 next_run 永不持久化; 现 except 内先 db.rollback() 再记日志, 会话可继续用; ②_get_fernet 的 DecryptError 包装第八轮贴在 encrypt/decrypt 两个调用点, get_secret_key_bytes (cases 的 HMAC URL 签名) 仍漏裸 ValueError 500 — 包装收敛进 _get_fernet 内部 (实际解析拆为 _resolve_fernet), 全部现在与未来调用方一处生效; ③execute_multi 超时/异常分支构造了超时错误结果却把 conn_error 置 None, 从未连上的设备落库 status=connected (仪表板把不可达设备显示成健康) — 超时错误串现同时进 conn_error, 状态落 error; ④RunResponse 的 cpu/memory/uptime/hostname/status/timestamp 声明非 Optional 但 DB 列可空 (默认值仅 Python 侧) — 历史/手工修库的一行 NULL 曾让整个 /reports/api 500 (旧 _run_dict 能序列化 null), 现全部 Optional; ⑤_run_scheduled 外层兜底曾把「_run_batch 已成功、仅 last_run/next_run 提交失败」的运行也墓碑退休 (客户端轮询一个实际成功的运行会丢失每台设备明细) — batch_done 标志收窄退休范围, 只兜 _run_batch 接管之前的失败; ⑥每会话限流锁表 _rate_locks 无回收路径 (软删除会话的锁永久滞留, 长驻进程缓慢内存增长) — drop_session_locks 在 delete_session 同时回收 seq/限流两张锁表; ⑦(label, command) 归一化曾三处复制且已漂移 (c.get('description') vs c['description'] 的 KeyError 风险) — 收敛为 _cmd_pairs 单一定义; ⑧resolve_provider 的 RuntimeError→400 兜底三处复制收敛为 _provider_or_400; ⑨_session_rate_lock 与 seq_lock 字节级复制收敛为 _keyed_lock 工厂。记录在案不改动: /reports/api 时间戳保持 ISO-8601 (与第七轮之前的长期格式一致; 空格分隔格式仅存在于第七至第八轮之间数日, 无 in-repo 消费方)。验证 20/20 (temp-DB 直连: 坏密钥三路 DecryptError 含 get_secret_key_bytes/commit 失败后会话仍可用/超时 conn_error 落 error/原生 SQL NULL 行不再 500/锁表回收/400 经 wrapper/failed 计数回归) + 14/14 (生产 HTTP 回归)

- 2026-08-14: **评审修复第八轮 (第七轮回归审查, 25 项)** — 对第七轮修复提交 (3d7a38c) 的复审 (8 角度 40 候选, 去重 25) 并全部修复, 多为第七轮修复自身的回归与未竟项: ①_is_private_host 重写误伤两端 — localhost/*.localhost 主机名被 ipaddress 解析拒绝导致本地模型网关 (http://localhost:11434) 被砖, 同时 is_private 过宽把链路本地段 169.254.0.0/16 (含云元数据 169.254.169.254) 与 0.0.0.0 放行为「内网」允许明文 http; 现显式放行 loopback+localhost 主机名, 排除 link-local/multicast/unspecified/reserved; ②失败的 show 命令翻成 failed 后不被 _rate_ok 计数, 设备宕机时限流槽位反而失效 (与注释自相矛盾) — 计数纳入 failed; ③进程级 _rate_lock 全局串行化改每会话锁; ④resolve_provider 的密钥不匹配 RuntimeError 在 chat/建会话/切供应商三处端点无捕获变 500 — 统一兜为 400 JSON; ⑤execute_multi 仍把 ORM CustomCommand 对象传进工作线程 (C2 只转换了 Device) — 请求线程预物化为纯 dict, run_commands_on_device 契约改 (results, conn_error) 元组并在入口归一化 cmds, 连接失败从「字符串前缀嗅探」改为数据返回; ⑥decrypt/encrypt 的 _get_fernet() 调用纳入 try, 畸形 INSPECT_SECRET_KEY 的裸 ValueError 统一包装为 DecryptError (不再从收窄的 except 逃逸成批次中途 500); ⑦_run_scheduled 恢复外层异常退休兜底 (R2 抽取时丢失, run-now 的 DB 查询失败曾永久泄漏进度条目); ⑧自定义命令 /delete 与 /toggle 补升 require_admin (V2 漏网); ⑨next_run 写库前 astimezone(CST) 转换 (UTC 容器里 hourly 计划曾差 8 小时); ⑩K4 兜底进度键幽灵条目修复 (设备加载失败时不再以数字 id 为键, 真实条目不永卡等待中); ⑪dashboard 删除冗余 latest 查询改用 all_runs[0] (该查询还漏了 defer raw_data); ⑫/register 三处复制收敛为 _register_and_persist; ⑬count_all_schedules 并入 load_all_schedules 返回 (registered, total) 单会话; ⑭定时/默认巡检设备查询改只取 id/ip 两列; ⑮main.py 残留 CST 副本删除; ⑯/reports/api 恢复 ISO-8601 时间戳 (改走 schemas.RunResponse + config_backup 扩展字段, raw_data 仍排除); ⑰cases 搜索 limit(500) 静默截断改 501 探测 + 模板横幅提示; ⑱配置备份文件名解析收敛为 _parse_backup_name (list_backups 与 export_zip 同一实现); ⑲ping 模板 devices or [] 防御; ⑳scheduler 页面对「启用但未注册 (配置无效)」的计划显示警告徽标; ㉑_stage_inspection_run 复制删除, helpers.save_inspection_run 加 commit 参数; ㉒_inspect_one 错误字典三份收敛为 _fail; ㉓解密失败结果字典收敛为 _key_mismatch_outcome。验证 30/30 (temp-DB 直连: localhost/link-local/failed 计数/每会话锁/400 兜底/DecryptError 包装/元组契约/commit=False/退休兜底/astimezone/ISO 格式等) + 14/14 (生产 HTTP 回归)

- 2026-08-13: **评审修复第七轮 (全量代码审查, 45 项)** — 对 HEAD (f6de53c) 全量审查 (8 角度 46 候选, 去重 45, 对抗验证 44 确认+1 存疑) 并全部修复: ①只读 token 越权收口: 配置对比 load-config 与 /reports 各接口 (含 raw_data 原始巡检载荷) 改 require_full_user, 只读 token 由 200 变 403; ②AI base_url 内网判定改 ipaddress 解析, 「192.168.1.1.attacker.com」类 DNS 名不再被 startswith 误判为内网而放行明文 HTTP 送 API key; ③CA 私钥下载 (PEM zip/PKCS#12) 提权为 require_admin (权限倒挂修复), P12 密码改为必填 min_length=8 (去掉硬编码默认 "changeme"); ④README 声明的管理员模块落到实处: 设备 CRUD/自定义命令/配置推送的写接口从 require_auth 统一为 require_admin, cases 模块删掉手写副本改用 auth.require_admin; ⑤ping 页任何 POST 不再 500 (模板无条件迭代 devices 而 POST 分支从未传); ⑥CA 页在存在已吊销证书后不再 500 (ca_page 补传 now); ⑦decrypt_password 对 ENC 密文解密失败改抛 DecryptError (8 个调用点全部捕获并给出「密钥不匹配」明确错误), 不再把密文原样当 SSH 密码造成全线误导性认证失败; _get_fernet 加锁堵双线程首发各自生成不同密钥 (文件/内存分叉, 重启后全线不可解密) 的竞态; ⑧计划任务: once 日期解析失败不再静默落回每日 06:00, 非法时间在提交前 400 拒绝 (此前提交后注册才 500, 留下永不运行的行), 「全部禁用」不再触发「无计划→默认每日 6 点全网巡检」兜底复活 (改为按表是否为空判断), next_run 字段真实写入/禁用清空 (此前定义但永远为 NULL, UI 恒显示 -); ⑨main.scheduled_inspection 与 scheduler._run_scheduled 的重复批量执行器收敛为共享 _run_batch, 四处进度初始化收敛为 _init_progress (消除 "等待中"/"waiting" 标签漂移); ⑩巡检: 设备加载/解密/自定义命令查询移入进度保护 (异常不再让前端永远卡在等待中), 未知 device_id 返回 404 而非 200 无 run_id (前端不再轮询 /inspect/status/undefined), 自定义命令执行复用 custom_cmds.run_commands_on_device (消除第五份解密+ConnectHandler 副本, 顺带补齐 BMC 设备 generic 映射与超时漂移); ⑪execute_multi 不再把请求作用域 ORM 对象传入线程池且同 Session 循环内 commit (DetachedInstanceError 竞态), 改预取纯 dict + 循环外单次 commit, 线程池弃用 with 块改 shutdown(wait=False, cancel_futures=True); ⑫AI: reject 改原子条件 UPDATE (与 confirm 竞态不再出现「设备已配置但审计记已拒绝」), 限流复核改按 executed_at 执行时刻统计 (新增列 + 幂等迁移, 旧提案不再绕过 6/分钟执行上限), show 命令限流改锁内原子占位, 空命令步骤直接过滤且全空报错 (不再把 "" 下发设备), 执行异常保留部分输出 (ConfigExecError 携带) 不再把部分生效误报为干净失败; ⑬效率: dashboard 趋势与 /reports 列表 defer(raw_data) (不再每次加载最多 500 条全量 CLI 文本), 导出 CSV 补 joinedload 消 N+1, cases 计数改 GROUP BY (两处), 巡检自定义命令复用连接助手; ⑭杂项: CA/证书私钥文件 chmod 0600+目录 0700, 配置导出 ZIP 设备前缀改 rsplit 修复 .202 结尾 IP 被截断丢失, 内存着色逻辑三处发散副本收敛为 _mem_color (N/A 处理一致), CST 时区三处重复定义收敛到 models, config_push 命令解析/错误重渲染去重 (9 处副本), bom_matcher 死分支与 inspect 死代码删除, 盐长度注释更正。验证 29/29 (temp-DB 直连+接线) + 12/12 (生产 HTTP 探针: ping POST/trace/CA 页/只读 token 403/404/422)。唯一结构性跳过: 巡检与自定义命令的双 SSH 握手 (首个连接在未检入的外部 inspection 模块, 本轮无法收敛)

- 2026-08-13: **容器化 v5 与部署文档** — 基于 HEAD (e714245) 构建 `network-inspection:v5` (=latest, 277MB, 3 秒缓存构建), 临时容器挂生产 DB 一致性副本完成 11 项验证 (登录/设备页/前导零 400/重复 409/端口 422/表单回填/镜像无密钥无 DB/代码与 HEAD 哈希一致), 生产 uvicorn 全程未动; compose 镜像标签 v4→v5; 新增三份文档: `docs/docker-build-v5-verify-2026-08-13.md` (构建验证记录) / `docs/docker-compose-runbook-2026-08-13.md` (运行手册: 预创建清单/挂载表/初始密码/裸进程切容器/故障速查) / `docs/dockerfile-explained-2026-08-13.md` (Dockerfile 逐行解析); README Docker 部署章节重写为 v5 现状 (原章节镜像名/端口/挂载均已过期)
- 2026-08-12: **验证发现收尾 (3 项)** — ①表单路径的校验错误 (前导零 IP/空 IP 等) 此前显示 FastAPI 裸 JSON 页, 现统一渲染进设备页错误横幅并回填已输入字段, 与重复 IP 冲突页体验一致 (API 路径保持 JSON 不变); ②编辑弹窗 422 提示从整段 JSON 改为「字段: 消息」可读格式 (如 `port: Input should be less than or equal to 65535`); ③剥除 main.py 的 UTF-8 BOM。验证 5/5: 表单校验横幅+回填×2 / API JSON 回归 / UI alert 可读 / 空端口保持回归
- 2026-08-12: **评审修复第六轮 (设备管理收尾, 10 项)** — ①编辑弹窗清空端口改为发送 null (服务端保持当前值), 不再被 parseInt||22 静默改指 22 端口; 非法/越界输入原样发送由服务端 422 给出可读提示, 前端不静默改值; ②前导零 IPv4 (010.0.0.1, 八进制歧义写法) 在三条写路径统一 400 拒绝 — 此前落入主机名旁路同时绕过应用查重与唯一索引; ③端口 1-65535 范围校验收敛进 pydantic schema (DeviceCreate/DeviceUpdate 均 Field(ge=1, le=65535)), 创建路径不再接受任意端口, 表单路径保留横幅提示; ④IP 未变更的编辑跳过查重 — 存量重复 IP 行的设备此前编辑任何字段都永远 409、UI 无修复路径; ⑤三处手写的 commit→IntegrityError→rollback→复查收敛为 _commit_or_ip_conflict 助手, 复查不命中 (非 ip 约束) 记日志并返回脱敏 400, 不再裸 raise 把原始 SQL 泄为 500; ⑥启动迁移先 PRAGMA 探测已有唯一索引直接早退 (新装不再重复建第二棵唯一 B-tree, 老库不再每次启动全表扫描); ⑦update 恢复「全部校验 (400/422) 先于冲突 (409)」顺序; ⑧strip+ipaddress 归一化收敛为共享 backend/ipnorm.py (写路径校验与启动迁移单循环共用同一实现, 规则演进不会两处漂移); ⑨迁移发现重复 IP 时回传标志, 设备页挂「唯一索引未启用, 请人工去重后重启」横幅 — 并发兜底静默失效不再无人知晓; ⑩编辑弹窗设备类型改用 dtype_options 宏 (与添加表单同一数据源), 新增类型不再两处维护。全部 23 项验证通过: 前导零 400 且不落库/端口越界 422×3/null 端口保持/重复行编辑放行+改重仍 409 (临时库真实代码)/提交助手 409+脱敏 400/索引探测与早退 (无全表扫描日志)/横幅按标志渲染/宏选项×2/并发双写恰一行/Playwright 空端口发 null 与 422 可读 alert
- 2026-08-12: **评审修复第五轮 (设备管理加固, 10 项)** — ①Device.ip 加 UNIQUE 约束 + 启动幂等迁移 (先归一化存量 IP 再补建唯一索引, 发现重复只告警不建索引), 写路径捕获 IntegrityError 转 409 — 并发双写同一 IP 不再双双落库 (应用级查重存在 check-then-insert 竞态窗口); ②IP 在验证边界归一化 (strip + ipaddress 标准形式: IPv6 压缩小写/去前导零), 「10.0.0.1 」(尾空格)、「FE80::0:1」等文本变体不再绕过查重, 非 IP 字面量按主机名放行; ③编辑设备 password 传空串/null 视为不修改 (此前空串以明文写库致设备永不能认证, null 触发 IntegrityError 500); ④编辑弹窗清空端口不再写入 NULL (JS parseInt NaN→22 兜底 + 服务端 None 丢弃 + 1-65535 范围校验); ⑤空/纯空格 IP 直接 400 (此前可创建空 IP 设备); ⑥编辑弹窗对 FastAPI 422 的 detail 对象数组改 JSON 展示 (此前 alert 显示 [object Object]); ⑦编辑接口恢复「先校验后查重」顺序 (非法输入不再先收到 409 再收到 400); ⑧表单重复 IP 回显时回填已输入的 ip/类型/用户名/端口 (密码不回显), 不再整表重输; ⑨查重逻辑收敛为 _find_duplicate_ip 单一查询实现 + 统一冲突文案, 表单与 API 不再各写一份; ⑩设备页渲染收敛为 _render_devices 统一入口。全部 16 项验证通过: 唯一索引/并发双写恰一行 (200+409)/空格与 IPv6 变体 409/空 IP 400/密码端口空值语义/校验顺序 400/表单回填/Playwright 422 可读提示与清空端口兜底
- 2026-08-12: **设备管理重复 IP 查重** — 新增设备 (表单 + JSON API) 与编辑设备改 IP 三条写路径此前均无冲突检查, 重复 IP 被静默创建, 巡检结果/配置推送/备份文件归属混乱; 现统一应用级查重: 表单路径回显 400 错误横幅「IP 地址 x 已存在 (设备 #n)」并保持表单展开, API 返回 409 Conflict 带冲突设备信息, 编辑弹窗展示服务端错误详情 (此前只有笼统 alert); 编辑保留自身 IP 不误伤 (exclude_self)。全部 10 项验证通过: 表单重复 400+不创建/唯一 303 回归/API 创建 409/编辑改重 409/改唯一 200/自编辑不撞/页面渲染回归
- 2026-08-12: **评审修复第四轮 (10 项+1)** — ①config_push 单台解密失败只记该台失败审计、批次继续 (此前请求线程未设防, 整批中止); ②_run_scheduled 加 cleaned 标志 + finally 兜底退休, 清理线程启动前抛错不再永久泄漏 run_id 进度条目; ③main 定时巡检弃用 with 线程池 (挂死 netmiko 会话会让 __exit__ 的 wait=True 永久卡住 APScheduler 线程), 与 scheduler 对齐 shutdown(wait=False, cancel_futures=True); ④config_push 审计改 5s 增量收割即时入库 (此前挂死线程会把已完成设备的审计拖延到全局预算到期, 期间进程重启 = 真实配置变更无记录); ⑤confirm 动作在原子认领前拦截设备已删 (此前 pool.exec_config(None) 崩 500); ⑥降级重试后模型仍返回空 → SSE 报错提示重试, 不再把空气泡存进对话历史; ⑦fallback 协议支持单行代码块 (```run show version``` 此前因强制换行整体失配, 命令被静默丢弃); ⑧确认卡片瞬时失败 (5xx/网络错误) 恢复按钮可重试且不做终态锁死 (仅 4xx 保持终态, 重试会被「已处理」400 安全拦截); ⑨chat worker 的 SessionLocal 移入 try + SSE q.get 加 30s 超时与 worker 活性检测, worker 静默死亡不再让前端无限等待; ⑩会话自动改名只匹配精确默认标题 (此前 endswith("对话") 会把用户手动改的「xx 对话」标题覆盖)。另修: 巡检面板轮询识别 401 →「登录状态已过期」并停止。全部 20 项验证通过: 单行/多行代码块解析/异常退休墓碑/坏设备批次继续双审计/已删设备 404 不认领/mock LLM 空响应报错不存气泡/单行 run 块真机执行落库/标题两分支/Playwright 确认卡 500+断网+400 三态/401 面板/run-now happy path 回归
- 2026-08-12: **评审修复第三轮 (12 项)** — ①config_push 全局预算按波次缩放 (ceil(设备数/workers) x 单波最坏路径), 超过 10 台时合法排队的推送不再被误报挂死; 审计区分「未执行 (被取消, 设备未触碰, 可安全重试)」与「疑似挂死 (状态未知)」; 推送线程改用纯数据 dict (请求线程 commit 使 ORM 对象过期后, 僵尸线程惰性刷新会静默丢审计); ②scheduler run-now/定时巡检/main 定时巡检三处清理统一走 retire_progress 墓碑退休, 运行中的巡检不再被误报 404「已过期」; ③LLM API key 保护: base_url 非 https 仅允许本机/内网 (防 Bearer key 明文出公网), 跨主机 302 重定向剥离 Authorization 头 (urllib 默认会重发); ④巡检失败不再用占位 'N/A' 覆盖设备真实主机名; ⑤入库失败前端可见: db_error 脱敏后渲染并计入「巡检完成 (有失败)」 (此前静默丢数据+吞告警; 原文含 SQL/参数会泄露给只读 token); ⑥巡检面板设备输出 (cpu/mem/alerts) 全部转义, 堵设备输出→innerHTML 的存储型 XSS; ⑦fallback 文本协议执行的命令与输出落库 (此前刷新即丢, 下轮 LLM 上下文丢失); ⑧propose_config 的 steps 非对象数组时返回纠正错误让模型重试 (此前 AttributeError 杀死整轮), command/purpose 归一化为字符串; ⑨消息 seq 分配加每会话锁 (双标签页并发发送不再产生重复 seq); ⑩面向 LLM 的设备输出与审计同长截断 (show run 级输出曾在 8 个工具轮重复全量上传, ~8x token 放大; 前端工具块仍显示全量)。全部 20 项验证通过: key 保护 7 用例+302 实测/真机推送/失败巡检主机名保持/run-now 全生命周期/并发 seq 唯一/入库失败注入/XSS 探针/真实聊天回归
- 2026-08-11: **巡检状态语义与 AI 卡片一致性修复** — ①/inspect/status 引入完成墓碑表 (_finished_runs, TTL 1h): run_id 不存在/过期返回 404, 已完成并清理的返回 done:true (此前两者都返回 done:true, 无法区分, 调用方会把瞎编的 run_id 当成"已完成"); 前端轮询识别 404 显示「巡检已结束」并停止 (此前会空转 5 分钟后误报"巡检超时"); ②reject 已处理卡片与 confirm 对齐返回 400「该卡片已处理 (status)」 (此前静默 200 幂等, 两端点状态机语义不一致)。全部 7 项行为验证通过: bogus 404/真巡检完成带进度/retire 后墓碑不 404/reject 400/pending reject 正常/GUI 残留 run_id 优雅结束
- 2026-08-11: **AI 助手评审修复第二轮 (10 项+2)** — ①SSE 串台防线: 发送/切换会话递增 sendToken, 过期流事件一律丢弃 (此前切换会话后旧流仍往新气泡写); ②config_push 全局超时兜底: wait(timeout=2*PUSH_TIMEOUT+60), 线程挂死不再永久阻塞并明确提示人工核对; ③巡检异常修复: db_error 时不再写入幻影告警, 设备 IP 在重试前固定; ④非管理员不再收到全局供应商 key 掩码片段; ⑤限流 TOCTOU 修复: 原子认领后再复核计数, 超限回滚占位恢复 pending 可重试 (前端 429 恢复按钮不锁死); ⑥fallback 提示词修复字面 \n 转义 (此前降级协议必然死胡同); ⑦个人供应商留空 key 更新不再 422, 首次无 key 明确 400; ⑧fallback 解析改 finditer 支持多块多命令; ⑨历史工具消息结构化返回 (command+content, 不再裸 JSON); ⑩只读 token 访问受限页面返回友好 HTML 403 (浏览器) 而 API 保持 JSON。另修: fix_rounds 计数语义、CR 偷渡双闸门 (_propose_config 拒绝 + confirm_action 400 并审计 rejected)、会话池 last 初始化+在途不回收。全部 23 项验证通过: 15/15 API + 3/3 真机推送链路 + 5/5 巡检与 Playwright 界面回归
- 2026-08-10: **AI 助手评审修复 (10 项)** — ①保存失败不再被吞: exec_config 保存失败抛 SaveFailedError, 审计输出明确标注「保存失败」, 前端卡片显示 ⚠️ 警告横幅而非「✅ 已保存」; ②confirm/reject 补上软删除过滤, 已删除会话的待确认卡片不可再下发配置; ③新增启动时幂等列迁移 (PRAGMA table_info + ALTER TABLE), 旧库/备份恢复升级不再 500; ④删除进行中会话全面协调: 删除请求不再阻塞 (后台断连), agent 循环每轮 + 每条设备命令执行前检查 deleted 即停 (同轮批量工具调用也拦截, 不再透明重连占 VTY), 前端删除时中止在途 SSE; ⑤删除供应商时自动解绑相关会话 (清除绑定+标签), 不再静默回落默认且列表显示陈旧标签; ⑥会话归属查询收敛为 _get_owned_session 单一入口 (此前复制 5 处且已漂移); ⑦供应商行查询/解密去重 (创建/切换直接用已查出的行); ⑧chat/confirm 改用 AISession.device 关系; ⑨修复供应商下拉启动竞态 (openSession 等待首次加载完成再赋值); ⑩sessHint 标题/供应商分开存储不再正则截断含 ' · ' 的标题, 表格渲染支持行内代码中的 `|` (如 `` `display current | include vlan` ``)。全部 25 项验证通过: 真机保存路径/已删会话 404/迁移端到端 (29 行保留 0 NULL)/流式中删除 0 泄漏/Playwright 界面与 XSS 回归
- 2026-08-10: **AI 助手体验与修复** — ①「执行并保存」改用 netmiko save_config 按平台分发 (Cisco=write memory, 华为=save 自动应答 Y/N, 此前华为会静默保存失败), 保存失败明确提示"配置已生效但未写入启动配置"; ②AI 回复气泡支持 Markdown 渲染 (表格/粗体/标题/列表/代码块, 自研轻量渲染器先转义后还原, XSS 安全, 流式打字机效果保留); ③修复过期确认卡片点击报 500 (output 为 NULL 时的 TypeError); ④供应商弹窗支持 ESC 关闭; ⑤修复新会话列表元信息裸分隔符
- 2026-08-10: **AI 助手: 按会话选择/切换模型 + 会话删除** — 工具栏新增模型下拉, 列出全部可用供应商 (全局+个人), 新建会话绑定所选模型, 已开会话可随时切换 (新增 `POST /ai/sessions/{id}/provider`); 会话绑定持久化在 ai_sessions.provider_source/provider_ref, 绑定项被删自动回落默认; 会话列表支持删除 (悬停 × 按钮) — 采用软删除 (ai_sessions.deleted), 对话与配置变更审计流水全量保留, 删除同时释放设备 SSH 连接
- 2026-08-10: **AI 助手安全终审加固** — ①只读白名单拒绝内嵌换行/控制字符 (`show version\nconfigure terminal` 曾可绕过白名单直改配置); ②/ai/* 全部接口改 require_full_user, 只读 token 全 403; ③空闲设备 SSH 连接回收任务挂入调度器 (60s, 此前定义未调度, 长期使用会占满设备 VTY); ④修复管理员供应商面板永不渲染 (模板误判字段 user.role → user.is_admin); ⑤修复 SSE 断连后 worker 继续跑、确认卡片双击可重复下发 (原子认领); ⑥DeepSeek 实测全链路通过 (对话→show 执行→确认卡片→人工下发→审计核对)
- 2026-08-07: **AI 助手模块上线** — 对话式设备巡检/配置 (页面 `/ai`, 导航栏入口): 支持 Kimi/DeepSeek/GLM/本地 OpenAI 兼容模型, 全局+个人双轨配置, API key Fernet 加密存储; 只读命令直接执行并回显, 配置变更逐条全文展示、人工逐条确认后才下发设备 (原子认领防重复执行); 对话/命令/输出/确认人全量审计; 页面与接口要求完整登录用户 (只读 token 403)
- 2026-08-07: **免登录白名单改为精确/前缀双语义** — `PUBLIC_PATHS` 的 startswith 前缀匹配意味着未来新增 `/login-xxx`、`/logout-all`、`/staticAdmin` 这类路由会被静默公开; 现拆为精确匹配集合 + 带尾斜杠的前缀元组, 堵死撞名自动公开
- 2026-08-07: **巡检稳定性三连修** — ①巡检/配置推送线程池弃用 with 块 (挂死的 netmiko 线程会让 shutdown(wait=True) 永久阻塞), 改 shutdown(wait=False, cancel_futures=True); ②采集 finally 里 conn.disconnect() 加保护, SSH 通道中途断开不再丢弃已采数据; ③巡检入库段加 locked 重试 (最多 3 次退避) 且进度 done 无条件递增, SQLite 并发写冲突不再导致前端进度卡死
- 2026-08-07: **越权修复: 配置备份/拓扑不再对只读 token 开放** — 新增 `require_full_user` 依赖 (require_auth 会被只读 token 的合成用户通过); 配置备份的页面/列表/下载/导出 ZIP 与拓扑页面/数据接口 全部要求真实登录用户; 备份下载另加文件名白名单 + 目录约束防路径穿越
- 2026-08-07: **日志轮转** — 应用日志启用 RotatingFileHandler (10MB x 5, 敏感字段掩码), main.py 启动时接入; systemd stdout 日志 /home/ivan/inspect.log 由 logrotate (/etc/logrotate.d/network-inspect, size 10M/rotate 5/copytruncate) 接管, 日志不再无限膨胀
- 2026-08-07: **Case 重名校验** — 新建 Case 名称与现有 Case 重复时(大小写不敏感、自动去首尾空格)拒绝创建并回显错误横幅「已存在同名 Case」, 不再静默建出重名 Case (Case 名即 T1 订单号, 重名会让 QC webhook 链接指向不明)
- 2026-08-06: **Dell iDRAC 存储解析修复** — 硬件摘要在有 BOSS 卡的服务器上丢 BOSS 控制器和直插 NVMe 盘: `parse_idrac_disk` 只认 `Disk.Bay.*` 背板盘, BOSS 直插 M.2 (`Disk.Direct.*:BOSS.*`) 被整块跳过; `parse_idrac_raid` 只认 InstanceID 含 RAID 的控制器, BOSS 卡 (`BOSS.SL.*`) 丢失且背板 (`Enclosure.Internal.*:RAID.*`, ProductName "BP15G+") 被误统计为 RAID 卡。修复: 控制器按 FQDD 前缀精确匹配 (RAID./BOSS./AHCI.), 物理盘覆盖 Disk.Bay+Disk.Direct (排除 Disk.Virtual); 历史报告 #109/#118/#119 摘要已重算
- 2026-07-29: **Docker 镜像 v4** — 适配最新代码重建镜像 (已 34 项容器内验证全过): 新增 mtr-tiny/tzdata (容器内路由追踪可用、日志 CST); 补 COPY `inspection.py` (配置备份模块依赖); 新增 Case 附件/CA 证书数据卷 (v3 会丢这些数据); `INSPECT_SECRET_KEY` 改必填合法 Fernet 密钥 (v3 默认值无效会崩加解密); 镜像不再含密钥/DB/Case 附件/CA 私钥, 可安全分发; 部署runbook 见 dockerivan.MD
- 2026-07-29: **只读 Token 免密访问** (T1 集成) — 配置 `INSPECT_READONLY_TOKEN` 环境变量后, 链接带 `?token=...` (或 `X-Readonly-Token` 请求头) 即可免登录浏览; 首次访问后自动种下 `inspect_rt` Cookie (30 天) 站内跳转无需重复带参; 中间件强制仅 GET/HEAD (其余方法 403), 且屏蔽 `/users`、`/change-password` 及 CA 私钥下载 (pem/p12); token 经 `hmac.compare_digest` 常量时间比对, 空值 = 功能关闭; token 值只存于 systemd unit 不入 git
- 2026-07-24: Case 内容变更 **webhook 通知 T1 质检系统** — 新建 Case/上传文件/删除文件/删除 Case 时, 后台线程自动 POST `bom.ici-cn.com/api/v1/qcLink/webhook` (order_number=Case 名, url=相对路径 `cases/N`, remark 描述变更内容); fire-and-forget 不阻塞请求、失败仅记日志不影响业务; URL/token 可用 `QC_WEBHOOK_URL`/`QC_WEBHOOK_TOKEN` 环境变量覆盖
- 2026-07-24: 密码功能**代码审查修复**(10 项中 8 修复+2 缓议,51 项线上验证全过) — admin 不可在用户页重置自己密码(防唯一 admin 打错字永久锁死,须走修改密码页);`/users/add` 补套统一密码策略(≥8 位/非纯空白/≤128 位,三处入口同一 `_validate_new_password`);改密拒绝新密码=旧密码;重置表单加确认输入;重置不存在用户显示“目标用户不存在”(不再静默 303);新增 `require_admin` 依赖替换 4 处手写守卫(非 admin 访问返回 403 而非静默跳转);改密先做免费校验再做 PBKDF2 验旧密码(错误表单零哈希开销);缓议:改密端点节流(并入登录限流)、password_version 列(多 worker 吊销,当前单进程不受影响)
- 2026-07-24: 新增**修改密码功能** — 自助改密页 `/change-password`(验旧密码、两次确认、≥8 位);admin 在用户管理页可**重置任意用户密码**;改密/重置/删用户后**自动吊销该用户全部会话**(强制重新登录);导航栏新增“修改密码”入口
- 2026-07-24: 代码审查第二轮 — **跨路由安全/稳定性修复**(16 项,15 修复+1 缓议,均已线上验证): Case 预览签名密钥改用 crypto 真实加密密钥(删除硬编码公开回退,防伪造);签名验证先拒绝非 hex 输入(修公开端点 compare_digest TypeError 500)且**先验签后查库**(垃圾探测零 DB 开销);文件服务统一 `_serve_case_file` 改 **FileResponse 流式**(不再整文件读入内存)+`X-Content-Type-Options: nosniff`;上传改完整 uuid4 防碰撞、失败时清理 `.tmp` 半成品文件;类别 slug 去重改单条 LIKE 查询;Case 详情页 `Cache-Control: no-store`(防缓存过期签名 URL)且仅为图片生成签名 URL;`config_push` 上传改**有界读取** `read(MAX+1)`(超限前不整文件入内存,防 OOM);CA 证书(4 处)/BOM 导出/配置备份下载统一走 `helpers.download_headers` RFC 6266 编码(修中文文件名 latin-1 500);XR 分平台命令选择另议
- 2026-07-23: Case 系统**安全加固**(代码审查 9 项,均已线上验证) — 文件服务改**扩展名白名单**(仅光栅图片+PDF 内联,HTML 等强制 `application/octet-stream` 下载 → 杜绝上传 HTML 的存储型 XSS);`/cases/preview` 公开预览改 **HMAC 签名+6h 过期**(无签名/过期返回 404,消除公开且永不失效的链接);上传改**有界读取**(`read(MAX+1)`,超限前不把整文件读入内存 → 防 OOM)且多文件中途失败**回滚已写磁盘文件**(防孤儿);下载 `Content-Disposition` 用 RFC 6266 编码(修中文文件名 latin-1 崩溃);类别改名加**重复名/slug 校验**(返回 400 而非 500);搜索转义 LIKE 通配符;`cases.html` 删除确认把 Case 名移出 JS 字符串(防存储型 XSS);修复类别名双重编码乱码(“巡检报告”)
- 2026-06-18: 新增 BOM 匹配验证功能 — 支持上传 BOM xlsx 文件，与巡检报告自动匹配设备型号，服务器配置逐项比对，结果可导出 Excel
- 2026-06-30: 新增 CA 证书服务器 — 根CA创建/下载、证书签发/吊销、外部CSR签名、PEM/PKCS#12双格式导出（2026-07-01: 代码审查修复 — 累积CRL撤销链、UUID唯一目录、空指针检查、异常回滚、密钥路径守卫）
- 2026-07-17: BOM 匹配支持 Dell 服务器(硬件摘要匹配) — 无 PID 输出的 BMC(idrac 等)改用 Model/CPU/Memory/NIC/RAID/Disk/PSU 硬件摘要与 BOM Description 做匹配;词级匹配容忍 (R)/(TM) 商标符号;BROADCOM XXXX 自动转 BCMXXXX;CPU 24C/48T 只取核心数 24C 匹配
- 2026-07-16: Case 系统**搜索功能** — 列表页搜索框,跨表搜索 Case 名称/备注/文件名(ilike),结果内联展示匹配文件;详情页加文件名实时过滤;列表页加删除按钮
- 2026-07-15: 新增 **Case 系统** — 按项目/案件归档巡检报告、设备文档、照片;每 Case 一个文件夹,文件按可配置类别分组(默认 巡检报告/设备文档/照片,设置页可增删改,非空不可删);支持多文件上传(≤50MB/文件)、下载、**在线查看**(图片内联显示、PDF 浏览器内打开、HTML 沙箱 iframe 渲染防 XSS);扁平存储+DB 类别标签(类别改名/删除为纯 DB 操作);文件名净化+uuid+路径防穿越+handler 级鉴权+管理员限类别设置/删 Case
- 2026-07-02: CA 安全加固 — CRL 改为从数据库 `status='revoked'` 重建（文件为可重建缓存，消除损坏/截断时静默丢失吊销），原子写入(temp+os.replace)+线程锁防撕裂/并发丢更新；`revoke_cert` 先提交DB再生成CRL；`delete_cert` 重新生成CRL避免幽灵序列号；`download_pem/p12` 类型化错误处理(不再泄露服务器路径)；`get_pem_zip` 空密钥路径抛错(与p12一致)；`sign_csr` 回滚时清理孤儿证书文件；`ca_page` 复用 `_get_certs`，`_ca_certs.html` 渲染 `csr_error`
- 2026-07-03: 
  - CA 二轮加固 — CRL 重建改为**锁内调用读取提供者**(修复并发吊销丢失更新的竞态)；`delete_cert` 限制为**仅过期吊销证书可删**(避免删除即解吊销)并清理证书/私钥文件；新增 `GET /api/cert/{id}/download/crt` **仅证书端点**(CSR 签名证书可下载,`openssl verify` 通过)；CRLNumber 改为从现有 CRL 种子的**单调计数器**(重启不回退,符合 RFC 5280,替代时钟派生)；CRL 生成失败/坏序列号/空 `revoked_at` 增加日志；抽取 `_load_ca_pair`/`_get_cert_and_root`/`_bundle_or_500` 去重
  - 仪表盘「最近告警」Ack 空白页修复 — 改 HTMX `hx-post`(原生 form 整页跳转到空 200 响应导致空白)，审计确认全仓无同类隐患
  - 安全卫生 — 取消跟踪 CA 私钥/活跃数据库/配置备份(`.gitignore`)，私钥仍在本地历史(无远程)；推送到共享远程前需轮换根 CA

- 2026-07-03 (全项目代码审查修复，33 项): 设备字段服务端校验+模板 tojson/esc 转义防存储型 XSS；/devices/api 不再泄露加密密码列；crypto.is_encrypted 要求合法 Fernet token 防明文落库；/docs /openapi.json 改为需登录；登录时序均摊+next 开放重定向修复；资源上限(subnet/bom/config_compare/reports PDF)防 OOM；config_push 改同步防阻塞事件循环；scheduler 启动容错(坏记录不再瘫痪全部)+per-future 超时+run_id 唯一+once 时区；inspection.py 备份文件名净化+chmod 0o600+NX-OS CPU clamp+路由校验/主机名/SEL 解析加固；scheduler.html 去重(原 4 处重复模态/函数+title 吞模态)；首启管理员改随机密码
- 2026-06-18: 新增 LLM VRAM 计算器 — 支持10种预设模型+自定义，推理/训练/多GPU三大场景，8种量化精度对比表
| 模块 | 优化内容 |
|------|----------|
| **配置备份** | 完整备份管理 — 浏览/查看/下载/手动强制备份/批量ZIP导出/批量删除, 设备下拉(IP+ID), 文件vs目录诊断, 路径穿越保护 | — 复用 inspection.CONFIG_DIR 避免硬编码, API 加载设备列表防 XSS, 清理冗余导入/死代码 | — 浏览/查看/下载/手动强制备份/批量ZIP导出/批量删除, 设备下拉菜单(IP+ID), 持久状态提示 | — 浏览/下载/手动触发备份/批量 ZIP 导出 |
| **Docker部署** | network1-inspection 镜像, docker-compose up -d 启动, dockerivan.MD 完整新手指南(800行) |
| **前端交互** | HTMX 渐进增强 + 配置备份批量删除 (勾选→确认→删除, 路径穿越保护) | — 仪表盘 /api/dashboard/stats 轻量端点 (30s 刷新)、告警/报告行内操作、去除 deleteOne 死代码 |
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
| **数据库恢复** | 损坏 DB dump→ROLLBACK→COMMIT 修复, 7 表 40 行数据 37 行成功恢复 |
| **系统防护** | main.py 单例锁 + 启动完整性检查, systemd 崩溃循环保护, WAL 定期 checkpoint |
| **验证** | 全模块 16/16 PASS (13 页面 + 3 API), 单例锁/未认证拦截/错误密码拒绝/公开路径 全部验证 |
| **代码审查** | 2 个 CRITICAL, 8 个安全漏洞, 4 个性能优化 |



-----如果您支持我可以请问喝一杯咖啡--------------
<img width="628" height="701" alt="image" src="https://github.com/user-attachments/assets/503b3532-8109-4bd2-945d-061272a2a5f6" />

<img width="571" height="643" alt="image" src="https://github.com/user-attachments/assets/a05c8081-2e49-4e58-8aba-d100daa1066d" />




