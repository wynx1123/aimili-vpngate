# AimiliVPN Enhanced

[中文](#中文) | [English](#english)

> [!IMPORTANT]
> This is an independent second-development project based on
> [baoweise-bot/aimili-vpngate](https://github.com/baoweise-bot/aimili-vpngate).
> Sincere thanks to the original author and every upstream contributor. This
> repository is not the official upstream project and is not endorsed by the
> upstream maintainers.

## 中文

AimiliVPN Enhanced 是基于 AimiliVPN 的 VPN 出口管理与 HTTP/SOCKS5 代理网关二次开发版。
本版本重点优化多来源 OpenVPN 节点管理、延迟检测、平滑切换、固定路由策略和配置缓存治理。

### 鸣谢与项目关系

- 原始项目：[baoweise-bot/aimili-vpngate](https://github.com/baoweise-bot/aimili-vpngate)
- 原作者及核心贡献者：[`baoweise-bot`](https://github.com/baoweise-bot)，感谢其提供 AimiliVPN 的核心实现、安装器和管理能力。
- 二次开发维护者：[`wynx1123`](https://github.com/wynx1123)。
- AI 辅助贡献：OpenAI ChatGPT / Codex 参与架构分析、代码实现、测试和中英文文档整理；最终审查与发布责任由人类维护者承担。
- 本仓库是独立维护的衍生版本。问题请提交到本仓库，不要要求上游作者为本版本提供支持。
- 完整贡献角色见 [CONTRIBUTORS.md](CONTRIBUTORS.md)。本项目保留 GNU GPL v3 的著作权、许可证和源码开放义务，详见 [NOTICE.md](NOTICE.md) 和 [LICENSE](LICENSE)。

### 二次开发新增功能

- **双节点来源**：兼容原有 VPNGate，并新增 PublicVPNList；支持单独启用或合并使用。
- **OpenVPN TCP/UDP**：按节点配置使用 TCP 或 UDP。WireGuard 配置不能直接作为 OpenVPN 配置使用。
- **轻量延迟检测**：无需先启动完整 OpenVPN 隧道即可并发测量候选节点延迟。
- **平滑切换**：使用 `tun0`/`tun1` 双槽 make-before-break，候选隧道验证成功后才切换新连接。
- **连接排空**：旧代理连接可继续使用原隧道，直到自然结束或达到排空超时。
- **异步连接 API**：前端提交切换后立即返回任务 ID，避免页面等待和卡顿。
- **精细筛选**：支持固定 IP、固定国家/地区、协议、最低速度、最大延迟、验证状态和来源筛选。
- **节点画像**：展示出口 IP、城市、来源、住宅/机房等 IP 类型及可用的纯净度信息。
- **按需配置下载**：只在测试、连接或手动下载时生成 `.ovpn` 文件，避免刷新列表时大量落盘。
- **定时配置清理**：清理无效、孤立、过期和遗留测试配置，并保护活动、排空、固定 IP 和收藏节点。
- **管理界面重构**：按待检测、当前连接和可用节点组织状态，保留管理员账号、密码、安全路径和代理设置。
- **自动恢复**：活动出口失效时自动选择可用备用节点，不用先中断健康连接再测试候选节点。

### 架构概览

```text
VPNGate -----------\
                    > 节点标准化 -> 并发延迟检测 -> 策略筛选
PublicVPNList -----/                            |
                                                v
                                      候选隧道 tun0/tun1
                                                |
                                      验证出口后原子切换
                                                |
                                    HTTP/SOCKS5 127.0.0.1:7928
```

主要模块：

- `vpngate_manager.py`：管理 API、节点编排、OpenVPN 生命周期、策略路由和后台任务。
- `vpn_sources.py`：来源适配、筛选、分页缓存、配置下载和配置安全校验。
- `tunnel_slots.py`：活动/排空双隧道状态管理。
- `proxy_server.py`：HTTP/SOCKS5 数据面及按连接绑定出口接口。
- `config_cleanup.py`：有界配置缓存和受保护节点清理策略。
- `webui/`：管理界面。

更多实现细节见 [BACKEND_ARCHITECTURE.md](BACKEND_ARCHITECTURE.md)。

### 安装

要求：Linux VPS、Python 3、OpenVPN、root 权限，以及可用的 `/dev/net/tun`。

```bash
bash <(curl -Ls https://raw.githubusercontent.com/wynx1123/aimili-vpngate/main/install.sh)
```

安装器默认将源码部署到 `/opt/aimilivpn`，创建系统服务并生成随机管理账号、密码和安全路径。
安装完成后请立即妥善保存凭据。运行 `ml` 可进入管理菜单。

### 代理使用

默认代理地址：

```text
HTTP:   http://127.0.0.1:7928
SOCKS5: socks5://127.0.0.1:7928
```

默认仅建议监听本机。不要在没有强认证、防火墙来源限制和审计措施的情况下将代理端口暴露到公网。

### 常用配置

| 环境变量 | 默认值 | 说明 |
| --- | ---: | --- |
| `NODE_SOURCE` | `vpngate` | `vpngate`、`publicvpnlist` 或 `all` |
| `LOCAL_PROXY_HOST` | `127.0.0.1` | 代理监听地址 |
| `LOCAL_PROXY_PORT` | `7928` | HTTP/SOCKS5 统一端口 |
| `UI_PORT` | `8787` | 管理界面端口 |
| `BACKGROUND_TEST_NODE_LIMIT` | `15` | 后台单轮测试上限 |
| `LATENCY_PROBE_WORKERS` | `10` | 延迟检测并发数 |
| `TUNNEL_DRAIN_SECONDS` | `45` | 旧隧道最短排空时间 |
| `TUNNEL_DRAIN_MAX_SECONDS` | `180` | 旧隧道最大排空时间 |
| `CONFIG_CLEANUP_INTERVAL_SECONDS` | `3600` | 配置清理周期 |
| `CONFIG_MAX_FILES` | `300` | `.ovpn` 缓存上限 |
| `CONFIG_MAX_AGE_SECONDS` | `259200` | 配置最长缓存时间，默认 3 天 |

### 测试

```bash
python -m unittest discover -s tests
python -m py_compile vpngate_manager.py proxy_server.py vpn_sources.py \
  tunnel_slots.py vpn_utils.py config_cleanup.py
```

### 安全、合规与许可证

- 仅在当地法律允许且你有权使用的网络和设备上部署。
- 禁止用于未授权访问、凭据攻击、恶意扫描、垃圾流量、侵权分发或其他违法活动。
- 公共 VPN 节点由第三方运营，不应视为可信网络。不要通过未知节点传输未做端到端加密的敏感信息。
- 使用者负责遵守所在司法辖区、服务提供商以及节点数据来源的条款和监管要求。
- 完整风险与责任说明见 [LEGAL.md](LEGAL.md)。该文档不是法律意见。

本项目继承上游的 **GNU GPL v3 or later**。GPL 允许商业使用，因此不能在衍生版本中追加具有法律约束力的“禁止商业使用”限制。维护者不提供商业部署、代理转售或付费节点服务的授权、担保和支持；这是项目立场，不是对 GPL 权利的额外限制。

---

## English

AimiliVPN Enhanced is an independently maintained derivative of AimiliVPN. It
focuses on multi-source OpenVPN node management, low-overhead latency probing,
smooth tunnel switching, fixed routing policies, and bounded profile caching.

### Credits and relationship to upstream

- Upstream project: [baoweise-bot/aimili-vpngate](https://github.com/baoweise-bot/aimili-vpngate)
- Original author and core contributor: [`baoweise-bot`](https://github.com/baoweise-bot), with thanks for the core AimiliVPN implementation, installer, and management features.
- Derivative maintainer: [`wynx1123`](https://github.com/wynx1123).
- AI-assisted contributions: OpenAI ChatGPT / Codex assisted with architecture analysis, implementation, tests, and bilingual documentation. Final review and release responsibility remains with the human maintainer.
- This repository is an independent derivative. Report issues here and do not ask upstream maintainers to support this version.
- See [CONTRIBUTORS.md](CONTRIBUTORS.md) for contribution roles. Upstream copyright, GNU GPL v3 terms, and source-distribution obligations are preserved. See [NOTICE.md](NOTICE.md) and [LICENSE](LICENSE).

### Added in this derivative

- **Two node catalogs**: the original VPNGate source plus PublicVPNList, usable separately or together.
- **OpenVPN TCP/UDP**: each node uses the transport declared by its profile. WireGuard profiles are not interchangeable with OpenVPN profiles.
- **Lightweight latency probes**: benchmark candidate endpoints concurrently without first starting full VPN tunnels.
- **Smooth switching**: `tun0`/`tun1` make-before-break switching; a candidate must pass egress verification before it becomes active.
- **Connection draining**: existing proxy clients retain the previous tunnel until they finish or reach the drain deadline.
- **Asynchronous connect API**: switching returns a job ID immediately so the UI stays responsive.
- **Detailed filtering**: fixed IP, country/region, protocol, minimum speed, maximum latency, verification state, and source.
- **Node intelligence**: exit IP, city, source, residential/datacenter classification, and available IP-quality signals.
- **Lazy profile materialization**: `.ovpn` files are created only for testing, connection, or explicit download.
- **Scheduled cache cleanup**: removes unavailable, orphaned, expired, and abandoned test profiles while protecting active, draining, fixed-IP, and favorite nodes.
- **Reworked management UI**: pending, connected, and available stages plus administrator credentials, secure path, and proxy settings.
- **Automatic recovery**: failed exits are replaced with verified standby nodes without tearing down a healthy tunnel first.

### Architecture

```text
VPNGate -----------\
                    > normalization -> latency probes -> policy filters
PublicVPNList -----/                                  |
                                                        v
                                              tun0/tun1 candidate
                                                        |
                                           verify, then atomic switch
                                                        |
                                          HTTP/SOCKS5 on 127.0.0.1:7928
```

See [BACKEND_ARCHITECTURE.md](BACKEND_ARCHITECTURE.md) for implementation details.

### Installation

Requirements: a Linux VPS, Python 3, OpenVPN, root privileges, and an available
`/dev/net/tun` device.

```bash
bash <(curl -Ls https://raw.githubusercontent.com/wynx1123/aimili-vpngate/main/install.sh)
```

The installer deploys to `/opt/aimilivpn`, creates a system service, and
generates a random administrator username, password, and secure URL path. Store
the generated credentials securely. Run `ml` to open the management menu.

### Proxy endpoints

```text
HTTP:   http://127.0.0.1:7928
SOCKS5: socks5://127.0.0.1:7928
```

Keep the proxy bound to localhost by default. Do not expose it publicly without
strong authentication, source firewall rules, monitoring, and abuse controls.

### Configuration

| Variable | Default | Purpose |
| --- | ---: | --- |
| `NODE_SOURCE` | `vpngate` | `vpngate`, `publicvpnlist`, or `all` |
| `LOCAL_PROXY_HOST` | `127.0.0.1` | Proxy bind address |
| `LOCAL_PROXY_PORT` | `7928` | Combined HTTP/SOCKS5 port |
| `UI_PORT` | `8787` | Management UI port |
| `BACKGROUND_TEST_NODE_LIMIT` | `15` | Background test limit per round |
| `LATENCY_PROBE_WORKERS` | `10` | Concurrent latency probes |
| `TUNNEL_DRAIN_SECONDS` | `45` | Minimum old-tunnel drain time |
| `TUNNEL_DRAIN_MAX_SECONDS` | `180` | Maximum old-tunnel drain time |
| `CONFIG_CLEANUP_INTERVAL_SECONDS` | `3600` | Profile cleanup interval |
| `CONFIG_MAX_FILES` | `300` | Maximum cached `.ovpn` files |
| `CONFIG_MAX_AGE_SECONDS` | `259200` | Maximum profile age, 3 days by default |

### Tests

```bash
python -m unittest discover -s tests
python -m py_compile vpngate_manager.py proxy_server.py vpn_sources.py \
  tunnel_slots.py vpn_utils.py config_cleanup.py
```

### Security, compliance, and license

- Deploy only where lawful and only on networks and systems you are authorized to use.
- Do not use this software for unauthorized access, credential attacks, malicious scanning, spam, infringement, or other unlawful activity.
- Public VPN exits are operated by third parties and must be treated as untrusted. Use end-to-end encryption for sensitive traffic.
- Operators are responsible for applicable law and for the terms of their hosting provider and node-data sources.
- Read [LEGAL.md](LEGAL.md) for the complete risk and responsibility notice. It is not legal advice.

This derivative remains licensed under **GNU GPL v3 or later**. GPL permits
commercial use, so a derivative cannot add a legally binding non-commercial
restriction. The maintainers do not offer commercial deployment, proxy resale,
or paid-node-service authorization, warranty, or support. That is a project
policy, not an additional restriction on GPL rights.
