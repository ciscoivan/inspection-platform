# Network Automation Inspection Platform

A Python FastAPI-based automated inspection and operations platform for network devices and servers, supporting SSH information collection across 9 major network vendors + 5 major server BMC platforms, configuration backup, batch Ping/Traceroute, configuration comparison, configuration push, scheduled inspection scheduling, an alert system (escalation/silencing/acknowledgment/history), custom command execution, report export (PDF/Word/CSV/HTML), and other operations features. Cross-platform support for Linux / Windows. Supports Chinese/English UI switching.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Platform Feature Matrix](#platform-feature-matrix)
- [Feature Modules](#feature-modules)
- [Directory Structure](#directory-structure)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Docker Deployment](#docker-deployment)
- [Windows Deployment](#windows-deployment)
- [Default Accounts](#default-accounts)
- [API Endpoints](#api-endpoints)
- [Configuration](#configuration)
  - [Database](#database)
  - [Configuration Backup Deduplication](#configuration-backup-deduplication)
- [Performance Optimization](#performance-optimization)
- [Routing Table Validation and Automatic Fallback](#routing-table-validation-and-automatic-fallback)
- [Language Switching](#language-switching)
- [Security Notes](#security-notes)
- [Optimization Log](#optimization-log-2026-06)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                        Browser                          │
├─────────────────────────────────────────────────────────┤
│    FastAPI + Jinja2 (unified web frontend & backend)    │
├──────────────────┬───────────────────┬────────────────────┬─────────────────────┬──────────────────────────┬────────────────────┬──────────────────────┤
│ auth             │ devices           │ inspect            │ ping                │ config_compare           │ config_push        │ scheduler            │
│ Authentication   │ Device Management │ Inspection Engine  │ Network Diagnostics │ Configuration Comparison │ Configuration Push │ Scheduled Inspection │
├──────────────────┼───────────────────┼────────────────────┼─────────────────────┼──────────────────────────┼────────────────────┼──────────────────────┤
│ alerts           │ reports           │ subnet             │ custom_cmd          │ config_backup            │ topology           │ helpers              │
│ Alert System     │ Report Export     │ Subnet Calculation │ Custom Commands     │ Config Backup Mgmt       │ Network Topology   │ Shared Utils         │
├──────────────────┼───────────────────┼────────────────────┼─────────────────────┼──────────────────────────┼────────────────────┼──────────────────────┤
│ constants        │                   │                    │                     │                          │                    │                      │
│ Shared Constants │                   │                    │                     │                          │                    │                      │
├──────────────────┴───────────────────┴────────────────────┴─────────────────────┴──────────────────────────┴────────────────────┴──────────────────────┤
│              SQLAlchemy ORM + SQLite                     │
├─────────────────────────────────────────────────────────┤
│        netmiko SSH → network devices (9 vendors)        │
└─────────────────────────────────────────────────────────┘
```

- **Web framework**: FastAPI 0.136 + Jinja2 templates (server-side rendering) + BackgroundTasks (async tasks)
- **ORM**: SQLAlchemy 2.0 + SQLite WAL mode (Write-Ahead Logging, read/write concurrency performance improved 3-5x)
- **Connection pool**: pool_pre_ping + pool_recycle (3600s) + pool_size=5 + max_overflow=10
- **SSH engine**: Netmiko 4.7 (2 connection retries, 30s timeout, 180+ device types dispatched via registry)
- **Scheduled jobs**: APScheduler 3.11 + BackgroundScheduler (scheduled inspections + automatic data cleanup)
- **Password encryption**: cryptography (Fernet AES-128-CBC + HMAC, three-tier key lookup: environment variable 2192 /etc/inspection/ 2192 auto-generated)
- **Logging**: structured logging + sensitive-field redaction filter (password/secret/token/key)
- **Configuration backup**: SHA256 deduplication (skip writing when content unchanged) + automatic rotation (latest 5 versions retained per device)

---



---

## Technology Comparison (Industry Research)

> Based on in-depth research from 2026-06: 5 search angles -> 23 sources -> 81 claims -> adversarial validation (3-vote system) -> 4 high-confidence conclusions

### Open Source vs In-House vs Commercial Overview

| Dimension | This platform (in-house) | LibreNMS + Oxidized | Netshot | SolarWinds NPM |
|------|:---:|:---:|:---:|:---:|
| **Architecture** | FastAPI + Netmiko | PHP + SNMP Poller | Java + React 19 | Windows + .NET |
| **Deployment** | Single file / pip | LAMP stack | Docker Compose / K8s | Windows Server + SQL Server |
| **SSH inspection** | 14 vendors | Requires Oxidized | 7 vendors with Java drivers | Supported |
| **SNMP monitoring** | Not supported | LibreNMS | Not supported | Supported |
| **Configuration backup** | SHA256 deduplication + rotation | Git (Oxidized) | SHA256 + PostgreSQL | Supported |
| **Compliance checks** | Planned | Not supported | Three tiers: software/hardware/configuration | Supported |
| **Alert system** | Escalation/silencing/acknowledgment | LibreNMS | Not supported | Supported |
| **Topology discovery** | CDP/LLDP | LibreNMS | Not supported | Supported |
| **gNMI telemetry** | Not supported | Not supported | Not supported | Not supported |
| **License** | Free | Free | Free | Paid element-based licensing |
| **Vendor coverage** | 14 platforms | 130+ OS (Oxidized) | About 7 vendors | Broad |

### Industry Architecture Consensus

1. **Agentless + Pull is the dominant model**: LibreNMS, Prometheus SNMP Exporter, and Nagios Core all use agentless polling; the difference is whether alerting/visualization is delegated (Grafana/Alertmanager) or built in
2. **Oxidized (130+ OS) far ahead of RANCID (about 35, Cisco-centric)**: Huawei/H3C/Fortinet/Palo Alto are natively supported only by Oxidized, and RANCID has entered maintenance mode
3. **Netshot is the open source configuration management platform with the highest functional integration**: 6-in-1 (backup + assets + software compliance + hardware compliance + configuration compliance + change automation); React 19 + TypeScript frontend development is extremely active (daily commits in 2026-05/06), but the new frontend is not yet included in releases (pom.xml comment: Exclude new WebUI files until release)
4. **Commercial tools have architectural ceilings**: rConfig V8 supports only 5 traditional connection methods (no NETCONF/RESTCONF/gNMI); SolarWinds beyond 12,000 elements requires an additional Polling Engine + SQL Server Enterprise

### This Platform's Differentiation

| Capability | Open source tool limitations | This platform's advantages |
|------|:--:|:--:|
| Deep CLI information collection | SNMP can only fetch OIDs and cannot obtain hardware serial numbers/transceiver diagnostics | SSH executes arbitrary commands + dedicated parsers |
| Unified multi-BMC management | No tool covers Dell/HP/Lenovo/Huawei/Inspur at the same time | Unified Command Map across 5 platforms |
| Routing table log pollution detection | No automatic detection | validate_routing_output() + automatic fallback |
| Chinese/English bilingual | Most tools are English-only | i18n with Cookie persistence |

### Netshot Frontend Progress (tracked to 2026-06-06)

| Date | Update |
|------|------|
| 2026-06-06 | fix(web): adjust padding/margin; feat(web): frontend improvements |
| 2026-05-31 | feat(web): rewrite query builder; refactor(web): rename pages |
| 2026-05-29/30 | Compliance view enhancements, tree display improvements, diagnostics view enhancements |
| 2026-05-23 | feat(web): compliance rule suggestion feature (new core feature) |
| 2026-02-16 | v0.24.0 released (new frontend webui/** excluded by pom.xml) |

> **Conclusion**: Netshot's new frontend (React 19 + Chakra UI v3 + TanStack + Vite) is under extremely active development but unreleased; it may reach RC in 2026 Q4. This platform continues to develop independently and can use its technology stack as a reference.

---


---


---

## Platform Feature Matrix


- **BOM matching validation**: Upload a project BOM file (≤20MB) and match it against inspection reports to verify devices are configured per the order — network devices match Product#↔PID exactly; servers without PID output such as Dell are word-level matched against the hardware summary using Model/CPU/memory/disk/RAID/NIC/power supply extracted from Description; tri-state results (success/unmatched/configuration anomaly) are color coded, and rows can be excluded before exporting an Excel report
- **CA certificate server**: Built-in PKI system supporting root CA creation, end-entity certificate issuance, CSR signing, PEM/PKCS#12 export, and certificate revocation. CRLs are rebuilt with the database as the single source of truth (files are rebuildable caches); atomic writes + thread locks eliminate loss of revocation records due to corruption/concurrency
- **Case management**: Archive inspection reports, device documents, and photos by project/case; configurable categories (add/delete/edit on the settings page, non-empty ones cannot be deleted); multi-file upload (≤50MB, bounded reads prevent OOM, rollback on mid-way failure prevents orphans), download, online viewing (images/PDF inline; HTML etc. force download to prevent stored XSS); preview URLs carry an HMAC signature + 6h expiry; flat storage + DB category tags; filename sanitization + path traversal protection; creating a duplicate name (case-insensitive) is rejected with a prompt
- **LLM VRAM calculator**: Estimates the VRAM required for inference/training/multi-GPU deployment based on model parameter count and quantization precision, with a comparison table of 10 preset models and 8 quantization precisions
- **AI assistant**: Conversational device inspection/configuration — supports Kimi/DeepSeek/GLM/local OpenAI-compatible models (global + personal dual-track configuration, key encrypted with Fernet); the toolbar dropdown selects/switches models per session, and sessions can be deleted (soft delete, records retained); read-only commands execute directly, while configuration changes are shown in full text item by item and sent only after manual confirmation; full auditing (conversations/commands/output/confirmer)

### Inspection Collection Capabilities

| Inspection category | Cisco IOS | Cisco XR | Cisco NX-OS | Juniper | Huawei | H3C | Fortinet | Arista | Ruijie |
|----------|:---------:|:--------:|:-----------:|:-------:|:------:|:---:|:--------:|:------:|:------:|
| **Basic information** |
| Version/model | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Hardware inventory/serial number | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | — |
| Running configuration | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Device serial number (ESN) | — | — | — | — | ✅ | — | — | — | — |
| **Performance status** |
| CPU usage | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Memory usage | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Environment status (power/fans/temperature) | ✅ | ✅ | — | — | ✅ | ✅ | — | — | — |
| **Interface status** |
| IP interface summary | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Interface details (errors/packet loss) | ✅ | ✅ | ✅ | — | ✅ | ✅ | — | ✅ | ✅ |
| Interface descriptions | ✅ | ✅ | ✅ | ✅ | — | — | — | ✅ | ✅ |
| HA high availability status | — | — | — | — | — | — | ✅ | — | — |
| **Optical transceiver information** |
| Transceiver diagnostics (optical power/temperature/voltage) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Neighbor information** |
| CDP neighbors | ✅ | — | ✅ | — | — | — | — | — | — |
| LLDP neighbors | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Logs and routing** |
| System log | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ |
| Routing table summary | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Routing fallback** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Session statistics | — | — | — | — | — | — | ✅ | — | — |
| **Automatic configuration backup** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

### Exact Commands Executed per Platform

#### Cisco IOS / IOS-XE (`cisco_ios`)

| Inspection category | Command executed | Metrics collected |
|----------|---------|---------|
| Basic information | `show version` | Version, model, uptime |
| | `show inventory` | Hardware serial numbers |
| | `show running-config` | Running configuration (automatic backup) |
| Performance status | `show processes cpu sorted` | CPU usage (5s average) |
| | `show processes memory sorted` | Memory usage (Processor Pool) |
| | `show chassis environment` | Power, fans, temperature |
| Interface status | `show ip interface brief` | IP interface summary table |
| | `show interfaces` | Interface details (error/packet-loss counters) |
| | `show interfaces description` | Interface descriptions |
| Optical transceiver | `show interfaces transceiver` | Optical power, temperature, voltage |
| Neighbors | `show cdp neighbors detail` | CDP neighbor details |
| | `show lldp neighbors detail` | LLDP neighbor details |
| Logs/routing | `show logging` | System log buffer |
| | `show ip route summary` | Routing table summary |

#### Cisco IOS-XR (`cisco_xr`)

| Inspection category | Command executed | Metrics collected |
|----------|---------|---------|
| Basic information | `show version` | Version, model, uptime |
| | `show inventory` | Hardware serial numbers |
| | `show running-config` | Running configuration (automatic backup) |
| Performance status | `show processes cpu` | CPU usage (5s average) |
| | `show memory summary` | Physical memory usage |
| | `show environment all` | Power, fans, temperature |
| Interface status | `show ip interface brief` | IP interface summary |
| | `show interfaces` | Interface details (errors/packet loss) |
| | `show interfaces description` | Interface descriptions |
| Optical transceiver | `show controllers optics all` | Optical power (Port/Tx/Rx) |
| Neighbors | `show lldp neighbors` | LLDP neighbors |
| Logs/routing | `show logging` | System log |
| | `show route summary` | Routing table summary |

#### Cisco NX-OS / Nexus (`cisco_nxos`)

| Inspection category | Command executed | Metrics collected |
|----------|---------|---------|
| Basic information | `show version` | Version, model, uptime |
| | `show inventory` | Hardware serial numbers |
| | `show running-config` | Running configuration (automatic backup) |
| Performance status | `show system resources` | CPU + memory (single command, 100%-idle) |
| Interface status | `show ip interface brief` | IP interface summary |
| | `show interface` | Interface details (errors/packet loss) |
| | `show interface description` | Interface descriptions |
| | `show interface status` | Interface status summary |
| Optical transceiver | `show interface transceiver details` | Transceiver diagnostics |
| Neighbors | `show cdp neighbors` | CDP neighbors |
| | `show lldp neighbors` | LLDP neighbors |
| Logs/routing | `show logging last 200` | Last 200 log entries |
| | `show ip route summary` | Routing table summary |

#### Juniper JunOS (`juniper`)

| Inspection category | Command executed | Metrics collected |
|----------|---------|---------|
| Basic information | `show version` | Version, model (including Hostname) |
| | `show system uptime` | System boot time |
| | `show chassis hardware` | Hardware inventory/serial numbers |
| | `show configuration \| display set` | Running configuration (backed up in set format) |
| Performance status | `show chassis routing-engine` | CPU (100%-idle) + memory (single command) |
| | \ | Power, fans, temperature |
| Interface status | `show interfaces terse` | IP interface summary |
| | `show interfaces description` | Interface descriptions |
| | `show interfaces detail` | Interface details (errors/packet loss) |
| Optical transceiver | `show interfaces diagnostics optics` | Transceiver diagnostics |
| Neighbors | `show lldp neighbors` | LLDP neighbors |
| Logs/routing | `show log messages \| last 200` | Last 200 log entries |
| | `show route summary` | Routing table summary |

#### Huawei VRP (`huawei`)

| Inspection category | Command executed | Metrics collected |
|----------|---------|---------|
| Basic information | `display version` | Version, model, uptime |
| | `display device` | Hardware inventory (board information) |
| | `display esn` | Device serial number |
| | `display current-configuration` | Running configuration (automatic backup) |
| Performance status | `display cpu-usage` | CPU usage |
| | `display memory-usage` | Memory usage |
| | `display health` | Power, fans, temperature |
| Interface status | `display ip interface brief` | IP interface summary |
| | `display interface brief` | Brief interface status |
| | `display interface` | Interface details (errors/packet loss) |
| Optical transceiver | `display transceiver verbose` | Transceiver diagnostics (optical power/temperature/voltage) |
| Neighbors | `display lldp neighbor brief` | LLDP neighbors |
| Logs/routing | `display logbuffer` | System log buffer |
| | `display ip routing-table statistics` | Routing table statistics |

#### H3C Comware (`hp_comware`)

| Inspection category | Command executed | Metrics collected |
|----------|---------|---------|
| Basic information | `display version` | Version, model, uptime |
| | `display device manuinfo` | Hardware inventory/serial numbers |
| | `display current-configuration` | Running configuration (automatic backup) |
| Performance status | `display cpu-usage` | CPU usage |
| | `display memory-usage` | Memory usage |
| | `display environment` | Power, fans, temperature |
| Interface status | `display ip interface brief` | IP interface summary |
| | `display interface brief` | Brief interface status |
| | `display interface` | Interface details (errors/packet loss) |
| Optical transceiver | `display transceiver verbose` | Transceiver diagnostics |
| Neighbors | `display lldp neighbor brief` | LLDP neighbors |
| Logs/routing | `display logbuffer` | System log buffer |
| | `display ip routing-table statistics` | Routing table statistics |

#### Fortinet FortiOS (`fortinet`)

| Inspection category | Command executed | Metrics collected |
|----------|---------|---------|
| Basic information | `get system status` | Version, model, serial number, uptime |
| | `show full-configuration` | Full configuration (automatic backup) |
| Performance status | `get system performance status` | CPU + memory (single command, 100%-idle) |
| Interface status | `get system interface physical` | Physical interface summary |
| | `get system ha status` | HA high availability status |
| Optical transceiver | `get system interface transceiver` | Transceiver diagnostics |
| Neighbors | `get system lldp neighbors` | LLDP neighbors |
| Logs/routing | `execute log display` | System log (recent) |
| | `get router info routing-table all` | Routing table |
| | `get system session status` | Session statistics |

#### Arista EOS (`arista_eos`)

| Inspection category | Command executed | Metrics collected |
|----------|---------|---------|
| Basic information | `show version` | Version, model, uptime |
| | `show inventory` | Hardware serial numbers |
| | `show running-config` | Running configuration (automatic backup) |
| Performance status | `show system resources` | CPU + memory (single command) |
| Interface status | `show ip interface brief` | IP interface summary |
| | `show interfaces` | Interface details (errors/packet loss) |
| | `show interfaces description` | Interface descriptions |
| Optical transceiver | `show interfaces transceiver` | Transceiver diagnostics |
| Neighbors | `show lldp neighbors` | LLDP neighbors |
| Logs/routing | `show logging last 200` | Last 200 log entries |
| | `show ip route summary` | Routing table summary |

#### Ruijie RGOS (`ruijie_os`)

| Inspection category | Command executed | Metrics collected |
|----------|---------|---------|
| Basic information | `show version` | Version, model, uptime |
| | `show version | include System` | Device model/boot time |
| | `show running-config` | Running configuration (automatic backup) |
| Performance status | `show cpu-usage` | CPU usage (5 output formats supported) |
| | `show memory-usage` | Memory usage (4 output formats supported) |
| Interface status | `show ip interface brief` | IP interface summary |
| | `show interfaces` | Interface details (errors/packet loss) |
| | `show interfaces description` | Interface descriptions |
| Optical transceiver | `show interfaces transceiver` | Transceiver diagnostics |
| Neighbors | `show lldp neighbors` | LLDP neighbors |
| Logs/routing | `show logging` | System log |
| | `show ip route summary` | Routing table summary (automatic fallback to `show ip route` on anomaly) |

### CPU/Memory Parsing Strategy

| Platform | CPU parsing method | Memory parsing method |
|------|-------------|-------------|
| Cisco IOS | `five seconds` / `one minute` / generic CPU utilization fallback | Ratio of Processor Pool Used/Total |
| Cisco XR | Regex extraction of `five seconds: N%` | Physical Memory used/total ratio |
| Cisco NX-OS | `100% - idle%` (from `show system resources`) | Memory usage used/total ratio |
| Juniper | `100% - idle%` / User percent / generic fallback | Memory utilization percentage extracted directly |
| Huawei | Regex extraction of `CPU Usage: N%` | Memory using percentage extracted |
| H3C | Regex extraction of `CPU Usage: N%` | Memory using percentage extracted |
| Fortinet | `100% - idle%` (from `get system performance status`) | used(N%) extracted directly via regex |
| Arista | Regex extraction of `CPU utilization: N%` | Memory utilization percentage extracted |
| Ruijie | 5-layer fallback matching (RGOS/Cisco/generic formats) | 4-layer fallback matching (RGOS/generic formats) |

### Server BMC Platforms (5)

| Platform ID | Vendor | Connection | CLI tool |
|------|------|:--:|------|
| `dell_idrac` | Dell server | SSH :22 | `racadm` CLI |
| `hp_ilo` | HP server | SSH :22 | iLO `show /system1/...` CLI |
| `lenovo_xcc` | Lenovo server | SSH :22 | `syshealth` / `sysinfo` CLI |
| `huawei_ibmc` | Huawei server | SSH :22 | `ipmcget -d ...` CLI |
| `inspur_bmc` | Inspur | SSH :22 | `fru` / `sdr` / `sel` CLI |

#### Unified Server Collection Capabilities

| Collection category | Metrics collected | Dell | HP | Lenovo | Huawei | Inspur |
|---------|---------|:--:|:--:|:--:|:--:|:--:|
| Basic information | Model / serial number / firmware | ✅ | ✅ | ✅ | ✅ | ✅ |
| Processor | CPU model / frequency / health | ✅ | ✅ | ✅ | ✅ | ✅ |
| Memory | Capacity / type / frequency / health | ✅ | ✅ | ✅ | ✅ | ✅ |
| Sensors | Fan speed / temperature / voltage | ✅ | ✅ | ✅ | ✅ | ✅ |
| Power supply | Wattage / health / redundancy | ✅ | ✅ | ✅ | ✅ | ✅ |
| Network | MAC / link status | ✅ | ✅ | ✅ | ✅ | ✅ |
| Storage | RAID controllers / physical drives / logical drives | ✅ | ✅ | ✅ | ✅ | ✅ |
| Hardware log | System event log (SEL) | ✅ | ✅ | ✅ | ✅ | ✅ |
| PCIe/GPU | GPU/PCIe device inventory | ✅ | ✅ | ✅ | ✅ | ✅ |
| Health overview | Overall health status determination | ✅ | ✅ | ✅ | ✅ | ✅ |

> All server BMCs connect via standard SSH (port 22); Netmiko uses the `generic` driver for compatibility. Health status is determined automatically: all green → Healthy, any Warning → Warning, any Critical/Error → Critical.
> 
> **Hardware summary**: A hardware summary is automatically generated at the top of the "Basic information" section of the inspection report, covering CPU model/count, memory model/capacity, NIC model/count, RAID controller model, disk model/capacity, and power supply model/status. Dell iDRAC uses a dedicated parser (`racadm hwinventory`); other platforms use a generic parser (automatically matching key fields such as `Model`/`Size`/`Cores`). Storage parsing covers PERC backplane drives (`Disk.Bay.*`) and BOSS cards with their directly attached M.2 NVMe drives (`BOSS.SL.*` / `Disk.Direct.*`); non-controller components such as backplanes/batteries are not mistakenly counted in the RAID list.

---

## Feature Modules

### 1. Authentication (`routers/auth.py`)
- **Users**: Administrator (admin)
- Cookie-based session management (httponly + samesite=lax, 7-day validity)
- PBKDF2-SHA256 password hashing (600,000 iterations); legacy SHA256 format automatically upgraded at login
- Unified password policy: ≥8 characters / ≤128 characters / not whitespace-only (same validation for add/modify/reset)
- Self-service password change page /change-password (verifies old password + double confirmation)
- Administrators can create/delete users and reset user passwords (cannot reset their own on the users page, preventing accidental lockout)
- All of a user's sessions are automatically revoked after password change/reset/user deletion (forces re-login)
- Unified `require_admin` dependency on administrator endpoints (returns 403 for non-administrators)
- Authentication enforced on all API endpoints

### 2. Device Management (`routers/devices.py`)
- **Users**: Administrator
- Device CRUD (web UI + REST API)
- Supported fields: IP, device type, SSH username/password, port
- Device passwords automatically stored encrypted (Fernet)

### 3. Inspection Engine (`routers/inspect.py` + `engine/inspector.py` + `../inspection.py`)
- **Users**: Administrator
- Collects 6 major categories of inspection metrics from devices via Netmiko SSH (see [Platform Feature Matrix](#platform-feature-matrix))
- Running configurations automatically backed up to the `configs/` directory
- Supports single-device and batch inspections (up to 100 concurrent, 300s timeout per device)
- Progress panel shows each device's status in real time (CPU/memory/online status)
- Custom commands embedded in the inspection workflow
- Device status markers (connected / error / timeout / auth_failed / unknown)
- Scheduled inspections: flexible scheduling (once/hourly/daily/monthly) or default daily at 06:00
- Three-tier hostname fallback extraction: regular command → platform-specific fast command → device prompt
- Hybrid command execution:  default (wait for prompt), large configurations automatically switch  long timeout
- SSH connections retried 2 times, 3-second interval

### 4. Network Diagnostics (`routers/ping.py`)
- **Users**: All logged-in users
- Batch ping (up to 100 target IPs, 50 concurrent, configurable timeout 500-5000ms)
- **Quick device selection**: dropdown fills targets with an IP picked from the device list
- Traceroute (Linux: MTR, Windows: Tracert)
- Continuous ping test (up to 100 attempts)
- Supports IP range input:
  - CIDR: `192.168.1.0/24`
  - Range: `192.168.1.1-192.168.1.50`
  - Comma/newline separated: `10.0.0.1, 10.0.0.2`

### 5. Configuration Comparison (`routers/config_compare.py`)
- **Users**: All logged-in users
- Paste, upload, or **load from device** two configuration files
- Device dropdown loads the latest configuration backup in one click
- One-click Swap to exchange A/B configurations, Clear to empty them
- Adjustable diff context lines (0/1/3/5/8/All)
- Unified Diff line-level comparison + color syntax highlighting (+green/-red/@@blue)
- HTML side-by-side visual comparison

### 6. Alert System (`routers/alerts.py` + `routers/inspect.py`)
- **Users**: Administrator (rule management) / all users (view & acknowledge)
- **Alert rules**: rules created from CPU/memory thresholds, global and per-device supported
- **Alert levels**: Warning / Critical / Info, supports the `>` `>=` `==` operators
- **Alert escalation**: automatically escalates from Warning to Critical after N consecutive triggers (configurable escalation_count)
- **Alert silencing**: alert rules can be silenced by hours (Silence); no triggering during the silence period
- **Alert acknowledgment**: Ack acknowledges alerts, tracking handled/unhandled
- **Alert history**: dedicated history page showing the latest 200 alert records in reverse chronological order, with Ack acknowledgment and Clear All/ Clear Acknowledged bulk clearing
- **Dashboard alert panel**: homepage shows a recent alerts list + active alert count stat card (red pulse animation)
- All enabled rules are automatically evaluated during inspections; violations generate AlertHistory records

### 7. Subnet Calculation (`routers/subnet_calc.py`)
- **Users**: All logged-in users
- IPv4 subnet information: network address, mask, broadcast, usable IP range, wildcard mask, binary mask
- IPv4 **VLSM**: enter host count -> automatic optimal plan | **Route aggregation**: multiple networks -> smallest supernet | Subnetting: equal-sized subnets (up to 256) | Subnet enumeration: 3-column display (up to 500)
- IPv6 subnet information: compressed/expanded addresses, link-local detection, hostmask
- Private address detection (IPv4/IPv6)

### 8. Configuration Push (`routers/config_push.py`)
- **Users**: Administrator
- Batch-push configuration commands to network devices
- Supports pasting command text or uploading a configuration file (.txt/.cfg/.conf, max 2MB)
- Parallel push: ThreadPoolExecutor 10-way concurrency, 120s timeout protection, duration statistics
- Push results automatically saved to inspection reports
- Three-step safety flow: select devices → preview & confirm → execute push
- Uses `netmiko.send_config_set()` to automatically enter/exit configuration mode
- Pushes serially device by device; all results displayed at once on completion (success/failure + detailed output)
- Push results automatically saved to the inspection report (`InspectionRun`)
- Supports `#` comment-line filtering

### 9. Custom Commands (`routers/custom_cmds.py`)
- **Users**: Administrator
- Configure custom commands per device platform
- Three execution modes: single-command quick execution, single-device batch execution (saves report), multi-device batch execution (independent report per device)
- Supports the `all` platform wildcard (applies to all devices)
- Commands can be enabled/disabled
- Supported platform tags: `all`, `cisco_ios`, `cisco_xr`, `cisco_nxos`, `juniper`, `huawei`, `hp_comware`, `fortinet`, `arista_eos`, `ruijie_os`

### 10. Scheduled Inspection Scheduler (`routers/scheduler.py`)
- **Users**: Administrator
- **Scheduler**: BackgroundScheduler (thread-based scheduling, no dependency on the asyncio event loop)
- **Timezone**: all scheduled jobs use CST (UTC+8), ensuring on-time triggering at Beijing time
- 4 schedule types: once (specified date & time) / hourly (every N hours) / daily (specified time) / monthly (specified date + time)
- Each scheduled job can optionally target specific devices (none selected = all devices, up to 100 concurrent)
- Dynamic APScheduler management: add/modify/delete/enable/disable take effect immediately, no restart needed
- One-time jobs are automatically disabled after execution; expired jobs automatically deferred to the next day
- Supports a "Run Now" button + real-time progress panel (AJAX + polling)
- "Run Now" returns JSON to drive the progress panel, no page navigation needed
- Falls back to the default daily 06:00 CST when there are no DB scheduled jobs

### 11. Network Topology ( + )
- **Users**: All logged-in users
- Automatically generates an interactive topology graph from CDP/LLDP neighbor information
- Uses the vis.js force-directed layout; supports dragging nodes, scroll-wheel zoom, and click for details
- **Automatic role recognition**: Core / Distribution / Access, tiered by connection count
- **Path tracing**: select two devices, BFS shortest path highlighted with hop count annotated
- **Alert integration**: devices with triggered alerts flash a red border
- **Cross-protocol IP match merging**: the same device discovered by CDP and LLDP is automatically deduplicated
- Devices automatically grouped by /24 subnet, arranged in tiers
- Links colored by port speed (GE/10G green, FE orange), hover shows all ports
- Click a node for a device detail popup (IP/CPU/memory/neighbors/role/alerts)
- Click a link to show both endpoint devices and port information
- Search & locate + auto refresh

### 12. Reports Module (`routers/reports.py`)
- **Users**: All logged-in users
- **Bulk delete**: checkbox multi-select + one-click bulk deletion of inspection reports
- **PDF export**: full inspection report PDF with header/footer/page numbers/stat cards. Font system: Helvetica-Bold for English headings, Courier for code, DroidSansFallback for Chinese
- **Word export**: `.docx` format with headings/stat cards/gray-background code blocks/colored status labels
- **HTML export**: complete page with CSS styling (dark theme, print-friendly)
- **CSV export**: bulk export of the latest 500 records (ID/time/IP/hostname/CPU/memory/uptime/status)
- Export HTML/Word directly from each row of the report list
- Inspection history list (latest 200 entries, device filter dropdown)
- Statistics overview (total/success/failure)
- Single inspection detail view (raw command output, JSON format)

### 13. BOM Matching Module (`routers/bom.py` + `bom_matcher.py` + `templates/bom_match.html`)
- **Users**: All logged-in users
- Upload a project BOM file (.xlsx/.xls, ≤20MB bounded reads prevent OOM); automatically locates the `Product#` header row and parses the Product#/Description/Vendor/QTY columns
- Matches against the selected inspection records to verify delivered devices are configured per the order:
  - **Network devices**: BOM `Product#` exactly matched against the PID in the inspection data's "hardware inventory"
  - **Servers** (BMCs without PID output, such as Dell iDRAC): Model/CPU/memory/disk/RAID/NIC/power keywords extracted from the Description and word-level matched against the inspection "hardware summary" — tolerant of (R)/(TM) trademark symbols; `BROADCOM XXXX` automatically normalized to `BCMXXXX`; CPU `24C/48T` takes only the core count `24C`
- Tri-state match results: matched / unmatched / configuration anomaly (servers list per-item configuration check details, flagging missing items)
- Result rows can be checked for exclusion (clean up mismatched rows before export)
- Export an Excel matching report (status color coding: green=matched / yellow=unmatched / red=configuration anomaly; RFC 6266 safe Chinese filenames)
- BOM data cached in server-side memory per session (session-level isolation, mutually invisible)

### 14. Case System (`routers/cases.py` + `templates/case*.html`)
- **Users**: All logged-in users (category management: administrator)
- Archive inspection reports, device documents, and photos by project/case; one separate directory per case
- **Duplicate name check**: when a new case name duplicates an existing case (case-insensitive, leading/trailing spaces trimmed automatically), creation is rejected with an error banner; rejected creations do not trigger the QC webhook (the case name is the T1 order number, and a duplicate would make the QC link ambiguous)
- Configurable categories (defaults: inspection report/device document/photo): add/delete/edit, rename with duplicate check, non-empty categories cannot be deleted
- **Search**: the list page searches case names/notes/filenames across tables (LIKE wildcards escaped), matching files displayed inline; the detail page filters filenames in real time
- Multi-file upload (single file ≤50MB): bounded reads prevent OOM, filename sanitization + uuid collision prevention + path traversal protection, rollback of files already written to disk on mid-way failure
- **Online viewing**: images/PDF inline; other types such as HTML force download (eliminates stored XSS), uniform `X-Content-Type-Options: nosniff`
- Preview URLs carry an HMAC signature + 6h expiry (signature verified before the DB lookup, unforgeable/unenumerable)
- Downloads streamed via FileResponse + RFC 6266 Chinese filenames
- Deleting a case cascades to delete all files and directories
- **QC integration**: content changes (create/upload/delete file/delete case) automatically notify the T1 quality inspection system via webhook (see `qc_webhook.py`)

### 15. CA Certificate Server (`routers/ca_server.py` + `ca_engine.py`)
- **Users**: All logged-in users
- Root CA creation (RSA-2048/4096, ECC P-256/P-384, configurable validity period) and root certificate download
- End-entity certificate issuance (Common Name + SAN, RSA/ECC); supports **external CSR signing** (the server does not hold the private key)
- Certificate revocation: **the DB is the single source of truth**, CRL files are rebuildable caches — atomic writes + thread locks eliminate loss of revocation records due to corruption/concurrency
- Revoked certificates **can be deleted only after expiry** (prevents serial numbers from being silently "un-revoked" by early removal from the CRL)
- Export: PEM zip (certificate + private key + CA chain) / bare .crt / PKCS#12 (custom password; certificates issued from a CSR have no private key, only .crt can be downloaded)
- All downloads use RFC 6266 encoding (no crashes on Chinese certificate names)

### 16. Configuration Backup Management (`routers/config_backup.py` + `../inspection.py`)
- **Users**: All logged-in users
- Browse the backup list (filter by device IP, shows size/time)
- Online viewing (inline) / download `.cfg` (RFC 6266 filenames)
- Manually trigger a single-device backup (netmiko; SHA256 deduplication, can be forced)
- Bulk export ZIP (filter by device) / bulk delete (only .cfg inside the backup directory, path validation)
- Rotation: manual backups keep the latest 10 per device; automatic inspection backups keep 5 versions after deduplication

### 17. LLM VRAM Calculator (`routers/vram_calc.py`)
- **Users**: All logged-in users
- 10 preset models (LLaMA 3 / Qwen 2.5 / DeepSeek V3 / R1 / Mistral / Gemma / ChatGLM / Yi) + custom parameter counts
- Comparison table of 8 quantization precisions (FP32 / FP16 / BF16 / INT8 / FP8 / INT4 / GPTQ / AWQ)
- Estimates for three scenarios: inference (parameters × bytes × 1.2) / training (×4) / multi-GPU deployment (TP overhead ×1.05, PP ×1.02)
- Pure calculation tool, no data storage

---

## Directory Structure

```
/home/ivan/network-inspection/
├── inspection.py                   # Core inspection engine (netmiko SSH collection + parsing + HTML report generation)
├── inspection.db                   # SQLite database
├── devices.csv                     # CSV device inventory (for bulk import)
├── inspection-platform/            # Web platform
│   ├── .encryption_key             # Password encryption key (mode 600, auto-generated on first startup)
│   └── backend/
│       ├── main.py                 # FastAPI entry point, LoginMiddleware, scheduled inspections, Dashboard
│       ├── database.py             # SQLAlchemy engine & Session factory
│       ├── models.py               # ORM models (Device/User/InspectionRun/AlertRule/AlertHistory/CustomCommand/InspectionSchedule)
│       ├── schemas.py              # Pydantic request/response models
│       ├── crypto.py               # Password encryption/decryption utilities (Fernet AES-128-CBC + HMAC)
│       ├── constants.py            # Shared constants (SERVER_PLATFORMS)
│       ├── helpers.py              # Shared helper functions (save_inspection_run)
│       ├── templating.py           # Jinja2 template engine instance
│       ├── engine/
│       │   └── inspector.py        # Inspection engine wrapper (calls inspection.py)
│       ├── routers/
│       │   ├── auth.py             # Authentication routes (login/logout/user management/Session)
│       │   ├── devices.py          # Device CRUD (Web + API)
│       │   ├── inspect.py          # Inspection triggering & progress tracking
│       │   ├── ping.py             # Ping / Traceroute / MTR
│       │   ├── config_compare.py   # Configuration file comparison (paste/upload/load from device)
│       │   ├── alerts.py           # Alert rule management
│       │   ├── subnet_calc.py      # IPv4/IPv6 subnet calculation & division
│       │   ├── config_push.py     # Configuration push (commands/file upload)
│       │   ├── config_backup.py   # Configuration backup management (browse/download/manual backup/bulk export)
│       │   ├── custom_cmds.py      # Custom command management & real-time execution
│       │   ├── scheduler.py        # Scheduled inspection scheduling (dynamic APScheduler management)
│       │   └── topology.py         # Network topology (vis.js interactive graph)
│       │   └── reports.py          # Inspection report viewing & export
│       ├── templates/              # Jinja2 HTML templates (15 pages)
│       │   ├── base.html           # Base layout (navigation bar)
│       │   ├── login.html          # Login page
│       │   ├── dashboard.html      # Dashboard (device status + alert panel + CPU/memory trends)
│       │   ├── devices.html        # Device management page
│       │   ├── users.html          # User management page
│       │   ├── alerts.html         # Alert rule configuration & history page
│       │   ├── config_push.html   # Configuration push page (select/preview/results)
│       │   ├── config_backup.html # Configuration backup management page (list/download/manual backup/ZIP export)
│       │   ├── custom_cmds.html    # Custom command management & execution page
│       │   ├── scheduler.html      # Scheduled inspection management page
│       │   └── topology.html       # Network topology page (CDP/LLDP visualization)
│       │   ├── ping.html           # Network diagnostics page
│       │   ├── subnet.html         # Subnet calculation page
│       │   ├── config_compare.html # Configuration comparison page (input + results in one)
│       │   ├── reports.html        # Report list page
│       │   ├── report.html         # Single inspection detail page
│       │   └── adhoc.html          # Ad-hoc inspection page
│       └── static/
│           └── app.css             # Global styles
├── configs/                        # Device configuration backup directory (*.cfg)
└── reports/                        # HTML report output directory
```

---

## Requirements

| Dependency | Version | Purpose |
|------|------|------|
| Python | ≥ 3.10 | Runtime environment |
| FastAPI | 0.136 | Web framework |
| Uvicorn | 0.49 | ASGI server |
| SQLAlchemy | 2.0 | ORM |
| Netmiko | 4.7 | SSH connections & command execution |
| APScheduler | 3.11 | Scheduled inspections |
| cryptography | 41.0 | Fernet password encryption |
| Jinja2 | 3.1 | Template rendering |
| python-multipart | 0.0.32 | File upload parsing |

Full installation command:

```bash
pip install fastapi uvicorn sqlalchemy netmiko apscheduler cryptography jinja2 python-multipart
```

---

## Quick Start

### Development Mode

```bash
cd /home/ivan/network-inspection/inspection-platform
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Visit `http://<server IP>:8000`

API docs: `http://<server IP>:8000/docs`

### Production Mode (systemd)

Service file: `/etc/systemd/system/network-inspect.service`

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

Management commands:

```bash
# start / stop / restart
sudo systemctl start network-inspect
sudo systemctl stop network-inspect
sudo systemctl restart network-inspect

# view status
sudo systemctl status network-inspect

# live logs
journalctl -u network-inspect -f
tail -f /home/ivan/inspect.log

# enable at boot
sudo systemctl enable network-inspect
```

---

## Default Accounts

| Username | Password | Role |
|--------|------|------|
| `admin` | Random password auto-generated on first startup | Administrator (can manage users/devices/alerts) |

> After generation, the initial password is written to `/tmp/inspect_initial_admin_password` (permissions 0600; save it and delete the file immediately), or you can preset it via the environment variable `INSPECT_INITIAL_ADMIN_PASSWORD`.
> ⚠️ **After logging in for the first time, change the initial password immediately via the "Change Password" page.**

---

## API Endpoints


- `/bom-match` — BOM matching verification page
- `/ca-server` — CA certificate management page
- **CA certificate server**: built-in PKI system that supports creating a root CA, issuing end-entity certificates, CSR signing, PEM/PKCS#12 export, and certificate revocation. The CRL is rebuilt with the database as the single source of truth (the file is a rebuildable cache); atomic writes + thread locks eliminate revocation records lost to corruption/concurrency
- `/vram-calc` — LLM VRAM calculator page

> All `/api` endpoints require authentication (Cookie: `inspect_session`).  
> Unauthenticated API requests are intercepted by LoginMiddleware and returned an HTTP 303 redirect to the login page.

### Devices

| Method | Path | Description | Auth |
|------|------|------|:----:|
| GET | `/devices` | Device management page | ✅ |
| GET | `/devices/api` | Device list (JSON) | ✅ |
| POST | `/devices/api` | Create device (JSON) | ✅ |
| POST | `/devices/add` | Create device (form) | ✅ |
| PUT | `/devices/api/{id}` | Update device | ✅ |
| DELETE | `/devices/api/{id}` | Delete device | ✅ |

### Inspection

| Method | Path | Description | Auth |
|------|------|------|:----:|
| POST | `/inspect` | Trigger an inspection (`?device_id=N` for a single device) | ✅ |
| GET | `/inspect/status/{run_id}` | Query inspection progress (polling) | ✅ |

### Authentication

| Method | Path | Description |
|------|------|------|
| GET | `/login` | Login page |
| POST | `/login` | Login submission (Form: username, password, next) |
| GET | `/logout` | Logout |
| GET | `/change-password` | Change password page |
| POST | `/change-password` | Submit password change (Form: old_password, new_password, confirm_password) |
| GET | `/users` | User management page (administrator) |
| POST | `/users/add` | Add user (administrator, password ≥ 8 characters) |
| POST | `/users/reset-password/{id}` | Reset user password (administrator, cannot reset own) |
| POST | `/users/delete/{id}` | Delete user (administrator) |

### Network Diagnostics

| Method | Path | Description |
|------|------|------|
| GET | `/ping` | Ping tool page (with quick device-selection dropdown) |
| POST | `/ping` | Run Ping/Traceroute/MTR |

### Configuration Comparison

| Method | Path | Description |
|------|------|------|
| GET | `/config-compare` | Configuration comparison page (with device-selection dropdown) |
| POST | `/config-compare` | Submit comparison (paste/upload/load from device) |
| GET | `/config-compare/load-config?device_id=N` | Load a device's latest configuration backup (JSON) |

### Configuration Push

| Method | Path | Description | Auth |
|------|------|------|:----:|
| GET | `/config-push` | Configuration push page | ✅ |
| POST | `/config-push/preview` | Preview push content (select device + command preview) | ✅ |
| POST | `/config-push/execute` | Execute push (send_config_set per device) | ✅ |

### Alerts

| Method | Path | Description | Auth |
|------|------|------|:----:|
| GET | `/alerts` | Alert rules page | ✅ |
| GET | `/alerts/history` | Alert history page | ✅ |
| POST | `/alerts/add` | Add alert rule (supports severity/escalation_count) | ✅ |
| POST | `/alerts/silence/{rule_id}` | Silence alert rule (hours=N) | ✅ |
| POST | `/alerts/ack/{history_id}` | Acknowledge alert | ✅ |
| DELETE | `/alerts/api/{rule_id}` | Delete alert rule | ✅ |

### Subnet Calculation

| Method | Path | Description |
|------|------|------|
| GET | `/subnet` | Subnet calculation page (5 tabs: IPv4/subnetting/VLSM/aggregation/IPv6) |
| POST | `/subnet` | Calculate subnets (IPv4/IPv6/VLSM/route aggregation/subnet enumeration) |

### Custom Commands

| Method | Path | Description | Auth |
|------|------|------|:----:|
| GET | `/custom-commands` | Command management page | ✅ |
| POST | `/custom-commands/add` | Add command | ✅ |
| POST | `/custom-commands/execute` | Execute command on a device (results saved automatically) |
| POST | `/custom-commands/execute-multi` | Parallel execution across multiple devices (ThreadPool, 120s timeout) | ✅ |
| POST | `/custom-commands/delete/{id}` | Delete command | ✅ |
| POST | `/custom-commands/toggle/{id}` | Enable/disable command | ✅ |

### Network Topology

| Method | Path | Description | Auth |
|------|------|------|:----:|
| GET | `/topology` | Network topology page (vis.js interactive graph, Fit/Export (JSON download)/Auto-refresh 60s) | ✅ |
| GET | `/topology/data` | Topology data JSON (nodes + edges + groups + roles + alerts) | ✅ |

### Scheduled Inspection

| Method | Path | Description | Auth |
|------|------|------|:----:|
| GET | `/scheduler` | Scheduled job management page | ✅ |
| POST | `/scheduler/add` | Add scheduled job |
| POST | `/scheduler/edit/{id}` | Edit scheduled job |
| POST | `/scheduler/batch-delete` | Batch delete scheduled jobs | ✅ |
| POST | `/scheduler/run-now/{id}` | Run now (supports JSON response) | ✅ |
| POST | `/scheduler/toggle/{id}` | Enable/disable scheduled job | ✅ |
| POST | `/scheduler/delete/{id}` | Delete scheduled job | ✅ |

### Reports

| Method | Path | Description | Auth |
|------|------|------|:----:|
| GET | `/reports` | Report list page (supports ?device_id=N device filtering, statistics overview) | ✅ |
| GET | `/reports/api` | Report list (JSON) | ✅ |
| POST | `/reports/api/batch-delete` | Batch delete reports (JSON: [id1,id2,...]) | ✅ |
| GET | `/reports/{run_id}` | Single inspection details | ✅ |
| GET | `/reports/{run_id}/export` | Export HTML report | ✅ |
| GET | `/reports/{run_id}/export/docx` | Export Word report (.docx) | ✅ |
| GET | `/reports/{run_id}/export/pdf` | Export PDF report | ✅ |
| GET | `/reports/export/csv` | Export CSV | ✅ |
| DELETE | `/reports/api/{run_id}` | Delete a single report | ✅ |

### BOM Matching

| Method | Path | Description |
|------|------|------|
| GET | `/bom-match` | BOM matching page (lists the 50 most recent inspection records) |
| POST | `/bom-match/api/upload` | Upload and parse a BOM xlsx (≤20MB, returns a statistics snippet) |
| POST | `/bom-match/api/match` | Run matching against the selected inspection records (returns a result table) |
| POST | `/bom-match/api/remove` | Remove result rows by row number |
| GET | `/bom-match/api/export` | Export Excel matching report |

### Case Management

| Method | Path | Description |
|------|------|------|
| GET | `/cases` | Case list (`?q=` cross-table search of names/remarks/filenames) |
| POST | `/cases/create` | Create case (duplicate names rejected with the error echoed) |
| GET | `/cases/{id}` | Case details (includes signed preview URL) |
| POST | `/cases/{id}/upload` | Multi-file upload (≤50MB per file) |
| GET | `/cases/{id}/files/{fid}/download` | Download file |
| GET | `/cases/{id}/files/{fid}/view` | In-browser view page |
| GET | `/cases/{id}/files/{fid}/raw` | View inline/download raw file |
| GET | `/cases/preview/{id}/{stored}` | Signed preview (public, requires valid exp+sig) |
| POST | `/cases/{id}/files/{fid}/delete` | Delete file |
| POST | `/cases/{id}/delete` | Delete case (cascades) |
| GET | `/cases/categories` | Category management page (administrator) |
| POST | `/cases/categories/add` | Add category (administrator) |
| POST | `/cases/categories/{id}/rename` | Rename category (administrator) |
| POST | `/cases/categories/{id}/delete` | Delete empty category (administrator) |

### CA Certificates

| Method | Path | Description |
|------|------|------|
| GET | `/ca-server` | CA management page |
| POST | `/ca-server/api/root/create` | Create root CA |
| GET | `/ca-server/api/root/{id}/download` | Download root certificate |
| POST | `/ca-server/api/cert/issue` | Issue end-entity certificate |
| POST | `/ca-server/api/csr/sign` | Sign external CSR |
| POST | `/ca-server/api/cert/{id}/revoke` | Revoke certificate (rebuilds the CRL) |
| POST | `/ca-server/api/cert/{id}/delete` | Delete certificates that are both revoked and expired |
| GET | `/ca-server/api/cert/{id}/download/pem` | Download PEM zip (certificate + private key + CA) |
| GET | `/ca-server/api/cert/{id}/download/crt` | Download bare certificate |
| POST | `/ca-server/api/cert/{id}/download/p12` | Download PKCS#12 (Form: password) |

### Configuration Backup

| Method | Path | Description |
|------|------|------|
| GET | `/config-backup` | Backup management page |
| GET | `/config-backup/api/list` | Backup list (`?device_ip=` filter) |
| GET | `/config-backup/api/download/{filename}` | Download (`?view=1` to view in browser) |
| POST | `/config-backup/api/backup-now` | Manually back up a single device |
| GET | `/config-backup/api/export-zip` | Batch export ZIP |
| POST | `/config-backup/api/batch-delete` | Batch delete backups |

### VRAM Calculation

| Method | Path | Description |
|------|------|------|
| GET | `/vram-calc` | Calculator page |
| POST | `/vram-calc` | Calculate (Form: model/custom_params/quant/scenario/gpu_count/strategy) |

### Others

| Method | Path | Description |
|------|------|------|
| GET | `/` | Redirects → `/dashboard` |
| GET | `/dashboard` | Dashboard (device statistics + active alerts + recent alerts panel + CPU/memory trend bar chart) |
| GET | `/docs` | Swagger API docs (login required) |
| GET | `/openapi.json` | OpenAPI Schema (login required) |

---



---

## Current Running State

> Data last updated: 2026-06-16

### Database Statistics

| Table | Row count | Description |
|---|:---:|------|
| devices | 7 | Managed devices |
| inspection_runs | 7 | Historical inspection records |
| alert_history | 2 | Alert history (including escalation test data) |
| inspection_schedules | 3 | Active scheduled inspection jobs |
| custom_commands | 3 | Custom command templates |
| users | 3 | Platform users |

> ⚠️ 2026-06-16: the database suffered corruption at one point (since repaired); preventive measures deployed: singleton lock + startup integrity check + systemd crash-loop protection + periodic WAL checkpoints
>
> ✅ 2026-06-16 07:22: full-module verification passed (16/16), zero new errors (14MB WAL bloat + multi-process concurrent writes); recovered via dump→rebuild. 3 inspection_runs rows were lost to page corruption. Preventive measures deployed (see the safety notes below).

### Configuration Backup Overview

configs/ directory: 100+ .cfg backup files

Covered device IPs: 172.16.1.1, 172.16.1.5, 172.16.1.55, 192.168.10.1,
192.168.10.3, 192.168.10.47, 192.168.55.2, 192.168.100.63, 192.168.100.105

Latest backup: 2026-06-12 05:22 (the scheduled inspection in the early hours ran normally)

### Recent Activity

- 2026-06-16 07:22: WAL checkpoint mechanism deployed + full-module verification (16/16 PASS)
- 2026-06-16 04:42: service back up, all 13 modules verified
- 2026-06-16 03:29: database corruption recovery (dump→rebuild, 18/21 inspection_runs retained)
- 2026-06-16: deployed singleton lock + startup integrity check + systemd crash-loop protection
- 2026-06-14 12:17: security fixes verified (login/logout/authentication/backup/timestamps all normal)
- 2026-06-11 13:57: verification tests passed (test_verify.py)
- 2026-06-11 13:57: alert escalation test completed (172.16.1.5, 3 rounds)

### Git Status

- Branch: master
- Latest commit: bf51a1f fix: prevent DB corruption - singleton lock, integrity check, crash-loop protection
- Cleanup: .bak backup files deleted, configs/ brought under version control
- Untracked: many .bak backup files + new config files
- Deleted: old configuration backups (cleaned up by scheduled rotation)

---


---


---

## Configuration

### Environment Variables

| Variable | Description | Default |
|------|------|--------|
| `INSPECT_SECRET_KEY` | Fernet encryption key (Base64-encoded) | Auto-generated into the `.encryption_key` file |
| `INSPECT_DB_PATH` | SQLite database file path | `/home/ivan/network-inspection/inspection.db` |

### Encryption Key

- Key file (recommended): `/etc/inspection/.encryption_key` (a directory that is not web-accessible)
- Key file (legacy location): `inspection-platform/.encryption_key` (automatically migrated to the new location at startup)
- Environment variable: `INSPECT_SECRET_KEY` (highest priority)
- Algorithm: Fernet (AES-128-CBC + HMAC-SHA256)
- Permissions: `600` (readable/writable by the owner only)
- Auto-generated on first startup, reused on subsequent startups
- **Back up this file** — without it, stored device passwords cannot be decrypted

### Database

- Type: SQLite (WAL mode)
- Location: defaults to `/home/ivan/network-inspection/inspection.db`, can be overridden with the `INSPECT_DB_PATH` environment variable
- Tables: `users`, `devices`, `inspection_runs`, `alert_rules`, `alert_history`, `inspection_schedules`, `custom_commands`
- Table schemas are created automatically on first startup (SQLAlchemy `Base.metadata.create_all`)
- Plaintext passwords are automatically migrated to encrypted storage on first startup
- **WAL mode**: reads and writes do not block each other, 3-5x better concurrency performance
- **Connection pool**: `pool_size=5` + `max_overflow=10` + `pool_pre_ping=True` (automatically detects dropped connections)
- **Connection recycling**: `pool_recycle=3600` (1 hour)
- **Busy timeout**: `busy_timeout=5000ms` (avoids "database is locked" errors)
- **Foreign key constraints**: enforced with `foreign_keys=ON`
- **Automatic cleanup**: daily at 03:00 CST, prunes inspection records older than 30 days and acknowledged alerts older than 90 days

### Configuration Backup Deduplication

- SHA256 hash comparison: each backup is compared against the previous backup's content; if the content is unchanged, the write is skipped
- Automatic rotation: the latest 5 backup versions are kept per device, older versions are cleaned up automatically
- Storage location: `configs/` directory, file naming format `{ip}_{timestamp}.cfg`

### Scheduled Inspections

- Default schedule: daily at 06:00
- Configuration location: `backend/main.py`, line 89
  ```python
  scheduler.add_job(scheduled_inspection, CronTrigger(hour=6, minute=0), id="daily", name="daily")
  ```

### Inspection Concurrency Parameters

| Parameter | Default | Description |
|------|--------|------|
| `MAX_WORKERS` (Web) | `min(os.cpu_count() * 2, 50)` | Dynamically adjusted, capped at 50 |
| `MAX_WORKERS` (CLI) | 10 | CLI script concurrency |
| `CONN_TIMEOUT` | 30s | SSH connection timeout |
| `CMD_TIMEOUT` | 60s | Single-command execution timeout |
| `CONN_RETRIES` | 2 | SSH connection retry count |
| `RETRY_DELAY` | 3s | Retry interval |
| Per-device timeout | 300s | 5-minute guard to prevent blocking |
| Progress retention | 10s | Progress kept for 10s after the inspection finishes for frontend polling |

---


## Docker Deployment

### Image Details

| Item | Details |
|------|------|
| Current image | `network-inspection:v5` (= `latest`, built 2026-08-13, code baseline git `e714245`) |
| Historical images | `v4` / `v3` kept locally on the server, rollback available |
| Base image | `python:3.12-slim` |
| Exposed port | `8000` (in-container), mapped to `9001` on the host by default |
| Working directory | `/app/inspection-platform` |
| Run user | `inspect` (non-root, uid 1000) |

> Full manual: `dockerivan.MD` at the repo root (beginner edition); a condensed runbook is at
> `docs/docker-compose-runbook-2026-08-13.md`; a line-by-line Dockerfile walkthrough is at
> `docs/dockerfile-explained-2026-08-13.md`; the v5 build and verification record is at
> `docs/docker-build-v5-verify-2026-08-13.md`.

### Quick Start (fresh server)

The repo root ships with `setup.sh`; run it once before the first launch and it pre-creates everything
(.env / empty inspection.db / data directories / Fernet key / owner uid 1000):

```bash
cd /home/ivan/network-inspection   # or your deployment directory (must contain the full set of files alongside the Dockerfile)
./setup.sh                         # one-time initialization
sudo docker compose up -d          # start
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:9001/login   # expect 200
```

Manual pre-creation checklist (when not using setup.sh): `.env` (containing `INSPECT_SECRET_KEY`),
**empty file** `inspection.db` (must be created with touch, otherwise Docker creates a same-named directory),
`configs/ reports/ logs/ data/cases/ data/ca/`, all owned by uid 1000.

### docker-compose.yml (current version)

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

> Note: `INSPECT_SECRET_KEY` cannot be changed once it is in use (changing it makes every device password in the DB undecryptable);
> when migrating from an old server, put the old key into `.env` first, then run setup.sh.

### Initial admin password (first start with a fresh DB)

When an existing DB is mounted the password is unchanged; on first start with a **fresh DB**, a 22-character random password is generated and written to a file inside the container:

```bash
sudo docker exec network-inspect cat /tmp/inspect_initial_admin_password
# or preset INSPECT_INITIAL_ADMIN_PASSWORD=<password> in .env before the first start (no file generated)
```

After logging in and changing the password, delete the file: `sudo docker exec network-inspect rm /tmp/inspect_initial_admin_password`

### Building the image

```bash
cd /home/ivan/network-inspection     # must be run from this directory (build context)
sudo docker build -t network-inspection:v6 -t network-inspection:latest .
sudo docker save network-inspection:v6 -o network-inspection-v6.tar   # export for distribution
```

The dependency layer and code layer are separated, so a rebuild after code changes takes about 3 seconds (the 135MB pip layer hits the cache).

### Cross-server deployment procedure

```
Source server (192.168.26.53)              Target server
─────────────────────────            ─────────────────────────
docker build -t network-inspection:v6
docker save -o network-inspection-v6.tar
                                       ↓ scp transfer (image + compose + setup.sh + .env.example)
                                    docker load -i network-inspection-v6.tar
                                    ./setup.sh && docker compose up -d
```

### In-container path mapping

| Host | In-container | Purpose |
|--------|--------|------|
| `./inspection.db` | `/app/inspection.db` | SQLite database (WAL) |
| `./configs/` | `/app/configs/` | Device configuration backups |
| `./reports/` | `/app/reports/` | Inspection reports |
| `./logs/` | `/app/logs/` | Log files |
| `./data/cases/` | `/app/inspection-platform/backend/data/` | Case attachments |
| `./data/ca/` | `/app/inspection-platform/data/` | CA certificate materials |

### Common management commands

```bash
sudo docker compose ps                     # status
sudo docker compose logs -f                # logs
sudo docker compose restart                # restart
sudo docker compose down                   # stop
sudo docker exec -it network-inspect /bin/bash   # enter the container

# Update: build a new tag → change image: in compose →
sudo docker compose up -d
```

### Pull from the Alibaba Cloud registry (alternative)

```bash
docker pull crpi-onapv500ctq06zb5.cn-hangzhou.personal.cr.aliyuncs.com/ivannetwrok/networkauto:latest
```

> Note: the registry image may lag behind the local v5; the tags in the build record document are authoritative.

### Fixing Docker networking failures

The Dockerfile is already configured with the Alibaba Cloud PyPI mirror. The apt sources can also be replaced:

```dockerfile
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources
```

See `dockerivan.MD` for detailed documentation.

---

## Windows Deployment
This project fully supports Windows deployment; the core code uses pure-Python cross-platform libraries (FastAPI / SQLAlchemy / Netmiko / APScheduler).

### Windows-specific adaptations

| Feature | Linux | Windows | Handling |
|------|-------|---------|---------|
| Ping | `ping -c 4 -W 1000` | `ping -n 4 -w 1000` | `ping.py` auto-detects `sys.platform` |
| Traceroute | MTR (`mtr --report`) | Tracert (`tracert -d`) | `ping.py` switches the command automatically |
| File permissions | `os.chmod(0o600)` | No POSIX chmod support | `crypto.py` skips safely via try/except |
| Process management | systemd (`systemctl`) | NSSM / Windows Service / run directly | See below |

### Starting on Windows

**Option 1: run directly (development/testing)**

```powershell
cd C:\network-inspection\inspection-platform
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Option 2: register as a Windows service with NSSM (production)**

```powershell
# Install NSSM
winget install NSSM.NSSM

# Register the service
nssm install NetworkInspect python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
nssm set NetworkInspect AppDirectory C:\network-inspection\inspection-platform
nssm set NetworkInspect AppStdout C:\network-inspection\inspect.log
nssm set NetworkInspect AppStderr C:\network-inspection\inspect.log
nssm start NetworkInspect
```

**Option 3: Task Scheduler**

Create a task triggered "at system startup" that runs:
```
Program: python
Arguments: -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
Start in: C:\network-inspection\inspection-platform
```

### Path adjustments

When migrating from Linux to Windows, only this needs to be changed:

```python
# database.py — change the relative path to an absolute path
DATABASE_URL = "sqlite:///C:/network-inspection/inspection.db"
```

All other paths use `pathlib.Path` and adapt to the OS separator automatically.

### Dependency installation (Windows)

```powershell
pip install fastapi uvicorn sqlalchemy netmiko apscheduler cryptography jinja2 python-multipart
```

> ⚠️ On Windows, Netmiko requires PyCryptodome: `pip install pycryptodome`

---

## Git Version Control

The project has an initialized Git repository, supporting git status/diff/commit/log/checkout.

## Language Switching

The right side of the navigation bar provides an **EN / Chinese** toggle button. Implemented with / attributes + JavaScript Cookie:
- By default all navigation labels are displayed in Chinese
- Click EN to switch to the English interface (Dashboard, Devices, Reports, etc.)
- The language preference is persisted via a Cookie (valid for 1 year) and survives refreshes
- Does not affect the language of device data, inspection reports, and other content

---
---

## Routing Table Validation and Automatic Fallback

The inspection platform has a built-in routing table output validation mechanism that automatically detects whether the data returned by a command is log pollution rather than routing information.

**How it works:**
1. Execute the routing table command (e.g. `display ip routing-table statistics`)
2. The validator `_validate_routing_output()` checks whether the output contains log signatures (`FIREWALLATCK`, `%%01ATK`, etc.)
3. If log pollution is detected, it automatically falls back to the backup command (e.g. `display ip routing-table`)
4. Validate the fallback command's output again to ensure the data is correct

**Routing commands and fallbacks per vendor:**

| Vendor | Primary command | Fallback command |
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

## Known Issues and Future Improvements

### Security (priority: high)

| # | Issue | Impact | Improvement plan |
|---|------|------|----------|
| 1 | User passwords used weak hashing | Security risk | Upgraded to PBKDF2-SHA256 (600K iterations) |
| 2 | CLI script inspection.py reads plaintext passwords from CSV | Password leak risk | Reuse crypto.py Fernet encryption or read from the web database |
| 3 | devices.csv stores the password column in plaintext | File-permission leak risk | Migrate into the web database (encrypted) |

### Code quality (priority: medium)

| # | Issue | Impact | Improvement plan |
|---|------|------|----------|
| 1 | 19+ .bak/.bak_* files scattered around | Cluttered codebase | Clean up in one pass, keeping the most recent versions |
| 2 | H3C_COMMANDS defined twice, at lines 138 and 196 | The latter overrides the former | Merge into a single definition |
| 3 | inspection.db-wal 6.6MB | Disk usage | PRAGMA wal_checkpoint(TRUNCATE) |

### Feature enhancements (priority: low-medium)

| # | Direction | Reference solution | Priority |
|---|------|----------|:---:|
| 1 | Add SNMP performance collection | LibreNMS / Prometheus SNMP Exporter | Medium |
| 2 | Integrate configuration backup with Git | Oxidized Git model | Medium |
| 3 | Compliance check engine | Netshot policy engine | Low |
| 4 | Containerized deployment | Netshot compose.yaml reference | Low |
| 5 | gNMI streaming telemetry research | OpenConfig vendor support matrix | Low |
| 6 | Upgrade password hashing to bcrypt/argon2 | OWASP recommendation | Medium |

### Project cleanup commands

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

## Security fix log (2026-06-14)

8 security issues fixed based on a full-project code review:

| # | File | Fix |
|---|------|----------|
| 1 |  | Path traversal protection: reject  and path separators, validate the parent directory, add  authentication |
| 2 |  | Add  response header |
| 3 |  | Fix image name to , mount  to prevent key loss |
| 4 |  | Add  lock protection to  dictionary writes, eliminating the concurrent race condition |
| 5 |  | Add  lock protection to  in  |
| 6 |  | Add  and  attributes to the Session Cookie |
| 7 |  | Fix legacy SHA256 password verification path: PBKDF2 only matches 64-character hex salts, legacy formats upgrade normally |
| 8 |  | Add  comment explaining that the  suffix must not be added (it would break existing encrypted passwords) |

| 9 | inspection.py | 5 occurrences of datetime.now() changed to datetime.now(CST_TZ); backup file names and report times use Beijing time |
| 10 | config_backup.py | backup_now and export_zip use now_cst(), list_backups displays fromtimestamp(tz=CST) |
| 11 | models.py | Fix salt length check 64->32 (16 bytes hex = 32 chars), restoring PBKDF2 password verification |
| 12 | auth.py | Remove secure=True; the app runs on HTTP and does not need HTTPS-only cookies |

> Verified (2026-06-14 12:17 CST): login/logout/authentication/backup times/file name timestamps all working normally.

---

## Database corruption incident and recovery (2026-06-16)

### Incident timeline

| Time | Event |
|---|---|
| Jun 11 09:03 | First crash: two uvicorn processes writing to inspection.db simultaneously; the WAL file starts to bloat |
| Jun 11 09:03 ~ Jun 16 03:29 | 1472 crash loops (systemd Restart=always + RestartSec=5 tight loop) |
| Jun 16 03:29 | Manual systemd restart stops the loop |
| Jun 16 12:30 | User reports Dashboard Internal Server Error |
| Jun 16 12:34 | Diagnosis confirmed: database disk image is malformed |
| Jun 16 12:38 | Fix: .dump → change ROLLBACK→COMMIT → rebuild with Python executescript |
| Jun 16 12:42 | All 13 modules verified passing |

### Root cause

**Two uvicorn processes writing to the same SQLite database concurrently:**

- PID 300863: started manually with `python3 -m uvicorn --reload`, running for 2+ days
- PID 353870: the systemd `network-inspect` service

SQLite WAL mode supports multiple readers and a single writer; two processes writing simultaneously caused:
- Freelist size mismatch (actual 4183 ≠ expected 4675)
- Tree 6 (inspection_runs) overflow list length error
- Duplicate page reference (page 3624)
- 90+ orphan pages
- WAL file bloated to 14 MB (normally < 1 MB)

### Recovery result

| Table | Before recovery | After recovery | Lost |
|---|:---:|:---:|:---:|
| devices | 7 | 7 | 0 |
| users | 3 | 3 | 0 |
| inspection_runs | 21 | 18 | 3 |
| alert_rules | 2 | 2 | 0 |
| alert_history | 2 | 4 | 0 |
| inspection_schedules | 3 | 3 | 0 |
| custom_commands | 3 | 3 | 0 |

**Integrity check: ok**

### Preventive measures

| Layer | Measure | File |
|---|---|---|
| Python application layer | `flock` singleton lock (`/tmp/network-inspect.lock`), acquires an exclusive lock at startup | `main.py` |
| Python application layer | `PRAGMA integrity_check` startup check, FATAL exit on corruption | `main.py` |
| systemd | `Restart=on-failure` (replacing `always`), avoiding indiscriminate restarts | `network-inspect.service` |
| systemd | `StartLimitBurst=5` + `StartLimitIntervalSec=120`, at most 5 restarts within 2 minutes | `network-inspect.service` |
| systemd | `RestartSec=10` (replacing `5`), leaving enough time for WAL checkpoints | `network-inspect.service` |
| Ops guideline | Always use `systemctl restart network-inspect`; manual `uvicorn --reload` is forbidden | CLAUDE.md |

## Read-only token passwordless access (T1 integration)

A **fixed read-only token** for external systems such as T1 to embed links / view without logging in. Visitors carrying a valid token can browse pages without an account, but they **can only view — no creates, deletes, or updates of any kind**, and sensitive data areas such as configuration backup and topology are closed to them.

### Configuration (token kept out of git)

The token value is written only in the systemd unit and never appears in the repository:

```ini
# /etc/systemd/system/network-inspect.service  [Service] section
Environment="INSPECT_READONLY_TOKEN=<token value>"
```

After changing it, run `sudo systemctl daemon-reload && sudo systemctl restart network-inspect`. **Setting it empty = the entire feature is disabled**.

### Usage

```
http://<server>:8000/cases/2?token=<token value>     # T1 embed link (any page can carry it)
curl -H "X-Readonly-Token: <token value>" ...        # programmatic calls
```

After the first visit with `?token=`, the server automatically sets the `inspect_rt` Cookie (httponly, 30 days); subsequent in-site click navigation and file downloads no longer need the parameter.

### Permission constraints (enforced at both the middleware and router layers, not left to individual routers' discretion)

| Request | Result |
|---|---|
| GET/HEAD page browsing, Case file downloads, CA public certificates (crt/root) | 200 normal |
| Any POST/PUT/PATCH/DELETE | 403 (middleware layer) |
| `/users*`, `/change-password*` | 403 (middleware layer) |
| CA private key material download (`/download/pem`, `/download/p12`) | 403 (middleware layer) |
| Configuration backup (`/config-backup*` page/list/download/export ZIP) | 403 (router layer `require_full_user`) |
| Network topology (`/topology` page + `/topology/data`) | 403 (router layer `require_full_user`) |

- Token verification uses `hmac.compare_digest` constant-time comparison (defends against timing side channels)
- Accesses using the token via the query parameter are logged (`read-only token access: <path> from <ip>`)
- Synthetic visitor identity `T1 guest (read-only)`: `is_admin=False`, passes `require_auth`; but endpoints involving sensitive data use `require_full_user` to exclude it (configuration backups contain device credential material, topology data contains each device's complete raw_data)
- Possessing the token = visibility into all data in the system; issue it only to trusted parties; on the public internet, always pair it with HTTPS (otherwise the token appears in plaintext in the URL)

## Security Notes

- ✅ Device passwords stored encrypted with Fernet (AES-128-CBC + HMAC)
- ✅ User passwords hashed with PBKDF2-SHA256 (600,000 iterations)
- ✅ Session Cookie sets `httponly` + `samesite=lax` flags (prevents XSS theft / CSRF)
- ✅ Unified password policy: ≥8 chars / ≤128 chars / not pure whitespace; the same validation at all three entry points (add/change/reset)
- ✅ A user's sessions are all automatically revoked after password change/reset/user deletion (stolen sessions die with the old password)
- ✅ Admin endpoints uniformly use the `require_admin` dependency (non-admins get 403)
- ✅ Read-only token passwordless access (T1 integration): middleware enforces GET/HEAD only + a sensitive-path blacklist, token stored only in the systemd unit and kept out of git, constant-time comparison (see the "Read-only token passwordless access" section)
- ✅ Uniform login-failure message + virtual-hash timing equalization (prevents username enumeration)
- ✅ All API endpoints enforce authentication (`require_auth` dependency injection)
- ✅ Server-side validation of alert rule operators (only `>` `>=` `==` allowed; invalid operators return 400)
- ✅ Passwords stored encrypted (Fernet AES-128-CBC + HMAC)
- ✅ Log system redacts sensitive fields: password/secret/token/key automatically replaced with `***MASKED***`
- ✅ Automatic migration of plaintext passwords supported: old passwords detected and encrypted at startup
- ✅ Encryption key file permission 600
- ✅ Automatic compatibility with legacy SHA256 passwords — detected at login and auto-upgraded to PBKDF2-SHA256
- ✅ Singleton lock (flock): prevents multiple uvicorn instances from running at once, avoiding multi-process concurrent writes corrupting SQLite
- ✅ Startup database integrity check (PRAGMA integrity_check): exits immediately upon detecting corruption and prints recovery guidance
- ✅ systemd crash-loop protection: Restart=on-failure, StartLimitBurst=5, StartLimitIntervalSec=120
- ✅ Periodic WAL checkpoint: the daily cleanup task runs PRAGMA wal_checkpoint(TRUNCATE), preventing unbounded WAL file growth

### Data Protection
- ✅ SQLite WAL mode: concurrent-safe reads and writes
- ✅ Foreign key constraints enforced
- ✅ Configuration backup SHA256 deduplication + automatic rotation (latest 5 versions)
- ✅ Automatic data cleanup: inspection records >30 days + acknowledged alerts >90 days
- ⚠️ Production recommendations:
  - Change the default admin password
  - Use the environment variable `INSPECT_SECRET_KEY` instead of the key file
  - Set up an HTTPS reverse proxy (Nginx/Caddy)
  - Back up `inspection.db` and `.encryption_key` regularly
  - Use read-only permissions for device accounts (principle of least privilege)

---

## Optimization Log
### Hotfix: batch inspection frozen at 0/7 — leftover out-of-package relative imports from the T1 migration — 2026-08-24

- Symptom: after the W3 deployment, a manual batch inspection left the progress panel stuck forever at "Inspecting 0/7"; all 7 cards frozen in the initial Waiting/CPU=… state; no new result rows in the DB
- Root cause: T1 moved `_inspect_one` up from `routers/inspect.py` (package level `backend.routers`, where `..engine` = `backend.engine` is legal) to `backend/inspection_runs.py` (package level `backend`, the top-level package), but the lazy import inside the function body, `from ..engine.inspector import run_single_device`, was not updated for the new level — `..` escapes the top-level package, so all 7 workers hit ImportError on entry, and the exception fires before any `_bump_done` → done never advances; the `import backend.main` startup probe cannot catch lazy imports inside function bodies, so this morning's 06:00 scheduled inspection still ran the old code, and the problem only surfaced when the user triggered it manually
- Fix: the line changed to the single-point `from .engine.inspector import run_single_device` (backend.engine, a same-package subpackage module)
- Deployment-process hardening: the deployment probes gained a "lazy-import runtime probe" — it execs import statements from function bodies in module context, so hierarchy errors of this "slip past the startup probe, explode at runtime" class are now intercepted at deployment time
- Verification: first reproduced the ImportError on the server (confirming the root cause) → after deployment all probes green → admin triggered a full run on 7 devices: 15.3s 4/7 → 18.4s 6/7 → 142.7s 7/7 all connected, 7 new DB rows (id 161-167); side quantification: 192.168.10.47 alone took ~124s (slow-tail device), the other 6 finished within 15s — a full batch taking ~2.5 minutes after the fix is normal; the panel ticks in real time again (⏳→✓)

### Project-wide /code-review fixes W4: 5 index/efficiency items — 2026-08-24

- E1 `routers/config_backup.py` export_zip: the ZIP is now written to a temp file first and then streamed back in chunks, with a BackgroundTask cleaning up at the end — previously the entire ZIP accumulated in an in-memory BytesIO before the first byte was returned, peak memory = the sum of all .cfg files, and StreamingResponse wrapping an already-formed buffer is not actually streaming
- E3 `ai_engine.py` rate-limit wait: sleep the full computed wait duration in slices, then return to the loop and re-check once — previously it re-queried the rate-limit count every 1s, so a single 60s wait meant up to 75 DB aggregation queries + lock round trips; slicing (≤5s) preserves session-deletion responsiveness during the wait
- E4 `main.py` LoginMiddleware + `routers/auth.py`: session validation only consults the in-memory _sessions table (no longer opens a DB session + PK SELECT for it), and user_id is attached to request.state and reused by get_current_user — per request, "middleware queries once + router queries again" drops to a single SELECT for the whole request; validate_session (whose only caller was the middleware) was deleted along with it
- E5 `routers/ping.py`: two-phase scan probing (1 probe first to determine liveness, then 4 probes on live hosts for latency stats) — a /24 scan drops from 254×4 packets/subprocess to 254×1 + live hosts×4, cutting probe time by 3/4 per host on unreachable segments; ping_one gained a count parameter
- E6 `models.py` + one-time DDL: composite indexes on ai_messages(session_id,seq) / ai_actions(session_id,executed_at) — rate-limit counting and message sequencing are hot queries on every AI tool command, previously full-table SCAN + temporary B-TREE; create_all only adds indexes to newly created tables, so for existing tables an explicit CREATE INDEX IF NOT EXISTS ran in a downtime window; _next_seq now uses a COVERING INDEX and recent_exec_rows an INDEX SEARCH

Deployment: 6 files, trickle+md5+AST+import probes all green, two restarts (code wave + index-building stop/start); live verification PASS (not logged in 303 → logged in all pages 200 / stats fragment / ping two-phase 2/2 Up / export-zip 200 with all 12 .cfg files intact in the zip / no leftover cfgbak_* in /tmp).

### Project-wide /code-review fixes W3: duplicate-code consolidation, 17 items (groups R/S/T) — 2026-08-24

**Group R (duplicate definitions single-sourced)**

- R1 `custom_cmds.py`: the PLATFORM_TYPES platform catalog (14 entries) single-point definition + platform_types() as the unified reader; hand-copied catalogs everywhere consolidated
- R2 `routers/ai_assistant.py`: 14 hand-copied `_api_404` blocks → shared helper
- R3 `routers/config_compare.py`: CONFIG_DIR now references the engine's `inspection.CONFIG_DIR` (module-level sys.path injection); the hand-copied path constant is gone
- R4 `routers/devices.py` + `templates/devices.html`: the device page's platform dropdown is now rendered from injected PLATFORM_TYPES (previously 14 entries hardcoded in the template, and when the custom commands page gained a platform this dropdown was missed)
- R5 `routers/reports.py`: new `_load_run` — consolidates 4 duplicated run+raw_data loads, with consistent 404 semantics as a side effect
- R6 `main.py`: new `_dashboard_core` — single source for the statistics in both dashboard and /api/stats

**Group S (engine parsing single-sourced)**

- S1 `inspection.py`: new `_find_output(sections, cats, min_len, match, require_kw)` — single point for the six scanning loops over cpu/mem×2/power×2/raid/disk/nic; previously six inline hand-copies whose ERROR guards had drifted (the raid/disk/mem second pass did not block, so long error strings with len>100 were fed into the parser as disk/RAID inventories, producing hallucinated data)
- S2 `inspection.py`: PSU_OK_WORDS (added healthy) + `_psu_status_fallback` + `_dimm_summary` — the PSU good-words list and DIMM summary previously existed as two drifted hand-copies across parse_server_* and parse_idrac_* (hp_ilo/lenovo "Healthy" power supplies were once counted as faults)
- S3 `routers/reports.py` export_html: section output normalized by `_coerce_section_output` + a truncation marker beyond 300 lines (previously overlong output was stuffed wholesale into a single cell)
- S5 `routers/vram_calc.py` + `_vram_result.html`: BASE_OVERHEAD/SCENARIO_MULTIPLIERS single-sourced; the comparison table calls calc_vram directly per tier, and the formula row references them via context (previously three separate copies — any parameter tuning silently forked)
- S6 `routers/vram_calc.py`: calc_vram's lazy parameter (the multi_gpu branch was always true) removed; the multiplier is now returned as a field

**Group T (cross-module private-reference consolidation)**

- T1 new `backend/inspection_runs.py` (~380 lines): the _progress registry/_inspect_one worker (formerly routers/inspect.py) and _init_progress/_light_device_rows/_run_batch (formerly routers/scheduler.py) all relocated — the bidirectional coupling where two router modules reached into each other's private names via function-level deferred imports is eliminated, with a single reference direction (routers+main → inspection_runs)
- T3 `constants.py` PENDING_STATUS + `templating.py` Jinja global + `base.html` reference — the "Waiting" magic string single-sourced (constants is a leaf module, no import cycle introduced)
- T4 `routers/ca_server.py` PRIVATE_KEY_DOWNLOAD_SUFFIXES + `main.py` _readonly_blocked now anchored with endswith — the read-only blacklist suffixes and the route definitions share one source; renaming a route no longer silently misses the block
- T5 `routers/auth.py` _ensure_full_user — single point for the read-only rejection check shared by the twin routes require_full_user and change-password
- T6 `inspection.py` CMD_SYNTAX_ERRORS (9 kinds) single-sourced — shared by the engine's two alert/fallback sites and ai_engine's correction hint (lazy import); previously four separate drifted copies (the AI side only recognized 2 kinds, so "% Ambiguous"-style rejections got no correction hint and kept guessing blindly)
- T2 (403 detail constants) verified as already landed in W1, no change needed

Deployment: 21 files (18 py + 3 html), trickle+md5+AST + `import backend.main` circular-import probe + engine function probes all green, one restart; live verification all PASS (login/dashboard waiting icon rendering / devices platform dropdown 14 entries / config-compare / vram POST formula row ×1.2×4 / inspect 404 / read-only pem 403 · crt 200 / seven pages 200).

### Project-wide /code-review fixes W2: 8 secondary-correctness items — 2026-08-24

- B6 `database.py`: PRAGMA busy_timeout 5000→30000, aligned with connect_args' timeout:30 (previously the PRAGMA executed later silently overrode "wait 30s for the lock" with 5s, making concurrent writes throw locked early); the four user-management write points in auth.py (password change / user creation / reset / deletion) swapped bare commits for the shared commit_with_locked_retry replay closure — failures now show a friendly message instead of 500
- C4 `custom_cmds.py`: execute / execute-batch single-device persistence now uses commit=False + the retry closure (same strategy as execute_multi), with a persist_error page-message fallback on failure (reusing an existing template slot); the render-list query switched to the query_or_empty fallback; the uncalled _save_inspection_run wrapper deleted
- C5 `config_push.py /preview`: device_ids now a fault-tolerant list[str] parse (when the empty selection field is missing entirely, list[int]=Form(...) throws a bare 422 and never reaches the "please select at least one device" message) — live verified 200 friendly page
- A1 `inspect.py`: new _bump_done — the done increment and the identity guard in the same critical section; lost updates from concurrent workers' read-modify-write could leave done forever trailing total (frontend polling stuck); both call sites migrated
- A2 `engine/topology.py`: parse_cdp's Port ID line re.match→re.search; on IOS merged lines like "Interface: Gi0/1,  Port ID (outgoing port): Gi0/24", remote_port previously never matched due to line-start anchoring
- A5 `engine/topology.py`: new _summary_neighbors header-driven summary parser (columns split on 2+ spaces, values taken by column name) — NX-OS CDP summary headers previously produced garbage as neighbors in the detail parser; XR/Arista/Ruijie/Juniper LLDP summaries were previously dropped wholesale or fell into the Huawei position fallback, treating hostnames as local_port; detail and Huawei brief paths regress-free (probe 7/7 passed)
- A6 `scheduler.py`: the "today" for an empty once date is now taken in CST — with the server on UTC, naive now() gives yesterday during CST 0:00-8:00, so a user meaning today was judged past (+1 day shift or even PastDateError)
- A4 `inspection.py parse_idrac_power`: InstanceID block-type gating (in_psu_block) — the System.Embedded.1 block's Model=PowerEdge R740 / Power Capacity previously leaked into psus as ghost power supplies ("PowerEdge" contains "power", so even keyword filtering could not block it); the getsensorinfo path without InstanceID keeps its original behavior

Deployment: 8 files trickle+md5+AST, one restart; all 22 write-free verification items PASS (8 structural + 11 function probes + 3 live), zero Tracebacks in the journal.

### Project-wide /code-review fixes W1: 10 correctness items — 2026-08-24

8 angles, 41 candidates → 31 CONFIRMED / 9 PLAUSIBLE, fixed in 4 waves; this wave is the 10 correctness items:

- C1 `alerts.py /alerts/add`: device_id now a fault-tolerant str parse (empty string/non-numeric → None = global rule), fixing the 422 on submitting the "All devices" checkbox empty and global alert rules being unreachable from the UI (verified: three POST variants 303 into the DB; test rows deleted right after creation, counts restored)
- C2 `custom_cmds.py execute_multi`: as_completed replaced with the same wait+deadline polling as config_push (concurrency min(10, device count)); hung threads no longer block the request forever; over-budget results are marked "result unknown, please verify manually"
- B2 `main.py` singleton lock: O_CREAT|O_NOFOLLOW (win32 exempt) replaces the bare open("w"); /tmp symlink hijacking can no longer truncate/forge the lock (probe: ELOOP rejected and the target file untouched)
- B3 `main.py` unauthenticated redirect: quote(request.url.path) encodes CJK paths, fixing the latin-1 response-header 500 (live: /network-network → 303, next parameter percent-encoded)
- A3 `inspection.py parse_server_mem`: explicitly capture MB|GB units; 512 MB no longer inflates as GB (probe: 512MB+256GB+no-unit 512 = 768GB, old code 1280GB)
- E2 `inspection.py` command loop: after a prompt exception, set a sticky prompt_bad flag; subsequent commands go straight to send_command_timing instead of retrying double timeouts one by one
- B4 `ca_engine.py get_pem_zip`: the CN sanitized into a safe file name (illegal characters→_, leading/trailing ./_ stripped), blocking zip-slip path traversal (probe: ../../tmp/evil → tmp_evil.crt/key)
- C3 `config_backup.py backup_now`: finally-block fallback conn.disconnect(); SSH connections no longer leak when the peer does not echo
- B5 `ca_server.py create_root/issue_cert`: rollback on exception + unlink cleanup of already-written keys/certificates + template error-banner feedback (probe: invalid request 200+error banner; no more 500 or orphan keys)
- S4 `topology.py` alert linkage: added the silence_until silencing check and operator mapping (previously silenced rules were still flagged red)

Deployment: 10 files trickle+md5+AST verified, one restart; zero Tracebacks/ERRORs in the journal/app logs.



### Low-priority cleanup wave: duplicate-code consolidation + dead-code sweep (13 items) — 2026-08-24

Low-priority cleanup items accumulated over multiple review rounds consolidated in one pass, with zero behavior change as the principle (two semantic alignments noted):

1. **"Password decryption failed (key mismatch)" hand-copied in 7 places → `crypto.DECRYPT_FAIL_MSG` constant** — the raiser (ai_session.DeviceSessionPool) and the failure results and translation tables of config_backup / config_push / custom_cmds / inspect / ai_assistant all reference the single definition, eliminating the risk of the UI prompt, audit storage, and translation table each drifting on their own.
2. **AI rate-limit counting's duplicated filter conditions → `ai_engine.recent_exec_rows`** — `_rate_wait` (show path) and the `confirm_action` re-check share the same query criteria (executed_at window + the three states executed/confirmed/failed); previously two hand-copied filter conditions — changing one but not the other would split the two rate limiters' criteria.
3. **DOCX/PDF export's duplicated conversion/truncation blocks → `reports._coerce_section_output` / `_trunc_marker`** — the two hand-copies of H7's type coercion and H4's truncation marker consolidated into shared helpers.
4. **mtr subprocess invocation duplicated → `ping._run_mtr`** — command-line assembly for do_trace and ping_post, the ~1s+20s per-cycle timeout, and the stdout+stderr merge criteria single-sourced.
5. **Manual-inspection executor's duplicate copy deleted, merged into `scheduler._run_batch`** — the entire hand-copied `_run_inspection_sync` (thread pool + _inspect_one + 300s per device + retirement cleanup) deleted; trigger_inspection now uses `_light_device_rows` light rows (id/ip, no longer materializing full ORM rows with the encrypted-password column) and reuses _run_batch; the two thread-pool caps (scheduled 100 / manual MAX_WORKERS) unified to inspect.MAX_WORKERS (2*cpu capped at 50); start/end logging unified in _run_batch (the manual/scheduled/run-now trigger paths leave consistent ops traces).
6. **run_now's double write of last_run → single write point** — the request thread's pre-write (bare commit + whole-block fallback) deleted; the worker thread writes back uniformly after finishing, same semantics as the scheduled path (last_run records the completion time), which also eliminates two threads concurrently writing the same field.
7. **`_classify_403`'s string-equality coupling → `auth.ADMIN_REQUIRED_DETAIL` / `READONLY_DETAIL` constants** — the raise points (require_admin / require_full_user / the twin change-password routes) and main's classification comparison share them; changing detail wording no longer mis-renders the browser-friendly 403 page's category or mislabels T1 monitoring markers.
8. **StaticCache / Lang, two simple middlewares, converted to pure ASGI** — they wrap send/receive directly instead of going through BaseHTTPMiddleware's per-request anyio task + memory streams (each saves a layer of task overhead); LoginMiddleware (heavily dependent on call_next) left untouched.
9. **`backup_host_prefix`'s double definition consolidated into the engine** — the definition point moved into the repo-root inspection.py (the engine is lower-level and must not import backend in reverse); backend/helpers forwards via lazy import; the previous sync obligation of "byte-identical hand-copied duplicates" is gone.
10. **topology showNode's local `badge` string shadowing the global `badge(n)` icon function** — renamed to statusBadge; the latent trap where a future badge(...) call inside the popup would invoke a string and throw TypeError is removed.
11. **pyflakes full-tree sweep of 16 dead-code spots** — dead imports: auth.SessionLocal, bom.json, config_compare.HTMLResponse, config_push.RedirectResponse, custom_cmds.OperationalError, inspect.datetime+SessionLocal+ThreadPoolExecutor, reports.Query/Inches/Emu/TA_LEFT/TA_RIGHT/KeepTogether, scheduler._json+HTTPException, engine/topology.json; dead variables: custom_cmds.start_time, reports.r4/mem_color and the PDF-side GRAY100+GREEN+RED, vram_calc.multiplier+vram, and the unused except bindings in main and inspection. main._logger_setup (side-effecting import, noted) intentionally kept.
12. (Intentionally unchanged) ai_engine._exec_show's wait loop of 1Hz sliced sleep + db.refresh — the comment explicitly documents it as designed to "preserve deletion responsiveness while waiting"; not waste.

**Verification (38 assertions all green)**: 17 structural assertions (each single-point definition / constant-reference file lists / middleware inheritance relationships / duplicate-copy deletion confirmed) + 21 pages 200 with zero BOM + `/static` response `Cache-Control: no-cache` (pure ASGI in effect) + en-mode title switching (LangMiddleware pure-ASGI in effect) + real mtr run 200 with hops table (_run_mtr single point) + config-backup 200 (helpers→engine sanitize forwarding works) + read-only token three pages zero write buttons + **single real-device inspection (vpn 172.16.1.1) through the merged _run_batch full chain connected** (InspectionRun persisted connected|39%|55.8%, unified start/end logs start=1/done=1) + journal zero Tracebacks + app logs zero ERROR + Playwright 8 change-related pages zero pageerror.

### Full-repo review triaged fixes (7 items, excluding false positives and intentional designs) — 2026-08-23

Findings from multiple rounds of full-repo code review were verified one by one on this machine and handled in three categories: **false positives** (the `_parse_mtr` regex actually has 9 groups/9 names/7 columns, correct; `_exec_show`'s device deletion during the wait is naturally blocked by the ORM's expire_on_commit; the esc race was already fixed by d70e16b), **intentional designs** (qc_webhook http egress policy, removal of the p12 password default, /reports/api dropping raw_data, the daily 6 a.m. fallback condition, etc. — all documented), **confirmed fixes** (this entry):

1. **config_push timeout path CancelledError 500** — after the global timeout, tasks cancelled by `cancel_futures` also have `done()` true, entering `_harvest` first so `f.result()` throws `CancelledError` (a BaseException, escaping `except Exception`) → the whole execute 500s, already-collected results discarded, remaining devices un-audited; the "not executed (safe to retry)" branch was dead code. `cancelled()` is now checked before `done()`.
2. **ping IPv6 CIDR → 500** — `ip_network` accepts IPv6; the expanded v6 string, outside the per-part try, was thrown as a ValueError by the `IPv4Address` sort key. The sort key is now fault-tolerant (v4 → v6 → string, three levels).
3. **UTF-8 BOM stripped from 11 templates** — adhoc/alerts/cases/case_categories/ca_server/config_compare/ping/scheduler/vram_calc/_ca_certs/_ca_roots each had an extra EF BB BF in rendered response headers, and htmx fragment swaps injected zero-width characters into the DOM. After byte-level stripping the whole directory is BOM-free.
4. **Three-page button gating** (same kind as H1) — devices' add/edit/delete, custom-commands' all write forms, ca-server's issue/revoke/delete/PEM/P12: the corresponding endpoints had already been raised to require_admin/require_full_user, but the buttons still rendered for non-admins (click → 403 with form input lost). Routes now pass `user` (including 7 htmx fragment re-render points, so buttons don't disappear after admin actions), templates gate on `user.is_admin`; CRT/root-certificate downloads remain visible as require_auth.
5. **subnet split-mode echo** — the POST render context lacked `split_mode`/`new_prefix`; after splitting by count the dropdown sprang back to "by prefix" and the input cleared, so the next submit would split by prefix without the user noticing. The context now includes both fields.
6. **reports.html local triggerInspect dead code deleted** — the shared version in base.html's chrome block (more complete) always overrode the local copy, and the local version's error extraction with only the single key `detail` had drifted.
7. **export_csv gained `defer(raw_data)`** — previously 500 rows fully materialized (each row's raw inspection JSON can reach hundreds of KB) just to write an 8-column CSV; now aligned with list_runs/reports_page in the same file.

**Verification**: page responses byte-level zero BOM (8 pages) + admin/read-only-token dual-view gating (devices/custom-commands/ca-server, 6 assertions total) + subnet count-mode echo and input retention + POST /ping `2001:db8::/126` 200 (no longer 500) + export_csv headers + config_push cancelled/elif-done structural assertions + journal zero Tracebacks + 21-page smoke all 200.

### Moved shared JS helpers in base.html into head (esc race condition — a real bug found by the all-module health check) — 2026-08-22

The four shared pure functions `esc`/`apiErrorText`/`alertOnErr`/`toggleAll` were previously defined in the body-end `{% block chrome %}` (rendered **after** `{% block content %}`), while some pages' content scripts fire fetches during HTML parsing (config_backup's `loadBackups()`, the ai page's `loadDevices()`/`loadSessions()`, etc.), whose async continuations — on warm connections — execute before the chrome-block script — `esc` not yet defined → `ReferenceError: esc is not defined` (unhandled rejection) → the backup table/session list **silently fails to render**, leaving users to rely on manual filtering or refresh luck.

Production reproduction (Playwright, 8 loads per page): /config-backup hit **8/8**, /ai racked up **309** pageerrors over 8 loads (session polling failed every tick); /adhoc's same-class risk did not trigger at the time. It hadn't surfaced before because, on cold connections, the chrome script happened to finish parsing first — pure timing luck.

**Fix**: the four functions moved up into `<head>` (next to `t()`; head scripts already guarantee the earlier position of "chrome-block scripts run before the body end"), and the chrome block keeps only DOM-related scripts such as the inspection panel/polling. A single-file change; each function still has exactly one definition.

**Verification**: after the fix, /config-backup, /adhoc, and /ai each loaded 8 times with **0 pageerror**; 21-page smoke all 200; the full health check (service/journal/app logs/disk/SQLite quick_check/business data/APScheduler/21 pages/JSON API/read-only token/browser zero pageerror) all green except for this commit's pre-existing uncommitted worktree items.

### Inspection report module review fixes (H1-H7) — 2026-08-22

1. **H1 delete-endpoint permission hardening + button gating** — `DELETE /reports/api/{id}` and `batch-delete` raised from `require_auth` to `require_full_user` (read-only-token write requests were already blocked by LoginMiddleware; this is defense-in-depth consistent with the F-wave precedent, zero behavior change); the list page's delete/batch-delete buttons were previously visible to read-only visitors (403 only on click), now gated on `user.id` and not rendered; `updateSelection` gained a corresponding null guard.
2. **H2 detail-page memory grading unified with the exporters (display bug)** — report.html previously hand-classified with `|float` ("N/A" became 0.0 → wrongly shown as green ok), the 4th hand-rolled check to slip past `_mem_color`'s docstring promise of "no more individual hand-checks". The route now computes `mem_class` with the shared `_mem_color` and passes it in, same semantics as the three HTML/DOCX/PDF exporters (N/A → gray info).
3. **H3 nonexistent runs uniformly 404** — `report_detail` previously rendered an empty base.html skeleton with status 200, inconsistent with the export endpoints' `raise 404`.
4. **H4 DOCX/PDF truncation marker** — outputs truncated beyond 300 lines previously had no marker at all (same kind as configuration comparison P1); now a "… (truncated, N lines remaining)" marker line is appended (following the request language).
5. **H5 list-page device dropdown narrow columns** — full-column `query(Device)` (including the encrypted-password column) changed to narrow id/ip/hostname columns.
6. **H6 minor cleanup** — the single-delete `hx-confirm`'s hardcoded English is now set with `t()` by language at page load; deleted the triple comment-header iteration leftovers of the PDF export.
7. **H7 push-audit run export 500 (newly found during verification, real bug)** — the Config Push section's `Success` is a bool; DOCX/PDF exports called `.split`/`.splitlines` on it, an immediate AttributeError 500 — Word/PDF exports of every push-audit run had always crashed (the HTML export already had `str()` and was unaffected). Non-string values are now converted to text first (bool/int → str, dict/list → JSON string).

**Verification**: structural probes + HTTP (admin list-page buttons present / nonexistent run 404 / N/A-memory run #138 detail-page info card / run #138 DOCX contains the truncation marker and PDF 200 = H4+H7 tested together / run 130 detail and all three exports regression) + read-only-token view (page 200 with zero delete buttons, DELETE middleware 403) + Playwright (hx-confirm zh/en switching, zero pageerror) + 21-page smoke all 200.

### Configuration push module review fixes (G1-G6) — 2026-08-22

1. **G1 textarea placeholder i18n misuse (real bug)** — the command input previously used the `data-zh`/`data-en` attribute pair; base.html's applyI18n writes textContent for that pair, and a textarea's textContent is its actual content: after switching language the description/example text would become the input's real content, and if the user previewed without clearing, that text would be pushed to the device as real commands. Switched to the placeholder-specific pair `data-zh-ph`/`data-en-ph` (a mechanism added to base.html in the configuration-comparison wave; the second user).
2. **G2 recovery-config capture takes the command per platform** — the pre-push recovery reference previously hardcoded `show running-config`; non-Cisco platforms (Huawei etc.) silently captured nothing = no recovery reference when things go wrong. Now taken from `DEVICE_PROFILES[device_type].backup_cmd` (same as config_backup), falling back to the original value without a profile.
3. **G3 bilingual error messages** — 9 English error strings in `_render_input` now go through `T()`.
4. **G4 import consolidation** — netmiko exception imports moved to the top; deleted the duplicate `import logging`/`getLogger` inside execute.
5. **G5 display-query narrow columns** — 4 full-column `query(Device)` spots (including the encrypted-password column) on the input/preview/result pages changed to `_display_devices` narrow columns; execute keeps full columns (password decryption + ORM persistence need them).
6. **G6 file/text toggle leftover** — after choosing a file and switching back to "paste commands", the leftover file was still submitted with the form and the server preferred it (the user thought they were pushing text but the old file was pushed). `toggleInputMode` now clears the file input when switching back to text.

**Verification**: structural probes + bilingual HTTP (zh/en error branches) + Playwright (zh/en placeholders with textarea content always empty = proof of G1's fix; file cleared after choosing a file and switching modes = G6) + real-device push round-trip (device 1 pushed `interface Loopback100 + description G2Verify` successfully, audit raw_data contains non-empty RecoveryConfig = proof G2 works, followed by a successful `no interface Loopback100` rollback) + 21-page smoke all 200.

### Configuration backup module review fixes (F1-F6) — 2026-08-22

1. **F1 manual backup now uses the shared write** — `backup_now`'s force path was previously a third write implementation: no chmod (credential-bearing config files world-readable at umask 644) + bare-unlink rotation (a failure deleting the old file would falsely report "backup failed" after a successful write). It now shares `inspection.write_config_backup` with inspection backups (naming/disk-write/chmod 600/fault-tolerant rotation single point); the whole platform has only this one write semantics left.
2. **F2 import consolidation** — netmiko exception imports moved to the module top; deleted the duplicate `import inspection` inside `backup_now` (the module top already has `_insp`).
3. **F3 filter debounce + sequence guard** — the filter input previously fired a full list request per keystroke, now debounced 300ms; during fast typing, in-flight responses arriving out of order would show stale filter results — a sequence guard now accepts only the last response.
4. **F4 device-list fetch fault tolerance** — `/devices/api` failures were previously silent (the export feature quietly unavailable); now it shows "Failed to load the device list; export may be unavailable" (bilingual).
5. **F5 dead code** — deleted the uncalled `onDeviceSelect` and its onchange attribute.
6. **F6 double-click protection** — the backup-now button is disabled while a request is in flight (restored in try/finally); double clicks no longer concurrently trigger backups of the same device (same-second file names would overwrite each other).

**Verification**: server function probes (tmp-directory `write_config_backup` write+chmod 600 / rotation 13→10 keeping the newest / `backup_config` dedup regression) + HTTP (page template anchors / list API) + real-device backup-now on device 1 (32KB new file, stat 600, visible in the list) + Playwright en-mode button/placeholder textContent, zero pageerror + 21-page smoke all 200.

### Configuration comparison module review fixes (P1-P6) — 2026-08-22

1. **P1 silent-truncation warning** — previously each side's config was truncated to 2MB/5000 lines with no hint at all: when both sides truncate at the same point and the differences lie beyond the truncation point, it would falsely report +0/-0 "no differences". Now when truncation occurs the result area shows a warning banner ("Configuration A is too large; only the first 5000 lines compared", bilingual); the comparison logic itself is unchanged.
2. **P2 page bilingual completion** — error messages now go through `T()`; the template's `-- Load from device --` / `or upload:` / `context:` / `comparison result` / `side-by-side` / line-count units gained data-zh/data-en; placeholders made bilingual via the `data-zh-ph`/`data-en-ph` attribute pair newly added to base.html (same mechanism as the existing title/aria pairs; config_compare is the first user).
3. **P3 device dropdown narrow columns** — the GET/POST `query(Device)` full-column materialization (including the encrypted-password column) changed to fetch only id/ip/hostname/device_type, same treatment as the config_backup page.
4. **P4 `_page_ctx(db)` helper** — the GET/POST verbatim-duplicated "devices + backup list" page context consolidated to a single point.
5. **P5 `context_lines` clamp** — the dropdown only offers 0/1/3/5/8/999, but a crafted POST could send negative/huge values; now clamped to [0, 999].
6. **P6 `import json` moved to the top** — deleted the import inside load_device_config.

**Verification**: 16 live HTTP items (basic comparison counts / no banner without truncation / 6000-line truncation banner / negative and huge values clamped without crashing / error in Chinese / load-config regression / Playwright zh+en dual-mode dropdown placeholders and placeholder textContent / zero pageerror) + 21-page smoke all 200 after the base.html shared change.

### Inspection module review fixes (A1: custom commands reuse the inspection SSH connection) — 2026-08-22

**Motivation**: previously, after the main inspection flow connected → collected → disconnected, `run_commands_on_device` opened a **second SSH connection** to the same device to run custom commands — every device with custom commands enabled paid the connection+authentication cost twice per inspection round (~2-5s/device).

**Changes** (3 files):
1. `inspection.py` — `inspect_device` gained an optional pure-data `extra_commands=[(label, command)]` parameter (the engine stays DB-agnostic); custom commands run over the same connection after the main command loop; per-command fault-tolerance semantics identical to the old path (`send_command_timing` read_timeout=30 delay_factor=2, failures `[Error]`), and the section is appended after all profile categories (report display position unchanged).
2. `engine/inspector.py` — `run_single_device` passes the parameter through.
3. `routers/inspect.py` — `_inspect_one` now normalizes via `custom_cmds._cmd_pairs` (the label rules still have exactly one definition point) and passes it in; the second SSH leg and the second serialization are deleted (raw_data is serialized uniformly by the engine); the "storage keys are not translated" policy comment moved into the engine side along with the section keys.

**Verification**:
- 11 mock-connection probes (zero writes): exactly one connection throughout / custom commands execute in order on the same connection / output and `[Error]` semantics / section in last position / engine raw_data contains the section / compatibility when the parameter is absent.
- 11 real-device A/B items: device 1 (172.16.1.1) new-path run 128 vs old-path baseline run 124 — identical custom-command key sets, the 3 command outputs equivalent one by one (same success/error classification), identical profile section sets, main-section content of the same kind.
- 21-page smoke all 200. (One RemoteDisconnected during polling was a transient break; the service did not crash and the run completed normally.)

### Inspection module review fixes (A2/A3/C2) — 2026-08-22

1. **A2 `parse_idrac_nic` dead loop deleted** — the function had two passes: the first pass's state machine (~30 lines) results were explicitly discarded by `nic_models.clear()` and the second pass re-ran. First pass deleted, zero behavior change (synthetic hwinventory probes: NIC aggregate count / SSD not miscounted / FC HBA counted once per card / empty input N/A — four cases).
2. **A3 `backup_config` size fast path** — compare file sizes before the dedup decision: different sizes necessarily changed, skipping the full-file read + SHA256; same size still goes through hash confirmation (same size ≠ same content). Windows CLI writes convert `\n→\r\n`, making sizes incomparable — the gate falls back to the old path. 5 tmp-directory probe cases: first write / identical dedup / same size different content judged changed / different size judged changed / dedup again after a change.
3. **C2 `version_output` selection rewritten** — the original "pre-read DESC_VERSION + double loop" logic rewritten as a `_first_long` + `or` chain, making the three-branch semantics explicit (basic-info long output → DESC_VERSION short-value fallback → processor category). An 8-case matrix probe verified the old and new algorithms equivalent branch by branch (including trap cases like a short value taking precedence over the processor and the 20-character boundary).

**Verification**: 14 server function probes all passed + 21-page smoke all 200. (Found during probing: backup_config's same-second same-name overwrite is pre-existing behavior, unrelated to this change, left alone.)

### Inspection module review fixes (B1/B2/B3) — 2026-08-22

1. **B1 backup retention policy unified** — the inspection engine (`inspection.py`) kept 5 versions, manual backup (`config_backup.py`) kept 10; the two writers truncated each other in the same `configs/` directory. Added the `inspection.BACKUP_KEEP = 10` constant; the manual backup path shares it via `_insp.BACKUP_KEEP`, and both paths now have one policy (unified at the user-chosen 10; under dedup, unchanged configs don't consume a version).
2. **B2 `_validate_routing_output` dead parameter deleted** — the `device_type` parameter had never been referenced by the function body since its definition; both call sites slimmed in sync; routing-output validation behavior unchanged (empirically probed with three cases: valid output / log garbage / error echo).
3. **B3 `parse_idrac_power` output determinism** — `", ".join(set(statuses))`'s unstable set iteration order made the power string order differ between adjacent runs for the same device (report display jitter); changed to `sorted(set(...))`; also deleted the `total_watts` dead variable, accumulated but never used.

**Verification**: 12 server function probes (BACKUP_KEEP constant shared by both paths / single-parameter signature / routing validation three cases behavior unchanged / power parsing same input twice same output + multi-status ordered join `[Ok, Warning]`) + 21-page smoke all 200 + config_backup list API normal.

### Post-cap review cleanup (5 items landed + 1 skipped with evidence) — 2026-08-22

**Zero-impact cleanup, each item with evidence**:

1. **topology.html local `esc` copy deleted** — same character set as the base.html canonical; engine/topology.py guarantees node id/label/ip/devicetype/status are all non-empty (the `String(s||'')` vs `String(s)` difference is unreachable); esc calls are all inside fetch callbacks/events, by which time the chrome-block script is defined. Triple evidence of zero impact, removing the parallel copy that could shadow future global hardening.
2. **`alertOnErr` moved into base.html as shared** — alerts.html's two verbatim-identical `resp.ok` guards consolidated into `if(await alertOnErr(r))return;`. (The review finder's claim of 5 copies was outdated: the config_backup/adhoc variants go through different display channels — showStatus bilingual prefix / prefixed alert — not verbatim duplicates, kept.)
3. **bom_matcher.py `import time` moved to the top** — deleted 2 in-function `import time as _t`; a module-level identity probe verified `bm.time is time`.
4. **scheduler once trigger rewritten to a single comparison point** — `dt < now - 1 day → PastDateError`; `dt < now → +1 day`. Equivalent case by case to the old double guard (example-table probe, 4 cases: future unchanged / today-but-past shifts to tomorrow / yesterday within 24h shifts without throwing / the day before yesterday throws PastDateError).
5. **config_backup BMC comment relocated** — moved from above the decrypt block to directly above `netmiko_connect(...)` (the comment describes the driver mapping, unrelated to decryption).
6. **Pool deleted-check centralization — skipped after verification** — the pool layer is DB-agnostic by design, and the two call sites need different responses (410 JSON vs LLM prompt text); centralizing would introduce a layering inversion, not zero impact; recorded honestly as not done.

**Verification**: server function probes 7/7 (once example table 4 cases + bom module-level time + cache write-read-clear); Playwright 11/11 (21-page smoke 200, topology vis canvas rendering + node-popup esc render path + popup free of undefined/null text, alerts page `typeof alertOnErr === 'function'`, zero pageerror throughout).

- 2026-08-22: **Review deep fixes (review_diff_head2, 6 items, restart required)** — after /code-review (8 finders × 29 candidates, verified item by item against HEAD: 4 already fixed by 77c8721 / 3 disproven / 10 reported), fixed the 6 still current: (1) confirm_action's S7 deleted-session 410 branch didn't roll back — after the atomic claim committed confirmed, db.refresh sees deleted and returns 410, leaving the card permanently stuck at confirmed (audited as confirmed though never executed, and every later confirm gets 400 already-processed); fix: roll back to the rejected terminal state + audit trail "session deleted, dispatch cancelled" + confirmed_by/executed_at cleared (a card whose session is deleted can never execute; rejected is an honest terminal state instead of a pending zombie). (2) config_compare load_device_config's read_text ran unguarded — mtime_safe only fixed the sort-key race; concurrent rotation/batch-delete unlink between glob and read still let FileNotFoundError go straight to 500; fix: OSError caught, falling back to the inspection run config when no backup exists. (3) delete_run's empty 200 broke the public API contract documented in the README — external scripts' resp.json() on an empty body throws JSONDecodeError and reports success as failure; fix: branch on the HX-Request header (htmx keeps the empty 200 outerHTML-swap contract, non-htmx returns {"ok": true}). (4) the change-password POST relied only on the middleware's path-name blacklist (GET had long had an explicit guard) — renaming the route would silently expose the real change-password endpoint; fix: POST gained the same READONLY_VIEWER 403 guard. (5) _PAST_DATE_MSG's string-equality classification — the raise point and the classifier were coupled by message text; any wording drift meant misclassification; fix: typed PastDateError(ValueError), except on the subclass first, the registration path's except ValueError compatibility unchanged. (6) the form_int mechanism was trapped in scheduler.py — promoted into helpers as a single point (docstring notes the clamping semantics don't apply to the port field, which must error on out-of-range values), scheduler's two call sites and comments switched; devices' port normalization consolidated into a single port_s (keeping out-of-range erroring rather than clamping). Verification: 11 server function probes (dangling symlink reproduces the read_text race without throwing + real-backup positive control / read-only identity directly calling the change-password POST 403 / expired once zh/en passthrough without prefix + real format errors still prefixed + PastDateError subclass compatibility / form_int behavior + scheduler single point); 14 HTTP items (delete_run dual contract / expired once 303 flash without persisting / interval=abc 303 not 422 / 21-page all-module smoke / 6 read-only items); 5 function-level reproductions of the S7 race window (410 + rejected + trail + cleared; note: HTTP delete-then-confirm hitting the existing 404 early guard is correct behavior; the S7 window can only be reproduced at function level); Playwright 8 pages zero pageerror.

- 2026-08-21: **AI assistant: fallback-protocol text persistence fix + rate-limit wait made visible to the frontend (restart required)** — the re-review closed two more items: (1) the assistant explanation text of the fallback protocol (models without function-calling use ```run blocks) was previously only appended in memory and never persisted (the configs branch had long persisted; the shows branch was missed) — refreshing the page made the model's words disappear, and the history rebuilt from the DB next round also lacked that segment, so the model couldn't see what it had previously said; fix: the shows branch now saves the assistant text with _save_msg before executing commands. (2) rate-limit wait visible to the frontend — after the previous wave's server-side wait-retry shipped, hitting the 6-per-minute rate limit left the user in silence for up to ~60s, looking frozen; fix: on entering the wait, _exec_show emits a tool_wait event (emit-only, not persisted, bilingual, with countdown seconds), and the frontend's handleSseEvent gained a branch reusing the thinking hint bar to show "command rate limit (6/minute), auto-executing in about N seconds". Verification: 6 production probes — after one round of the fallback run block, the assistant text + tool result both persisted; after seeding 6 actions to fill the window, the first event is tool_wait (message "auto-executing in about 11 seconds"), waited 10.1s and executed transparently and successfully; probe data cleaned itself up.

- 2026-08-21: **AI assistant three optimizations: partial summary on round exhaustion / vendor command quick reference / syntax-error correction hints (restart required)** — following the rate-limit wait fix, treatment of session 57's remaining two root causes and tail failures: (1) round exhaustion no longer errors out bare — after all 8 rounds are used, a "round limit reached" instruction is appended automatically and tools disabled for one more LLM call, letting the model write a partial summary from the collected command outputs (required to self-label as incomplete), pushed via the typewriter and persisted as an assistant message, with the stream ending normally via done; only if the summary call itself fails does it fall back to the original "tool-call round limit exceeded" error. (2) the system prompt (zh/en dual templates, equivalent item by item) gained retry discipline (don't immediately retry a command that errored or was rejected; explore with display ? / show ? first) and a per-platform common-command quick reference (cisco_ios / huawei VRP / huawei USG firewall including display security-policy rule all — the correct syntax session 57 guessed wrong twice). (3) _exec_show detects Unrecognized command / % Invalid input output and appends a fixed Chinese correction hint at the end of the returned text (persisted with the tool result; the audit AIAction.output still stores only the raw device output), an engine-level backstop not relying on prompt discipline. Incidentals: the typewriter push extracted into a _stream_text helper, deduplicated. Verification: 11 production probes — both templates render with the quick reference; Unrecognized output carries the hint / normal output doesn't; after simulating 8 tool rounds, the 9th LLM call has use_tools=False, summary pushed + persisted, no error event; probe data cleaned itself up.

- 2026-08-21: **AI assistant rate limiting no longer burns tool rounds (restart required)** — user reported "tool-call round limit exceeded, stopped"; forensics on session 57: after the model guessed 2 command syntaxes wrong for the USG firewall (ICI-FW, huawei) and explored 4, it hit the 6-per-minute rate limit, and after the "[rejected] command rate limit exceeded" text was returned, the model immediately retried the same command 4 times — each rejection burned a round for nothing, exhausting the 8-round MAX_TOOL_ROUNDS and stopping empty-handed, while after the rate-limit window passed the same command (display security-policy rule all) actually succeeded and retrieved 8 security policies. Fix: _rate_ok→_rate_wait (returns the seconds until the window opens; counting policy unchanged, still executed_at and the confirm re-check on the same criteria); when rate-limited, _exec_show sleeps in slices server-side waiting for the window to open, then executes transparently — rejections are no longer returned to the model and don't consume tool rounds; during the wait it refreshes the DB every second to keep deletion responsiveness, with a 75s bottom-line fallback returning the original rejection text to prevent pathological spinning. Verification: production probe (seeded 6 AIActions to fill the window, oldest 50s ago) — the 7th waited 10.2s for the window to open then executed transparently and successfully, the placeholder audit row persisted normally, probe data cleaned itself up.

- 2026-08-21: **Review fixes (6e700d9 regression review, 6 items, restart required)** — another /code-review on 1cd30ac+6e700d9 (actual range e3ea8d3..HEAD; local cr_sync_full checked hash-by-hash against HEAD, then read directly for verification; 5 CONFIRMED + 1 PLAUSIBLE): (1) save_inspection_run's dev=None regression — after R10's unified entry point it bare-dereferenced dev.id, so failed runs on inspect._inspect_one's device-query-failure path (K4 fallback) could never be persisted; fix: the helper gained a device_id parameter tolerating dev=None (restoring the old code's device_id=dev_id + if dev guard semantics), with _persist passing dev_id. (2) expired once leaving a stale next_run — B4's rejection only blocked new ones; existing expired once entries left a past next_run on two paths (startup registration failure / toggle committing enabled=1 first then registration failure), and the "enabled but next_run empty" badge was fooled by the old value and never surfaced; fix: _register_and_persist's failure branch clears next_run in a separate commit, and load_all_schedules clears it synchronously when a single entry fails. (3) inspection buttons gated site-wide — after POST /inspect was raised to require_admin, the five trigger buttons on dashboard/devices/reports/_stat_cards/adhoc remained visible-to-all guaranteed-403 buttons (a governance escape of the same kind as alerts); fix: the five routes now pass user (dashboard/dashboard_stats/devices/reports/adhoc), six templates gate on user.is_admin, read-only adhoc gets an "inspection requires admin privileges" hint; the polling fragment /api/dashboard/stats is gated the same way (hx-swap won't swap an already-gated card back into an onclick-bearing version). (4) _PAST_DATE_MSG's bare Chinese — the en UI flashed Chinese (sibling errors all go through T); fix: the passthrough branch joins T() bilingually, the constant remains the comparison key. (5) _mtime_safe's two copies (config_backup closure + config_compare module-level) consolidated into helpers.mtime_safe, single point. (6) the alerts rules table's action column gated only the td contents, not the td itself — non-admins saw 6 headers over 7 cells; fix: the whole td moved inside the gate. Verification: server probes (dev=None run persisted with correct fields, self-cleaned / expired once registration failure next_run=None and job not registered, self-cleaned); 23+5 HTTP items (button gating asserted via onclick markers — the first run falsely matched base.html function definitions and confirm-message literals, all passed after correction; en/zh bilingual flash each proven; config-compare/config-backup helpers.mtime_safe paths 200; alerts read-only 6=6 / admin 7=7 header-cell alignment); Playwright dual-context 5 pages zero pageerror + the read-only adhoc hint visible

- 2026-08-21: **once past-date error message fix (found by a /verify probe, restart required)** — B4's rejection was functionally correct but the message contradicted itself: the "scheduled time is in the past" thrown by _schedule_config_to_trigger got the "invalid schedule time format: " prefix from _build_schedule_config's blanket except ValueError, so the user saw "invalid schedule time format: scheduled time is in the past". Fix: the _PAST_DATE_MSG constant single-point definition; semantic errors pass through verbatim without the prefix. Verification: production re-test error flash = "scheduled time is in the past (once date earlier than today)" with no prefix; rejection zero-writes unchanged

- 2026-08-21: **Review fixes (e3ea8d3 project-wide /code-review, 47 candidates consolidated to 34 items, restart required)** — 8 finders (47 candidates) → dedup to 38 → 5 verification agents → 34 items (30 CONFIRMED + 4 PLAUSIBLE) all handled, 3 rejected (reports export authorization = the README-declared deliberate design; topology dropdown injection disproven since ids are always DB integers; the apiErrorText Chrome-interception theory doesn't hold). **Permission corrections (aligned with the README permission table)**: CA write-endpoint permission inversion fixed — create_root/issue_cert/delete/revoke/sign_csr raised from require_full_user to require_admin (previously ordinary logged-in users could issue/revoke certificates); CA public-certificate download (root.crt/single crt) lowered to require_auth (the read-only token can download public certificates; the middleware already permits GET); POST /inspect raised to require_admin; alert write endpoints add/silence/delete/clear raised to require_admin (ack stays require_auth — "all users view & acknowledge"); config_backup backup-now/batch-delete raised to require_full_user; the two alerts pages' write controls template-gated on user.is_admin (read-only/ordinary users no longer see guaranteed-failure buttons). **Bug fixes**: batch_delete_backups' bare list[str] without Body() always 422 → Body(...); PDF export's run.error/cat/desc not html.escape'd, 500 on special characters; reports delete_run now returns an empty 200 (htmx contract — a non-empty {"ok":true} would be outerHTML-swapped into bare JSON text); scheduler once past-time rejection + _build_schedule_config unifying add/edit config construction; devices form port fault-tolerant parsing (bare int Form throws 422 on non-numeric and drops the whole form); the BOM network branch adds matched_summary (the hardware summary column was always '—'); the BOM cache gains a 7-day TTL + 64-entry cap (previously never expiring, unbounded growth); configuration backup/comparison glob getmtime race with a _mtime_safe fallback; AI confirm re-checks the session's soft deletion after the atomic claim before dispatch (410 cancels dispatch, same policy as _exec_show's per-command db.refresh); adhoc multi-device changed to a single POST /inspect?device_id=N&device_id=M (the backend now takes a list — previously one POST per device overwrote each other's localStorage, and the panel tracked only the last run); topology esc() hardened to the full character set &<>"' with from_port/to_port (LLDP/CDP device-side-controllable strings) escaped before being concatenated into the modal innerHTML. **Refactors**: helpers.netmiko_connect unified entry (SERVER_PLATFORMS→generic driver mapping + timeout single point; 4 call sites' separate hardcodes consolidated); models.check_password returns 'pbkdf2'/'legacy'/None with verify_password a pure bool wrapper (the 'upgrade:' dual-form return deleted); i18n.py dead code _translations/t() deleted; route-level set_lang(get_lang(request)) zeroed out (LangMiddleware the sole setter, 9 files 30 sites); the get_current_user_sync alias deleted; main.py homepage/alerts N+1 (joinedload/defer raw_data); subnet_calc's 7 try/except blocks consolidated into _parse_v4/_parse_v6; base.html gained shared toggleAll(master, selector) — seven pages' verbatim copies (adhoc/config_backup/config_push/custom_cmds/reports/scheduler/_bom_result) consolidated, esc()'s three page copies deleted (unified base canonical); app.css dead rules deleted (.status-ok/.status-err selector arms/.alert-info/.device-progress/.text-warn, zero references repo-wide). **Recorded as not fixed**: E4's middleware+route double User SELECT (the middleware-cached ORM object crossing sessions carries detached-mutation risk, outweighing the benefit of one PK query); R2's backup_now force=False branch (external automation contract preserved). Verification: local py_compile 22 py + jinja2 parse 11 tpl all passed; server TMPDIR=/tmp/_ick import check passed; 43 production HTTP items (read-only token all write endpoints 403 / admin write paths end-to-end add-delete self-cleaning / batch-delete JSON body 200 / multi-device single POST single run_id / PDF·DOCX exports 200 / CA public certificates read-only download 200); Playwright 13 items (admin+read-only dual contexts, shared toggleAll proven on three pages, en language, zero JS console errors)

- 2026-08-21: **Brand bilingual gap-fill (nav brand name still Chinese in en mode, template-only, no restart)** — the last bilingual blind spot found by /verify production final verification (5a52b90): the base.html nav brand "ivan network inspection & ops platform" (Chinese) wasn't wired to data-zh/data-en (the 26 pages' tab titles and the login page h1 were already bilingual; this was the only omission). Fix: the brand text wrapped in a span wired into applyI18n (a span, not an a — applyI18n's textContent replacement would wipe the logo img inside an a), English taken as "ivan NetOps Platform" (consistent with the site-wide title_en suffix, and shorter, easing nav crowding). Recorded as not fixable: the native "Choose File" button text of file uploads is decided by the browser UI language (English browsers automatically show Choose File), unreachable at the application layer. Verification (production Edge): en brand ivan NetOps Platform + no Chinese + logo img alive + tab title English; zh brand Chinese + devices h1 regression; the not-logged-in login page h1 English unaffected; zero pageerror

- 2026-08-21: **Review fixes (3340418 regression review, 32 candidates consolidated to 7 mainline items, restart required)** — another /code-review on the previous wave's fix commit 3340418 (8 finders + cross-session forwarding → dedup 32 candidates, 1 rejected: tmp.innerHTML XSS — verified that no unescaped user markup currently reaches it), all handled: (1) BOM upload area refactor — the form moved out of the htmx swap target #bom-info (success/error fragments no longer destroy the file input; previously a full page refresh was required to upload again after a success); htmx:responseError handling promoted from an in-page listener in bom_match.html to a global listener in base.html (site-wide 400/413/500 errors render into the top of the requesting target area: apiErrorText extracts JSON error/detail + DOMParser inert HTML fragment parsing + textContent injection-proofing + the target not cleared, and the next successful swap auto-clears the error bar); (2) AI title sentinel eradicated — the sentinel ('{label} Chat' in each language) drifted with language/hostname and had needed drift fixes three waves in a row; changed to storing an empty title string at creation + naming on the first non-blank message (an empty title never equals a user title; identification depends on no creation-time state; the frontend ai.html already has a 'Session N' fallback); _default_title_variants(hostname, ip) now only recognizes old default titles of pre-2026-08 legacy sessions; naming no longer gated on seq (a blank first message no longer permanently locks out later renaming); (3) 403 explicit classification — _classify_403: read-only-token identity (readonly_token_ok) takes priority over detail wording (a read-only token hitting require_admin always renders as a read-only rejection, so T1 monitoring markers don't miss), detail exact-matches two constants, everything else falls to the generic branch (three branches with distinct wording; the stable marker appears only on read-only rejection); (4) BOM translation/efficiency — config_checks no longer stores the 'actual' display string (it's a pure function of the match boolean; dual representations can drift); translate_config_checks derives it at render time (found/not found) with copy-on-write (unchanged entries reuse the original dict); the status table and fixed-string table unified to a key→(zh,en) shape + a _bilingual() accessor + status_labels() direct output (the STATUS_KEYS and routers._bilingual_labels re-wrappers deleted); _kw_match's summary.upper() hoisted to once per run (previously recomputed KB-scale text per keyword); _extract_config_keywords once per BOM (previously twice per unit + non-matching runs ran for nothing); extract_run_facts does a single json.loads taking both the PID set and the hardware summary (previously two functions each parsed once); (5) ai_engine persistence T() residue zeroed — 10 spots across _exec_show/_propose_config return values and assistant fallbacks ([stopped]/[rejected]×2/truncation suffix/steps errors ×4/[confirmation card generated]/[hint] per-round/unknown tool) changed to fixed Chinese (persisted via _save_msg into AIMessage; stored values are not translated); (6) comment consolidation — the "fixed Chinese, not translated" in-place comment copied at 10+ points consolidated into a language-policy paragraph in the ai_engine/ai_session/custom_cmds module headers (new persistence points no longer depend on copying comments to hold the line); (7) confirm_action display side — after the audit went fixed-Chinese, the UI response still returned str(e) directly (English UI showing Chinese errors, a display regression); added an _display_err prefix table translating on the display side (save failed / config dispatch failed / device connection failed / password decryption failed), audit fields stay fixed Chinese. Verification (production): bom page structural probes (form outside the target / global listener in place / in-page listener removed) + no-BOM-match 400 bilingual + invalid-format 400 bilingual + read-only token 403 in two client shapes (API plain-text stable marker / browser bilingual friendly page + comment marker) + admin /users 200; server-side probes: actual derivation zh/en + stored-string translation + copy-on-write same object + status_labels bilingual + extract_run_facts single parse + _kw_match both states + _display_err zh/en/unknown passthrough + title-variant recognition and naming conditions four states + _classify_403 three branches + marker isolation + ai_engine persisted zero T() by grep; /login 200 after restart

- 2026-08-21: **Review fixes (6ccb60b regression review, 10 items, restart required)** — another /code-review on the previous wave's fix commit 6ccb60b (8 finders → per-candidate verification, 10 reported items), all handled: (1) custom_cmds' 5 error strings (key mismatch / task submission failed / SSH connection failed / SSH execution timeout) still wrapped in T() and persisted via save_inspection_run (the same defect class fixed in config_push/inspect the previous wave, but missed) → all fixed Chinese; (2) ai_session's RuntimeError/SaveFailedError/ConfigExecError messages in T(), persisted via confirm_action's blanket except and _exec_show into AIAction.output audits and the AIMessage chat history → all fixed Chinese (T import removed), ai_engine's [execution failed] return value fixed Chinese; (3) read-only token 403 friendly page overreach — the _friendly_403 exception handler returned the read-only-token-specific page + stable marker for every 403 with Accept: text/html, so require_admin's 'Admin required' 403 (logged-in non-admin) was both misleading and marker-misreported; fix: _friendly_403_html(detail) distinguishes by detail, embedding the marker only for read-only rejections; other 403s show "administrator privileges required"; (4) BOM config_checks' actual stored as English found/not found and not covered by _CONFIG_CHECK_STRINGS → changed to canonical Chinese 'found'/'not found' storage + translations added (zh not-found / en not found); (5) AI title sentinel hostname drift — the sentinel was recomposed from the current hostname or ip; if the hostname was NULL at session creation and later backfilled by inspection, the comparison missed; fix: _default_title_variants(hostname, ip) recognizes all 4 variants (2 labels × 2 languages); (6) the relaxed sentinel could overwrite a manually same-named title → auto-renaming limited to the first message (seq_last is None); later messages no longer touch the title; (7) bom upload 413/400/500 invisible to htmx users (htmx by default doesn't swap non-2xx and had no responseError handling) → bom_match.html gained an htmx:responseError listener (JSON detail and HTML fragments both render into the target area, textContent injection-proofing), the 413 detail made bilingual along the way; (8) the STATUS_LABELS derived table's values read by no one (the sole consumer iterates only keys) + an outdated comment → the derived table deleted, replaced by the STATUS_KEYS key tuple; (9) subnet.html's two yn tuples were the repo's last bare lang-cookie sniffing → switched to the template globals T()/T() (the zh/en Yes/No pairs), template cookie sniffing zeroed out; (10) the default-title suffix literal duplicated at creation/comparison → the _TITLE_SUFFIXES constant + helper single source. Verification (production): deployed code grep shows zero T() at each storage point + ai_session has no T import; 403 in three shapes (read-only page with marker / Admin page without marker and wording about admin privileges / read-only token POST actually blocked 403 + marker); title sentinel 4 variants + en-created session with zh first-message auto-rename + second message not overwriting, all live-tested; BOM translate_config_checks zh/en/original-list-unchanged three probes; subnet en Yes/No + zh yes/no + lang=fr falls back to Chinese; 413 bilingual confirmed; /login 200 after the service restart

- 2026-08-20: **Review fixes (post-bilingual Wave 1+2 regression review, 9 items + 6 additional, restart required)** — /code-review of the bilingual series commits (9556383→22cfcd5 + the uncommitted final-verification fixes) (8 finders → adversarial verification, 9 reported items), all handled: (1) the AI session default-title sentinel's cross-language mismatch — creation stored the language-specific default ('X Chat') per the then-current language, but chat() rebuilt the sentinel per the current language to compare, so after switching languages the first message's auto-rename failed forever; fix: the sentinel recognizes both languages (stored values untranslated; only the comparison relaxed); (2) persisted fields fall back to fixed Chinese (implementing the self-imposed "stored values and comparison keys are not translated" rule) — AIAction.output audit markers ([expired auto-rejected]/[execution output]/[save failed]/[execution failed]), the AI config-change goal, InspectionRun.error (key mismatch), and config-push audit errors (decryption failed / queue cancelled / suspected hang) all had T() removed; (3) the raw_data section key fixed to the Chinese literal for 'Custom Commands' (it previously drifted between the Chinese and English forms with the triggerer's language; the storage schema depended on the language); (4) cases webhook remarks fixed Chinese — the remarks notify_case_change sends to the external T1/QC channel previously drifted zh/en with the operator's UI language (also removing the English variant's 'and N in total' duplicate counting); (5) BOM config_checks stores canonical Chinese + translation at render — the language at match time was previously baked into the cross-request cache _last_results, so after switching languages remove-rows/export mixed languages within the same row; added translate_config_checks() and a render copy in bom.py _render_results (cache untouched), STATUS_LABELS now derived from the bilingual table (single source), build_export_excel dropped the lang parameter/set_lang duplicated with the route; (6) read-only token 403 stable marker — after the final-verification fix changed the browser 403 from plain text to a bilingual friendly page, machine clients sending a browser Accept lost the fixed 'Forbidden: read-only token...' marker; the friendly page's tail embeds that ASCII marker (HTML comment); the API path (no html Accept) keeps the original plain text; (7) get_lang unified — 19 hand-written set_lang(request.cookies.get(...)) copies all consolidated into set_lang(get_lang(request)) (8 files + LangMiddleware); (8) evidence-rejected item (on record): the review claimed 4 routers' sync routes lacking manual set_lang would always output Chinese — the premise doesn't hold (LangMiddleware sets it before call_next + anyio.to_thread.run_sync copies the contextvar, so sync endpoints naturally reach it; production testing showed custom-commands' platform dropdown and scheduler flash correctly bilingual without manual set_lang); the existing manual set_lang kept as a harmless explicit fallback, and the comment in ai_assistant.py stating the wrong premise was corrected; (9) additional confirmed items — bom.py's upload 413 swallowed by a blanket except into a 500 "parse failed" (added except HTTPException: raise); scheduler run-now's 'Schedule not found' single-language English made bilingual; the chat worker gained defenses against None dereferences from concurrent session/device/user deletion (graceful bilingual errors replacing Internal error: NoneType); ai_engine's in-loop T() header hoisted out of the loop; base.html's switchLang judged by the raw un-normalized cookie (with lang=fr the language button's first click did nothing) — now reuses the already-normalized i18nLang from head + the dead variable at body end deleted; main.py's duplicate _MWHTML alias deleted; custom_cmds PLATFORM_TYPES' dead 'all' entry deleted. Verification (production): custom-commands en All Platforms / zh all-platforms; scheduler run-now bilingual flash; read-only 403 en/zh bilingual page + stable marker + API plain text unchanged; an AI en-created session 'vpn Chat' → the zh first message's auto-rename hits; password-change bilingual regression; BOM translate_config_checks server-side en/zh direct probes; deployed code grep zero T() at storage points; lang=fr renders Chinese and the language button switches to English on the first click; zero pageerror. Known residue (on record): persisted/outbound strings (audit markers/push errors/webhook remarks) display Chinese under the English UI (storage over display; display-layer translation deferred); the pre-existing inconsistency of custom_cmds standalone executions storing the 'Custom Commands' key while inspections store the Chinese equivalent key left untouched (historical-data compatibility)

- 2026-08-20: **Bilingual final-verification fixes (lang whitelist aligned front and back + read-only token 403 bilingual friendly page)** — the /verify final verification (17 probes) caught two edge cases: (1) with an illegal cookie value like lang=fr, the frontend JS only checked `==='zh'` and rendered English while the backend whitelist fell back to Chinese → mixed-language pages; fix: base.html's i18nLang normalizes against the whitelist (anything not en is zh, same direction as the backend set_lang), and the body-end script reuses the already-normalized window.i18nLang from head; (2) a read-only token hitting a restricted page (/users etc.) intercepted by LoginMiddleware returned plain-text English Forbidden, inconsistent with the router layer 403's bilingual friendly-page style; fix: the friendly-page HTML extracted into _friendly_403_html() shared by both, and the middleware likewise returns the bilingual friendly page for Accept: text/html interceptions (API calls without html Accept keep plain text). Verification (production): with lang=fr, backend fragments Chinese + frontend full page Chinese (h1/tab/nav, no more mixing) + the language button shows EN; the read-only token /users returns the 403 Access Denied / 403 access-denied friendly page under lang=en/zh respectively; the API path plain text unchanged; en/zh normal switching regression; zero pageerror

- 2026-08-20: **Bilingual blind spots all fixed, Wave 2 (backend strings bilingual, restart required)** — per "fix all", clearing the last class of blind spot: backend .py emitting Chinese strings directly (previously unreachable by the mechanism). (1) i18n infrastructure — i18n.py adds T(zh,en) + a contextvar (same shape as the frontend t()); main.py adds LangMiddleware (writes the lang cookie into the contextvar per request, add=outermost so early paths like the 403 handler are covered too); templating.py registers the Jinja global T; sync def routes run in the thread pool where the contextvar doesn't propagate — the affected route entries call set_lang(request.cookies.get(...)) explicitly, with 5 routes that previously had no request parameter gaining a Request parameter (FastAPI auto-injects); (2) scale of the conversion (~80 user-visible strings; logs/docstrings/comments stay Chinese): all bom.py htmx fragment texts + STATUS_LABELS made bilingual (_bilingual_labels, templates look up by key unchanged) + the Excel export (headers/status/the BOM match report build_export_excel gains a lang parameter); auth's password-policy/change-password/reset errors + the T1 guest (read-only) username becomes an @property; ai_assistant's all JSON errors + the session title "Chat"; ai_engine's RuntimeError/SSE event text; ai_tools' tool descriptions become a build_tools() function (a module-level constant would freeze as zh at import) + **a complete English system prompt added**, SYSTEM_PROMPT_TEMPLATE_EN and the fallback-protocol FALLBACK_SUFFIX_EN (in English mode the LLM answers with English prompts); ai_session/crypto exception messages; devices/subnet/vram/cases/config_backup error messages; the 403 page HTML; (3) the worker-thread lang passing chain — inspection (trigger_inspection→BackgroundTasks→_inspect_one), run-now (run_now→_run_scheduled→_run_batch→_inspect_one), multi-device commands (execute_multi→_run_cmds_with_lang): the entry points uniformly pass get_lang(request), the workers set_lang so T() takes effect; the APScheduler scheduled path keeps the default zh unchanged; (4) skipped items (on record): stored values/comparison keys not translated (the scheduler's "waiting" status value, the device raw_data parse keys for hardware inventory/serial number), and legacy Chinese in historical reports/historical inspection records not retrofitted. Verification (production): after the server passed a TMPDIR-isolated-lock import check and restart, seven API probe groups — BOM empty upload / no-upload match / subnet invalid address / vram empty and invalid parameter counts / password-change mismatch / AI session creation with a nonexistent device — all hit the expected language in both en/zh directions; all 20 pages × lang=en traversal 200 + zero pageerror

- 2026-08-20: **Bilingual blind spots all fixed, Wave 1 (default light theme + tab titles/tooltips bilingual, template-only, no restart)** — per "default theme light + fix all": (1) default theme dark→light — base.html's pre-paint script and switchTheme defaults changed from dark to light (existing users with a theme=dark cookie are unaffected; new visitors get light on first visit); (2) tab titles bilingual — base.html's title tag changed to `<title data-zh="{{ self.title() }}" data-en="{% block title_en %}{{ self.title() }}{% endblock %}">`, reusing the applyI18n mechanism; the 26 page templates each add a title_en block (brand suffix unified as "ivan NetOps Platform"; titles with {{ }} dynamics translate only the static part; pages not defining title_en fall back to Chinese); (3) tooltips/aria bilingual — applyI18n adds data-zh-title/data-en-title and data-zh-aria/data-en-aria attribute-pair handling; the site's 13 title/aria-label spots that previously stayed Chinese are all wired in (topology's three zoom keys / bom's clear button / _ca_certs' P12 hint / ai's three select aria / scheduler's four titles). Verification (production Edge): a brand-new visitor (no cookie) gets the login page data-theme=light + body rgb(241,245,249); theme=dark-cookie users stay rgb(2,6,23); light → toggle → dark + label flip ☾ dark / ☀ light; lang=en tab titles Subnet/Devices English + lang=zh back to Chinese; topology tooltips round-trip bilingual; console zero errors. Deployment note: burst packet loss on the network path caused two failed deployments, diagnosed as intermittent large-packet drops (1400/1800-byte attempts failed while 2000 succeeded, not a hard MTU); the deploy script upgraded to resume-from-breakpoint (md5 comparison skips files already current) + 1KB chunks + 30 retries per chunk, then passed in one go

- 2026-08-20: **Site-wide content bilingualization (module content anglicized, 30 templates, 575 annotated spots)** — following UI-unification Wave 4 (which covered only nav + titles/buttons), per the "module content should also display English" requirement, bilingual coverage extended to all page content (templates only, no restart): (1) base.html mechanism extensions — applyI18n extracted into an _i18nSet helper; elements with a placeholder attribute get their placeholder replaced, input[type=submit/button] get their value replaced (previously only textContent was replaced, so form placeholders couldn't be translated); the i18nLang and t() definitions moved forward into the head pre-paint script (the chrome-block inspection-panel script runs before the body-end i18n script, so panel JS strings previously couldn't use t()); all hardcoded Chinese in the inspection progress panel (inspection progress / login expired / inspection complete / inspecting / inspection timeout / request failed / confirm prompts / refresh button) switched to t(); (2) all 30 templates fully annotated — all site-visible static text (h1/h3/label/button/th/option/empty states/subtitles/modals), 575 data-zh/data-en spots; in-template JS dynamic strings (alert/confirm/innerHTML concatenation/textContent), ~90 spots switched to t(); terminology unified site-wide (Inspection/Online/Timeout/No data, etc.); Chinese rendered by default, data-zh holds the Chinese original, switching to EN turns the whole page's content English; (3) Jinja inline Chinese handling — `{{ 'success' if x else 'failure' }}`-style expressions, ~10 spots (server-rendered, out of the JS mechanism's reach): badge types changed to {% if %} branches wrapping bilingual spans (custom_cmds/config_push/case_detail/scheduler), and subnet's 6 yes/no spots use a yn tuple reading request.cookies for lang; (4) sentences with zh/en word-order differences split into reordered spans (e.g. "N subnets, M usable IPs per subnet" — English is "N subnets, M usable IPs each"), pure quantifier measure-words hidden by setting the span's data-en to an empty string. Verification (production Edge): lang=en across all 20 pages with zero Chinese residue (high-frequency-word probes: add/save/cancel/delete/edit/status/actions/loading/no-data — all 0 hits) + the devices form placeholder takes effect in English + console zero errors; switching back to lang=zh re-checked page by page, all data-zh elements display Chinese (the initial zh probe falsely FAILed on 7 natively-English-majority pages; targeted re-checks confirmed all normal); 32/32 templates Jinja-compile clean. Mechanism boundaries honestly recorded (uncovered, deferred): title/aria-label attributes (~8 tooltip spots still Chinese in English mode) / the block title tab titles / server-side .py-emitted strings (the device status "waiting", bom.py fragment texts, inspection result texts) — the last class needs backend changes and a restart, explicitly out of scope this round

- 2026-08-20: **Site-wide UI unification Wave 4 (bilingual completion + htmx fragment bilingual hooks + final site-wide dual-theme regression)** — fourth wave of the series (templates only, no restart): (1) base.html's i18n mechanism patched two holes — the initialization logic extracted into applyI18n(root) with an htmx:afterSwap listener registered (previously fragments inserted by htmx partial refreshes weren't translated; initialization ran only on first paint); a new t(zh,en) helper lets JS dynamic text pick per the current language; (2) English pages wired to data-zh/data-en bilingual — ca_server + _ca_roots/_ca_certs (CA certificate management / root CA / sign external CSR / issue certificate / certificate list / all form labels/buttons/headers), alerts (clear all / clear acknowledged / acknowledge / add / silence 2h / delete / empty states), ping (network diagnostics title), config_compare (configuration comparison title + compare/swap/clear buttons), the vram_calc empty-state hint sentence; Chinese by default; after switching to EN these pages turn English in sync (same mechanism as the nav); (3) final regression — production Edge, all 20 pages × dark/light dual-theme traversal: all 200, every page's h1/card structure in place, no "white island" background elements under dark (card/th/table probes), console zero errors; bilingual verification: under lang=en the ca/ping/config_compare titles and alerts buttons turn English, applyI18n takes effect on swapped fragments, switching back to zh restores everything. Honestly recorded: the inline style count is 527 vs the 523 baseline, essentially flat — this series consolidated private style blocks/hardcoded colors/duplicated components (the design-system layer); pre-existing inline layout attributes were not swept page by page (the form-layout inline styles on subnet etc. deferred)

- 2026-08-20: **Site-wide UI unification Wave 3 (page skeleton/empty states/modals unified + orphan compare template discovered)** — third wave of the series (templates/CSS only, no restart): (1) compare.html (inspection comparison), a bare-bones page, brought into the fold — card wrapper + table-wrapper + status badges + .empty-state; **note: a full-repo grep confirms no route renders compare.html and no page links /compare — the template is an orphan (dead code); this pass only adopted it structurally; whether to wire it up or delete it awaits the user's decision**; (2) config_backup.html — the site's only page using h2 as the page title changed to h1 + .page-header; deleted the three private wheels .backup-table/.btn-backup/.status-msg → the shared table/.toolbar/btn family/.alert family (showStatus now uses alert-success/alert-error); JS-built table rows synced (unquoted attributes fixed, conflict markers #EF4444 → .text-err, empty-state rows use .empty-state); dead code r["new"] ? "ok" : "ok" cleaned; (3) alerts.html — the severity badges' inline colors (#EF4444/rgba hardcodes) → tokenized .alert-sev classes; the page-header rules/history tabs moved into .page-header; 'No alert history' → .empty-state; (4) 4 hand-written modal shells (devices/scheduler/topology/ai, verbatim-duplicated position:fixed+rgba(0,0,0,0.7)) adopted into the shared .modal-overlay/.modal classes, with ai.html keeping the .ai-modal-mask/.ai-modal layout hooks; (5) empty states/subtitles unified — cases/scheduler's hand-centered paragraphs → .empty-state, adhoc/cases/case_categories/scheduler's inline subtitles → .page-desc; (6) latent bug fixed — scheduler.html uses the status-badge info-badge modifier classes but app.css never defined them (the badge never had a background); added the .status-badge.info/.info-badge definitions. Verification (production Edge): alerts severity badge colors match the --*-text tokens dynamically / the alert history page normal / config backup h1+toolbar+shared table rendering 22 data rows / devices edit modal dark inner #0F172A + light pure white + overlay rgba(0,0,0,0.6) / the scheduler page normal + info-badge blue in effect / the topology canvas renders without regression / console zero errors

- 2026-08-20: **Site-wide UI unification Wave 2 (shared classes into the library + eliminating the bom/ca/vram three light-theme islands)** — second wave of the series (templates/CSS only, no restart): (1) app.css shared classes added — distilled from the repo's 523 inline styles: .page-header/.page-desc/.form-row/.form-group/.modal-overlay/.modal/.btn-outline/.btn-outline-danger/.btn-block/tr.row-ok/row-warn/.status-badge.warn/.page-narrow/.page-wide/.flex/.mb-16/.text-ok/.text-err; note that .btn-outline was previously used by the case-series pages and _ca_roots/_ca_certs but never defined in app.css (rendering as bare buttons all along) — now defined; (2) deleted the global input/select/textarea margin:0 6px 6px 0 (the root cause of inline-margin proliferation); (3) three "light-theme island" pages eliminated — bom_match (~75 lines of private light <style> all deleted), ca_server (19 lines, and it **redefined the global .btn/.btn-primary/.btn-danger/.btn-sm without scoping**, polluting the shared buttons while that page was open), vram_calc (23 lines, privately redefining .card/.alert-error over the shared classes); the hardcoded #fff/#2563eb/#f1f5f9/#eff6ff/#bbf7d0 etc. zeroed; private tables (.bom-table/.ca-table)/badges (.badge-active)/buttons (.btn-export/.btn-calc) all mapped to shared classes; (4) the classes bom.py's route emits directly as HTMLResponse strings (btn-clear/upload-error/match-error) keep tokenized aliases in app.css — changing .py needs a restart; adoption deferred to a later wave; (5) the theme-toggle button's label flips with the current theme (showing ☀ light under dark, ☾ dark under light). Verification (production Edge): the three islands show no white-island backgrounds under the dark theme / under the light theme cards pure white + page background #F1F5F9, the hierarchy holds / the ca page's buttons regress to the shared Fira Code font (private overrides gone) / vram calc htmx swap produces the results table (38.4 GB) / bom shared card + empty state in place / after the global margin removal, spot-check screenshots of subnet+devices+adhoc+config_push show no layout squeezing / console zero errors

- 2026-08-20: **Site-wide UI unification Wave 1 (design-token layer + light theme + nav highlight + login page stripped of nav + htmx localization)** — first wave of the "optimize all module UI" series (templates/CSS/static assets only, no restart): (1) tokens completed — :root gains the semantic token families (alert/badge text colors --*-text, solid-button text --*-contrast, semantic borders --*-border, neutral background --muted-glow); all hardcoded colors in app.css (the alert-text #FCA5A5 family, alert rgba borders, .btn-success's #020617, the three .alert-sev colors, the .result-card border, the .status-badge.unknown background) consolidated into var() references; the dead token --bg-elevated deleted; (2) light theme — a [data-theme="light"] override block added (light-white background #F1F5F9 / pure-white cards / semantic colors stepped down to keep contrast / lighter shadows), the nav bar gains a ☀ toggle (cookie theme=light persisted, same mechanism as lang, reload-style switching), 3 lines of pre-paint script in head prevent dark-flash; (3) nav active highlight — the .nav-links a.active style had existed for two years but was never set; now pure JS location.pathname prefix matching (detail pages fold into list pages; testing found / 303s to /dashboard, both count as the dashboard); the logout link's inline #EF4444 changed to the .nav-danger class; (4) the login page no longer renders the full navbar and inspection progress overlay — base.html's nav/inspection panel wrapped in {% block nav %}/{% block chrome %}, login.html overrides them empty (previously not-logged-in users saw all 21 menus + the logout link); the i18n script defends against a missing #lang-switch; (5) htmx 1.9.10 localized from the unpkg CDN to static/htmx.min.js (no longer breaks on intranet-isolated deployments; the version pinned, not upgraded to 2.x); (6) a badge bug fixed in passing — .status-badge.timeout/.auth_failed's ::before dots had no color rule (the dots were invisible). Verification (production Edge): dark zero regression (body rgb(2,6,23)) / light toggle round-trip (dataset.theme+cookie+body rgb(241,245,249)+pure-white cards+dark body text) / nav highlight /devices·/·/cases three states / login page no navbar, no inspection overlay / htmx loads locally, typeof htmx defined / the timeout badge dot red / console zero errors

- 2026-08-20: **Subnet calculator optimization (IPv4/IPv6 splitting + fixing a real form bug of same-name field overwriting)** — (1) slash-prefixed input was rejected: the split input's placeholder invites "/26" with a slash; the old implementation's int('/26') errored outright; now _resolve_prefix uniformly parses with strip().lstrip('/'); (2) new split-by-count mode (split_mode=count): enter the desired number of subnets (e.g. 4 or 100), automatically converted to the smallest new prefix that fits that count (count rounded up to a power of 2: /24+4→/26, /24+5→/27, v6 /32+100→/39); the IPv4 split card and IPv6 split card each gain a by-prefix/by-count dropdown; (3) large-number formatting _fmt_pow2: the subnet count for /32→/48 changes from the bare 65536 to 2^16 (65,536); v6 addresses per subnet likewise in 2^80 (...) form; (4) same-prefix/smaller-prefix now give an explicit error (the new prefix equals the current one, no split needed) instead of silent empty results; (5) VLSM insufficient capacity no longer silently breaks, discarding remaining demands — an unallocated list is recorded and the page's alert-warn states explicitly "the following host-count demands could not be allocated"; (6) v6 ULA detection fixed: Python 3.11's IPv6Network has no is_unique_local attribute; the old getattr fallback was always False; now explicitly judged against the fc00::/7 range; the v6 card gains address attribute rows (global unicast/ULA/link-local/multicast + expanded form); (7) all result cards wrap an error branch — previously calculation errors only returned {"error": ...} while the template had no check, rendering blank cards; now a uniform alert-error red bar; (8) **same-name field overwriting bug (caught by live production browser testing)**: inside the IPv6 panel, the basic-info and subnet-split cards share name="ipv6_addr"; Starlette takes the last occurrence for duplicate fields — filling the address in the basic-info card and clicking "calculate", the empty input of the split card behind overwrote the value with an empty string, and the server replied "Enter an IPv4 or IPv6 address"; prepareSubmit adds a dedup rule: disable the later empty duplicate fields within the visible panel (keeping the one the user actually filled); (9) v4 usable hosts/total IPs and v6 total IPs gain thousands separators (16,777,214); (10) cleanup: the route layer's dead int() try/except deleted (_resolve_prefix takes over), the IPv6 branch's duplicated dead list branch deleted, the template's duplicated switchTab definitions deduplicated. Verification: 8 local behavioral assertions (slash/plain number/count rounding/2^N formatting/same-prefix error/VLSM unallocated/ULA both states) all passed + a production Edge real-user flow (click tabs to switch panes, fill the form, click the button) 9/9 PASS: v4 '/26' and '26' both yield 4 subnets, count 5→/27 yields 8 subnets including 192.168.1.224/27, v6 /48 shows 2^16 (65,536), v6 count 100→/39, the same-prefix error bar, the VLSM unallocated banner, ULA fd00::/8 recognized, the invalid-address error card, the /8 basic calculation regression (thousands separator in place)

- 2026-08-20: **Static-asset caching fix (users' browsers' old CSS rendered the logo as the 200px original)** — Starlette's StaticFiles sends no Cache-Control by default, so browsers cached heuristically (~10% of file age); after the new app.css was deployed, users' browsers held the old CSS: the new HTML referenced the logo image but the old CSS lacked the .brand img 26px constraint, and it still had the ⚡ ::before. Fix: (1) StaticCacheMiddleware — /static responses uniformly get Cache-Control: no-cache (browsers revalidate each time; StaticFiles' built-in ETag hits return 304, minimal overhead); (2) the app.css and logo.png references gained ?v= version numbers, forcing browsers holding the old CSS to fetch the new version immediately. Verification: production response headers Cache-Control: no-cache + ETag in place; Edge testing shows the brand icon rendering at 26×26

- 2026-08-20: **Official logo rolled out site-wide (ivanioc.png)** — /home/ivan/ivanioc.png (a 200×200 network-node graphic, deep-blue background matching the theme) copied to backend/static/logo.png and applied to three brand spots: (1) the navbar brand — replaces the CSS ::before's ⚡ character; .brand changed to flex + a 26px rounded icon; (2) the browser tab favicon — replaces the previous day's inline SVG data-URI, now pointing to /static/logo.png; (3) the login page — the h1's ⚡ replaced with a 96px large logo image. Verification: production Edge screenshots confirm the login page's large logo + navbar icon render normally, /static/logo.png 200, console zero errors

- 2026-08-20: **Traceroute/MTR fix + optimization (fixing a parser that never worked)** — an empirical finding: on Linux, the Trace results table had **never rendered**: mtr 0.95's output has hop numbers glued as `1.|--`, the old _parse_mtr's `parts[0].isdigit()` is always false and skips every line, leaving only the raw text in details; and mtr omits the % sign for 100% loss (column alignment), so a bare `([\d.]+)%` regex misses all-loss hops. Rewritten as a line-by-line regex parser (hop/IP/Loss/Snt/Last/Avg/Best/Wrst/StDev, all columns, % optional), unit-tested with real mtr samples from the server. Optimizations: (1) the Trace and MTR forms uniformly render the full-column stats table (shared Jinja macro; Windows tracert degrades to times text lines), loss-colored badges (0% green / >0 orange / 100% or ??? red), the title carries an N hops · M cycles summary, and the raw output stays in a collapsible details; (2) the two forms' mtr cycle count is selectable (5/10/20/30, the _cycles whitelist clamped 1-30, the subprocess timeout adapting at cycles*2+20); (3) a target-host whitelist _clean_host — although subprocess is list-form with no shell injection, targets like `--help` get parsed as options by mtr/ping (option injection); now rejected with an invalid-target page message; (4) Continuous ping's Linux -W also corrected to seconds (the same unit bug as the batch path). Verification (production HTTP + Edge screenshots): the Trace gateway 1-hop table renders / Trace 223.5.5.5 cycles=10 yields 17 hops including 13 * hops + a 40%-loss hop with an orange badge / the MTR form produces the table + the raw collapsible preserved / `--help` intercepted / batch and Continuous regress normally

- 2026-08-20: **Ping module supports a full /24 (254 hosts) + truncation notice + the timeout control wired up** — batch ping limit MAX_HOSTS 100→254 (workers 50→64): previously entering /24 was silently truncated to the first 100 hosts with no page hint (testing 198.51.100.0/24 returned only 100 rows; users would think the whole subnet was scanned); now expand_targets returns an (ips, truncated) flag, and over the limit the results page shows an alert-warn banner "Only the first 254 addresses pinged; the rest are truncated, untested". Two latent issues on the same page fixed in passing: (1) the timeout dropdown (500/1000/2000/5000ms) was a dead control — ping_post never received a timeout_ms parameter; now wired to ping_one (invalid values fall back to the default 1000ms); (2) Linux ping -W is in seconds (only Windows -w is milliseconds); passing the 1000-millisecond value straight through = waiting 1000 seconds per packet, with unreachable hosts actually relying on the subprocess timeout=6 bottom line; now converted per platform (Linux seconds / Windows milliseconds), and the subprocess timeout adapts at 4 packets × timeout + a 3s margin. Verification (production HTTP): a full /24, 254 result rows, done in 17s with no truncation banner; /23 (510 hosts) truncated to 254 with the banner shown; the timeout control verified working (500ms→4.2s / 5000ms→8.2s response-time difference); Continuous Ping and the range form regress normally

- 2026-08-20: **Topology page /verify probe fixes (4 UX/display issues)** — found and fixed by production /verify of the beautification waves (4c95b1b..61ad932) (Playwright-driven real-page interaction probes): (1) the zoom percentage readout fell out of step after button zooming — vis's zoom event fires only on wheel/pinch zooming; the programmatic moveTo/fit from zoomBy/fitAll/Trace don't fire it, so after clicking + the canvas enlarged while the readout stayed at 58% (contradicting the README's "live zoom percentage" claim); fix: a syncZoomPct helper consolidated, with programmatic zoom hooking network.once('animationFinished') to sync (the wheel path still uses the zoom event); (2) Trace's hop count and Clear's reset occupied #last-update, so the Updated timestamp was overwritten/wiped until the next refresh — split out into an independent #path-status status slot; last-update only shows the update time; (3) Trace across connected components popped a native alert('No path found') (the production topology actually has 3 connected components: core 13 nodes / office-sw1 11 nodes / ICI-FW 2 nodes — the LLDP collection status quo, not a defect, but it means the prompt gets hit often); changed to an inline "No path (nodes not connected)" in #path-status; (4) favicon 404 console noise — base.html gained an inline SVG data-URI icon (⚡, zero external resources). Verification (production Edge, real pages): button zoom 58%→75%, Fit 75%→56%, the readout synced; Trace 'Path: 2 hops' goes into path-status and the Updated timestamp stays; disconnected pairs show no dialog popup, an inline hint instead; Clear empties path-status; console zero errors (the favicon 404 gone); pageerror zero

- 2026-08-19: **Network topology page beautification (visual upgrade + fixing a timer leak)** — a full visual redo of the topology page; the engine layer touched only one line of external-node labels: (1) node iconography — ASCII characters (`*` `<>` `^`) replaced with inline SVG badges (vis image shape + data-URI, zero external resources): shape = device type (switch/router/firewall/WLC/server/external host, classified heuristically by devicetype+hostname), type accent coloring, outer ring + bottom color bar = status (online/abnormal/unknown), dashed outline for external nodes; (2) deterministic layered layout — roles already had core/distribution/access/external tiers, changed to fixed layering (core on top, descending layer by layer, same-tier rows sorted by subnet+name), physics off — previously the initial placement was handed to forceAtlas2 to rearrange, re-scattering the whole graph on every refresh; (3) edge-label noise reduction — each edge's 8px port pair, permanently on the canvas, changed to hover-only tooltips (title); the canvas keeps only the "N links" aggregate label and speed coloring (GE/10G green / FE orange), edge arrows removed (misleading for an undirected graph); (4) node two-line labels (hostname + a second-line small IP), external Unknown nodes now labeled by IP (engine: falls back to the IP when the name is missing/Unknown — previously a row of indistinguishable "Unknown"s on the graph; 0 Unknowns remaining among the 26 production nodes); (5) alert presentation upgraded + leak fixed — border-width blinking changed to a red-shadow breathing pulse, and the old implementation ran one setInterval per alert node, stacking without recycling on every loadTopo (auto-refresh 60s) — changed to a single shared timer + clear-old-before-reload; (6) canvas polish — a fine dot-grid background + inner shadow, bottom-right +/−/Fit floating zoom controls with a live zoom percentage; (7) the legend panelized — a bottom-left floating card: online/abnormal/external/alert with live counts, click-to-filter (dims non-matching nodes), and a link color-band legend; (8) the popup's CPU/memory changed to mini progress bars (>85% red / >65% orange), the neighbors area shows counts. Verification: 11/11 key page markers + /topology/data Unknowns zeroed (external-node samples all have distinguishing labels) + devices/dashboard no regression; layout stability guaranteed by physics:false (no re-scatter on refresh). Not done (rejected after evaluation): subnet background boxes (vis has no native support and it easily gets visually messy — replaced by legend filtering)

- 2026-08-19: **Topology page beautification follow-up fix (production error Cannot set properties of null (textContent))** — after the beautified version went live, the browser errored on open. Root cause (verified against the production vis-network.min.js 9.1.2 source): `Network._create()` starts with `for(;container.hasChildNodes();) container.removeChild(...)` — **vis empties all the container's child nodes at construction**; the beautified version put the legend panel/zoom controls inside the `#topo` container, so the moment `new vis.Network()` ran, the controls along with `#zoom-pct` were deleted on the spot, and the next line's `getElementById('zoom-pct').textContent=...` hit null → the catch rendered the error (the old version worked precisely because the container was empty). Fix: (1) restored the "vis container must be empty" structure — the legend/zoom controls/error layer all became sibling nodes outside the container (absolutely positioned within the wrapper), with a comment at the marker noting the pitfall to prevent recurrence; (2) the error path rewritten to a dedicated `#topo-error` sibling overlay, no longer nuking the vis container (the old catch rewrote the container's innerHTML, deleting the controls too — one transient error amplified into null crashes on all subsequent refreshes); (3) all `textContent` assignments go through a setTxt guard helper. Verification: node --check syntax + **production headless Edge real-render verification** (an admin session opening /topology, real production /topology/data): screenshots confirm the canvas renders (26 node badges + links, layered layout), legend counts (online 7 / abnormal 0 / external 19 / alert 2, matching the data), the zoom controls and live percentage (58%), the Updated timestamp refreshing, the #topo-error overlay staying hidden, pageerror zero (the original error gone). Lesson recorded: the vis-network container is the library's private territory (9.x empties it at construction); overlays must always be sibling nodes

- 2026-08-18: **Review fixes round 17 (post-round-16 regression review, 7 correctness + 14 cleanup, all fixed)** — re-review of round 16's commits (e1136d4→38b8d42) (8 finders → 26 candidates → 3 verifiers → 7/7 all CONFIRMED; 5 of them regressions/over-fixes introduced by the previous round itself, honestly recorded): (1) ai_engine's allowed_hosts reopened rebinding — the allowed set contained the original hostname, so a redirect back to the original hostname kept credentials while that hop had urllib re-resolve DNS (a resolver answering loopback at pin time but a public address now receives the plaintext key; before the change, old_host was the pinned numeric address and would have been stripped); fix: the redirect target hostname is pinned again (req.pinned_hosts passed hop by hop, the netloc swapped back to the pinned address, so that hop bypasses the resolver); (2) qc_webhook refused to send to http://localhost (a five-angle consolidation regression) — _is_private_host's localhost branch was deleted on the "sole caller" premise and falsified that same round by webhook, the second caller; fix: the localhost-domain branch restored (resolution verified loopback), the docstring honestly rewritten for the two consumers; (3) inspect's ad-hoc slow-worker results discarded — Timer(10) unconditional retirement × the strict guard: a healthy device whose SSH total slightly exceeded the 300s budget finished after its entry had already retired → the real result discarded wholesale while status was already done:true (the guard comment "retirement only happens after all workers finish" is false for this path); fix: the ad-hoc retirement window extended to max(N*60,10)s with an expected identity guard (same as the scheduled path); (4) config_backup's '::1' full address wrongly killed by the ≥2-segment threshold (a single-hextet full address has one segment; the orphan filter got 0 rows); fix: full addresses q_addr can parse are let through; (5) the negative-TTL window's message reported a resolver hiccup as a "must use https" configuration violation (users see the raw text); fix: the localhost-domain rejection message distinguishes "cannot resolve" + the failure path leaves a server-side warning log; (6) _form_int's silent fallback (a third error channel created while fixing 422: entering abc got an interval-1 schedule persisted without feedback; the edit modal's JS submit() bypasses browser validation); fix: invalid returns None and goes through a ?error= flash rejection — /verify then caught an empty-string bypass (FastAPI replaces a submitted empty string with the default; with default="1", clearing the number box silently became 1 over HTTP and persisted — the probe accidentally created 3 hourly test schedules, confirmed deleted); fix: the default changed to "" so both the absent and cleared paths converge to the flash; (7) the conflict marker leaked into the ip data field (exportSelected's exact match always "no matching device found" for conflict groups; filter hits ran into prose); fix: ip stays a pure value + conflict gets its own field (recording the other side of the collision), the template renders badges by field; (8) cleanup: _current_entry's guard predicate consolidated (four hand-written copies in two variants → one named helper; the redundant pre-check outside the unit deleted — the helper throws on first non-locked contact, so the in-unit check was fully redundant); _rollback_and_log consolidated three verbatim except bodies; apiErrorText moved up to base.html, shared by three pages; query_or_empty's dead callable branch deleted; custom_cmds' device selector narrowed to five columns; the host-prefix judgment memoized (N files → D devices); the capacity guard simplified (over-limit clears directly); a dead port try/except and dead empty-query guards deleted. Verification 38/38 (temp-DB: re-pinning three hops / localhost four states / message distinction + logging / capacity guard / guard consolidation three states / retry-window discard / ::1 six forms / conflict pure value + separate field / flash four forms including empty string / consolidated-source assertions) + production HTTP re-probes (empty string/absent/abc three-way flash, 3 real schedules in the list, the adhoc shared function with no inline residue). Deployment chain: this round's network path suffered severe disconnections under burst traffic; the deploy script gained trickle (2KB/0.5s) + 8 reconnects. Recorded as unchanged: devs_snapshot's explicit origin parameter (adding an APScheduler snapshot later would make once permanently re-fire) / fully promoting the egress policy into an egress module. Also: while troubleshooting a deployment interruption, a ps timing issue — uvicorn starting the same second the files landed — was already covered by the "upload→restart" ordering + live-behavior double evidence

- 2026-08-18: **Review fixes round 16 (post-round-15 regression review, 12 CONFIRMED + 2 PLAUSIBLE all fixed)** — re-review of round 15's commit (e1136d4) (8 finders → 37 candidates → dedup 14 correctness + 15 cleanup → 4 verifiers adversarially checked, two reproduced by live packet capture/testing); the review anchored on the server-exported original e1136d4 tree (the local mirror contained undeployed later iterations; audited, then adopted as the base + gaps filled and deployed together): (1) ai_engine egress chain, triple — the Host header previously used the raw netloc; URL userinfo (http://user:pass@…) credentials were written in plaintext into the request header sent to the peer and landed in gateway access logs (reproduced live), rebuilt from hostname+port; the manual Host header survived redirects as-is (_SafeRedirect strips only Authorization; the internal vhost name leaked to the redirect target and mis-routed, reproduced live), changed to tracking the allowed host set per request ({original host} ∪ {each pinned address}, passed hop by hop); jumps leaving the set get both Authorization and Host stripped, in-set ones kept (a benign redirect back to the original hostname is no longer stripped into an anonymous 401); single-address pinning broke getaddrinfo's multi-address fallback (dual-stack localhost + a gateway listening only on ::1: connectable before, refused after pinning, with the key sent in plaintext to an unrelated service on 127.0.0.1), changed to pinning a candidate address list (IPv4 first) + _call_llm falling back through the backup addresses in order on refused/reset (timeout/resolution failure doesn't fall back, preventing a 120s timeout from multiplying); (2) negative resolution results cached with a 60s short TTL (positive 300s + a 256-entry capacity guard) — a black-hole resolver (getaddrinfo blocking for seconds to tens of seconds, not covered by LLM_TIMEOUT) previously dragged once per new round with no server-side log, but not caching at all would return to "a one-off failure closes off the provider until restart"; (3) inspect zombie guards completed in two spots — when an entry is retired (not replaced), a waking thread persisted as usual (the ad-hoc path's Timer(10) unconditional retirement + uuid keys never reused: past 300s it was unguarded after just 10s); the guard made strict (an active entry not from this round's instance is discarded, including None); the identity pre-check wasn't re-checked within _persist's retry window (after the pre-check passed, during the ~5s locked backoff a new round rebuilt the same-key entry, and the old worker's final retry still persisted — the pre-check was pierced by its own retry helper, while the post-retry progress-dict write was guarded); _persist re-checks before every replay, throwing _StaleRunError when superseded, caught and discarded at the call site (progress not advanced either: the done share belongs to the new round); (4) run_now's last_run stamping — the locked-time row deletion threw StaleDataError through (the thread had started yet 500; "false failure after start → invisible run" is exactly what the previous round aimed to eliminate; a retry-window variant throws ObjectDeletedError), and the retry synchronously blocked the request thread for up to ~20s (3×busy_timeout + pure sleep, while the pure APScheduler path rewrites once more when the worker finishes anyway); changed to a single attempt + full fallback, failures only logged; (5) once auto-disable now distinguishes manual/scheduled paths — an admin's "run now" smoke test of a future-dated one-time schedule would permanently disable it (the real scheduled trigger would never happen); changed to disabling only on the pure APScheduler path (devs_snapshot is None), with the disable split into its own retry unit + a finally removing the job (a last_run failure must not skip the whole disable block, or it re-fires on schedule); (6) config_backup filtering — colon-garbage fail-open (':' sanitized to '_' matches every timestamp-prefixed name; the comment's fail-closed claim only holds for colon-less garbage); the fallback channel changed to double admission: the sanitized form must contain alphanumeric characters AND colon-forms must have ≥2 non-empty hex segments (':1'→'_1' substring-hits '_16_1_1'-type names — bounded but too broad); case normalization + IPv6 compressed/expanded forms compared by address equality + a matcher factory (query-derived values computed once outside the loop, no more per-file re.sub); prefix collisions no longer silently lumped to one side (marked "prefix conflict" for display); (7) the scheduler page's other form endpoints — invalid types silently 303, time-parse failures bare 400 JSON (reachable by ordinary input; the global handler only softens 403), all changed to ?error= flashes; the error banner switched to the standard .alert alert-error pattern (previously a hand-rolled card + inline styles referencing a nonexistent --red token); during /verify the same class was caught on adjacent paths: integer fields' (schedule_day/interval_hours) `int = Form()` throws a bare 422 validation JSON on non-numeric input (box cleared / abc entered) — int defaults apply only when the key is absent; changed to str + _form_int fault-tolerant parsing (invalid falls back to the default with clamping); all four invalid-input kinds (month-day/interval/type/time) now flash; (8) qc_webhook egress policy (altitude) — the payload carries the QC token while QC_WEBHOOK_URL is env-configurable; one http-public misconfiguration sends the token off-site in plaintext; _post now validates with the same-source _is_private_host as ai_engine (https always allowed / http intranet only), rejecting with a log and skipping the network call; (9) incidental cleanup: _normalize_host single source (validation/judgment copies merged; _is_private_host's dead localhost branch deleted); wants_json shared Accept predicate; the _reject thin wrapper restored (error sites no longer share a magic-key protocol); helpers' exc_info=err replacing hand-rolled triples; query_or_empty takes the Query object directly (four lambda wrappers eliminated); callers' duplicated exhaustion logs consolidated (what carries context); scheduler_page/backup_page narrow columns (no more materializing encrypted passwords); {% set is_admin %} defined once; adhoc.html's guard got the dual keys (the lagging third copy); _light_device_rows extracted for sharing. Verification 42/42 (temp-DB: pinning three states / negative TTL three steps / Host rebuild / refused fallback / redirects both directions / retry-window supersede-discard / retired-entry discard / once by path / StaleDataError fallback / single-attempt stamping / colon double admission six forms / egress policy five states / narrow-column rendering) + production HTTP all green (banner rendering / three endpoints' ?error= flash instead of bare 400 / colon garbage 0 rows / dual-role gating / adhoc dual keys / read-only 403). Recorded as unchanged: promoting the whole egress policy into a standalone egress module (qc_webhook already reuses the same source; full migration deferred) / splitting devs_snapshot semantics into an explicit origin marker

- 2026-08-18: **Review fixes round 15 (post-round-14 regression review, 16 items all confirmed + 6 incidental cleanups)** — re-review of round 14's commit (bd38745) (8 finders → 30 candidates → dedup 16 correctness → 5 verifiers adversarially checked: 15 CONFIRMED + 1 PLAUSIBLE + 0 rejected), all fixed: (1) ai_engine's pinning branch, three high risks — a pure IPv6 loopback (::1-only) host was unconditionally pinned to 127.0.0.1 (the connection goes to a different socket: refused, or worse, the plaintext Bearer key lands on an unrelated service at 127.0.0.1:port), changed to pinning the actually resolved loopback address (IPv4 preferred; IPv6 enters the netloc in [::1] form); bare localhost was exempted from the pinning branch (_is_private_host let it through with zero resolution — the rebinding TOCTOU the previous round claimed closed remained open on the most common hostname), now going through resolution + pinning like *.localhost; u.port throws a bare ValueError on illegal ports (:abc/:99999) and _check_base_url was called outside _call_llm's try (piercing run_agent_turn's RuntimeError catch net, feeding users "internal error: Port could not be cast…" every round), wrapped into an "illegal port" RuntimeError; (2) negative resolution results cached forever (a one-off resolver failure, or configuring the provider before adding a hosts entry, rejected that provider until process restart) — only positives cached (hostname→pinned address; after pinning, connections bypass the resolver, permanently safe), negatives re-queried every time; (3) after pinning, the Host header became 127.0.0.1 (deployments where the local gateway vhost-routes by Host all hit the default vhost 404) — _call_llm explicitly preserves the original Host when the netloc is rewritten; (4) the zombie thread's persistence side effects had no guard (the previous round's entry identity guard protected only the two _progress dict writes; the _persist unit — InspectionRun insert / Device.status overwrite / AlertHistory insert — ran unconditionally before the guard, so a hung SSH thread waking later persisted stale results at the current time with no trace) — an identity check before persistence: if the active entry has been replaced by a new round's instance, the entire stale result is discarded with an alert (an entry retired to None keeps the original behavior; only new-old transitions are blocked); (5) run_now's last_run bare commit leaked out of the retry consolidation (locked after the thread and progress entry were built → 500; the admin sees failure and stops polling while the inspection invisibly finishes in the background) — uses the shared retry, exhaustion only logged (last_run is a display field); (6) the scheduler page's select-all checkbox leaked from the is_admin gating (#batch-del-btn was gated; showBatchBtn's bare null dereference → a read-only user clicking select-all always throws TypeError) — the checkbox brought inside the gate + a JS null guard, double insurance; (7) config_backup's orphan-IPv6 filter regression (after the previous round's real-IP reverse lookup, backups of deleted devices fell back to the lossy '2001.db8..1' restoration; colon-form queries never matched) — colon-containing queries fall back to comparing against the sanitize prefix encoded the same way as the file names (colon-forms only; the garbage value '%' stays fail-closed); the reverse lookup order_by(Device.id) for a deterministic order (collision lumping no longer drifts across requests) + takes only the ip column (no more materializing encrypted passwords); (8) _json_or_redirect generalized and consolidated (the fifth Accept sniff of run_now's success path absorbed too); the redirect branch carries a ?error= flash into the list page's error banner (previously form-POST errors silently bounced, the same class as this round's AJAX silent-failure fix); (9) _run_scheduled's schedule-side TOCTOU (the device snapshot fixed the device side, but the thread re-queries sched.enabled: a schedule disabled/deleted between validation and thread start still produced a done:true/progress:null fake-completion tombstone) — the snapshot path is treated as a validated one-shot request and runs; a missing sched only skips the last_run write-back; (10) incidentals: _run_batch's exception-fallback retirement gained an expected=entry identity guard (the same function's _clean thread had a fallback; this one didn't); helpers' retry-exhaustion log gained a traceback (the old logger.exception's stack was lost in the consolidation; a NULL next_run left only a one-line stackless error) + the backoff gained jitter (N threads locked, marching in step and re-colliding); base.html's triggerInspect guard got the err.error dual keys (drift with scheduler.html eliminated — a {error}-shaped 400 used to show only a bare "HTTP 400"); the render fallback consolidated into helpers.query_or_empty (custom_cmds logs / ping silently swallowed — unified to log, with per-query independent fallback) + the ping page's query narrowed to three columns; scheduler.html's stale comment corrected. Recorded as unchanged: consolidating the localhost policy into an ipnorm module / a unified read-only gating mechanism / crypto's priority-3 icacls copy / commit retry-contract consolidation, and other standalone cleanups (next round's review candidates). Verification 31/31 (temp-DB: pinning four states + port guard + cache positive/negative / Host preservation / exhaustion traceback / snapshot TOCTOU disable + delete / _json_or_redirect three forms / zombie-thread persistence guard / colon query dual hit + fail-closed / fallback helper) + production HTTP all green (dual-role gating precise-marker re-probe / form 303→?error=→banner render / AJAX error shape / read-only token 403 / fail-closed probes)

- 2026-08-17: **Review fixes round 14 (post-round-13 regression review, 6 reported items + 7 late items)** — re-review of round 13's fix commit (9920f1d) (8 finders + inline adversarial verification, 6 reported; a late finder agent added 7, all included after dedup), fixed: (1) scheduler.html's runSchedulerNow missed round 12 item 10's resp.ok guard — after run-now was raised to require_admin, a non-admin clicking gets 403 {detail} (no error key); the frontend wrote the string "undefined" into localStorage and polled /inspect/status/undefined, and base.html's resume logic replayed the fake polling on every page load (a twin copy of base.html's own bug back in the day); added the resp.ok interception, the error text compatible via the err.error || err.detail dual keys; (2) execute_multi's fallback leaked on two paths: it only caught OperationalError — when a device was deleted mid-execution, commit threw StaleDataError/FK IntegrityError piercing through as 500 (verification reproduced StaleDataError); and the post-fallback render query still ran on a possibly-dead session (the rollback swallowed by except-pass), still 500 — non-locked exceptions also fall back now + the render query falls back to an empty list; a completed batch's SSH results are no longer lost on either path; (3) *.localhost's loopback validation happened only once at config-check time; urllib re-resolves DNS at connection time — a rebinding TOCTOU could let the Bearer key leave the machine in plaintext; _check_base_url now returns a pinned URL (*.localhost, verified all-loopback, replaced with 127.0.0.1 — connections no longer pass through the resolver); incidentally fixed the ValueError crash for scoped IPv6 (fe80::1%eth0), a newly introduced crash class; resolution results cached by hostname (_check_base_url runs every LLM round; repeated getaddrinfo under a slow resolver would drag down conversations); (4) _backup_host_prefix's "sole definition point" in name only — the real backup writer (repo-root inspection.py) kept an inline copy; the helper moved into helpers.py as the single source (config_backup's three spots + config_compare share it), the docstring honestly noting that external writers must sync; (5) the third hand-written SQLite-locked retry unit (inspect._persist / execute_multi._persist_all / load_all_schedules) consolidated into helpers.commit_with_locked_retry — the subtlety that rollback discards pending objects and the whole unit must be replayed (round 12's MULTI-2 got this wrong once, verified) no longer needs re-deriving by every writer; load_all_schedules's inner per-schedule except no longer swallows OperationalError (a lazy refresh of rollback-expired objects hitting locked was once misclassified as a single registration failure, and an empty commit succeeding just broke out — schedules never register and next_run stays NULL); (6) run_now's four in-function Accept sniffs + a local import JSONResponse consolidated into a _reject helper; (7) late items: run_now hands the already-validated non-empty device snapshot directly to the worker thread (eliminating the empty-device fake-completion tombstone TOCTOU where devices are deleted between validation and the thread's re-query); _run_scheduled's pure-APScheduler empty-device branch gained a warning log (round 13 item 11 only added the exception path); _inspect_one gained an entry identity guard (periodic jobs reuse the sch_{job_id} key + a thread pool with wait=False; a previous round's hung SSH thread waking later once wrote done+=1 and results into the new round's entry); the scheduler page's six write controls is_admin-gated (non-admins now truly read-only — no more clickable buttons that jump the whole page to a 403 JSON; the devices page's same-class item stays deferred per round 12); crypto's priority-3 migration path's chmod sharing a try with the file write (a same-source copy of the priority-4 issue) split to else with a warning only; ping _render's device-query failure falls back to an empty list (subprocess results first) and ping_page reuses _render; config_backup's list now reverse-looks-up real IPs from the device table — the frontend exportSelected's lossy-restoration match missing meant IPv6 backup exports were unreachable from the only UI entry (round 13 item 6 fixed only the server side); the list's garbled IPv6 column and the garbage filter value's fail-open fixed together. Recorded as unchanged: sanitize prefix collisions (1.2.3.4 and 1:2:3:4 both map to 1_2_3_4) — the collision lives at the disk file-name level, the writer is the untracked inspection.py, and one-sided charset changes would orphan existing backups. Verification 30/30 (direct temp-DB: shared helper three states / snapshot TOCTOU / retry replay / StaleDataError fallback / dead-session render fallback / entry identity guard / localhost pinning + cache + scope guard / migration chmod / real-IP reverse lookup + fail-closed) + 14/14 (production HTTP regression) + surface /verify PASS (dual-role gating / four error shapes / mtr rendering / zero-production-write probes)

- 2026-08-17: **Review fixes round 13 (post-round-12 regression review, 11 items = 10 fixes + 1 incidental)** — re-review of round 12's fix commit (321620f) (baseline→current cumulative diff, 27 files, 8 finders + item-by-item adversarial verification, 10 confirmed/suspect taken as 10), all fixed: (1) the scheduler's six write endpoints (add/toggle/delete/run-now/edit/batch-delete) were still require_auth — the README permission matrix declares scheduled tasks an admin module; ordinary logged-in users could add/delete/modify/run-now any inspection schedule (round 7 had unified the devices/commands/push modules; this module escaped); all raised to require_admin (the page GET stays require_auth, read-only viewable); (2) execute_multi's three-retries-then-locked raise re-threw db_error as-is — the SSH work was all done, and one 500 threw the whole successful batch's results (all devices' outputs) away from the user, visible only in logs; changed to a degraded render: results shown as usual + a "not saved to inspection records" banner at the page top (same strategy as inspect.py's db_error degradation); (3) when a device IP was edited mid-inspection, _inspect_one overwrote the progress-key snapshot with the live dev.ip — the old-key entry stayed in devices with no one updating it, the frontend showed a ghost card forever "waiting", and the new key wasn't in progress so its results were invisible too; dev_key now prefers the snapshot (the live value only when None); (4) run_now returned 200 + run_id for schedules whose bound devices were all deleted; the worker retired the progress immediately, and the frontend polled a done:true/progress:null fake-completion tombstone (zero devices, no error); the endpoint now pre-checks with 400 "this schedule has no devices to inspect"; (5) load_all_schedules' startup path batch-registers + a single commit with no retry against SQLite locked (concurrent with backup/cleanup tasks) — the job was already in APScheduler while next_run stayed NULL forever with no page hint (round 10's batching simplified away round 8's per-entry tolerance); added 3 locked retries (rollback discards the pending next_run assignments, so the retry replays the whole registration+commit unit; _register_schedule is idempotent), and on failure a full rollback with logging; the schedule page gained a warning badge for "enabled but next_run empty"; (6) the configuration-backup file-name host prefix drifted between two writers: backup writes used the full-charset sanitize (re.sub) while export_zip/list filtering/config_compare used ip.replace('.','_') replacing only dots — IPv6 devices' (containing ':') backup files were missed in ZIP exports, unmatched by device filter, unloadable on the comparison page; consolidated into config_backup._backup_host_prefix, one definition shared by four sites; (7) ping_post queried all devices at the request start, then the mtr/tracert subprocess ran up to 35s — the ORM result set held its Session/connection for the whole subprocess duration; a few concurrent traces could exhaust the small connection pool; the devices query moved into a _render helper, queried only at render time; (8) _is_private_host let *.localhost hostnames through unresolved for plaintext http — RFC 6761 says the localhost domain should resolve back to the machine but depends on resolver config; if "evil.localhost" pointed at the public internet, the Bearer key went out in plaintext with it; now only localhost itself passes directly, *.localhost requires all getaddrinfo results to be loopback; (9) crypto's key bootstrap (priority 4) had permission hardening (chmod/icacls) and the file write in the same try — a hardening failure triggered a fallback that wrote the same new key again to the legacy location (two residues), with the log falsely claiming "falling back to legacy"; refactored so only mkdir/write failures go to the legacy fallback, hardening failures only warn; (10) the P12 download form's password had no frontend constraint — short passwords (<8) were rejected 422 by the backend, and the target=_blank tab showed a bare JSON error; the input gained minlength=8 + a hint (backend validation unchanged, double insurance); (11) incidental (a find by another recovered old review agent during the re-review): _run_scheduled's outer fallback was entirely silent on the pure APScheduler path (run_id=None) — device/schedule query failures during scheduled inspections left no log trace at all; the except branch now always logs, the run_id guard only retires progress. Verification 26/26 (direct temp-DB: require_admin counts / empty-device 400 no progress / locked retry replay then next_run truly persisted + job registered / all-persistence-failure degraded render no 500 / IPv6 prefix export + filter + comparison load / localhost resolution four ways / chmod failure no double legacy write / minlength form / always-log ordering) + 14/14 (production HTTP regression)

- 2026-08-17: **Review fixes round 12 (cumulative re-review of rounds 8-11, 10 items)** — re-review of the cumulative diff from the 2026-08-12 baseline to 2026-08-17 (26 files) (8 finders + item-by-item adversarial verification, 12 confirmed took 10; 2 minor UX residues deferred), all fixed: (1) _is_private_host's ipaddress.is_private test was too broad — TEST-NET (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24), the benchmark range 198.18.0.0/15, and 192.0.0.0/29 were all judged private and allowed plaintext http, sending the decrypted Bearer key to non-RFC1918 addresses; changed to an explicit _ALLOWED_HTTP_NETS range table (RFC1918 + loopback + IPv6 ULA); (2) _exec_show's placeholder audit row (status=executed) committed first, with `dev = session.device` resolved after and outside the try — a resolution error (e.g. a lazy-load failure after concurrent session deletion) left a fake audit recorded as executed though never executed, and the rate-limit slot unreleased; device resolution moved before the placeholder commit; (3) execute_multi's round 8 consolidated per-device commits into one final commit but without inspect.py's locked retry — with concurrent writes from scheduled inspections, SQLite locked threw the whole batch (all devices' InspectionRun + Device.status) away in one 500; added 3 retries, and because rollback discards already-added pending objects, the retry must replay the whole "persist+commit" unit (the first fix only retried the commit itself and was caught by verification: the retry succeeded yet zero rows persisted); (4) _run_batch's retirement-cleanup thread sleeps len(devices)*60 seconds then unconditionally calls retire_progress — periodic jobs reuse the sch_{job_id} key, so when the sleep exceeded the job interval (e.g. a 100-device hourly job sleeping 6000s > 3600s) the previous round's sleeper tombstoned the next round's in-flight run (device details all lost, the status page falsely complete); retire_progress gained an expected identity parameter, retiring only after confirming under the lock that the entry is still the instance this run created; (5) dashboard and /api/dashboard/stats' last_time had no NULL guard on timestamp — the column is nullable (round 9's RunResponse change to Optional already acknowledged such rows exist); an all-NULL scenario made strftime throw AttributeError and 500 the whole site; both spots null-checked (note: SQLite DESC sorts NULLs last, mixed rows unaffected); (6) _rate_ok (the show path) counted by created_at while the confirm re-check counted by executed_at — executions after confirming a stale card were invisible to the show limiter; the two limiters each passing 6 could actually reach 12/minute, and a same-minute propose+confirm was double-counted; _rate_ok unified to executed_at, making the comment "the two limiters must agree" real; (7) ConfigExecError took partial output via getattr(ex, 'output', '') — .output is a subprocess.CalledProcessError attribute; no netmiko 4.x exception has it (4.2/4.7 sources checked), so partially-applied config pushes never got device output, defeating the class's purpose; changed to a best-effort read_channel() after the exception to recover the channel residue; (8) execute_multi's pool.submit dict-comprehension throwing mid-way (pool broken/resource exhaustion) threw away the submitted devices' SSH results and all audits with a 500; changed to a per-device try, recording "task submission failed" for one device and continuing the batch; (9) run_now returned 200 + run_id for disabled schedules; the worker retired progress in milliseconds, and the frontend polled a done:true/progress:null fake-completion tombstone (the user's manual run never actually happened, with no hint); the endpoint now pre-checks with 400 "schedule is disabled"; (10) base.html's shared triggerInspect (used by the devices/dashboard/_stat_cards pages) missed round 7 K5's 404 semantics update — it checked only data.error, not resp.ok; clicking inspect with zero devices wrote the string "undefined" into localStorage and polled /inspect/status/undefined, swallowing the real error "no devices to inspect"; the resp.ok interception added. Deferred (minor UX residue): the P12 short-password bare 422 JSON page; the devices page's forms lacking is_admin gating for non-admins (403 only on submit). Verification 18/18 (direct temp-DB: range table both directions / executed_at counting both ways / dev resolution order / read_channel partial output / submit-failure batch preserved / locked retry truly persisted / expected-identity retirement / all-NULL dashboard / disabled 400 / base.html interception) + 14/14 (production HTTP regression)

- 2026-08-17: **Verification fixes round 11 (found by live production testing, 1 item)** — while /verify drove the production HTTP surface: an enabled schedule's next_run always showed "—"; the production DB has the field NULL, and every restart's app logs show `failed to register scheduled task id=3 / AttributeError: 'Job' object has no attribute 'next_run_time'` — main.py's load_all_schedules() runs before scheduler.start(), and pending jobs have no next_run_time attribute; this startup path had never succeeded since round 7 S1 introduced the next_run field (every temp-DB verification missed it: the test process imports backend.main with the scheduler already started, a different startup order than production; scheduling itself is unaffected, only the display field is empty). Fix: _register_schedule computes the next fire time directly from trigger.get_next_fire_time when the job has no next_run_time (pending), no longer depending on the scheduled job. Verification 6/6 (temp-DB reproducing the production startup order: load_all_schedules without a started scheduler persists next_run=next day 06:00 / the started-scheduler main path regresses and matches APScheduler's own computation) + a production check: DB next_run=2026-08-18 06:00:00, the schedule page's "day" row renders 08-18 06:00, no new registration failures in the restart logs

- 2026-08-17: **Review fixes round 10 (post-round-9 regression review, 4 items)** — the re-review confirmed 4 new findings on round 9's commit (f2b1de9) and fixed all: (1) when a device is deleted mid-inspection (or the Device query hits SQLite locked), round 8's fix for ghost numeric keys skipped the failed path's per-device write entirely — done still incremented, but that device's card stayed "waiting" forever, the failure completely invisible in the UI, and operators would trust incomplete results as complete; _inspect_one now takes an ip_hint parameter (the caller already knows the id→ip snapshot when initializing progress, passed through both batch paths _run_inspection_sync and scheduler._run_batch), writing the "device deleted" error into the real ip entry on device-load failure; (2) the confirm path's rate-limit re-check still counted only executed/confirmed, forking from round 8's tightened _rate_ok (the show path, including failed) — a confirmed card whose execution turned failed released the confirm-side slot while still occupying the show side; during failure bursts, dense confirm operations could exceed the device protection rate; both limiters now count failed with the same policy; (3) load_all_schedules' round 8 became per-entry _register_and_persist (one commit per entry) while expire_on_commit defaults on — every commit expires all ORM objects in the session, forcing later iterations' attribute reads into lazy re-SELECTs (N schedules = N commits + N-1 refreshes; registrations are independent with no transactional benefit); the startup path restored to batch registration + a single commit (registration exceptions still isolated per entry; a commit failure rolls the whole thing back), the endpoint path keeping _register_and_persist's per-entry immediate-persistence semantics; (4) save_inspection_run's commit flag used to flip the return type (True→None / False→run) and its only commit=False caller never used the return value — the dual shape was dead generality and a misuse trap; now always returns the run object. Verification 11/11 (direct temp-DB: deleted device writes the real-ip error entry / no hint produces no ghost key / key_map wired through both batch paths / failed occupies the confirm slot / single commit / next_run persisted / rollback regression / both paths return run) + 14/14 (production HTTP regression)

- 2026-08-14: **Review fixes round 9 (round 8 regression review, 10 items = 9 fixes + 1 recorded)** — re-review of round 8's fix commit (c88d6f1) (8 angles, 10 confirmed), all handled: (1) _register_and_persist swallowed commit failures without rollback — in load_all_schedules' single-session loop, one failure (SQLite locked) poisoned the session and all later schedules failed in a chain, while the job was already registered in APScheduler (the "not registered" badge wouldn't flag it) and next_run was never persisted; the except now does db.rollback() before logging, and the session remains usable; (2) the DecryptError wrapping added in round 8 sat at the encrypt/decrypt call sites, but get_secret_key_bytes (the HMAC URL signing for cases) still leaked a bare ValueError 500 — the wrapping consolidated inside _get_fernet (the actual resolution split into _resolve_fernet), taking effect for all current and future callers in one place; (3) execute_multi's timeout/exception branches constructed a timeout error result but set conn_error to None, so never-connected devices were persisted with status=connected (the dashboard showed unreachable devices as healthy) — the timeout error string now also goes into conn_error and the status is persisted as error; (4) RunResponse's cpu/memory/uptime/hostname/status/timestamp were declared non-Optional but the DB columns are nullable (defaults only on the Python side) — a single NULL row from history/manual DB surgery once 500'd the whole /reports/api (the old _run_dict could serialize null); now all Optional; (5) _run_scheduled's outer fallback used to tombstone-retire runs where "_run_batch had succeeded, only the last_run/next_run commit failed" too (a client polling an actually-successful run would lose every device's details) — the batch_done flag narrows the retirement scope to failures before _run_batch took over; (6) the per-session rate-limit lock table _rate_locks had no reclaim path (soft-deleted sessions' locks lingered forever, slow memory growth in a long-lived process) — drop_session_locks reclaims both the seq and rate-limit lock tables when delete_session runs; (7) the (label, command) normalization was copied in three drifted places (the c.get('description') vs c['description'] KeyError risk) — consolidated into a single _cmd_pairs definition; (8) resolve_provider's RuntimeError→400 fallback copied in three places consolidated into _provider_or_400; (9) _session_rate_lock and seq_lock, byte-level duplicates, consolidated into a _keyed_lock factory. Recorded as unchanged: /reports/api timestamps stay ISO-8601 (consistent with the long-standing pre-round-7 format; the space-separated format existed only for a few days between rounds 7 and 8, with no in-repo consumers). Verification 20/20 (direct temp-DB: bad-key three paths' DecryptError including get_secret_key_bytes / session still usable after commit failure / timeout conn_error persisted as error / raw-SQL NULL rows no longer 500 / lock-table reclaim / 400 via the wrapper / failed-count regression) + 14/14 (production HTTP regression)

- 2026-08-14: **Review fixes round 8 (round 7 regression review, 25 items)** — re-review of round 7's fix commit (3d7a38c) (8 angles, 40 candidates, dedup 25), all fixed — mostly regressions and unfinished business of round 7's own fixes: (1) _is_private_host's rewrite hurt both ends — localhost/*.localhost hostnames were rejected by ipaddress resolution, bricking local model gateways (http://localhost:11434); meanwhile is_private's breadth let the link-local range 169.254.0.0/16 (including the cloud metadata 169.254.169.254) and 0.0.0.0 through as "intranet" allowing plaintext http; now explicitly allows loopback + localhost hostnames, excludes link-local/multicast/unspecified/reserved; (2) failed show commands that turned into failed weren't counted by _rate_ok, so when a device was down the rate-limit slots stopped working instead (contradicting its own comment) — failed now counted; (3) the process-level _rate_lock's global serialization changed to per-session locks; (4) resolve_provider's key-mismatch RuntimeError was uncaught at three endpoints (chat/session creation/provider switch) becoming 500 — uniformly wrapped into 400 JSON; (5) execute_multi still passed ORM CustomCommand objects into worker threads (C2 had converted only Device) — the request thread pre-materializes pure dicts, run_commands_on_device's contract changed to a (results, conn_error) tuple with cmds normalized at the entry, and connection failures changed from "string-prefix sniffing" to a data return; (6) decrypt/encrypt's _get_fernet() calls brought inside the try — a malformed INSPECT_SECRET_KEY's bare ValueError is uniformly wrapped as DecryptError (no longer escaping from the narrowed except into a mid-batch 500); (7) _run_scheduled regained its outer exception-retirement fallback (lost when R2 was extracted; run-now's DB-query failures once leaked progress entries permanently); (8) custom commands' /delete and /toggle raised to require_admin (V2's escape); (9) next_run converted with astimezone(CST) before writing to the DB (in a UTC container, hourly schedules were once 8 hours off); (10) the K4 fallback's progress-key ghost entries fixed (on device-load failure, no longer keyed by numeric id; real entries no longer stuck waiting); (11) dashboard's redundant latest query deleted in favor of all_runs[0] (that query also missed defer raw_data); (12) the three copies of /register consolidated into _register_and_persist; (13) count_all_schedules merged into load_all_schedules returning (registered, total) in a single session; (14) the scheduled/default-inspection device queries changed to fetch only the id/ip columns; (15) main.py's leftover CST copy deleted; (16) /reports/api restored to ISO-8601 timestamps (now via schemas.RunResponse + config_backup extension fields, raw_data still excluded); (17) the cases search's silent limit(500) truncation changed to a 501 probe + a template banner hint; (18) the configuration-backup file-name parsing consolidated into _parse_backup_name (list_backups and export_zip share one implementation); (19) the ping template's devices or [] defensive; (20) the scheduler page shows a warning badge for schedules that are "enabled but not registered (invalid config)"; (21) the _stage_inspection_run copy deleted, helpers.save_inspection_run gains a commit parameter; (22) _inspect_one's three error dicts consolidated into _fail; (23) the decryption-failure result dict consolidated into _key_mismatch_outcome. Verification 30/30 (direct temp-DB: localhost/link-local / failed counting / per-session locks / 400 wrapping / DecryptError wrapping / the tuple contract / commit=False / the retirement fallback / astimezone / the ISO format, etc.) + 14/14 (production HTTP regression)

- 2026-08-13: **Review fixes round 7 (full code review, 45 items)** — a full review of HEAD (f6de53c) (8 angles, 46 candidates, dedup 45, adversarial verification 44 confirmed + 1 suspect), all fixed: (1) read-only token privilege-escalation closed: configuration comparison's load-config and the /reports endpoints (including the raw_data raw inspection payloads) changed to require_full_user; the read-only token went from 200 to 403; (2) the AI base_url's intranet check changed to ipaddress resolution — DNS names like "192.168.1.1.attacker.com" are no longer misjudged as intranet by startswith, letting plaintext HTTP carry the API key out; (3) CA private key downloads (PEM zip/PKCS#12) escalated to require_admin (permission-inversion fix), the P12 password now required with min_length=8 (the hardcoded default "changeme" removed); (4) the README's declared admin modules made real: the write endpoints of device CRUD/custom commands/configuration push unified from require_auth to require_admin, and the cases module dropped its hand-written copy in favor of auth.require_admin; (5) the ping page no longer 500s on any POST (the template unconditionally iterated devices while the POST branch never passed it); (6) the CA page no longer 500s once revoked certificates exist (ca_page now passes now); (7) decrypt_password now raises DecryptError when ENC ciphertext decryption fails (all 8 call sites catch it and give the explicit "key mismatch" error), instead of feeding the ciphertext to SSH as the password and causing misleading authentication failures across the board; _get_fernet gained a lock to close the race where two threads each generate different keys on first run (file/memory forking; after restart nothing decrypts); (8) scheduled tasks: a once date that fails to parse no longer silently falls back to daily 06:00 — invalid times are rejected 400 before submission (previously 500 only at registration after submission, leaving rows that never run); "disable all" no longer triggers the "no schedules → default daily 6 a.m. network-wide inspection" fallback revival (now judged by whether the table is empty); the next_run field is really written/cleared on disable (previously defined but forever NULL, the UI always showing -); (9) main.scheduled_inspection and scheduler._run_scheduled's duplicate batch executors consolidated into a shared _run_batch, and the four progress initializations into _init_progress (eliminating "waiting"-label drift); (10) inspection: device loading/decryption/custom-command queries moved inside progress protection (exceptions no longer leave the frontend stuck waiting forever), an unknown device_id returns 404 instead of 200 with no run_id (the frontend no longer polls /inspect/status/undefined), and custom-command execution reuses custom_cmds.run_commands_on_device (eliminating the fifth decrypt+ConnectHandler copy, incidentally fixing the BMC device generic mapping and timeout drift); (11) execute_multi no longer passes request-scoped ORM objects into the thread pool while committing inside the same Session loop (DetachedInstanceError race) — changed to pre-fetched pure dicts + a single commit outside the loop; the thread pool abandoned the with block for shutdown(wait=False, cancel_futures=True); (12) AI: reject changed to an atomic conditional UPDATE (the confirm race no longer produces "device configured but the audit says rejected"); the rate-limit re-check changed to counting by executed_at execution time (a new column + an idempotent migration; old proposals no longer bypass the 6/minute execution cap); the show-command rate limit changed to an atomic in-lock slot claim; empty command steps are filtered up front and an all-empty errors out (no longer sending "" to the device); execution exceptions keep partial output (carried by ConfigExecError) instead of misreporting a partially-applied change as a clean failure; (13) efficiency: dashboard trends and the /reports list defer(raw_data) (no longer loading up to 500 full CLI texts at a time), the CSV export gains joinedload killing N+1, the cases count changed to GROUP BY (two places), and the inspection custom-commands reuse the connection helper; (14) misc: CA/certificate private key files chmod 0600 + directory 0700, the config export ZIP's device prefix changed to rsplit fixing IPs ending in .202 being truncated and lost, the three divergent copies of the memory-coloring logic consolidated into _mem_color (consistent N/A handling), the three duplicate CST timezone definitions consolidated into models, config_push's command parsing/error re-rendering deduplicated (9 copies), bom_matcher's dead branches and inspect's dead code deleted, and the salt-length comment corrected. Verification 29/29 (direct temp-DB + wiring) + 12/12 (production HTTP probes: ping POST/trace/CA page/read-only token 403/404/422). The only structural skip: the dual SSH handshakes of inspection and custom commands (the first connection lives in the untracked external inspection module; this round couldn't consolidate it)

- 2026-08-13: **Containerization v5 and deployment docs** — built `network-inspection:v5` from HEAD (e714245) (=latest, 277MB, 3-second cached build); a temporary container mounted on a consistency copy of the production DB completed 11 verifications (login/devices page/leading-zero 400/duplicate 409/port 422/form backfill/image has no keys and no DB/code hash matches HEAD); the production uvicorn untouched throughout; the compose image tag v4→v5; three new docs: `docs/docker-build-v5-verify-2026-08-13.md` (build verification record) / `docs/docker-compose-runbook-2026-08-13.md` (runbook: pre-creation checklist/mount table/initial password/bare-process-to-container switch/troubleshooting quick reference) / `docs/dockerfile-explained-2026-08-13.md` (line-by-line Dockerfile explanation); the README Docker deployment section rewritten to the v5 status quo (the old section's image name/ports/mounts were all outdated)
- 2026-08-12: **Verification findings wrap-up (3 items)** — (1) validation errors on the form path (leading-zero IP/empty IP etc.) previously showed a bare FastAPI JSON page; now uniformly rendered into the devices page error banner with the entered fields backfilled, consistent with the duplicate-IP conflict page experience (the API path keeps JSON unchanged); (2) the edit modal's 422 hint changed from the whole JSON blob to a readable "field: message" format (e.g. `port: Input should be less than or equal to 65535`); (3) stripped the UTF-8 BOM from main.py. Verification 5/5: form validation banner + backfill ×2 / API JSON regression / readable UI alert / empty-port retention regression
- 2026-08-12: **Review fixes round 6 (device management wrap-up, 10 items)** — (1) clearing the port in the edit modal now sends null (the server keeps the current value) instead of being silently changed to port 22 by parseInt||22; invalid/out-of-range input is sent as-is for the server's readable 422, the frontend no longer silently alters values; (2) leading-zero IPv4 (010.0.0.1, the octal-ambiguous form) uniformly rejected 400 on the three write paths — previously it fell into the hostname bypass, slipping past both the application duplicate check and the unique index; (3) the 1-65535 port range validation consolidated into the pydantic schema (DeviceCreate/DeviceUpdate both Field(ge=1, le=65535)); the create path no longer accepts arbitrary ports, the form path keeps the banner hint; (4) edits with an unchanged IP skip the duplicate check — devices on pre-existing duplicate-IP rows previously got 409 forever on editing any field, with no UI repair path; (5) three hand-written commit→IntegrityError→rollback→recheck blocks consolidated into an _commit_or_ip_conflict helper; a recheck miss (non-ip constraint) logs and returns a redacted 400, no longer bare-raising the raw SQL as a 500; (6) startup migration first probes with PRAGMA for an existing unique index and exits early (fresh installs no longer build a second unique B-tree; old databases no longer full-table-scan at every startup); (7) update restored the "all validation (400/422) before conflict (409)" order; (8) the strip+ipaddress normalization consolidated into a shared backend/ipnorm.py (write-path validation and the startup migration share one implementation in a single loop; rule evolution can no longer drift in two places); (9) when the migration finds duplicate IPs it returns a flag and the devices page shows a "unique index not enabled, please deduplicate manually and restart" banner — the concurrent backstop failing silently is no longer unnoticed; (10) the edit modal's device type switched to the dtype_options macro (same data source as the add form); new types no longer maintained in two places. All 23 verifications passed: leading-zero 400 with nothing persisted / out-of-range port 422×3 / null port retained / duplicate-row edit allowed + changing to a duplicate still 409 (real code on a temporary DB) / commit helper 409 + redacted 400 / index probe and early exit (no full-scan logs) / banner renders by flag / macro options ×2 / concurrent double-write exactly one row / Playwright empty port sends null and 422 shows a readable alert
- 2026-08-12: **Review fixes round 5 (device management hardening, 10 items)** — (1) Device.ip gained a UNIQUE constraint + an idempotent startup migration (first normalizes existing IPs, then adds the unique index; on finding duplicates it only warns and skips the index), and write paths catch IntegrityError into 409 — concurrent double-writes of the same IP no longer both persist (the application-level check had a check-then-insert race window); (2) IPs normalized at the validation boundary (strip + ipaddress canonical form: IPv6 compressed lowercase / leading zeros removed); textual variants like "10.0.0.1 " (trailing space) and "FE80::0:1" no longer bypass the duplicate check; non-IP literals pass as hostnames; (3) an empty string/null password on device edit means "no change" (previously an empty string was written to the DB in plaintext, making the device forever unauthenticated, and null triggered an IntegrityError 500); (4) clearing the port in the edit modal no longer writes NULL (JS parseInt NaN→22 fallback + the server drops None + 1-65535 range validation); (5) an empty/whitespace-only IP is an immediate 400 (previously devices with an empty IP could be created); (6) the edit modal renders FastAPI 422's detail object array as JSON (the alert previously showed [object Object]); (7) the edit endpoint restored the "validate first, then duplicate-check" order (invalid input no longer receives a 409 before the 400); (8) on a duplicate-IP echo the form backfills the entered ip/type/username/port (the password is not echoed), no longer requiring a full re-entry; (9) the duplicate-check logic consolidated into a single _find_duplicate_ip query implementation + a unified conflict message; the form and the API no longer each write their own; (10) the devices page rendering consolidated into a unified _render_devices entry. All 16 verifications passed: unique index / concurrent double-write exactly one row (200+409) / space and IPv6 variants 409 / empty IP 400 / empty password-port semantics / validation order 400 / form backfill / Playwright readable 422 hint and cleared-port fallback
- 2026-08-12: **Device management duplicate-IP check** — the three write paths (add device (form + JSON API) and edit device changing IP) previously had no conflict check; duplicate IPs were silently created, scrambling the attribution of inspection results/config push/backup files; now a unified application-level duplicate check: the form path echoes a 400 error banner "IP address x already exists (device #n)" and keeps the form expanded; the API returns 409 Conflict with the conflicting device's info; the edit modal shows the server error details (previously only a generic alert); edits keeping their own IP are not falsely flagged (exclude_self). All 10 verifications passed: form duplicate 400 + not created / unique 303 regression / API create 409 / edit to duplicate 409 / edit to unique 200 / self-edit no collision / page render regression
- 2026-08-12: **Review fixes round 4 (10 items+1)** — (1) config_push's single-device decryption failure now records only that device's failure audit and the batch continues (previously the request thread was undefended and the whole batch aborted); (2) _run_scheduled gained a cleaned flag + a finally fallback retirement; an error thrown before the cleanup thread starts no longer permanently leaks run_id progress entries; (3) main's scheduled inspection abandoned the with thread pool (a hung netmiko session would leave __exit__'s wait=True blocking the APScheduler thread forever), aligned with scheduler on shutdown(wait=False, cancel_futures=True); (4) config_push's audit changed to 5s incremental harvesting with immediate persistence (previously hung threads delayed the audits of completed devices until the global budget expired; a process restart during that window = real config changes with no record); (5) confirm actions intercept devices already deleted before the atomic claim (previously pool.exec_config(None) crashed 500); (6) when the model still returns empty after the fallback retry, SSE reports an error prompting retry instead of storing an empty bubble in the chat history; (7) the fallback protocol supports single-line code blocks (```run show version``` previously failed to match entirely due to the forced newline, and commands were silently dropped); (8) a transient confirmation-card failure (5xx/network error) makes the restore button retryable without terminal locking (only 4xx stays terminal; retries are safely intercepted by the "already processed" 400); (9) the chat worker's SessionLocal moved into the try + SSE's q.get gained a 30s timeout and worker-liveness detection; a silently dead worker no longer leaves the frontend waiting forever; (10) auto-renaming only matches the exact default title (previously endswith("Chat") overwrote titles users had manually renamed to "xx Chat"). Also fixed: the inspection panel's polling recognizes 401 → "login state expired" and stops. All 20 verifications passed: single-line/multi-line code-block parsing / exception retirement tombstone / bad-device batch continues with both audits / deleted device 404 not claimed / mock LLM empty response errors without storing a bubble / single-line run block executed on a real device and persisted / title both branches / Playwright confirmation card 500 + offline + 400 three states / 401 panel / run-now happy path regression
- 2026-08-12: **Review fixes round 3 (12 items)** — (1) config_push's global budget scales by wave (ceil(device count/workers) × the worst single-wave path); with more than 10 devices, legitimately queued pushes are no longer falsely reported as hung; the audit distinguishes "not executed (cancelled, device untouched, safe to retry)" from "suspected hung (state unknown)"; the push threads switched to pure-data dicts (after the request thread's commit expires ORM objects, a zombie thread's lazy refresh would silently drop audits); (2) the three cleanup paths of scheduler run-now/scheduled inspection/main's scheduled inspection unified through retire_progress tombstone retirement; a running inspection is no longer falsely reported 404 "expired"; (3) LLM API key protection: a non-https base_url allows only localhost/intranet (preventing the Bearer key going out to the public internet in plaintext); cross-host 302 redirects strip the Authorization header (urllib re-sends it by default); (4) inspection failures no longer overwrite the device's real hostname with the placeholder 'N/A'; (5) persistence failures visible to the frontend: db_error is redacted, rendered, and counted into "inspection complete (with failures)" (previously data silently dropped + alerts swallowed; the raw text contains SQL/parameters that would leak to the read-only token); (6) the inspection panel's device outputs (cpu/mem/alerts) all escaped, closing stored XSS from device output → innerHTML; (7) the commands and outputs executed by the fallback text protocol are persisted (previously lost on refresh; the next round's LLM lost the context); (8) propose_config returns a corrective error when steps is not an array of objects, letting the model retry (previously an AttributeError killed the whole round); command/purpose normalized to strings; (9) message seq assignment gained a per-session lock (two tabs sending concurrently no longer produce duplicate seqs); (10) device output shown to the LLM truncated to the same length as the audit (show-run-level output was once re-uploaded in full across 8 tool rounds, ~8x token amplification; the frontend tool block still displays the full text). All 20 verifications passed: key protection 7 cases + 302 live test / real-device push / failed inspection hostname retained / run-now full lifecycle / concurrent seq unique / persistence-failure injection / XSS probes / real chat regression
- 2026-08-11: **Inspection status semantics and AI card consistency fixes** — (1) /inspect/status introduces a finished-tombstone table (_finished_runs, TTL 1h): a nonexistent/expired run_id returns 404, a completed-and-cleaned one returns done:true (previously both returned done:true, indistinguishable, and callers would treat a made-up run_id as "completed"); the frontend's polling recognizes 404, shows "inspection has ended" and stops (previously it would spin empty for 5 minutes and then falsely report "inspection timeout"); (2) reject of an already-processed card aligns with confirm, returning 400 "this card has already been processed (status)" (previously a silent 200 idempotent success; the two endpoints' state-machine semantics were inconsistent). All 7 behavioral verifications passed: bogus 404 / real inspection completing with progress / post-retire tombstone not 404 / reject 400 / pending reject normal / GUI leftover run_id ends gracefully
- 2026-08-11: **AI assistant review fixes round 2 (10 items+2)** — (1) SSE cross-talk defense: sending/switching sessions increments sendToken; stale stream events are always discarded (previously, after switching sessions, the old stream kept writing into the new bubble); (2) config_push global timeout fallback: wait(timeout=2*PUSH_TIMEOUT+60); a hung thread no longer blocks forever and a manual-check prompt is shown; (3) inspection exception fixes: no phantom alerts written on db_error, and the device IP fixed before retries; (4) non-admins no longer receive global provider key mask fragments; (5) rate-limit TOCTOU fix: after the atomic claim the count is re-checked; over-limit rolls back the placeholder, restoring pending for retry (the frontend 429 restore button doesn't lock); (6) the fallback prompt fixed a literal \n escaping (previously the fallback protocol was always a dead end); (7) personal-provider empty-key updates no longer 422; a first save without a key gives an explicit 400; (8) fallback parsing switched to finditer supporting multiple blocks and multiple commands; (9) tool messages in history returned structured (command+content, no longer bare JSON); (10) the read-only token hitting restricted pages returns a friendly HTML 403 (browser) while the API keeps JSON. Also fixed: fix_rounds counting semantics, the CR smuggling dual gate (_propose_config rejection + confirm_action 400 with a rejected audit), and session-pool last initialization + no in-flight reclaim. All 23 verifications passed: 15/15 API + 3/3 real-device push chain + 5/5 inspection and Playwright UI regression
- 2026-08-10: **AI assistant review fixes (10 items)** — (1) save failures no longer swallowed: exec_config throws SaveFailedError on save failure, the audit output explicitly marked "save failed", and the frontend card shows a ⚠️ warning banner instead of "✅ saved"; (2) confirm/reject gained the soft-delete filter; pending confirmation cards of deleted sessions can no longer dispatch configs; (3) added an idempotent column migration at startup (PRAGMA table_info + ALTER TABLE); old databases/backup restores upgrading no longer 500; (4) deleting an in-progress session fully coordinated: the delete request no longer blocks (disconnect in the background), the agent loop checks deleted every round + before each device command executes and stops (same-round batched tool calls also intercepted, no more transparent reconnection hogging VTYs), and the frontend aborts the in-flight SSE on deletion; (5) deleting a provider auto-unbinds related sessions (binding + label cleared), no longer silently falling back to default with a stale label in the list; (6) session-ownership queries consolidated into the single _get_owned_session entry (previously 5 drifted copies); (7) provider row query/decryption deduplicated (create/switch reuse the already-fetched row); (8) chat/confirm switched to the AISession.device relationship; (9) fixed the provider-dropdown startup race (openSession waits for the first load to finish before assigning); (10) sessHint title/provider stored separately, no longer regex-truncating titles containing ' · '; table rendering supports `|` inside inline code (e.g. `` `display current | include vlan` ``). All 25 verifications passed: real-device save path / deleted session 404 / migration end-to-end (29 rows kept, 0 NULL) / deletion during streaming 0 leaks / Playwright UI and XSS regression
- 2026-08-10: **AI assistant UX and fixes** — (1) "execute and save" switched to netmiko's save_config dispatched per platform (Cisco=write memory, Huawei=save with automatic Y/N answering; previously Huawei's save silently failed); a save failure explicitly prompts "config applied but not written to the startup config"; (2) AI reply bubbles support Markdown rendering (tables/bold/headings/lists/code blocks; a homegrown lightweight renderer escapes first then restores, XSS-safe, with the streaming typewriter effect preserved); (3) fixed clicking an expired confirmation card throwing 500 (TypeError when output is NULL); (4) the provider modal supports closing with ESC; (5) fixed the new-session list's bare separator in the metadata
- 2026-08-10: **AI assistant: per-session model selection/switching + session deletion** — the toolbar gained a model dropdown listing all available providers (global + personal); a new session binds the selected model, and an open session can switch at any time (new `POST /ai/sessions/{id}/provider`); the session binding persists in ai_sessions.provider_source/provider_ref, and deleting a bound item falls back to default automatically; the session list supports deletion (hover × button) — using soft deletion (ai_sessions.deleted), with the full chat and config-change audit trail retained, and deletion also releases the device's SSH connection
- 2026-08-10: **AI assistant security final-audit hardening** — (1) the read-only whitelist rejects embedded newlines/control characters (`show version\nconfigure terminal` could once bypass the whitelist and change configs directly); (2) all /ai/* endpoints changed to require_full_user; the read-only token gets 403 across the board; (3) the idle-device SSH connection reclaim task hooked into the scheduler (60s; previously defined but never scheduled, and long-term use would fill up device VTYs); (4) fixed the admin provider panel never rendering (the template misjudged the field user.role → user.is_admin); (5) fixed the worker continuing to run after an SSE disconnect, and the confirmation card being double-clickable for repeated dispatch (atomic claim); (6) DeepSeek live-tested end-to-end (chat → show execution → confirmation card → manual dispatch → audit check)
- 2026-08-07: **AI assistant module launched** — conversational device inspection/configuration (page `/ai`, navbar entry): supports Kimi/DeepSeek/GLM/local OpenAI-compatible models, dual global + personal configuration tracks, API keys stored Fernet-encrypted; read-only commands execute and echo directly, config changes shown in full text one by one and dispatched to the device only after manual confirmation of each (atomic claim prevents repeated execution); full audits of chat/commands/outputs/confirmer; the page and endpoints require a full logged-in user (read-only token 403)
- 2026-08-07: **Login-free whitelist changed to exact/prefix dual semantics** — `PUBLIC_PATHS`'s startswith prefix matching meant that future routes like `/login-xxx`, `/logout-all`, `/staticAdmin` would be silently exposed; now split into an exact-match set + a prefix tuple requiring a trailing slash, closing off name-collision auto-exposure
- 2026-08-07: **Inspection stability triple fix** — (1) the inspection/config-push thread pools abandoned the with block (hung netmiko threads would leave shutdown(wait=True) blocking forever), switching to shutdown(wait=False, cancel_futures=True); (2) the collection's finally conn.disconnect() gained protection, so an SSH channel breaking mid-collection no longer discards the already-collected data; (3) the inspection persistence section gained a locked retry (up to 3 with backoff) and progress's done increments unconditionally, so SQLite concurrent-write conflicts no longer stall the frontend's progress
- 2026-08-07: **Privilege-escalation fix: configuration backup/topology no longer open to the read-only token** — added the `require_full_user` dependency (require_auth would be passed by the read-only token's synthetic user); configuration backup's page/list/download/export ZIP and topology's page/data endpoints all require a real logged-in user; backup download additionally gained a filename whitelist + directory constraint against path traversal
- 2026-08-07: **Log rotation** — application logs switched to RotatingFileHandler (10MB × 5, sensitive fields masked), wired in at main.py startup; the systemd stdout log /home/ivan/inspect.log is managed by logrotate (/etc/logrotate.d/network-inspect, size 10M/rotate 5/copytruncate), and logs no longer grow without bound
- 2026-08-07: **Case duplicate-name check** — creating a Case whose name duplicates an existing one (case-insensitive, leading/trailing spaces trimmed automatically) is rejected with the error banner "a Case with the same name already exists"; no more silently creating duplicate-name Cases (the Case name is the T1 order number; duplicates would make the QC webhook link ambiguous)
- 2026-08-06: **Dell iDRAC storage parsing fix** — hardware summaries lost BOSS controllers and directly-attached NVMe drives on servers with a BOSS card: `parse_idrac_disk` recognized only `Disk.Bay.*` backplane drives, and BOSS direct-attach M.2 (`Disk.Direct.*:BOSS.*`) was skipped wholesale; `parse_idrac_raid` recognized only controllers with RAID in the InstanceID, so BOSS cards (`BOSS.SL.*`) were lost and the backplane (`Enclosure.Internal.*:RAID.*`, ProductName "BP15G+") was miscounted as a RAID card. Fix: controllers matched exactly by FQDD prefix (RAID./BOSS./AHCI.), physical drives cover Disk.Bay+Disk.Direct (excluding Disk.Virtual); historical reports #109/#118/#119 summaries recomputed
- 2026-07-29: **Docker image v4** — image rebuilt for the latest code (34 in-container verifications all passed): added mtr-tiny/tzdata (route tracing works in the container; logs in CST); added COPY `inspection.py` (the configuration backup module depends on it); added Case-attachment/CA-certificate data volumes (v3 lost this data); `INSPECT_SECRET_KEY` now requires a valid Fernet key (v3's default value was invalid and crashed encryption/decryption); the image no longer contains keys/DB/Case attachments/CA private keys and can be distributed safely; deployment runbook in dockerivan.MD
- 2026-07-29: **Read-only token passwordless access** (T1 integration) — with the `INSPECT_READONLY_TOKEN` environment variable configured, a link carrying `?token=...` (or the `X-Readonly-Token` request header) browses without login; the first visit automatically sets the `inspect_rt` Cookie (30 days), so in-site navigation needs no repeated parameter; the middleware enforces GET/HEAD only (other methods 403), and blocks `/users`, `/change-password`, and CA private-key downloads (pem/p12); the token compared with `hmac.compare_digest` constant time; empty value = the feature is off; the token value lives only in the systemd unit, out of git
- 2026-07-24: Case content changes **notify the T1 QC system via webhook** — on Case creation/file upload/file deletion/Case deletion, a background thread automatically POSTs `bom.ici-cn.com/api/v1/qcLink/webhook` (order_number=Case name, url=relative path `cases/N`, remark describing the change); fire-and-forget, does not block the request; failures only logged, business unaffected; URL/token overridable via the `QC_WEBHOOK_URL`/`QC_WEBHOOK_TOKEN` environment variables
- 2026-07-24: password feature **code-review fixes** (8 of 10 items fixed + 2 deferred, 51 live verifications all passed) — admin cannot reset their own password on the users page (preventing the sole admin being locked out forever by a typo; must use the change-password page); `/users/add` gained the unified password policy (≥8 chars/not pure whitespace/≤128 chars; one `_validate_new_password` at three entry points); change-password rejects a new password equal to the old; the reset form adds a confirmation input; resetting a nonexistent user shows "target user does not exist" (no longer a silent 303); the new `require_admin` dependency replaces 4 hand-written guards (non-admin access returns 403 instead of a silent redirect); change-password does the free validation checks before the PBKDF2 old-password verification (zero hashing cost for wrong forms); deferred: change-password endpoint throttling (merging into login rate limiting), a password_version column (multi-worker revocation; currently single-process, unaffected)
- 2026-07-24: added the **change password** feature — self-service change-password page `/change-password` (verifies the old password, double confirmation, ≥8 chars); an admin can **reset any user's password** on the user management page; after change/reset/user deletion, **that user's sessions are automatically revoked** (forcing re-login); the navbar gained a "change password" entry
- 2026-07-24: code review round 2 — **cross-route security/stability fixes** (16 items, 15 fixed + 1 deferred, all verified live): the Case preview signing key now uses crypto's real encryption key (hardcoded public fallback deleted, preventing forgery); signature verification rejects non-hex input first (fixing a TypeError 500 on compare_digest at the public endpoint) and **verifies the signature before querying the DB** (garbage probes cost zero DB); file serving unified in `_serve_case_file` switched to **FileResponse streaming** (no longer reading whole files into memory) + `X-Content-Type-Options: nosniff`; uploads switched to full uuid4 against collisions, and `.tmp` partial files cleaned up on failure; the category-slug dedup changed to a single LIKE query; the Case detail page `Cache-Control: no-store` (preventing caching of expired signed URLs) and signed URLs generated only for images; `config_push` upload switched to **bounded reads** `read(MAX+1)` (no whole file into memory before the limit check, preventing OOM); CA certificates (4 spots)/BOM export/configuration backup downloads unified through `helpers.download_headers` RFC 6266 encoding (fixing Chinese file names latin-1 500); the XR per-platform command selection deferred for separate discussion
- 2026-07-23: Case system **security hardening** (9 code-review items, all verified live) — file serving switched to an **extension whitelist** (only raster images + PDF inline; HTML etc. forced to `application/octet-stream` download → eliminating stored XSS via HTML uploads); `/cases/preview` public preview switched to **HMAC signing + 6h expiry** (unsigned/expired returns 404, eliminating public links that never expire); uploads switched to **bounded reads** (`read(MAX+1)`, not reading the whole file into memory before the limit → preventing OOM), and mid-way multi-file failures **roll back files already written to disk** (preventing orphans); download `Content-Disposition` uses RFC 6266 encoding (fixing a Chinese-file-name latin-1 crash); category renaming gained **duplicate-name/slug validation** (returning 400 instead of 500); LIKE wildcards escaped in search; `cases.html`'s delete confirmation moved the Case name out of the JS string (preventing stored XSS); fixed double-encoded garbled category names ("inspection report")
- 2026-06-18: added the BOM matching verification feature — supports uploading a BOM xlsx file, automatically matching device models against inspection reports, comparing server configurations item by item; results exportable to Excel
- 2026-06-30: added the CA certificate server — root CA creation/download, certificate issue/revoke, external CSR signing, dual PEM/PKCS#12 export formats (2026-07-01: code-review fixes — cumulative CRL revocation chain, UUID-unique directories, null-pointer checks, exception rollback, key-path guards)
- 2026-07-17: BOM matching supports Dell servers (hardware-summary matching) — BMCs without PID output (idrac etc.) now match Model/CPU/Memory/NIC/RAID/Disk/PSU hardware summaries against the BOM Description; word-level matching tolerates (R)/(TM) trademark symbols; BROADCOM XXXX auto-converted to BCMXXXX; CPU 24C/48T matches on the core count 24C only
- 2026-07-16: Case system **search** — a list-page search box searching Case name/notes/file names across tables (ilike), with matching files shown inline in results; the detail page gained live filename filtering; the list page gained a delete button
- 2026-07-15: added the **Case system** — archiving inspection reports, device documents, and photos by project/case; one folder per Case, files grouped by configurable categories (default inspection report/device documents/photos; add/delete/edit on the settings page; non-empty ones cannot be deleted); multi-file upload supported (≤50MB/file), download, **online viewing** (images displayed inline, PDFs opened in-browser, HTML rendered in a sandboxed iframe against XSS); flat storage + DB category labels (category rename/delete are pure DB operations); filename sanitization + uuid + path-traversal protection + handler-level authorization + admin-only category settings/Case deletion
- 2026-07-02: CA security hardening — the CRL is rebuilt from the database `status='revoked'` (the file is a rebuildable cache, eliminating silent revocation loss on corruption/truncation); atomic writes (temp + os.replace) + a thread lock against tearing/concurrent lost updates; `revoke_cert` commits the DB before generating the CRL; `delete_cert` regenerates the CRL to avoid ghost serial numbers; `download_pem/p12` typed error handling (no longer leaking server paths); `get_pem_zip` throws on an empty key path (consistent with p12); `sign_csr` cleans up orphan certificate files on rollback; `ca_page` reuses `_get_certs`; `_ca_certs.html` renders `csr_error`
- 2026-07-03: 
  - CA second-round hardening — CRL rebuilding changed to **calling the read provider inside the lock** (fixing the race where concurrent revocations lose updates); `delete_cert` restricted to **expired-revoked certificates only** (avoiding delete-equals-unrevoked) and cleans up the certificate/private-key files; added `GET /api/cert/{id}/download/crt`, a **certificate-only endpoint** (CSR-signed certificates downloadable; `openssl verify` passes); CRLNumber changed to a **monotonic counter seeded from the existing CRL** (no regression across restarts, RFC 5280-compliant, replacing clock derivation); logging added for CRL generation failures/bad serial numbers/empty `revoked_at`; extracted `_load_ca_pair`/`_get_cert_and_root`/`_bundle_or_500` to deduplicate
  - Dashboard "recent alerts" Ack blank-page fix — switched to HTMX `hx-post` (the native form's full-page jump to an empty 200 response caused the blank); an audit confirmed no similar hazards repo-wide
  - Security hygiene — untracked CA private keys/the live database/configuration backups (`.gitignore`); the private keys remain in local history (no remote); rotate the root CA before pushing to a shared remote

- 2026-07-03 (full-project code-review fixes, 33 items): device field server-side validation + template tojson/esc escaping against stored XSS; /devices/api no longer leaks the encrypted-password column; crypto.is_encrypted requires a valid Fernet token to prevent plaintext landing in the DB; /docs /openapi.json now require login; login timing equalized + the next open-redirect fix; resource caps (subnet/bom/config_compare/reports PDF) against OOM; config_push made synchronous to avoid blocking the event loop; scheduler startup fault tolerance (bad records no longer paralyze everything) + per-future timeout + unique run_id + once timezone; inspection.py backup filename sanitization + chmod 0o600 + NX-OS CPU clamp + routing validation/hostname/SEL parsing hardening; scheduler.html deduplicated (originally 4 duplicated modals/functions + title swallowing the modal); first-boot admin changed to a random password
- 2026-06-18: added the LLM VRAM calculator — supports 10 preset models + custom, three major scenarios (inference/training/multi-GPU), a comparison table of 8 quantization precisions
| Module | Optimization content |
|------|----------|
| **Configuration backup** | Full backup management — browse/view/download/manual forced backup/batch ZIP export/batch deletion, device dropdown (IP+ID), file-vs-directory diagnostics, path traversal protection | — reuse inspection.CONFIG_DIR avoiding hardcoding, API device-list loading XSS-safe, redundant imports/dead code cleaned | — browse/view/download/manual forced backup/batch ZIP export/batch deletion, device dropdown menu (IP+ID), persistent status hints | — browse/download/manual backup trigger/batch ZIP export |
| **Docker deployment** | network1-inspection image, docker-compose up -d startup, dockerivan.MD complete beginner guide (800 lines) |
| **Frontend interactions** | HTMX progressive enhancement + configuration backup batch deletion (select → confirm → delete, path traversal protection) | — lightweight dashboard /api/dashboard/stats endpoint (30s refresh), inline alert/report row actions, remove deleteOne dead code |
| **IOS-XR inspection** | Command matrix 6→8 categories (added system redundancy/environmental status/alerts and logs), 12→21 commands, automatic alert fallback, case-insensitive log filtering |
| **Code quality** | Extracted SERVER_PLATFORMS→constants.py, save_inspection_run→helpers.py, topology N+1 fix, H3C_COMMANDS deduplicated |
| **Security hardening** | PBKDF2 auto-upgrade of old hashes, devices.csv security warning, config_push pre-configuration backup persistence, INSPECT_DB_PATH environment variable |
| **Inspection engine** | Routing table validation and automatic fallback (9 vendors), Huawei USG firewall compatibility, Juniper/NX-OS environmental monitoring, Arista routing fallback, Ruijie enhancements |
| **Server BMC** | 5 major BMC independent system-log categories (Dell getsel, HP iML, Lenovo eventlog, Huawei sel, Inspur sel) |
| **Database** | SQLite WAL mode, connection pool (pool_pre_ping/pool_recycle), Context Manager |
| **Security** | Three-tier key lookup (environment variable → /etc/inspection/ → auto-generate), sensitive log redaction, SHA256 backup deduplication |
| **Alerts** | Clear All / Clear Acknowledged batch clearing |
| **Configuration comparison** | Device configuration loading API, Swap/Clear buttons, adjustable context lines |
| **Configuration push** | ThreadPoolExecutor parallel push (10-way, 120s timeout), elapsed-time statistics |
| **Custom commands** | Parallel multi-device execution, single-command execution results saved automatically |
| **Ping** | Quick device-selection dropdown, configurable timeout (500ms-5000ms) |
| **Inspection reports** | Device filter dropdown, statistics overview (total/success/failure), Word export button |
| **Scheduled tasks** | Edit task modal, batch deletion, Run-now last_run timestamp fix |
| **Subnet calculator** | IPv6 is_global/is_unique_local, IPv6 subnet list, tab switching JS |
| **Network topology** | Fit zoom, JSON export, 60s auto-refresh |
| **Logging system** | Structured logging + SensitiveMaskFilter redaction of sensitive fields |
| **CLI script** | devices.csv template auto-generation, SHA256 configuration backup deduplication + rotation |
| **Ruijie RGOS** | Enhanced command matrix, 5-layer CPU/4-layer memory/3-layer uptime parsers |
| **Technical research** | In-depth comparison of industry solutions (LibreNMS/Oxidized/Netshot/SolarWinds), Netshot frontend progress tracking |
| **Documentation** | README added technical solution comparison, running status, known issues and future improvements |
| **Security** | Identified MD5 weak-hash risk, CSV plaintext password issues, H3C_COMMANDS duplicate definitions |
| **Technical research** | In-depth comparison of industry solutions (LibreNMS/Oxidized/Netshot/SolarWinds), Netshot frontend progress tracking |
| **Documentation** | README added technical solution comparison, running status, known issues and future improvements |
| **Code review** | Identified H3C_COMMANDS duplicate definitions, WAL bloat, .bak file cleanup, and other improvement points |
| **Parsers** | Cisco IOS CPU 3-layer fallback, Juniper CPU 4-layer fallback |
| **Database recovery** | Corrupt DB dump→ROLLBACK→COMMIT repair, 7 tables 40 rows of data, 37 rows successfully recovered |
| **System protection** | main.py singleton lock + startup integrity check, systemd crash-loop protection, periodic WAL checkpoint |
| **Verification** | All modules 16/16 PASS (13 pages + 3 APIs); singleton lock/unauthenticated interception/wrong-password rejection/public paths all verified |
| **Code review** | 2 CRITICALs, 8 security vulnerabilities, 4 performance optimizations |

