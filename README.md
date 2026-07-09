# 自有服务器出口 IP 健康检查工具

用于批量检测你自己拥有或租用的 VPS / 代理出口。默认只做公开信誉、IP 归属、DNSBL/RBL、DNS 一致性和低频连通性检查。

重要边界：

- 只检测自有或已授权使用的 IP / 代理出口。
- 不绕过 Cloudflare、验证码、人机验证或访问控制。
- 不自动化访问风控页面，不探测第三方网站风控策略。
- 不做压力测试，不高频请求。
- 不做账号注册、登录、批量操作。
- 不把“解锁成功”当成“IP 干净”。默认没有解锁分。

## 安装

本工具核心逻辑使用 Python 标准库和 `curl`，方便在干净服务器上直接跑。可选安装 YAML/Jinja 支持：

```bash
python3 -m pip install -r requirements.txt
```

当前环境如果没有 PyYAML，也可以直接使用默认配置运行。

## 使用

启动本地可视化页面：

```bash
python3 web.py --quick
```

然后打开：

```text
http://127.0.0.1:8765/
```

页面会先自动识别当前出口 IP 并填入默认输入框，可用 `+` 添加多条。检测完成后会按综合评分自动排序，用紧凑排名列表、红色到深绿色的热力表格和单 IP 详情面板展示结果。

页面会额外生成中文圈更直观的 `IP 画像` 标签，例如：`原生IP倾向`、`住宅IP`、`家宽/ISP`、`商业宽带`、`机房IP`、`代理IP`、`VPN`、`Tor`、`RBL 命中`。这些标签来自多源字段归一化，建议结合人工复核链接判断。

其中 `原生IP倾向` 表示多源国家/ASN 基本一致，且未见代理、VPN、Tor、Bogon、RBL 命中等明显异常；它不是任何单一网站的“绝对原生”结论。

如果 IP 目前 `risk=0`、无滥用、无 RBL 命中，但出现上游 ASN 与公司主体不一致、转租/托管命名、城市库冲突、DNS 国家不一致等信号，工具会把它降到“可用但观察”或“只建议备用”。这个评分更偏长期浏览器出口的稳定性和风控弹性，而不是只看当下是否干净。

Web 页面复用 CLI 的健康检查逻辑，检测报告会写入 `reports/web-*/`。

检测 IP 列表：

```bash
python3 main.py --ips ips.example.txt --output reports
```

检测代理出口：

```bash
python3 main.py --proxies proxies.example.txt --output reports
```

指定配置：

```bash
python3 main.py --ips ips.example.txt --config config.example.yaml --output reports
```

快速模式：

```bash
python3 main.py --ips ips.example.txt --quick --output reports
```

完整低频模式：

```bash
python3 main.py --ips ips.example.txt --full --output reports
```

只输出 Markdown 和 CSV：

```bash
python3 main.py --ips ips.example.txt --format md,csv --output reports
```

兼容旧入口：

```bash
python3 ip_audit.py --ips ips.example.txt --output reports
```

## 输入格式

`ips.txt`：

```text
<IP_ADDRESS_1>
<IP_ADDRESS_2>
<IP_ADDRESS_3>
```

`proxies.txt`：

```text
socks5h://USER:PASS@PROXY_HOST:PORT
http://USER:PASS@PROXY_HOST:PORT
```

代理支持取决于本机 `curl`，通常支持 `socks5`、`socks5h`、`http`、`https`。

## 输出

每次运行生成：

- `reports/report.json`
- `reports/report.csv`
- `reports/report.md`
- `reports/raw/<target>/`
- `reports/logs/`

Web 页面运行会生成按时间命名的子目录，例如：

- `reports/web-20260708T093000Z/report.json`
- `reports/web-20260708T093000Z/report.csv`
- `reports/web-20260708T093000Z/report.md`

## 评分维度

总分 100：

- 公开信誉分：35
- 归属一致性分：20
- RBL / DNSBL 分：15
- 网络稳定分：20
- 数据完整性分：10

建议等级：

- `85-100`：适合作为主出口继续观察
- `70-84`：可用，但建议观察
- `55-69`：只建议备用
- `40-54`：不建议长期使用
- `0-39`：高风险，不建议使用

评分会额外关注长期出口常见隐患：

- 机房/托管/Datacenter 明确标记会比普通 Business 类型扣更多分。
- 公司主体与 ASN 上游明显不一致时，会提示 `主体不一致`、`转租/上游风险`。
- `host`、`colo`、`server`、`vps`、`dedicated`、`qechost` 等命名信号会降低长期分。
- Business 段如果缺少住宅、家宽、固定宽带证据，不再作为明显加分项。
- 城市/地理库冲突、DNS 解析出口国家不一致会从归属一致性扣分。

## 数据源

默认可无 key 使用：

- `ipinfo.io`
- `ipapi.is`
- `Scamalytics` 页面单次访问，遇到挑战只记录，不绕过
- DNSBL/RBL：Spamhaus、SpamCop、SORBS、Barracuda、CBL、UCEPROTECT、PSBL、HostKarma、SpamEatingMonkey、Truncate GBUDB

可选 API Key：

```bash
export IPINFO_TOKEN="..."
export IPREGISTRY_KEY="..."
export IPDATA_KEY="..."
export IPQS_KEY="..."
export ABUSEIPDB_KEY="..."
```

也可以写进 `config.yaml`：

```yaml
api_keys:
  ipinfo: ""
  ipregistry: ""
  ipdata: ""
  ipqualityscore: ""
  abuseipdb: ""
```

缺 key 的数据源会跳过，不会导致整体失败。

## DNSBL 注意

DNSBL 查询用 DNS 查询实现，不爬网页。工具会检测 resolver 是否把不存在的域名解析成假 IP。如果发现 DNS 劫持/污染，会跳过该 resolver，避免误判。

邮件 RBL 主要反映邮件信誉，不等于浏览器访问风险；但长期出口仍建议纳入扣分和人工复核。

## 人工复核

报告会自动生成这些链接：

- IPRisk.top
- Ping0.cc
- IPPure
- LabIP.NET
- PingIP
- IPLark
- IPIPseek
- Scamalytics
- AbuseIPDB
- IPinfo
- bgp.tools
- MXToolbox Blacklist
- Spamhaus Check

IPPure、LabIP.NET、PingIP、IPLark、IPIPseek 等中文圈常用站点目前作为人工复核链接加入，暂不做自动采集。原因是这些站点多依赖浏览器环境、动态页面或挑战页；在确认有稳定、合规、低频可用的 API 前，工具不会爬页面或绕过验证。

浏览器指纹、业务网站响应、账号状态不在默认自动化范围内。

## 隐私防护

公开文档和示例文件只使用 `<IP_ADDRESS>`、`PROXY_HOST` 等占位符，不放真实出口 IP、邮箱、用户名、本机路径或 API Key。提交前建议运行：

```bash
python3 tools/privacy_scan.py
```
