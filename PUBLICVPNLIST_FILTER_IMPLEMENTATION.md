# PublicVPNList 节点筛选接入实现文档

## 1. 目标

将 PublicVPNList 接入 AimiliVPN 的节点维护流程，支持在拉取节点时按条件筛选，避免每次把全部节点下载到内存或页面：

- 最低速度
- 最大延迟
- 国家/地区
- 数据来源
- OpenVPN 传输协议
- IP 类型与 IP 纯净度
- 仅显示已验证节点
- 仅显示可下载配置的节点

现有 VPNGate 数据源继续保留。筛选配置应保存到 `vpngate_data/ui_auth.json`，节点配置文件仍按需下载并写入 `vpngate_data/configs/`。

## 2. 数据源策略

### 2.1 正式元数据接口

```text
GET https://publicvpnlist.com/api/v1/servers
```

支持的稳定参数：

| 参数 | 说明 |
| --- | --- |
| `page` | 从 1 开始的页码 |
| `page_size` | 最大 100 |
| `country` | 小写国家 slug，例如 `japan` |
| `source` | 来源名称，例如 `VPNGate` |

响应结构：

```json
{
  "ok": true,
  "items": [],
  "pagination": {"page": 1, "page_size": 100, "total": 8149},
  "snapshot": {}
}
```

每个 `item` 下面有 `endpoints`。OpenVPN 节点应从 endpoint 中读取：

```text
legacy_id
host / resolved_ip
port
transport_protocol
source
country / countryName
latency_ms
download_mbps
checker_status
downloadable
```

不要依赖未确认的查询参数。当前实测 `protocol` 没有得到有效过滤结果，`proto` 和 `transport_protocol` 会被忽略；协议条件应在本地归一化后判断。

### 2.2 可选加速接口

```http
GET https://publicvpnlist.com/local/api/vpn-data.php
X-Requested-With: XMLHttpRequest
```

当前实测一次返回约 7.36 MB、6397 条扁平记录。该接口只需 `X-Requested-With` 即可访问，但网站 `/export/` 页面明确说明完整批量导出不是公开稳定接口，因此只作为可配置的加速路径，不应作为唯一依赖。

使用规则：

1. 缓存时间按响应的约 900 秒处理。
2. 不要在每次刷新或每个页面请求中重新下载。
3. 需要全部数据时才使用该接口。
4. 有国家或来源条件时，优先使用 `/api/v1/servers` 分页接口。

### 2.3 配置文件接口

配置文件必须按需获取：

```http
POST https://publicvpnlist.com/get_token.php
Content-Type: application/x-www-form-urlencoded
X-Requested-With: XMLHttpRequest

id=160984
```

然后请求返回的短时 URL：

```http
GET https://publicvpnlist.com/download.php?token=...
Accept: application/x-openvpn-profile
```

Token 有效期约 300 秒。不要持久化 Token，也不要写入日志。只有用户执行“测试”或“连接”时才获取 `.ovpn`。

## 3. 筛选模型

建议增加以下配置字段：

```json
{
  "node_source": "publicvpnlist",
  "filter_country": "",
  "filter_source": "",
  "filter_protocol": "",
  "min_speed_mbps": 0,
  "max_latency_ms": 0,
  "ip_purity": "any",
  "only_verified": false,
  "only_downloadable": true
}
```

字段规则：

| 字段 | 规则 |
| --- | --- |
| `filter_country` | 空值表示全部；PublicVPNList 请求使用小写 slug |
| `filter_source` | 空值表示全部；值必须来自 `/api/v1/sources` |
| `filter_protocol` | `tcp`、`udp` 或空值；本地判断 endpoint 的 `transport_protocol` |
| `min_speed_mbps` | 0 表示不限制；使用 `download_mbps` |
| `max_latency_ms` | 0 表示不限制；使用 `latency_ms` |
| `ip_purity` | `any`、`residential`、`hosting`、`proxy_free` |
| `only_verified` | 使用 `isVerified` 或 `checker_status == tunnel_ok` |
| `only_downloadable` | 使用 `configAvailable` 或 endpoint 的 `downloadable` |

