from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

from .models import TargetReport
from .utils import ensure_dir, quote_url_value


def manual_review_links(ip: str) -> list[dict[str, str]]:
    q = quote_url_value(ip)
    return [
        {"name": "IPRisk.top", "url": "https://iprisk.top/", "note": "聚合信誉人工复核"},
        {"name": "Ping0.cc", "url": f"https://ping0.cc/ip/{q}", "note": "中文圈常用归属/ASN 复核"},
        {"name": "IPPure", "url": "https://ippure.com/", "note": "中文圈纯净度/浏览器环境人工复核"},
        {"name": "LabIP.NET", "url": "https://www.labip.net/", "note": "IP 类型、风险、DNS/WebRTC 等人工复核"},
        {"name": "PingIP", "url": "https://pingip.cn/", "note": "IP 质量、风控、平台适用性人工复核"},
        {"name": "IPLark", "url": "https://iplark.com/check", "note": "IP 质量、黑名单、VPN/代理人工复核"},
        {"name": "IPIPseek", "url": "https://check.ipipseek.com/", "note": "IP 属性、风险值、纯净度人工复核"},
        {"name": "Scamalytics", "url": f"https://scamalytics.com/ip/{q}", "note": "欺诈分人工复核"},
        {"name": "AbuseIPDB", "url": f"https://www.abuseipdb.com/check/{q}", "note": "公开举报记录"},
        {"name": "IPinfo", "url": f"https://ipinfo.io/{q}", "note": "ASN/隐私/归属"},
        {"name": "bgp.tools", "url": f"https://bgp.tools/ip/{q}", "note": "BGP/ASN 复核"},
        {
            "name": "MXToolbox Blacklist",
            "url": f"https://mxtoolbox.com/SuperTool.aspx?action=blacklist%3a{q}&run=toolpage",
            "note": "邮件 RBL 聚合人工复核",
        },
        {"name": "Spamhaus Check", "url": f"https://check.spamhaus.org/listed/?searchterm={q}", "note": "Spamhaus 复核"},
    ]


def write_reports(reports: list[TargetReport], output_dir: Path, formats: set[str]) -> None:
    ensure_dir(output_dir)
    payload = {
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "reports": [item.to_dict() for item in reports],
    }
    if "json" in formats:
        (output_dir / "report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if "csv" in formats:
        write_csv(reports, output_dir / "report.csv")
    if "md" in formats:
        (output_dir / "report.md").write_text(render_markdown(reports, payload["generated_at"]), encoding="utf-8")


def write_csv(reports: list[TargetReport], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "rank",
                "name",
                "mode",
                "ip",
                "total_score",
                "recommendation",
                "ip_type",
                "country",
                "city",
                "asn",
                "organization",
                "rbl_listed_count",
                "success_rate",
                "main_reasons",
            ],
        )
        writer.writeheader()
        for rank, item in enumerate(sorted_reports(reports), 1):
            primary = primary_observation(item)
            writer.writerow(
                {
                    "rank": rank,
                    "name": item.target.name,
                    "mode": item.target.mode,
                    "ip": item.exit_ip,
                    "total_score": item.scores["total_score"],
                    "recommendation": item.scores["recommendation"],
                    "ip_type": item.scores["ip_type"],
                    "country": primary.get("country"),
                    "city": primary.get("city"),
                    "asn": primary.get("asn"),
                    "organization": primary.get("organization"),
                    "rbl_listed_count": item.rbl.get("rbl_listed_count"),
                    "success_rate": item.stability.get("success_rate"),
                    "main_reasons": " | ".join(item.scores.get("main_reasons", [])),
                }
            )


