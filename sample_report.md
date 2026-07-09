# 自有服务器出口 IP 健康检查报告

- 生成时间：2026-07-08T00:00:00+00:00
- 边界：只检测自有或授权出口的公开信誉、DNSBL、归属一致性和轻量连通性；不绕过验证码、Cloudflare 或访问控制。

## 总排名

| 排名 | IP | 总分 | 建议 | 主要原因 |
|---|---|---:|---|---|
| 1 | `IP_ADDRESS_A` | 82 | 可用，但建议观察 | optional keyed sources skipped |
| 2 | `IP_ADDRESS_B` | 58 | 只建议备用 | RBL listed: Spamhaus ZEN; one or more sources mark hosting/datacenter |

## 单 IP 详情

### 1. demo / IP_ADDRESS_A

- 综合评分：**82 / 100**
- 建议：**可用，但建议观察**
- 国家/城市：US / Los Angeles
- ASN：64500
- ISP：Example ISP
- Organization：Example ISP
- IP 类型：ISP
- 公开信誉：32 / 35
- RBL / DNSBL：15 / 15，命中 0 个
- 出口一致性：19 / 20
- DNS 泄漏：suspected=false
- 网络稳定性：18 / 20，成功率 1.0
- 数据完整性：8 / 10
- 主要扣分项：optional keyed sources skipped
- 数据源冲突：无明显冲突

人工复核链接：

- [IPRisk.top](https://iprisk.top/)：聚合信誉人工复核
- [Ping0.cc](https://ping0.cc/ip/IP_ADDRESS_A)：中文圈常用归属/ASN 复核
- [IPPure](https://ippure.com/)：中文圈纯净度/浏览器环境人工复核
- [LabIP.NET](https://www.labip.net/)：IP 类型、风险、DNS/WebRTC 等人工复核
- [PingIP](https://pingip.cn/)：IP 质量、风控、平台适用性人工复核
- [IPLark](https://iplark.com/check)：IP 质量、黑名单、VPN/代理人工复核
- [IPIPseek](https://check.ipipseek.com/)：IP 属性、风险值、纯净度人工复核
- [Scamalytics](https://scamalytics.com/ip/IP_ADDRESS_A)：欺诈分人工复核
- [AbuseIPDB](https://www.abuseipdb.com/check/IP_ADDRESS_A)：公开举报记录
- [IPinfo](https://ipinfo.io/IP_ADDRESS_A)：ASN/隐私/归属
- [bgp.tools](https://bgp.tools/ip/IP_ADDRESS_A)：BGP/ASN 复核
- [MXToolbox Blacklist](https://mxtoolbox.com/SuperTool.aspx?action=blacklist%3aIP_ADDRESS_A&run=toolpage)：邮件 RBL 聚合人工复核
- [Spamhaus Check](https://check.spamhaus.org/listed/?searchterm=IP_ADDRESS_A)：Spamhaus 复核

## 说明

- 邮件 RBL 主要反映邮件信誉，不等于浏览器访问风险；但长期出口仍建议纳入扣分。
- 数据源缺 key 或访问失败会降低数据完整性，不会导致整轮检测失败。
- 浏览器指纹、账号状态、业务平台策略不在本工具自动检测范围内，需要人工按授权场景复核。