### 3.1 速度与延迟

PublicVPNList 使用 Mbps 和毫秒。现有 VPNGate 节点的速度字段通常是 bit/s，进入统一节点模型时必须统一为 `speed_mbps`，避免直接比较不同单位。

推荐筛选顺序：

1. 国家和来源
2. 可下载配置
3. 已验证状态
4. 最低速度
5. 最大延迟
6. IP 纯净度

### 3.2 IP 纯净度

PublicVPNList 元数据不直接提供可证明的 IP 纯净度。`operator_verified` 也不等于住宅 IP 或无滥用历史。

现有项目已经通过 `vpn_utils.enrich_ip_info()` 查询 IP 信息，因此应复用该流程：

- `proxy == true`：标记为 `proxy`
- `hosting == true`：标记为 `hosting`
- `mobile == true`：标记为 `mobile`
- 其余成功结果：标记为 `residential` 或 `normal`

`proxy_free` 只能表示 IP 信息接口未识别为代理，不应在界面上宣传为绝对“纯净”。IP 信息需要按 IP 缓存，例如 7 天，避免每次刷新重复请求。

## 4. 推荐数据流程

```text
读取筛选配置
    |
    +-- 有国家/来源条件 --> /api/v1/servers?page_size=100
    |
    +-- 无条件且需要全量 --> vpn-data.php（15 分钟缓存）
    |
归一化 PublicVPNList item/endpoint
    |
本地应用协议、速度、延迟、验证、可下载、IP 纯净度筛选
    |
IP 信息补充（只处理筛选后的候选节点，并使用缓存）
    |
按可用性、纯净度、延迟、速度排序
    |
仅在测试/连接时获取 .ovpn
```

分页接口没有确认的速度或延迟服务端过滤参数，因此不能假设一页就是“最快节点”。无国家/来源条件时，应使用后台分页任务逐页收集，达到候选数量后停止；同时设置最大扫描上限，避免异常条件触发全站扫描。

建议增加以下环境变量：

```text
NODE_SOURCE=publicvpnlist
PUBLICVPNLIST_PAGE_SIZE=100
PUBLICVPNLIST_MAX_PAGES=20
PUBLICVPNLIST_METADATA_TTL=900
PUBLICVPNLIST_USE_BULK_ENDPOINT=0
```

## 5. AimiliVPN 改造点

### 后端 `vpngate_manager.py`

1. 在 `load_ui_config()` 增加筛选默认值和字段兼容迁移。
2. 在 `get_state()` 返回当前筛选配置，供页面回填。
3. 将现有 `fetch_candidates()` 拆成：
   - `fetch_vpngate_candidates()`
   - `fetch_publicvpnlist_candidates(filters)`
4. 增加 PublicVPNList JSON 请求、分页、字段归一化和响应校验。
5. 增加 `ensure_node_config(node)`，在测试/连接/配置下载时执行两步 Token 流程。
6. 修改 `test_node_by_id()`、`test_multiple_nodes()` 和 `connect_node()`，在写临时配置前调用 `ensure_node_config()`。
7. 修改 `/configs/{filename}` 路由：节点没有 `config_text` 时先按需下载，再返回配置。
8. 增加独立的 `POST /api/update_node_filters`，不要把节点筛选和代理端口配置混在一起。
9. 筛选配置变化后清理旧候选节点，但保留当前活动节点，避免筛选切换导致活动连接状态丢失。

### 页面内嵌 JavaScript

现有页面已经有国家、IP 类型、状态筛选，但这些是对已下载节点的前端筛选。应增加：

- 来源下拉框
- 协议下拉框
- 最低速度下拉框或数字输入
- 最大延迟下拉框或数字输入
- IP 纯净度选项
- “仅已验证”复选框
- “仅可下载”复选框
- 应用筛选按钮
- 当前筛选结果数量和数据源说明

用户点击“应用筛选”时：

1. 校验数值范围。
2. 调用 `/api/update_node_filters`。
3. 后台触发节点刷新。
4. 页面轮询 `/api/nodes`，显示新的候选节点。

