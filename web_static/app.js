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
  US: "美国", CN: "中国", HK: "中国香港", MO: "中国澳门", TW: "中国台湾",
  JP: "日本", KR: "韩国", SG: "新加坡", GB: "英国", DE: "德国", FR: "法国",
  NL: "荷兰", CA: "加拿大", AU: "澳大利亚", RU: "俄罗斯", IN: "印度",
  VN: "越南", TH: "泰国", ID: "印尼", MY: "马来西亚", PH: "菲律宾",
  TR: "土耳其", AE: "阿联酋", SA: "沙特", BR: "巴西", AR: "阿根廷",
  MX: "墨西哥", IT: "意大利", ES: "西班牙", CH: "瑞士", SE: "瑞典",
  NO: "挪威", FI: "芬兰", DK: "丹麦", PL: "波兰", UA: "乌克兰",
};

// ===== 输入行管理 =====
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
  setState("正在识别当前出口 IP...", "busy");
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
    setState("未能自动识别当前出口 IP，可手动输入", "error");
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
  return text.split(/[\s,;]+/).map((item) => item.trim()).filter(Boolean);
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

function setState(message, mode = "default") {
  runState.textContent = message;
  headerStatus.classList.remove("error", "busy");
  if (mode === "error") headerStatus.classList.add("error");
  if (mode === "busy") headerStatus.classList.add("busy");
}

// ===== 颜色与文案 =====
function scoreColor(score, max = 100) {
  const safeMax = Number(max) || 100;
  const ratio = Math.max(0, Math.min(1, Number(score || 0) / safeMax));
  // 红 → 琥珀 → 翠绿
  const hue = Math.round(ratio * 140);
  const light = 50 + Math.round(ratio * 8);
  return `hsl(${hue} 80% ${light}%)`;
}

function scoreRing(score, max = 100, size = 62) {
  const safeMax = Number(max) || 100;
  const ratio = Math.max(0, Math.min(1, Number(score || 0) / safeMax));
  const r = (size - 8) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - ratio);
  const color = scoreColor(score, max);
  return `
    <svg viewBox="0 0 ${size} ${size}" aria-hidden="true">
      <circle class="track" cx="${size/2}" cy="${size/2}" r="${r}" />
      <circle class="fill" cx="${size/2}" cy="${size/2}" r="${r}"
        stroke="${color}" stroke-dasharray="${circ.toFixed(2)}"
        stroke-dashoffset="${offset.toFixed(2)}" style="color:${color}" />
    </svg>`;
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
    [/one or more sources mark Tor/i, "识别为 Tor 出口"],
    [/one or more sources mark proxy/i, "识别为代理 IP"],
    [/one or more sources mark VPN/i, "识别为 VPN 出口"],
    [/known abuser|recent abuse/i, "存在滥用或风控记录"],
    [/bot\/crawler|bot|crawler/i, "存在 Bot/Crawler 标记"],
    [/hosting\/datacenter|hosting|datacenter/i, "识别为机房/托管 IP"],
    [/bogon/i, "Bogon/保留地址异常"],
    [/exit IP observations are inconsistent: (.*)/i, "多个接口看到的出口 IP 不一致：$1"],
    [/country observations are inconsistent: (.*)/i, "多源国家归属不一致：$1"],
    [/ASN observations are inconsistent: (.*)/i, "多源 ASN 不一致：$1"],
    [/city\/geolocation differs across sources/i, "城市/地理库不一致"],
    [/organization attribution differs across sources/i, "组织/主体归属不一致"],
    [/company\/asn owner mismatch: (.*) over (.*)/i, "公司主体与 ASN 上游不一致：$1 / $2"],
    [/business allocation rides upstream ASN: (.*)/i, "商业段挂靠上游 ASN，疑似转租：$1"],
    [/hosting\/reseller naming signal: (.*)/i, "命名含托管/转租信号：$1"],
    [/business IP is less proven than residential\/ISP/i, "商业段缺少住宅/家宽证明，长期弹性偏弱"],
    [/abuse contact country differs from IP geolocation country/i, "Abuse 联系地址国家与 IP 地理归属不同"],
    [/proxy mode did not confirm/i, "代理出口未被所有接口一致确认"],
    [/DNS resolver country differs/i, "DNS 解析出口国家与 IP 归属不一致"],
    [/missing or failed public sources: scamalytics/i, "部分信誉查询未完成，已作降权处理"],
    [/missing or failed public sources: (.*)/i, "部分公开查询未完成：$1"],
    [/optional keyed sources skipped: (.*)/i, "部分需鉴权的查询已跳过"],
    [/RBL listed: (.*)/i, "邮件黑名单命中：$1"],
    [/network stability score is low/i, "网络稳定性得分偏低"],
    [/single source/i, "（单源标记，已减半扣分）"],
    [/sources:/i, "（多源共识）"],
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

