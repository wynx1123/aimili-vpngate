# Third-Party Notices / 第三方内容说明

This file is informational and is not a substitute for reviewing the current
terms and licenses of each provider.
本文仅作信息披露，不能替代对各提供方最新条款和许可证的审查。

## 中文

### 上游源码

- **AimiliVPN**：本项目基于
  [baoweise-bot/aimili-vpngate](https://github.com/baoweise-bot/aimili-vpngate)
  二次开发，继承 GNU GPL v3 or later。完整署名见 [NOTICE.md](NOTICE.md)。

### 软件和前端依赖

- **OpenVPN**：运行时外部依赖。本仓库不分发 OpenVPN 二进制文件；部署者应遵守
  OpenVPN 自身许可证和商标政策。本项目与 OpenVPN Inc. 无隶属或背书关系。
- **Lucide**：管理界面从 `unpkg.com` 加载 Lucide 图标库。Lucide 项目采用 ISC
  License；实际适用版本以界面引用和上游发布为准。
- **Google Fonts**：管理界面可从 Google Fonts 加载 Outfit、JetBrains Mono、
  Anton、Condiment、IBM Plex Mono 和 Noto Sans SC。字体通常以各自的 SIL Open Font
  License 或项目许可证提供，应以对应字体上游文件为准。

### 远程动画媒体

`webui/index.html` 引用了 `cloudfront.net` 上的三个演示动画视频地址。这些视频不在
本仓库存储，且不因源码使用 GPL 就自动获得 GPL 授权。本项目不对视频的所有权、
许可期限、持续可用性或适合公开分发作出保证。部署者必须确认自己拥有使用权；无法
确认时应删除这些 `<source>` 地址或替换为自有/明确授权并自托管的素材。

加载 Google Fonts、unpkg 或远程视频时，访问者的 IP、浏览器信息和 Referrer 可能
发送给相应第三方。对隐私、数据本地化或内容安全策略有要求时，应自托管依赖或关闭
外部资源。

### 节点和网络数据服务

- **VPNGate** 与 **PublicVPNList**：节点元数据和 OpenVPN 配置来自独立第三方；
  使用者应遵守其条款、隐私政策、研究/使用限制和节点运营者要求。
- **ipify、ip.sb、ifconfig.me、icanhazip.com**：用于出口 IP 或联网诊断。请求会向
  对应服务披露出口 IP 和必要网络元数据。

### 上游遗留链接

旧版嵌入式界面中可能保留上游作者加入的论坛、Telegram、VPS 推广或联盟链接。
保留这些链接用于兼容和尊重上游历史，不代表本衍生项目对第三方服务作质量保证，
也不表示相关第三方认可本项目。

## English

### Upstream source

- **AimiliVPN**: this project derives from
  [baoweise-bot/aimili-vpngate](https://github.com/baoweise-bot/aimili-vpngate)
  under GNU GPL v3 or later. See [NOTICE.md](NOTICE.md) for attribution.

### Software and frontend dependencies

- **OpenVPN**: an external runtime dependency. This repository does not
  distribute OpenVPN binaries. Operators must follow OpenVPN's own license and
  trademark rules. This project is not affiliated with or endorsed by OpenVPN
  Inc.
- **Lucide**: the management UI loads Lucide through `unpkg.com`. Lucide is
  published under the ISC License; confirm the license for the exact referenced
  release upstream.
- **Google Fonts**: the UI may load Outfit, JetBrains Mono, Anton, Condiment,
  IBM Plex Mono, and Noto Sans SC. These fonts are generally distributed under
  their respective SIL Open Font License or project license; consult each
  upstream font package for authoritative terms.

### Remote animation media

`webui/index.html` references three demonstration videos hosted on
`cloudfront.net`. The videos are not stored in this repository and do not
automatically become GPL-licensed because the surrounding source code uses GPL.
This project makes no representation about ownership, license duration,
continued availability, or public-distribution rights. Operators must confirm
that they have permission to use them. Otherwise, remove the `<source>` URLs or
replace them with self-hosted media they own or are clearly licensed to use.

Loading Google Fonts, unpkg, or remote videos can disclose a visitor's IP
address, browser metadata, and referrer to those providers. Self-host or disable
external assets where privacy, localization, or content-security requirements
apply.

### Node and network-data services

- **VPNGate** and **PublicVPNList**: node metadata and OpenVPN profiles come
  from independent third parties. Users must follow their terms, privacy
  policies, research/use restrictions, and node-operator requirements.
- **ipify, ip.sb, ifconfig.me, and icanhazip.com**: used for exit-IP and
  connectivity diagnostics. Requests disclose the egress IP and necessary
  network metadata to the respective provider.

### Inherited upstream links

The legacy embedded UI may retain forum, Telegram, VPS promotion, or affiliate
links originally added upstream. They remain for compatibility and historical
attribution. Their presence is not a quality warranty from this derivative and
does not imply that those third parties endorse this project.
