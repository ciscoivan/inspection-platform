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




