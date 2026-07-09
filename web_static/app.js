const ipList = document.querySelector("#ip-list");
const rowTemplate = document.querySelector("#ip-row-template");
const form = document.querySelector("#ip-form");
const addRowButton = document.querySelector("#add-row");
const clearButton = document.querySelector("#clear-all");
const runState = document.querySelector("#run-state");
const scoreBody = document.querySelector("#score-body");
const summaryStrip = document.querySelector("#summary-strip");
const rankCards = document.querySelector("#rank-cards");
const detailPanel = document.querySelector("#detail-panel");
const headerStatus = document.querySelector(".header-status");

let lastReports = [];
let selectedIp = null;

const COUNTRY_NAMES = {
  US: "美国",
  CN: "中国",
  HK: "中国香港",
  MO: "中国澳门",
  TW: "中国台湾",
  JP: "日本",
  KR: "韩国",
  SG: "新加坡",
  GB: "英国",
  DE: "德国",
  FR: "法国",
  NL: "荷兰",
  CA: "加拿大",
  AU: "澳大利亚",
  RU: "俄罗斯",
  IN: "印度",
};

function addRow(value = "") {
  const node = rowTemplate.content.firstElementChild.cloneNode(true);
  const input = node.querySelector(".ip-input");
  input.value = value;
  node.querySelector(".remove-row").addEventListener("click", () => {
    if (ipList.children.length > 1) {
      node.remove();
    } else {
      input.value = "";
      input.focus();
    }
  });
  input.addEventListener("paste", handlePaste);
  ipList.appendChild(node);
  input.focus();
}