def render_markdown(reports: list[TargetReport], generated_at: str) -> str:
    ordered = sorted_reports(reports)
    lines = [
        "# 自有服务器出口 IP 健康检查报告",
        "",
        f"- 生成时间：{generated_at}",
        "- 边界：只检测自有或授权出口的公开信誉、DNSBL、归属一致性和轻量连通性；不绕过验证码、Cloudflare 或访问控制。",
        "",
        "## 总排名",
        "",
        "| 排名 | IP | 总分 | 建议 | 主要原因 |",
        "|---|---|---:|---|---|",
    ]
    for rank, item in enumerate(ordered, 1):
        reasons = "; ".join(item.scores.get("main_reasons", [])[:3]) or "无明显扣分项"
        lines.append(
            f"| {rank} | `{item.exit_ip}` | {item.scores['total_score']} | {item.scores['recommendation']} | {reasons} |"
        )

    lines.extend(["", "## 单 IP 详情", ""])
    for rank, item in enumerate(ordered, 1):
        primary = primary_observation(item)
        dimensions = item.scores["dimensions"]
        lines.extend(
            [
                f"### {rank}. {item.target.name} / {item.exit_ip}",
                "",
                f"- 综合评分：**{item.scores['total_score']} / 100**",
                f"- 建议：**{item.scores['recommendation']}**",
                f"- 国家/城市：{primary.get('country') or 'unknown'} / {primary.get('city') or 'unknown'}",
                f"- ASN：{primary.get('asn') or 'unknown'}",
                f"- ISP：{primary.get('isp') or 'unknown'}",
                f"- Organization：{primary.get('organization') or 'unknown'}",
                f"- IP 类型：{item.scores.get('ip_type')}",
                f"- 公开信誉：{dimensions['reputation']['score']} / {dimensions['reputation']['max_score']}",
                format_rbl_line(item, dimensions),
                f"- 出口一致性：{dimensions['consistency']['score']} / {dimensions['consistency']['max_score']}",
                f"- DNS 泄漏：suspected={item.dns_leak.get('dns_leak_suspected')}",
                f"- 网络稳定性：{dimensions['stability']['score']} / {dimensions['stability']['max_score']}，成功率 {item.stability.get('success_rate')}",
                f"- 数据完整性：{dimensions['data_quality']['score']} / {dimensions['data_quality']['max_score']}",
                f"- 主要扣分项：{'; '.join(item.scores.get('main_reasons', [])) or '无明显扣分项'}",
                f"- 数据源冲突：{format_conflicts(item.scores.get('source_conflicts', {}))}",
                "",
                "人工复核链接：",
                "",
            ]
        )
        for link in item.manual_review_links:
            lines.append(f"- [{link['name']}]({link['url']})：{link['note']}")
        lines.extend(["", ""])

    lines.extend(
        [
            "## 说明",
            "",
            "- 邮件 RBL 主要反映邮件信誉，不等于浏览器访问风险；但长期出口仍建议纳入扣分。",
            "- 数据源缺 key 或访问失败会降低数据完整性，不会导致整轮检测失败。",
            "- 浏览器指纹、账号状态、业务平台策略不在本工具自动检测范围内，需要人工按授权场景复核。",
        ]
    )
    return "\n".join(lines) + "\n"


def sorted_reports(reports: list[TargetReport]) -> list[TargetReport]:
    return sorted(reports, key=lambda item: item.scores["total_score"], reverse=True)


def primary_observation(item: TargetReport) -> dict[str, Any]:
    preferred = ["ipapi.is", "ipinfo", "ipregistry", "ipdata", "ipqualityscore", "abuseipdb"]
    for name in preferred:
        for obs in item.observations:
            if obs.source == name:
                return obs.to_dict()
    return item.observations[0].to_dict() if item.observations else {}


def format_conflicts(conflicts: dict[str, Any]) -> str:
    if not conflicts:
        return "无明显冲突"
    chunks = []
    for field, values in conflicts.items():
        chunks.append(f"{field}: {'; '.join(values)}")
    return " | ".join(chunks)


def format_rbl_line(item: TargetReport, dimensions: dict[str, Any]) -> str:
    if item.rbl.get("skipped"):
        return f"- RBL / DNSBL：跳过，原因：{item.rbl.get('reason', 'unknown')}"
    blocked = item.rbl.get("rbl_query_blocked_names") or []
    suffix = f"，查询被阻断 {len(blocked)} 个" if blocked else ""
    return (
        f"- RBL / DNSBL：{dimensions['rbl']['score']} / {dimensions['rbl']['max_score']}，"
        f"命中 {item.rbl.get('rbl_listed_count', 0)} 个{suffix}"
    )
