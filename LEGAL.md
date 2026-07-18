# Legal, Safety, and Acceptable Use Notice / 法律、安全与合规说明

This document provides general project information, not legal advice.
本文仅为一般项目说明，不构成法律意见。

## 中文

### 合法和授权使用

使用者只能在当地法律允许的情况下，并在自己拥有或获得明确授权的设备、网络和
账户上安装、测试和运行本软件。不同国家和地区对 VPN、代理、加密通信、日志保存、
数据跨境传输和网络服务运营可能有不同要求，使用者应自行取得专业意见并承担合规责任。

不得将本软件用于未授权访问、绕过访问控制、凭据攻击、恶意扫描、垃圾信息、欺诈、
侵权内容分发、干扰网络服务、隐藏违法活动来源，或任何违反适用法律和第三方权利的用途。

### 第三方服务和出口节点

VPNGate、PublicVPNList、OpenVPN 配置提供方、VPS 服务商和公共 VPN 节点均为独立
第三方。本项目不拥有、运营、审核或担保这些节点。节点可能记录元数据、修改流量、
失效、被错误标注或受到当地法律约束。请将所有公共出口视为不可信网络，并始终使用
TLS、SSH 等端到端加密。不要经未知节点传输明文密码、私钥、支付资料或其他敏感数据。

使用者应分别阅读并遵守各数据来源、网络服务商、托管服务商和目标服务的条款、
隐私政策、流量限制、版权政策、出口管制和制裁要求。

### 部署和运营责任

默认情况下应将代理仅绑定在本机。公网开放代理可能被用于滥用并导致封禁、费用、
投诉或法律责任。若确需远程访问，运营者应至少配置强认证、来源 IP 防火墙、TLS/VPN
接入、速率限制、日志保护、监控、补丁管理和事件响应流程。

软件按“现状”提供，不保证节点可用性、匿名性、IP 纯净度、住宅属性、速度、安全性
或适用于任何特定目的。IP 类型、地理位置和纯净度数据只能作为第三方信号，不能作为
身份、合法性或风险的确定性证明。

### 许可证和商业使用

本项目继承 GNU GPL v3 or later。GPL 允许复制、修改、分发和商业使用，但分发衍生
作品时必须继续满足 GPL 的源码、许可证和版权义务。维护者不能在 GPL 衍生版本中追加
“禁止商业使用”的法律限制。

维护者不提供商业部署、代理转售、付费节点服务或规避监管用途的授权、担保和支持。
这是维护政策与风险提示，不构成对 GPL 已授予权利的额外限制。若业务必须采用具有
约束力的非商用许可证，应先取得所有相关版权所有者的单独书面授权。

## English

### Lawful and authorized use

Install, test, and operate this software only where lawful and only on devices,
networks, and accounts you own or are explicitly authorized to use. Rules for
VPNs, proxies, encrypted communications, log retention, cross-border data
transfers, and network-service operation vary by jurisdiction. Operators are
responsible for obtaining appropriate professional advice and meeting all
applicable requirements.

Do not use this software for unauthorized access, bypassing access controls,
credential attacks, malicious scanning, spam, fraud, infringement, service
disruption, concealing unlawful activity, or any activity that violates
applicable law or third-party rights.

### Third-party services and exit nodes

VPNGate, PublicVPNList, OpenVPN profile providers, hosting providers, and public
VPN nodes are independent third parties. This project does not own, operate,
audit, or warrant them. A node may log metadata, alter traffic, disappear, be
misclassified, or be subject to local law. Treat every public exit as an
untrusted network and use end-to-end encryption such as TLS or SSH. Never send
plaintext credentials, private keys, payment data, or other sensitive material
through an unknown node.

Users must review and comply with the terms, privacy policies, traffic limits,
copyright rules, export controls, and sanctions requirements of every data
source, network provider, hosting provider, and destination service involved.

### Deployment and operator responsibility

Keep the proxy bound to localhost by default. A public open proxy can be abused
and may lead to suspension, unexpected charges, complaints, or legal liability.
Where remote access is necessary, operators should at minimum use strong
authentication, source-IP firewall rules, TLS or VPN access, rate limiting,
protected logs, monitoring, patch management, and an incident-response process.

The software is provided "as is". There is no guarantee of availability,
anonymity, IP cleanliness, residential classification, speed, security, or
fitness for a particular purpose. IP type, geolocation, and quality indicators
are third-party signals and are not definitive proof of identity, legality, or
risk.

The management UI can load fonts, icons, and demonstration videos from remote
content-delivery networks. A visitor's IP address, browser metadata, and
referrer may therefore be disclosed to those providers. Review
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), confirm media rights, and
self-host or remove external assets where privacy or licensing requirements
demand it.

### License and commercial use

This project remains under GNU GPL v3 or later. GPL permits copying,
modification, distribution, and commercial use, subject to its source,
licensing, and copyright obligations when derivatives are distributed. A GPL
derivative cannot add a legally binding non-commercial restriction.

The maintainers do not offer authorization, warranty, or support for commercial
deployment, proxy resale, paid node services, or regulatory-evasion use. This is
a maintenance policy and risk notice, not an additional restriction on rights
already granted by GPL. A binding non-commercial license would require separate
written permission from every relevant copyright holder.