async function fillCurrentExit() {
  setState("正在识别当前出口 IP...");
  try {
    const response = await fetch("/api/current", { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok || !payload.ok || !payload.ip) {
      throw new Error(payload.error || "无法识别当前出口 IP");
    }
    const input = document.querySelector(".ip-input");
    if (input && !input.value.trim()) {
      input.value = payload.ip;
    }
    setState(`当前出口 IP：${payload.ip}`);
  } catch (error) {
    setState("未能自动识别当前出口 IP，可手动输入", true);
  }
}

function handlePaste(event) {
  const text = event.clipboardData.getData("text");
  const values = parseIpText(text);
  if (values.length <= 1) return;
  event.preventDefault();
  event.target.value = values.shift();
  values.forEach((value) => addRow(value));
}

function parseIpText(text) {
  return text
    .split(/[\s,;]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function collectIps() {
  return [...document.querySelectorAll(".ip-input")]
    .map((input) => input.value.trim())
    .filter(Boolean);
}

function setBusy(busy) {
  document.querySelectorAll("button, input").forEach((el) => {
    el.disabled = busy;
  });
}

function setState(message, isError = false) {
  runState.textContent = message;
  headerStatus.classList.toggle("error", isError);
}

function scoreColor(score, max = 100) {
  const safeMax = Number(max) || 100;
  const ratio = Math.max(0, Math.min(1, Number(score || 0) / safeMax));
  const hue = Math.round(ratio * 128);
  const light = 31 + Math.round((1 - Math.abs(ratio - 0.55)) * 5);
  return `hsl(${hue} 66% ${light}%)`;
}

function countryName(code) {
  if (!code) return "未知";
  return COUNTRY_NAMES[String(code).toUpperCase()] || String(code).toUpperCase();
}

function displayLocation(item) {
  const country = countryName(item.country);
  return [country, item.city].filter(Boolean).join(" / ") || "未知";
}

function displayAsn(value) {
  if (!value) return "未知";
  const text = String(value).toUpperCase();
  return text.startsWith("AS") ? text : `AS${text}`;
}

function displayValue(value) {
  if (value == null || value === "") return "未知";
  return String(value)
    .replace(/^unknown$/i, "未知")
    .replace(/^Datacenter\/Hosting$/i, "机房IP")
    .replace(/^Business$/i, "商业宽带")
    .replace(/^ISP$/i, "家宽/ISP")
    .replace(/^Mobile$/i, "移动网络")
    .replace(/^Education$/i, "教育网")
    .replace(/^Government$/i, "政府网络");
}

function profileOf(item) {
  return item.profile || {
    primary: displayValue(item.ip_type),
    primary_tone: "neutral",
    native: "原生待复核",
    native_tone: "neutral",
    risk: "待判断",
    risk_tone: "neutral",
    summary: "数据源不足，建议人工复核。",
    tags: [{ label: displayValue(item.ip_type), tone: "neutral" }],
    evidence: [],
    source_count: 0,
  };
}

function rblText(item) {
  const rbl = item.rbl || {};
  const count = Number(rbl.listed_count || 0);
  if (count > 0) return `命中 ${count} 个`;
  if (rbl.blocked_names && rbl.blocked_names.length) return "部分查询受限";
  return "未命中";
}

function dnsText(item) {
  return item.dns_leak && item.dns_leak.dns_leak_suspected ? "国家疑似不一致" : "正常";
}

function translateReason(reason) {
  const text = String(reason || "");
  const rules = [
    [/one or more sources mark Tor/i, "数据源标记为 Tor 出口"],
    [/one or more sources mark proxy/i, "数据源标记为代理IP"],
    [/one or more sources mark VPN/i, "数据源标记为 VPN"],
    [/known abuser|recent abuse/i, "存在滥用或风控记录"],
    [/bot\/crawler|bot|crawler/i, "存在 Bot/Crawler 标记"],
    [/hosting\/datacenter|hosting|datacenter/i, "数据源标记为机房/托管 IP"],
    [/bogon/i, "Bogon/保留地址异常"],
    [/exit IP observations are inconsistent: (.*)/i, "多个接口看到的出口 IP 不一致：$1"],
    [/country observations are inconsistent: (.*)/i, "多个数据源的国家归属不一致：$1"],
    [/ASN observations are inconsistent: (.*)/i, "多个数据源的 ASN 不一致：$1"],
    [/city\/geolocation differs across sources/i, "城市/地理库不一致"],
    [/organization attribution differs across sources/i, "组织/主体归属不一致"],
    [/company\/asn owner mismatch: (.*) over (.*)/i, "公司主体与 ASN 上游不一致：$1 / $2"],
    [/business allocation rides upstream ASN: (.*)/i, "商业段挂靠上游 ASN，疑似转租：$1"],
    [/hosting\/reseller naming signal: (.*)/i, "命名含托管/转租信号：$1"],
    [/business IP is less proven than residential\/ISP/i, "Business 类型缺少住宅/家宽证明，长期弹性偏弱"],
    [/abuse contact country differs from IP geolocation country/i, "Abuse 联系地址国家与 IP 地理归属不同"],
    [/proxy mode did not confirm/i, "代理出口未被所有接口一致确认"],
    [/DNS resolver country differs/i, "DNS 解析出口国家与 IP 归属不一致"],
    [/missing or failed public sources: scamalytics/i, "Scamalytics 自动查询失败，需人工复核"],
    [/missing or failed public sources: (.*)/i, "部分公开数据源失败：$1"],
    [/optional keyed sources skipped: (.*)/i, "部分需要 API Key 的数据源已跳过"],
    [/RBL listed: (.*)/i, "邮件黑名单命中：$1"],
    [/network stability score is low/i, "网络稳定性得分偏低"],
    [/clean/i, "未见明显命中"],
  ];
  for (const [pattern, replacement] of rules) {
    if (pattern.test(text)) return text.replace(pattern, replacement);
  }
  return text || "无明显扣分项";
}

function recommendationShort(text) {
  if (!text) return "待判断";
  if (text.includes("主出口")) return "主出口观察";
  if (text.includes("可用")) return "可用观察";
  if (text.includes("备用")) return "备用";
  if (text.includes("高风险")) return "高风险";
  if (text.includes("不建议")) return "不建议";
  return text;
}

function renderSummary(reports) {
  const count = reports.length;
  const avg = count ? Math.round(reports.reduce((sum, item) => sum + item.score, 0) / count) : 0;
  const pass = reports.filter((item) => item.score >= 85).length;
  const risk = reports.filter((item) => item.score < 55).length;
  summaryStrip.innerHTML = [
    summaryChip(count, "总数"),
    summaryChip(avg, "均分"),
    summaryChip(pass, "优质"),
    summaryChip(risk, "风险"),
  ].join("");
}

function renderRankCards(reports) {
  if (!reports.length) {
    rankCards.innerHTML = `
      <div class="result-empty">
        <strong>等待检测</strong>
        <span>提交 IP 后会在这里显示排序结论。</span>
      </div>`;
    return;
  }
  rankCards.innerHTML = reports
    .map((item) => {
      const location = displayLocation(item);
      const profile = profileOf(item);
      const reason = item.main_reasons && item.main_reasons.length ? translateReason(item.main_reasons[0]) : "无明显扣分项";
      const selected = item.ip === selectedIp ? " selected" : "";
      return `
        <article class="rank-card${selected}" data-ip="${escapeAttr(item.ip)}">
          <div class="rank-score" style="background:${scoreColor(item.score)}">${escapeHtml(item.score)}</div>
          <div class="rank-main">
            <div class="rank-title">
              <strong title="${escapeAttr(item.ip)}">${escapeHtml(item.ip)}</strong>
              <span>#${item.rank} · ${escapeHtml(recommendationShort(item.recommendation))}</span>
            </div>
            <div class="profile-line compact">
              <span class="profile-primary ${escapeAttr(profile.primary_tone || 'neutral')}">${escapeHtml(profile.primary)}</span>
              <span class="profile-status ${escapeAttr(profile.native_tone || 'neutral')}">${escapeHtml(profile.native)}</span>
              <span class="profile-status ${escapeAttr(profile.risk_tone || 'neutral')}">${escapeHtml(profile.risk)}</span>
            </div>
          </div>
          <div class="rank-meta">
            <span>${escapeHtml(location)}</span>
            <span>${escapeHtml(displayAsn(item.asn))}</span>
            <span>RBL ${escapeHtml(rblText(item))}</span>
          </div>
          <p>${escapeHtml(reason)}</p>
        </article>`;
    })
    .join("");

  document.querySelectorAll(".rank-card").forEach((card) => {
    card.addEventListener("click", () => selectReport(card.dataset.ip));
  });
}

function summaryChip(value, label) {
  return `<div class="summary-chip"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`;
}

function renderTable(reports) {
  if (!reports.length) {
    scoreBody.innerHTML = '<tr class="empty-row"><td colspan="10">无结果</td></tr>';
    return;
  }

  scoreBody.innerHTML = reports
    .map((item) => {
      const dims = item.dimensions || {};
      const rep = dims.reputation || { score: 0, max_score: 35 };
      const con = dims.consistency || { score: 0, max_score: 20 };
      const rbl = dims.rbl || { score: 0, max_score: 15 };
      const sta = dims.stability || { score: 0, max_score: 20 };
      const data = dims.data_quality || { score: 0, max_score: 10 };
      const profile = profileOf(item);
      const selected = item.ip === selectedIp ? " selected" : "";
      return `
        <tr class="result-row${selected}" data-ip="${escapeAttr(item.ip)}">
          <td class="rank-col">${item.rank}</td>
          <td title="${escapeAttr(item.ip)}"><strong>${escapeHtml(item.ip)}</strong></td>
          <td class="score-cell" style="background:${scoreColor(item.score)}">${item.score}</td>
          <td title="${escapeAttr(profile.summary || profile.primary)}">
            <div class="table-profile">
              <strong>${escapeHtml(profile.primary)}</strong>
              <span>${escapeHtml(profile.native)}</span>
            </div>
          </td>
          <td title="${escapeAttr(displayLocation(item))}">${escapeHtml(displayLocation(item))}</td>
          ${dimCell(rep)}
          ${dimCell(con)}
          ${dimCell(rbl)}
          ${dimCell(sta)}
          ${dimCell(data)}
        </tr>`;
    })
    .join("");

  document.querySelectorAll(".result-row").forEach((row) => {
    row.addEventListener("click", () => selectReport(row.dataset.ip));
  });
}

function dimCell(metric) {
  const score = Number(metric.score || 0);
  const max = Number(metric.max_score || 1);
  return `<td class="dim-cell" style="background:${scoreColor(score, max)}">${score}/${max}</td>`;
}

function selectReport(ip) {
  selectedIp = ip;
  renderRankCards(lastReports);
  renderTable(lastReports);
  const report = lastReports.find((item) => item.ip === ip);
  renderDetail(report);
}

function renderDetail(report) {
  if (!report) {
    detailPanel.innerHTML = '<div class="detail-empty">选择一行查看详情</div>';
    return;
  }
  const dims = report.dimensions || {};
  const reasons = report.main_reasons && report.main_reasons.length ? report.main_reasons.map(translateReason) : ["无明显扣分项"];
  const links = report.manual_review_links || [];
  const profile = profileOf(report);
  const evidence = profile.evidence || [];
  detailPanel.innerHTML = `
    <div class="detail-title">
      <div>
        <p class="eyebrow">当前选中</p>
        <h3>${escapeHtml(report.ip)}</h3>
      </div>
      <span class="detail-score" style="background:${scoreColor(report.score)}">${escapeHtml(report.score)}</span>
    </div>
    <div class="detail-profile">
      <span class="profile-primary ${escapeAttr(profile.primary_tone || 'neutral')}">${escapeHtml(profile.primary)}</span>
      <span class="profile-status ${escapeAttr(profile.native_tone || 'neutral')}">${escapeHtml(profile.native)}</span>
      <span class="profile-status ${escapeAttr(profile.risk_tone || 'neutral')}">${escapeHtml(profile.risk)}</span>
    </div>
    <p class="detail-summary">${escapeHtml(profile.summary || "建议结合人工复核链接判断。")}</p>
    <div class="detail-grid">
      ${metricCard("建议", report.recommendation)}
      ${metricCard("ASN", displayAsn(report.asn))}
      ${metricCard("ISP", displayValue(report.isp))}
      ${metricCard("组织", displayValue(report.organization))}
      ${metricCard("国家/城市", displayLocation(report))}
      ${metricCard("公开信誉", dimText(dims.reputation))}
      ${metricCard("一致性", dimText(dims.consistency))}
      ${metricCard("RBL", `${rblText(report)} · ${dimText(dims.rbl)}`)}
      ${metricCard("数据", dimText(dims.data_quality))}
      ${metricCard("稳定", formatRate(report.stability && report.stability.success_rate))}
      ${metricCard("DNS 状态", dnsText(report))}
      ${metricCard("数据源", profile.source_count ? `${profile.source_count} 个` : "不足")}
    </div>

    <div class="detail-section">
      <h4>证据摘要</h4>
      <div class="reason-list">
        ${evidence.map((item) => `<span class="reason-tag neutral">${escapeHtml(item)}</span>`).join("") || '<span class="reason-tag neutral">暂无更多证据</span>'}
      </div>
    </div>

    <div class="detail-section">
      <h4>主要原因</h4>
      <div class="reason-list">
        ${reasons.map((item) => `<span class="reason-tag warn">${escapeHtml(item)}</span>`).join("")}
      </div>
    </div>

    <div class="detail-section">
      <h4>人工复核</h4>
      <div class="link-list">
        ${links.map((link) => `<a href="${escapeAttr(link.url)}" target="_blank" rel="noreferrer" title="${escapeAttr(link.note || "")}">${escapeHtml(link.name)}</a>`).join("")}
      </div>
    </div>
  `;
}

function metricCard(label, value) {
  return `<div class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(displayValue(value))}</strong></div>`;
}

function dimText(metric) {
  if (!metric) return "未检测";
  return `${metric.score}/${metric.max_score}`;
}

function formatRate(value) {
  if (value == null) return "未检测";
  return `${Math.round(Number(value) * 100)}%`;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, "&#096;");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const ips = collectIps();
  if (!ips.length) {
    setState("请输入至少一个 IP", true);
    return;
  }
  setBusy(true);
  setState("检测中，当前流程会低频请求多个公开数据源...");
  rankCards.innerHTML = '<div class="result-empty"><strong>检测中</strong><span>正在低频查询公开数据源。</span></div>';
  scoreBody.innerHTML = '<tr class="empty-row"><td colspan="10">检测中</td></tr>';
  detailPanel.innerHTML = '<div class="detail-empty">等待结果</div>';
  try {
    const response = await fetch("/api/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ips }),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      throw new Error(payload.error || `HTTP ${response.status}`);
    }
    lastReports = payload.reports || [];
    selectedIp = lastReports[0] ? lastReports[0].ip : null;
    renderSummary(lastReports);
    renderRankCards(lastReports);
    renderTable(lastReports);
    renderDetail(lastReports[0]);
    const invalidCount = (payload.input_errors || []).length;
    const suffix = invalidCount ? `，忽略 ${invalidCount} 条无效输入` : "";
    setState(`完成 ${lastReports.length} 条检测${suffix}`);
  } catch (error) {
    setState(error.message || String(error), true);
    scoreBody.innerHTML = '<tr class="empty-row"><td colspan="10">检测失败</td></tr>';
  } finally {
    setBusy(false);
  }
});

addRowButton.addEventListener("click", () => addRow());
clearButton.addEventListener("click", () => {
  ipList.innerHTML = "";
  addRow();
  setState("准备就绪");
});

addRow();
renderSummary([]);
renderRankCards([]);
fillCurrentExit();