不要在每个下拉框的 `change` 事件中立即触发一次全量刷新，应使用“应用筛选”统一提交。

## 6. 节点统一模型

PublicVPNList 节点最终转换为现有模型时至少包含：

```json
{
  "id": "pvl_160984",
  "legacy_id": 160984,
  "source": "AutoOVPN",
  "country": "South Korea",
  "country_slug": "south-korea",
  "ip": "1.251.156.223",
  "remote_host": "1.251.156.223",
  "remote_port": 995,
  "proto": "tcp",
  "speed_mbps": 68.42,
  "latency_ms": 39,
  "probe_status": "not_checked",
  "verified": true,
  "downloadable": true,
  "ip_type": "",
  "quality": "",
  "config_text": ""
}
```

`config_text` 为空是合法状态，表示元数据已获取但配置尚未按需下载。现有 VPNGate 节点仍可继续使用原有 `config_text`。

## 7. 缓存与并发

缓存建议分层：

| 缓存 | 内容 | 建议 TTL |
| --- | --- | --- |
| 元数据缓存 | PublicVPNList 节点列表 | 900 秒 |
| IP 信息缓存 | ISP、ASN、hosting/proxy 判断 | 7 天 |
| 配置文件缓存 | 已成功下载的 `.ovpn` | 按节点或 300 秒重新验证 |
| Token | 下载授权令牌 | 不持久化 |

所有缓存写入使用现有 `write_json()`，避免并发刷新覆盖节点测试结果。节点刷新时保留旧节点的 `probe_status`、`latency_ms`、`ip_type` 和 `quality`。

## 8. 安全和失败处理

- 只允许固定的 PublicVPNList URL，不允许用户通过筛选参数注入任意 URL。
- `country`、`source`、`protocol` 使用白名单或严格长度限制。
- Token、完整 `.ovpn` 内容、代理认证信息不能写入日志或 API 节点列表响应。
- PublicVPNList 返回空页时停止分页。
- API 返回非 JSON、`ok != true` 或字段缺失时记录结构化错误，并保留旧缓存。
- IP 信息接口失败时将纯净度设为 `unknown`，不能把未知误标为住宅 IP。
- 所有公开 VPN 节点都应继续显示“技术可用不代表隐私安全”的提示。

## 9. 验收标准

1. 设置“日本 + VPNGate + TCP + 速度至少 50 Mbps + 延迟不超过 80 ms”后，后台请求只拉取对应国家/来源分页，不下载全量数据。
2. 设置“仅已验证”后，列表不出现 `isVerified=false` 的节点。
3. 设置“仅可下载”后，所有展示节点都满足 `configAvailable=true` 或 `downloadable=true`。
4. 设置 IP 纯净度为 `proxy_free` 后，未知 IP 信息不会被错误显示为纯净。
5. 列表展示可以没有配置内容，但点击测试或连接时能自动获取并使用 `.ovpn`。
6. Token 过期或配置下载失败时，节点被标记为不可用，并显示可读错误。
7. 筛选条件改变不会中断当前已建立的 OpenVPN 连接。
8. PublicVPNList 不可访问时，VPNGate 数据源和现有连接流程仍然可用。

## 10. 后端实现状态

后端第一阶段已实现，前端按要求暂不修改：

- PublicVPNList 分页元数据、900 秒缓存、本地筛选与统一 Mbps 单位。
- `.ovpn` 在测试、连接或配置下载时按需获取，Token 不持久化。
- 外部 `.ovpn` 危险脚本指令校验。
- 筛选配置保存及 `POST /api/update_node_filters`。
- 分页节点、轻量状态、快速延迟和异步连接 API。
- `tun0` / `tun1` 双槽先建后切，旧代理连接按接口排空。
- `nodes.json` 只保留节点元数据，配置内容独立存放在 `configs/`。

Linux 策略路由与真实连接排空仍需在 VPS 环境做集成验证，详见
`BACKEND_ARCHITECTURE.md`。