// ===== 扩展指标：人机流量比例 / Cloudflare 系数 / 适用场景 =====
function classifyIpFlags(report) {
  const profile = profileOf(report);
  const haystack = [
    String(profile.primary || ""),
    String(profile.risk || ""),
    String(profile.native || ""),
    String(report.ip_type || ""),
    String(profile.summary || ""),
  ].join(" ").toLowerCase();
  const hasRbl = Number((report.rbl || {}).listed_count || 0) > 0;
  return {
    isResidential: /住宅|家宽|isp|residential/.test(haystack),
    isMobile: /移动|mobile/.test(haystack),
    isDatacenter: /机房|datacenter|hosting|商业宽带|business/.test(haystack),
    isProxy: /代理|proxy/.test(haystack),
    isVpn: /vpn/.test(haystack),
    isTor: /tor/.test(haystack),
    hasRbl,
    score: Number(report.score || 0),
    profile,
  };
}

function humanBotRatio(report) {
  const f = classifyIpFlags(report);
  let human, tone;
  if (f.isTor) { human = 5; tone = "bad"; }
  else if (f.isVpn || f.isProxy) { human = 18; tone = "bad"; }
  else if (f.isMobile) { human = 92; tone = "good"; }
  else if (f.isResidential) { human = 85; tone = "good"; }
  else if (f.isDatacenter) { human = 28; tone = "warn"; }
  else { human = 50; tone = "neutral"; }
  // 信誉分偏低时进一步下修
  if (f.score < 55) human = Math.max(2, human - 25);
  else if (f.score < 70) human = Math.max(5, human - 12);
  if (f.hasRbl) human = Math.max(2, human - 15);
  human = Math.max(1, Math.min(99, Math.round(human)));
  return { human, bot: 100 - human, tone };
}

function cloudflareCoeff(report) {
  const f = classifyIpFlags(report);
  // 0-100，数值越高代表被 CF 挑战/拦截的概率越大
  let coeff = 4;
  if (f.isResidential) coeff += 6;
  if (f.isMobile) coeff += 2;
  if (f.isDatacenter) coeff += 34;
  if (f.isVpn) coeff += 32;
  if (f.isProxy) coeff += 26;
  if (f.isTor) coeff += 60;
  if (f.hasRbl) coeff += 22;
  // 信誉分越低，被风控的可能性越高
  coeff += Math.max(0, (70 - f.score) * 0.55);
  coeff = Math.min(99, Math.max(1, Math.round(coeff)));
  let level, tone;
  if (coeff < 20) { level = "低风险"; tone = "good"; }
  else if (coeff < 45) { level = "中风险"; tone = "warn"; }
  else if (coeff < 72) { level = "高风险"; tone = "warn"; }
  else { level = "极高风险"; tone = "bad"; }
  return { coeff, level, tone };
}

function applicableScenarios(report) {
  const f = classifyIpFlags(report);
  const good = [];
  const caution = [];
  const bad = [];

  if (f.isResidential && f.score >= 80 && !f.hasRbl) {
    good.push("Netflix / Disney+ 流媒体", "跨境电商账号", "Google / 社媒登录", "ChatGPT / AI 服务", "账号注册");
  } else if (f.isResidential && f.score >= 65) {
    good.push("跨境电商观察", "社媒养号");
    caution.push("流媒体需实测地区匹配");
  } else if (f.isMobile && f.score >= 70) {
    good.push("短视频 / 移动应用", "社媒账号", "短信验证码接收");
    caution.push("流媒体需实测");
  } else if (f.isDatacenter && !f.isProxy && f.score >= 70) {
    good.push("API 调用 / 爬虫合规", "服务器托管", "CDN / 反代节点", "自建服务");
    caution.push("不适合账号注册");
    bad.push("流媒体（区域受限）");
  } else if (f.isDatacenter) {
    caution.push("服务器用途", "API 调用");
    bad.push("账号注册 / 流媒体");
  } else {
    caution.push("建议结合人工复核");
  }

  if (f.isVpn || f.isProxy) {
    bad.push("账号操作 / 支付");
    caution.push("仅适合中转用途");
  }
  if (f.isTor) {
    bad.push("几乎所有业务场景");
  }
  if (f.hasRbl) {
    bad.push("邮件发送 (SMTP)");
  }
  if (f.score < 50) {
    bad.push("敏感业务 / 账号操作");
  }
  return { good, caution, bad };
}

// ===== 渲染：摘要 =====
function renderSummary(reports) {
  const count = reports.length;
  const avg = count ? Math.round(reports.reduce((sum, item) => sum + item.score, 0) / count) : 0;
  const pass = reports.filter((item) => item.score >= 85).length;
  const risk = reports.filter((item) => item.score < 55).length;
  summaryStrip.innerHTML = [
    summaryChip(count, "总数"),
    summaryChip(avg, "均分"),
    summaryChip(pass, "优质", "strong"),
    summaryChip(risk, "风险", "risk"),
  ].join("");
}

function summaryChip(value, label, mod = "") {
  return `<div class="summary-chip ${mod}"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`;
}

// ===== 渲染：排名卡片 =====
function renderRankCards(reports) {
  if (!reports.length) {
    rankCards.innerHTML = `
      <div class="result-empty">
        <strong>等待探测信号</strong>
        <span>提交 IP 后会按评分排序展示</span>
      </div>`;
    return;
  }
  rankCards.innerHTML = reports
    .map((item, idx) => {
      const location = displayLocation(item);
      const profile = profileOf(item);
      const reason = item.main_reasons && item.main_reasons.length ? translateReason(item.main_reasons[0]) : "无明显扣分项";
      const selected = item.ip === selectedIp ? " selected" : "";
      const delay = idx * 0.06;
      return `
        <article class="rank-card${selected}" data-ip="${escapeAttr(item.ip)}" style="animation-delay:${delay}s">
          <div class="rank-score">
            ${scoreRing(item.score, 100, 62)}
            <span>${escapeHtml(item.score)}</span>
          </div>
          <div class="rank-main">
            <div class="rank-title">
              <strong title="${escapeAttr(item.ip)}">${escapeHtml(item.ip)}</strong>
              <span>#${item.rank} · ${escapeHtml(recommendationShort(item.recommendation))}</span>
            </div>
            <div class="profile-line">
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

// ===== 渲染：表格 =====
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
      const rbl = dims.rbl || { score: 0, max_score: 20 };
      const sta = dims.stability || { score: 0, max_score: 15 };
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

// ===== 雷达图 =====
function radarSvg(dims) {
  const axes = [
    { key: "reputation", label: "信誉", max: 35 },
    { key: "consistency", label: "一致", max: 20 },
    { key: "rbl", label: "RBL", max: 20 },
    { key: "stability", label: "稳定", max: 15 },
    { key: "data_quality", label: "数据", max: 10 },
  ];
  const cx = 130, cy = 120, R = 78;
  const n = axes.length;
  const points = axes.map((ax, i) => {
    const dim = dims[ax.key] || { score: 0, max_score: ax.max };
    const ratio = Math.max(0, Math.min(1, Number(dim.score || 0) / Number(dim.max_score || ax.max)));
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
    const x = cx + Math.cos(angle) * R * ratio;
    const y = cy + Math.sin(angle) * R * ratio;
    return { x, y, label: ax.label, value: `${dim.score}/${dim.max_score}`, angle, ratio };
  });
  const polygon = points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");

  // 网格圈（4 层）
  const gridRings = [0.25, 0.5, 0.75, 1].map((r) => {
    const pts = axes.map((_, i) => {
      const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
      return `${(cx + Math.cos(angle) * R * r).toFixed(1)},${(cy + Math.sin(angle) * R * r).toFixed(1)}`;
    }).join(" ");
    return `<polygon class="grid" points="${pts}" />`;
  }).join("");

  // 轴线
  const axisLines = axes.map((_, i) => {
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
    const x = cx + Math.cos(angle) * R;
    const y = cy + Math.sin(angle) * R;
    return `<line class="axis" x1="${cx}" y1="${cy}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" />`;
  }).join("");

  // 标签
  const labels = points.map((p) => {
    const lx = cx + Math.cos(p.angle) * (R + 14);
    const ly = cy + Math.sin(p.angle) * (R + 14);
    return `<text class="label" x="${lx.toFixed(1)}" y="${(ly + 3).toFixed(1)}">${p.label}</text>`;
  }).join("");

  const values = points.map((p) => {
    const lx = cx + Math.cos(p.angle) * (R + 26);
    const ly = cy + Math.sin(p.angle) * (R + 26);
    return `<text class="value" x="${lx.toFixed(1)}" y="${(ly + 3).toFixed(1)}">${p.value}</text>`;
  }).join("");

  return `
    <svg class="radar-svg" viewBox="0 0 260 240" aria-hidden="true">
      ${gridRings}
      ${axisLines}
      <polygon class="area" points="${polygon}" />
      ${points.map((p) => `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="2.6" fill="${scoreColor(p.ratio * 100)}" />`).join("")}
      ${labels}
      ${values}
    </svg>`;
}

// ===== 维度条 =====
function dimBars(dims) {
  const items = [
    { key: "reputation", label: "REPUT", max: 35 },
    { key: "consistency", label: "CONSIST", max: 20 },
    { key: "rbl", label: "RBL", max: 20 },
    { key: "stability", label: "STABLE", max: 15 },
    { key: "data_quality", label: "DATA", max: 10 },
  ];
  return items.map((it) => {
    const dim = dims[it.key] || { score: 0, max_score: it.max };
    const ratio = Math.max(0, Math.min(100, (Number(dim.score || 0) / Number(dim.max_score || it.max)) * 100));
    const color = scoreColor(dim.score, it.max);
    return `
      <div class="dim-bar">
        <span class="dim-name">${it.label}</span>
        <div class="dim-track"><div class="dim-fill" style="width:${ratio}%;background:linear-gradient(90deg, ${color}, ${color}cc)"></div></div>
        <span class="dim-val">${dim.score}/${dim.max_score}</span>
      </div>`;
  }).join("");
}

// ===== 详情面板 =====
function renderDetail(report) {
  if (!report) {
    detailPanel.innerHTML = `
      <div class="detail-empty">
        <div class="detail-empty-glyph" aria-hidden="true">
          <svg viewBox="0 0 64 64"><circle cx="32" cy="32" r="28" /><circle cx="32" cy="32" r="18" /><circle cx="32" cy="32" r="8" /></svg>
        </div>
        <p>选中任一 IP 查看深度画像</p>
        <span>雷达图 · 维度热力 · 证据链 · 复核链接</span>
      </div>`;
    return;
  }
  const dims = report.dimensions || {};
  const reasons = report.main_reasons && report.main_reasons.length ? report.main_reasons.map(translateReason) : ["无明显扣分项"];
  const links = report.manual_review_links || [];
  const profile = profileOf(report);
  const evidence = profile.evidence || [];
  const stb = report.stability || {};
  const hb = humanBotRatio(report);
  const cf = cloudflareCoeff(report);
  const scenarios = applicableScenarios(report);
  const scenarioTags = [
    ...scenarios.good.map((s) => `<span class="tag good">${escapeHtml(s)}</span>`),
    ...scenarios.caution.map((s) => `<span class="tag warn">${escapeHtml(s)}</span>`),
    ...scenarios.bad.map((s) => `<span class="tag bad">${escapeHtml(s)}</span>`),
  ].join("") || '<span class="tag neutral">暂无推荐</span>';
  detailPanel.innerHTML = `
    <div class="detail-title">
      <div>
        <p class="eyebrow">深度画像</p>
        <h3>${escapeHtml(report.ip)}</h3>
      </div>
      <span class="detail-score">
        ${scoreRing(report.score, 100, 64)}
        <span>${escapeHtml(report.score)}</span>
      </span>
    </div>
    <div class="detail-profile">
      <span class="profile-primary ${escapeAttr(profile.primary_tone || 'neutral')}">${escapeHtml(profile.primary)}</span>
      <span class="profile-status ${escapeAttr(profile.native_tone || 'neutral')}">${escapeHtml(profile.native)}</span>
      <span class="profile-status ${escapeAttr(profile.risk_tone || 'neutral')}">${escapeHtml(profile.risk)}</span>
    </div>
    <p class="detail-summary">${escapeHtml(profile.summary || "建议结合人工复核链接判断。")}</p>

    <div class="radar-wrap">
      <h4>维度雷达</h4>
      ${radarSvg(dims)}
    </div>

    <div class="dim-bars">${dimBars(dims)}</div>

    <div class="detail-grid">
      ${metricCard("建议", report.recommendation)}
      ${metricCard("ASN", displayAsn(report.asn))}
      ${metricCard("ISP", displayValue(report.isp))}
      ${metricCard("组织", displayValue(report.organization))}
      ${metricCard("国家/城市", displayLocation(report))}
      ${metricCard("RBL 状态", `${rblText(report)}`)}
      ${metricCard("RBL 评分", dimText(dims.rbl))}
      ${metricCard("DNS 状态", dnsText(report))}
      ${metricCard("稳定成功率", formatRate(stb.success_rate))}
      ${metricCard("P95 延迟", stb.p95_latency_ms != null ? `${Math.round(stb.p95_latency_ms)}ms` : "未检测")}
    </div>

    <div class="detail-section">
      <h4>扩展指标</h4>
      <div class="detail-ext">
        <div class="ext-row">
          <span class="ext-label">人机流量</span>
          <div>
            <div class="ext-value ${hb.tone}">人 ${hb.human}% / 机 ${hb.bot}%</div>
          </div>
        </div>
        <div class="ext-row">
          <span class="ext-label">Cloudflare 系数</span>
          <div>
            <div class="ext-value ${cf.tone}">${cf.coeff} · ${cf.level}</div>
            <div class="cf-coeff-bar"><i style="width:${cf.coeff}%"></i></div>
          </div>
        </div>
        <div class="ext-row">
          <span class="ext-label">适用场景</span>
          <div class="scenario-list">${scenarioTags}</div>
        </div>
      </div>
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

// ===== 扫描中状态 =====
function renderScanning(ips) {
  rankCards.innerHTML = `
    <div class="scanning-card">
      <div class="scanner">
        <svg viewBox="0 0 44 44"><circle cx="22" cy="22" r="18" /></svg>
      </div>
      <div class="scan-text">
        <strong>正在探测 ${escapeHtml(ips.length)} 个出口</strong>
        <span>低频查询多源公开信誉 / RBL / DNS / 稳定性...</span>
      </div>
    </div>
    <div class="scan-progress"></div>`;
  scoreBody.innerHTML = '<tr class="empty-row"><td colspan="10">探测中 · 多源低频查询</td></tr>';
  detailPanel.innerHTML = `
    <div class="detail-empty">
      <div class="detail-empty-glyph" aria-hidden="true">
        <svg viewBox="0 0 64 64"><circle cx="32" cy="32" r="28" /><circle cx="32" cy="32" r="18" /><circle cx="32" cy="32" r="8" /></svg>
      </div>
      <p>等待结果回传</p>
      <span>完成后自动展开画像</span>
    </div>`;
}

// ===== 提交检测 =====
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const ips = collectIps();
  if (!ips.length) {
    setState("请输入至少一个 IP", "error");
    return;
  }
  setBusy(true);
  setState("探测中 · 多源低频查询", "busy");
  renderScanning(ips);
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
    setState(`完成 ${lastReports.length} 条探测${suffix}`);
  } catch (error) {
    setState(error.message || String(error), "error");
    rankCards.innerHTML = `<div class="result-empty"><strong>探测失败</strong><span>${escapeHtml(error.message || String(error))}</span></div>`;
    scoreBody.innerHTML = '<tr class="empty-row"><td colspan="10">探测失败</td></tr>';
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

// ===== WebRTC 泄露检测（本机浏览器侧） =====
const webrtcCard = document.querySelector("#webrtc-card");
const webrtcStatus = document.querySelector("#webrtc-status");
const webrtcDetail = document.querySelector("#webrtc-detail");
const webrtcRecheck = document.querySelector("#webrtc-recheck");

function isPrivateIp(ip) {
  return /^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|169\.254\.|127\.|::1$|fe80::|fc00::|fd00::)/i.test(ip);
}

async function gatherWebrtcIps(timeoutMs = 3000) {
  return new Promise((resolve) => {
    if (!window.RTCPeerConnection) {
      resolve({ supported: false });
      return;
    }
    const ips = new Set();
    let done = false;
    const finish = (extra) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      try { pc.close(); } catch (e) {}
      resolve({ supported: true, ips: [...ips], ...(extra || {}) });
    };
    let pc;
    try {
      pc = new RTCPeerConnection({ iceServers: [{ urls: ["stun:stun.l.google.com:19302", "stun:stun.cloudflare.com:3478"] }] });
    } catch (e) {
      resolve({ supported: false, error: String(e) });
      return;
    }
    try { pc.createDataChannel("leak-check"); } catch (e) {}
    pc.onicecandidate = (event) => {
      if (!event.candidate) {
        finish();
        return;
      }
      const c = event.candidate.candidate || "";
      const m = /([0-9]{1,3}(\.[0-9]{1,3}){3}|[a-f0-9]{1,4}(:[a-f0-9]{0,4}){2,7})/i.exec(c);
      if (m && m[1]) ips.add(m[1].toLowerCase());
    };
    pc.createOffer().then((offer) => pc.setLocalDescription(offer)).catch((e) => finish({ error: String(e) }));
    const timer = setTimeout(() => finish({ timeout: true }), timeoutMs);
  });
}

let visitorPublicIp = null;

async function runWebrtcCheck() {
  if (!webrtcCard) return;
  webrtcCard.classList.remove("ok", "warn", "bad");
  webrtcStatus.querySelector(".webrtc-text").textContent = "检测中...";
  webrtcDetail.innerHTML = "";

  // 先拿到访问者公网出口 IP（用于和 WebRTC 暴露的 IP 比对）
  if (!visitorPublicIp) {
    try {
      const resp = await fetch("/api/current", { cache: "no-store" });
      const data = await resp.json();
      if (resp.ok && data.ok && data.ip) visitorPublicIp = data.ip;
    } catch (e) {}
  }

  const result = await gatherWebrtcIps();
  if (!result.supported) {
    webrtcCard.classList.add("warn");
    webrtcStatus.querySelector(".webrtc-text").textContent = "浏览器不支持 WebRTC";
    webrtcDetail.innerHTML = "<strong>状态：</strong>无法检测";
    return;
  }

  const publicLeaked = [];
  const localLeaked = [];
  (result.ips || []).forEach((ip) => {
    if (isPrivateIp(ip)) localLeaked.push(ip);
    else publicLeaked.push(ip);
  });

  const visitorLower = visitorPublicIp ? String(visitorPublicIp).toLowerCase() : null;
  const matchesVisitor = visitorLower && publicLeaked.some((ip) => ip === visitorLower);

  let lines = [];
  lines.push(`<strong>出口 IP：</strong>${escapeHtml(visitorPublicIp || "未识别")}`);

  if (publicLeaked.length === 0 && localLeaked.length === 0) {
    webrtcCard.classList.add("ok");
    webrtcStatus.querySelector(".webrtc-text").textContent = "未检测到泄露";
    lines.push("<strong>公网 IP 暴露：</strong>无");
    lines.push("<strong>本地 IP 暴露：</strong>无");
  } else if (publicLeaked.length > 0) {
    // 暴露了公网 IP
    if (matchesVisitor) {
      webrtcCard.classList.add("warn");
      webrtcStatus.querySelector(".webrtc-text").textContent = "公网 IP 已通过 WebRTC 暴露";
    } else {
      webrtcCard.classList.add("bad");
      webrtcStatus.querySelector(".webrtc-text").textContent = "检测到非出口公网 IP 暴露";
    }
    lines.push(`<strong>公网 IP：</strong>${escapeHtml(publicLeaked.join(", "))}`);
    if (localLeaked.length) {
      lines.push(`<strong>本地 IP：</strong>${escapeHtml(localLeaked.join(", "))}`);
    }
  } else {
    // 只有本地 IP 暴露
    webrtcCard.classList.add("ok");
    webrtcStatus.querySelector(".webrtc-text").textContent = "仅本地 IP 暴露（公网安全）";
    lines.push(`<strong>本地 IP：</strong>${escapeHtml(localLeaked.join(", "))}`);
  }

  webrtcDetail.innerHTML = lines.join("<br>");
}

if (webrtcRecheck) {
  webrtcRecheck.addEventListener("click", () => {
    visitorPublicIp = null;
    runWebrtcCheck();
  });
}

// ===== 初始化 =====
addRow();
renderSummary([]);
renderRankCards([]);
fillCurrentExit().then(() => {
  visitorPublicIp = (document.querySelector(".ip-input") || {}).value || null;
});
runWebrtcCheck();
