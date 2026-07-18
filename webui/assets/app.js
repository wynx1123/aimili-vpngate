const $ = (id) => document.getElementById(id);
const typeLabels = { residential: "住宅 IP", hosting: "机房 IP", mobile: "移动网络", normal: "普通网络", unknown: "待判断" };
const statusLabels = { active: "当前连接", available: "可用", pending: "待检测", unavailable: "不可用" };
const routingModeLabels = { auto: "智能自动", fixed_region: "固定国家", fixed_ip: "固定 IP", favorites: "仅收藏" };
const qualityLabels = { normal: "未发现代理特征", proxy: "检测到代理特征", datacenter: "机房网络", mobile: "移动网络" };
const store = {
  nodes: [], state: {},
  options: { catalogs: ["vpngate", "publicvpnlist", "all"], protocols: ["tcp", "udp"], publicvpnlist_sources: [] },
  measuring: new Set(), switchingNodeId: "", loadingNodes: false,
  pollTimer: 0, pollRunning: false, lastNodesLoadedAt: 0
};

function esc(value) {
  return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

async function api(path, options = {}, timeoutMs = 15000) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  const init = { credentials: "same-origin", ...options, signal: controller.signal };
  if (init.body && typeof init.body !== "string") {
    init.headers = { "Content-Type": "application/json", ...(init.headers || {}) };
    init.body = JSON.stringify(init.body);
  }
  try {
    const response = await fetch(`./api/${path}`, init);
    let payload = {};
    try { payload = await response.json(); } catch (_) { payload = {}; }
    if (response.status === 401) {
      window.location.reload();
      throw new Error("登录状态已失效");
    }
    if (!response.ok || payload.ok === false) throw new Error(payload.error || payload.message || `请求失败 (${response.status})`);
    return payload;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("请求超时，请稍后重试");
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}

function applyState(nextState) {
  if (nextState && typeof nextState === "object") store.state = { ...store.state, ...nextState };
}

function normalizeStatus(raw) {
  if (raw.active || raw.id === store.state.active_openvpn_node_id) return "active";
  if (raw.probe_status === "available") return "available";
  if (raw.probe_status === "unavailable") return "unavailable";
  if (raw.verified && Number(raw.latency_ms || raw.reported_latency_ms || 0) > 0) return "available";
  return "pending";
}

function normalizeNode(raw) {
  const ipType = String(raw.ip_type || "unknown").toLowerCase();
  const quality = String(raw.quality || "").toLowerCase();
  const protocol = String(raw.proto || raw.transport_protocol || "").toUpperCase() || "-";
  return {
    ...raw,
    id: String(raw.id || ""), status: normalizeStatus(raw),
    ip: String(raw.ip || raw.remote_host || "-"),
    city: String(raw.location || raw.country || "未知地区"),
    country: String(raw.country || "未知地区"), type: ipType,
    purity: qualityLabels[quality] || (ipType === "hosting" ? "机房网络" : ["residential", "mobile"].includes(ipType) ? "未发现代理特征" : "待判断"),
    source: String(raw.source || raw.catalog_source || "未知来源"), protocol,
    latency: Number(raw.latency_ms || raw.reported_latency_ms || raw.ping || 0),
    speed: Number(raw.speed_mbps || 0),
    favorite: (store.state.favorite_node_ids || []).includes(raw.id)
  };
}

function syncNormalizedNodes() { store.nodes = store.nodes.map((node) => normalizeNode(node)); }
function activeNode() {
  const activeId = store.state.active_openvpn_node_id;
  return store.nodes.find((node) => node.id === activeId || node.status === "active") || null;
}
function availableNodes() { return store.nodes.filter((node) => node.status === "available"); }
function pendingNodes() { return store.nodes.filter((node) => node.status === "pending"); }
function latencyClass(value) { return !value ? "" : value <= 80 ? "latency-good" : value <= 180 ? "latency-mid" : "latency-poor"; }
function refreshIcons() { if (window.lucide) window.lucide.createIcons({ attrs: { "stroke-width": 1.8 } }); }

function setButtonBusy(button, busy, label) {
  if (!button) return;
  if (busy) {
    button.dataset.originalLabel = button.innerHTML;
    button.disabled = true;
    button.innerHTML = `<span class="busy-spinner" aria-hidden="true"></span>${esc(label || "处理中")}`;
  } else {
    button.disabled = false;
    if (button.dataset.originalLabel) button.innerHTML = button.dataset.originalLabel;
    delete button.dataset.originalLabel;
    refreshIcons();
  }
}

function toast(message, title = "状态已更新", kind = "info") {
  const item = document.createElement("div");
  item.className = `toast toast--${kind}`;
  const heading = document.createElement("strong");
  const body = document.createElement("span");
  heading.textContent = title; body.textContent = message;
  item.append(heading, body); $("toast-region").appendChild(item);
  window.setTimeout(() => item.remove(), kind === "error" ? 5200 : 3600);
}

function renderStage() {
  syncNormalizedNodes();
  const active = activeNode();
  const pending = pendingNodes();
  const available = availableNodes();
  const scanning = store.measuring.size > 0 || (store.state.maintenance_running && !store.state.is_connecting);
  const switching = Boolean(store.switchingNodeId || store.state.is_connecting);
  const proxyHealthy = store.state.proxy_ok !== false;
  $("waiting-count").textContent = pending.length;
  $("available-count").textContent = available.length;
  $("waiting-caption").textContent = scanning ? "正在并发测量" : "个节点等待测量";
  $("waiting-video-state").textContent = scanning ? "检测中" : "排队中";
  $("waiting-stage").classList.toggle("is-scanning", scanning);
  $("active-stage").classList.toggle("is-switching", switching);
  $("active-video-state").textContent = switching ? "正在切换" : (active ? "已连接" : "未连接");
  $("top-live-text").textContent = active ? (proxyHealthy ? "出口在线" : "出口待复检") : "出口已断开";
  document.querySelector(".live-dot").style.background = active && proxyHealthy ? "var(--neon)" : "var(--coral)";
  $("summary-routing").textContent = routingModeLabels[store.state.routing_mode] || "智能自动";
  if (!active) {
    $("active-latency").textContent = switching ? "连接中" : "--";
    $("active-caption").textContent = switching ? "正在建立候选出口" : "未选择出口";
    ["fact-ip", "fact-purity", "fact-type", "fact-city", "fact-source", "fact-protocol"].forEach((id) => { $(id).textContent = "-"; });
    $("summary-interface").textContent = "--"; $("summary-protocol").textContent = "--"; $("summary-country").textContent = "--";
    return;
  }
  const publicIp = store.state.proxy_ip && store.state.proxy_ip !== "-" ? store.state.proxy_ip : active.ip;
  const latency = Number(store.state.proxy_latency_ms || active.latency || 0);
  $("active-latency").textContent = switching ? "切换中" : (latency ? `${latency} ms` : "--");
  $("active-caption").textContent = switching ? "旧出口继续服务" : (proxyHealthy ? "出口稳定" : "等待健康复检");
  $("fact-ip").textContent = publicIp; $("fact-purity").textContent = active.purity;
  $("fact-type").textContent = typeLabels[active.type] || active.type || "待判断";
  $("fact-city").textContent = active.city; $("fact-source").textContent = active.source;
  $("fact-protocol").textContent = `OpenVPN ${active.protocol}`;
  $("summary-interface").textContent = store.state.active_openvpn_interface || "tun0";
  $("summary-protocol").textContent = active.protocol; $("summary-country").textContent = active.country;
}

function filteredNodes() {
  const term = $("search-filter").value.trim().toLowerCase();
  const status = $("status-filter").value; const type = $("type-filter").value;
  const maxLatency = Number($("latency-filter").value || 0);
  return store.nodes.filter((node) => {
    const haystack = `${node.ip} ${node.city} ${node.country} ${node.source} ${node.as_name || ""}`.toLowerCase();
    return (!term || haystack.includes(term)) && (status === "all" || node.status === status)
      && (type === "all" || node.type === type) && (!maxLatency || (node.latency > 0 && node.latency <= maxLatency));
  });
}

function statusMarkup(node) {
  const status = node.status in statusLabels ? node.status : "pending";
  return `<span class="status-badge status-${status}">${statusLabels[status]}</span>`;
}
function favoriteMarkup(node) {
  const label = node.favorite ? "取消收藏" : "加入收藏";
  return `<button class="button button--compact favorite-button${node.favorite ? " is-favorite" : ""}" data-action="favorite" data-id="${esc(node.id)}" title="${label}" aria-label="${label}">${node.favorite ? "★" : "☆"}</button>`;
}
function actionMarkup(node, mobile = false) {
  const busy = store.state.is_connecting || store.switchingNodeId;
  let action = "";
  if (node.status === "active") action = `<button class="button button--compact button--danger" data-action="disconnect" data-id="${esc(node.id)}" ${busy ? "disabled" : ""}>断开</button>`;
  else if (["pending", "unavailable"].includes(node.status)) {
    const measuring = store.measuring.has(node.id);
    action = `<button class="button button--compact" data-action="measure" data-id="${esc(node.id)}" ${measuring ? "disabled" : ""}>${measuring ? "测量中" : node.status === "pending" ? "测延迟" : "重测"}</button>`;
  } else {
    const switchingHere = store.switchingNodeId === node.id;
    action = `<button class="button button--compact${mobile ? " button--neon" : ""}" data-action="switch" data-id="${esc(node.id)}" ${busy ? "disabled" : ""}>${switchingHere ? "切换中" : "切换"}</button>`;
  }
  return `${favoriteMarkup(node)}${action}`;
}

function renderList() {
  const list = filteredNodes();
  $("filtered-count").textContent = `${list.length} / ${store.nodes.length}`;
  $("node-rows").innerHTML = list.length ? list.map((node) => `
    <tr class="${node.status === "active" ? "is-active" : ""}">
      <td>${statusMarkup(node)}</td><td class="mono" title="${esc(node.ip)}">${esc(node.ip)}</td>
      <td title="${esc(node.city)}">${esc(node.city)}</td><td><span class="type-badge">${esc(typeLabels[node.type] || node.type || "待判断")}</span></td>
      <td title="${esc(node.source)}">${esc(node.source)}</td><td class="mono">${esc(node.protocol)}</td>
      <td><span class="latency ${latencyClass(node.latency)}">${node.latency ? `${node.latency} ms` : "--"}</span></td>
      <td><div class="row-actions">${actionMarkup(node)}</div></td>
    </tr>`).join("") : `<tr><td class="empty-row" colspan="8">${store.loadingNodes ? "正在载入节点…" : "当前筛选条件没有匹配节点"}</td></tr>`;
  $("mobile-node-list").innerHTML = list.length ? list.map((node) => `
    <article class="mobile-node ${node.status === "active" ? "is-active" : ""}">
      <div class="mobile-node-head">${statusMarkup(node)}<span class="latency ${latencyClass(node.latency)}">${node.latency ? `${node.latency} ms` : "--"}</span></div>
      <div class="mobile-node-ip">${esc(node.ip)}</div>
      <div class="mobile-node-meta"><span>${esc(node.city)}</span><span>${esc(typeLabels[node.type] || "待判断")}</span><span>${esc(node.source)}</span><span>${esc(node.protocol)}</span></div>
      <div class="mobile-node-actions">${actionMarkup(node, true)}</div>
    </article>`).join("") : `<div class="empty-row">${store.loadingNodes ? "正在载入节点…" : "当前筛选条件没有匹配节点"}</div>`;
  refreshIcons();
}
function render() { renderStage(); renderList(); }
async function fetchNodePage(page) { return api(`v2/nodes?page=${page}&page_size=100`, {}, 20000); }
async function loadNodes({ silent = false } = {}) {
  if (store.loadingNodes) return;
  store.loadingNodes = true;
  if (!silent) renderList();
  try {
    const first = await fetchNodePage(1);
    applyState(first.state);
    store.nodes = (first.items || []).map(normalizeNode);
    store.lastNodesLoadedAt = Date.now(); store.loadingNodes = false;
    render();
    if (!$("settings-backdrop").classList.contains("is-open")) hydrateSettingsForms();
    const pages = Math.ceil(Number(first.pagination?.total || store.nodes.length) / 100);
    for (let start = 2; start <= pages; start += 4) {
      const pageNumbers = Array.from({ length: Math.min(4, pages - start + 1) }, (_, index) => start + index);
      const chunks = await Promise.all(pageNumbers.map(fetchNodePage));
      for (const chunk of chunks) store.nodes.push(...(chunk.items || []).map(normalizeNode));
      store.lastNodesLoadedAt = Date.now(); render();
    }
  } catch (error) {
    store.loadingNodes = false; renderList();
    if (!silent) toast(error.message, "节点载入失败", "error");
  }
}

async function loadOptions() {
  try { store.options = await api("node_source_options", {}, 12000); }
  catch (error) { toast(`节点来源选项暂时不可用：${error.message}`, "来源服务提示", "error"); }
  populateSourceOptions();
}

async function measureNodes(ids, title = "延迟测量") {
  const targets = [...new Set(ids)].filter(Boolean).slice(0, 100);
  if (!targets.length) return toast("当前没有可测量的节点");
  targets.forEach((id) => store.measuring.add(id)); render();
  try {
    const payload = await api("v2/latency", { method: "POST", body: { ids: targets } }, 30000);
    const byId = new Map((payload.results || []).map((item) => [item.id, item]));
    store.nodes = store.nodes.map((node) => {
      const result = byId.get(node.id);
      return result ? normalizeNode({ ...node, latency_ms: result.latency_ms }) : node;
    });
    const successful = (payload.results || []).filter((item) => Number(item.latency_ms) > 0).length;
    toast(`完成 ${targets.length} 个节点测量，${successful} 个返回有效延迟`, title);
  } catch (error) { toast(error.message, "延迟测量失败", "error"); }
  finally { targets.forEach((id) => store.measuring.delete(id)); render(); }
}

async function refreshNodes() {
  const button = $("refresh-nodes"); setButtonBusy(button, true, "更新中");
  try {
    const result = await api("refresh_nodes", { method: "POST" });
    toast(result.message || "节点更新已在后台启动", "更新任务已提交");
    await pollState(true);
  } catch (error) { toast(error.message, "节点更新失败", "error"); }
  finally { setButtonBusy(button, false); }
}

async function waitForConnection(jobId, nodeId, timeoutMs = 150000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    await new Promise((resolve) => window.setTimeout(resolve, 650));
    const payload = await api("state", {}, 8000); applyState(payload.state); renderStage();
    if (store.state.connect_job_id === jobId && store.state.connect_job_status === "failed") throw new Error(store.state.connect_job_error || "候选节点连接失败");
    if (store.state.active_openvpn_node_id === nodeId && !store.state.is_connecting) return;
    if (store.state.connect_job_id === jobId && store.state.connect_job_status === "completed" && !store.state.is_connecting) return;
  }
  throw new Error("切换等待超时；后台任务可能仍在继续，请稍后查看状态");
}

async function switchNode(node, { quiet = false } = {}) {
  if (!node || !node.id) throw new Error("节点信息无效");
  if (store.state.is_connecting || store.switchingNodeId) throw new Error("已有节点切换正在进行");
  if (node.id === store.state.active_openvpn_node_id) return true;
  store.switchingNodeId = node.id; render();
  if (!quiet) toast(`正在验证 ${node.ip}，当前出口会保持连接`, "候选隧道已启动");
  try {
    const result = await api("connect_async", { method: "POST", body: { id: node.id } });
    await waitForConnection(result.job_id, node.id);
    await loadNodes({ silent: true });
    if (store.state.active_openvpn_node_id !== node.id) throw new Error(store.state.connect_job_error || "节点未成为当前出口");
    if (!quiet) toast(`新出口已切换到 ${node.city}，旧连接正在排空`, "切换完成");
    return true;
  } catch (error) { toast(error.message, "切换失败，原出口未变", "error"); throw error; }
  finally { store.switchingNodeId = ""; render(); }
}

async function disconnect() {
  if (!activeNode() || store.state.is_connecting) return;
  try {
    await api("disconnect", { method: "POST" }, 20000);
    applyState({ active_openvpn_node_id: "", active_openvpn_interface: "", connection_enabled: false, proxy_ok: false });
    await loadNodes({ silent: true }); toast("当前出口已断开", "连接已关闭");
  } catch (error) { toast(error.message, "断开失败", "error"); }
}

async function toggleFavorite(node) {
  if (!node) return;
  try {
    const wasFavorite = node.favorite;
    const result = await api("toggle_favorite", { method: "POST", body: { id: node.id } });
    applyState({ favorite_node_ids: result.favorite_node_ids || [] }); syncNormalizedNodes(); renderList();
    toast(wasFavorite ? `${node.ip} 已取消收藏` : `${node.ip} 已加入收藏`, "收藏列表已更新");
  } catch (error) { toast(error.message, "收藏操作失败", "error"); }
}

async function handleAction(event) {
  const button = event.target.closest("[data-action]"); if (!button) return;
  const node = store.nodes.find((item) => item.id === button.dataset.id);
  try {
    if (button.dataset.action === "switch") await switchNode(node);
    if (button.dataset.action === "measure") await measureNodes([node?.id], "节点延迟已更新");
    if (button.dataset.action === "disconnect") await disconnect();
    if (button.dataset.action === "favorite") await toggleFavorite(node);
  } catch (_) { /* operation already reported */ }
}

function activateSettingsTab(name) {
  document.querySelectorAll("[data-settings-tab]").forEach((button) => {
    const active = button.dataset.settingsTab === name;
    button.classList.toggle("is-active", active); button.setAttribute("aria-selected", String(active));
    $("panel-" + button.dataset.settingsTab).hidden = !active;
  });
}
function selectedRadio(name) {
  const input = document.querySelector(`input[name="${name}"]:checked`); return input ? input.value : "";
}
function setRadio(name, value) {
  const input = document.querySelector(`input[name="${name}"][value="${CSS.escape(String(value || ""))}"]`);
  if (input) input.checked = true;
}
function updateRoutingFields() {
  const mode = selectedRadio("routing-mode");
  $("fixed-country-field").hidden = mode !== "fixed_region"; $("fixed-ip-field").hidden = mode !== "fixed_ip";
}
function updateFixedIpSummary() {
  const option = $("routing-fixed-ip").selectedOptions[0];
  $("fixed-ip-summary").textContent = option?.dataset.ip || option?.textContent?.split(" · ")[0] || "未选择";
}
function updateNetworkPreview() { $("proxy-port-preview").textContent = $("proxy-port").value || "-"; }
function updateAdminPreview() {
  const port = $("admin-port").value || "8787"; const suffix = $("admin-secret").value.trim() || "安全路径";
  const defaultPort = window.location.protocol === "https:" ? "443" : "80";
  const portPart = String(port) === defaultPort ? "" : `:${port}`;
  $("admin-url-preview").textContent = `${window.location.protocol}//${window.location.hostname}${portPart}/${suffix}/`;
}
function showSettingsError(id, message) {
  const target = $(id); target.textContent = message; target.classList.toggle("is-visible", Boolean(message));
}
function generateSecret() {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  $("admin-secret").value = Array.from(bytes, (value) => alphabet[value % alphabet.length]).join(""); updateAdminPreview();
}

function populateCountryOptions() {
  const counts = new Map();
  for (const node of store.nodes) if (node.country && node.country !== "未知地区") counts.set(node.country, (counts.get(node.country) || 0) + 1);
  const current = store.state.force_country || $("routing-country").value;
  const countries = [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0], "zh-CN"));
  $("routing-country").innerHTML = `<option value="">请选择国家</option>${countries.map(([country, count]) => `<option value="${esc(country)}">${esc(country)} · ${count} 个候选</option>`).join("")}`;
  $("routing-country").value = current;
}
function populateFixedIpOptions() {
  const currentId = store.state.fixed_node_id || store.state.active_openvpn_node_id || $("routing-fixed-ip").value;
  const candidates = store.nodes.filter((node) => node.status !== "unavailable" && node.downloadable !== false)
    .sort((a, b) => Number(b.id === store.state.active_openvpn_node_id) - Number(a.id === store.state.active_openvpn_node_id) || (a.latency || 999999) - (b.latency || 999999));
  $("routing-fixed-ip").innerHTML = candidates.length
    ? candidates.map((node) => `<option value="${esc(node.id)}" data-ip="${esc(node.ip)}">${esc(node.ip)} · ${esc(node.city)} · ${node.id === store.state.active_openvpn_node_id ? "当前连接" : node.latency ? `${node.latency} ms` : "待检测"}</option>`).join("")
    : `<option value="">暂无可锁定节点</option>`;
  if (candidates.some((node) => node.id === currentId)) $("routing-fixed-ip").value = currentId;
  updateFixedIpSummary();
}
function populateSourceOptions() {
  const catalogs = store.options.catalogs || ["vpngate", "publicvpnlist", "all"];
  $("source-catalog").innerHTML = catalogs.map((value) => `<option value="${esc(value)}">${value === "all" ? "全部目录" : value === "vpngate" ? "VPNGate" : value === "publicvpnlist" ? "PublicVPNList" : esc(value)}</option>`).join("");
  const sources = [...new Set(store.options.publicvpnlist_sources || [])].sort();
  $("source-name").innerHTML = `<option value="">全部提供方</option>${sources.map((source) => `<option value="${esc(source)}">${esc(source)}</option>`).join("")}`;
}
function hydrateSettingsForms() {
  const state = store.state; const filters = state.node_filters || {};
  setRadio("routing-mode", state.routing_mode || "auto"); setRadio("routing-ip-type", state.routing_ip_type || "all");
  populateCountryOptions(); populateFixedIpOptions(); updateRoutingFields(); populateSourceOptions();
  $("source-catalog").value = filters.node_source || "vpngate"; $("source-name").value = filters.filter_source || "";
  $("source-country").value = filters.filter_country || ""; $("source-protocol").value = filters.filter_protocol || "";
  $("source-speed").value = Number(filters.min_speed_mbps || 0); $("source-latency").value = Number(filters.max_latency_ms || 0);
  $("source-purity").value = filters.ip_purity || "any"; $("only-verified").checked = Boolean(filters.only_verified);
  $("only-downloadable").checked = filters.only_downloadable !== false;
  $("proxy-port").value = Number(state.proxy_port || 7928); $("admin-username").value = state.username || "";
  $("admin-port").value = Number(state.port || 8787); $("admin-secret").value = state.secret_path || "";
  updateNetworkPreview(); updateAdminPreview();
}
function openSettings() {
  hydrateSettingsForms(); $("settings-backdrop").classList.add("is-open"); document.body.style.overflow = "hidden";
  $("close-settings").focus({ preventScroll: true });
}
function closeSettings() {
  $("settings-backdrop").classList.remove("is-open"); document.body.style.overflow = "";
  $("open-settings").focus({ preventScroll: true });
}

async function saveRouting(event) {
  event.preventDefault();
  const form = event.currentTarget; const button = form.querySelector('[type="submit"]');
  const mode = selectedRadio("routing-mode"); const country = $("routing-country").value;
  const fixedNodeId = $("routing-fixed-ip").value; const ipType = selectedRadio("routing-ip-type") || "all";
  if (mode === "fixed_region" && !country) return showSettingsError("routing-error", "固定国家模式必须选择目标国家；目标国家全部失效时不会跨国回退。");
  if (mode === "fixed_ip" && !fixedNodeId) return showSettingsError("routing-error", "固定 IP 模式必须选择一个可连接节点。");
  showSettingsError("routing-error", ""); setButtonBusy(button, true, mode === "fixed_ip" ? "连接并锁定" : "保存中");
  try {
    if (mode === "fixed_ip" && store.state.active_openvpn_node_id !== fixedNodeId) {
      const target = store.nodes.find((node) => node.id === fixedNodeId); closeSettings(); await switchNode(target, { quiet: true });
    }
    const result = await api("update_routing", { method: "POST", body: { routing_mode: mode, force_country: country, routing_ip_type: ipType } });
    applyState({ routing_mode: mode, force_country: country, routing_ip_type: ipType, fixed_node_id: mode === "fixed_ip" ? fixedNodeId : store.state.fixed_node_id });
    closeSettings(); render(); toast(result.message || `${routingModeLabels[mode]}已生效`, "路由策略已保存");
  } catch (error) {
    showSettingsError("routing-error", error.message); if (!$("settings-backdrop").classList.contains("is-open")) openSettings();
  } finally { setButtonBusy(button, false); }
}

async function saveSourceFilters(event) {
  event.preventDefault(); const button = event.currentTarget.querySelector('[type="submit"]'); setButtonBusy(button, true, "应用中");
  try {
    const result = await api("update_node_filters", { method: "POST", body: {
      node_source: $("source-catalog").value, filter_source: $("source-name").value,
      filter_country: $("source-country").value.trim(), filter_protocol: $("source-protocol").value,
      min_speed_mbps: Number($("source-speed").value || 0), max_latency_ms: Number($("source-latency").value || 0),
      ip_purity: $("source-purity").value, only_verified: $("only-verified").checked,
      only_downloadable: $("only-downloadable").checked
    } }, 20000);
    if (result.filters) applyState({ node_filters: result.filters }); closeSettings(); toast(result.message || "来源筛选已保存", "筛选已应用");
  } catch (error) { toast(error.message, "筛选保存失败", "error"); }
  finally { setButtonBusy(button, false); }
}

async function saveNetwork(event) {
  event.preventDefault(); const button = event.currentTarget.querySelector('[type="submit"]');
  const port = Number($("proxy-port").value);
  if (!Number.isInteger(port) || port < 1024 || port > 65535) return showSettingsError("network-error", "代理端口必须在 1024 至 65535 之间。");
  if (port === Number($("admin-port").value)) return showSettingsError("network-error", "代理端口不能与管理网页端口相同。");
  showSettingsError("network-error", ""); setButtonBusy(button, true, "保存中");
  try {
    const result = await api("update_settings", { method: "POST", body: {
      proxy_port: port, routing_mode: store.state.routing_mode || "auto",
      force_country: store.state.force_country || "", routing_ip_type: store.state.routing_ip_type || "all"
    } });
    applyState({ proxy_port: port }); closeSettings();
    toast(result.message || "代理设置已保存", result.restart_needed ? "服务准备重启" : "代理设置已保存");
    if (result.restart_needed) window.setTimeout(() => window.location.reload(), 3200);
  } catch (error) { showSettingsError("network-error", error.message); }
  finally { setButtonBusy(button, false); }
}

async function saveSecurity(event) {
  event.preventDefault(); const button = event.currentTarget.querySelector('[type="submit"]');
  const username = $("admin-username").value.trim(); const password = $("admin-password").value;
  const confirmation = $("admin-password-confirm").value; const port = Number($("admin-port").value);
  const suffix = $("admin-secret").value.trim();
  if (!username) return showSettingsError("security-error", "管理用户名不能为空。");
  if (password && password.length < 8) return showSettingsError("security-error", "新密码至少需要 8 个字符；留空表示保持当前密码。");
  if (password !== confirmation) return showSettingsError("security-error", "两次输入的新密码不一致。");
  if (!Number.isInteger(port) || port < 1 || port > 65535 || port === Number(store.state.proxy_port)) return showSettingsError("security-error", "管理端口必须有效，且不能与代理端口相同。");
  if (!/^[A-Za-z0-9]+$/.test(suffix)) return showSettingsError("security-error", "登录安全路径只能包含英文字母和数字。");
  showSettingsError("security-error", ""); setButtonBusy(button, true, "保存中");
  try {
    const result = await api("update_credentials", { method: "POST", body: { username, password, port, secret_path: suffix } });
    $("admin-password").value = ""; $("admin-password-confirm").value = ""; closeSettings();
    toast(result.message || "账号安全设置已更新", result.restart_needed ? "管理服务准备重启" : "账号安全已更新");
    if (result.restart_needed) {
      const defaultPort = window.location.protocol === "https:" ? 443 : 80;
      const portPart = port === defaultPort ? "" : `:${port}`;
      const nextUrl = `${window.location.protocol}//${window.location.hostname}${portPart}/${suffix}/`;
      window.setTimeout(() => { window.location.href = nextUrl; }, 3200);
    } else if (result.reauth_required) window.setTimeout(() => window.location.reload(), 900);
    else applyState({ username, port, secret_path: suffix });
  } catch (error) { showSettingsError("security-error", error.message); }
  finally { setButtonBusy(button, false); }
}

async function logout() {
  try { await api("logout", { method: "POST" }); } catch (_) { /* session may already be gone */ }
  window.location.reload();
}
function schedulePoll(delay) {
  window.clearTimeout(store.pollTimer); store.pollTimer = window.setTimeout(() => pollState(), delay);
}
async function pollState(force = false) {
  if (store.pollRunning) return; store.pollRunning = true;
  try {
    const previousActive = store.state.active_openvpn_node_id || "";
    const previousConnecting = Boolean(store.state.is_connecting);
    const previousFavorites = JSON.stringify(store.state.favorite_node_ids || []);
    const previousMaintenance = Boolean(store.state.maintenance_running);
    const payload = await api("state", {}, 8000); applyState(payload.state); syncNormalizedNodes(); renderStage();
    const activeChanged = previousActive !== (store.state.active_openvpn_node_id || "");
    const connectionPhaseChanged = previousConnecting !== Boolean(store.state.is_connecting);
    const favoritesChanged = previousFavorites !== JSON.stringify(store.state.favorite_node_ids || []);
    const maintenanceFinished = previousMaintenance && !store.state.maintenance_running;
    const drawerOpen = $("settings-backdrop").classList.contains("is-open");
    const staleNodes = !drawerOpen && Date.now() - store.lastNodesLoadedAt > 20000;
    if (activeChanged || connectionPhaseChanged || favoritesChanged) renderList();
    if ((force || activeChanged || maintenanceFinished || staleNodes) && !store.loadingNodes) await loadNodes({ silent: true });
  } catch (error) { if (force) toast(error.message, "状态刷新失败", "error"); }
  finally {
    store.pollRunning = false;
    schedulePoll(store.state.is_connecting || store.state.maintenance_running ? 900 : 3000);
  }
}

async function initialize() {
  refreshIcons(); store.loadingNodes = true; render();
  try {
    const statePayload = await api("state", {}, 10000); applyState(statePayload.state);
    store.loadingNodes = false;
    await Promise.all([loadOptions(), loadNodes()]); hydrateSettingsForms(); render();
  } catch (error) {
    store.loadingNodes = false; render(); toast(error.message, "控制台初始化失败", "error");
  }
  schedulePoll(1200);
}

$("search-filter").addEventListener("input", renderList);
["status-filter", "type-filter", "latency-filter"].forEach((id) => $(id).addEventListener("change", renderList));
$("node-rows").addEventListener("click", handleAction); $("mobile-node-list").addEventListener("click", handleAction);
$("scan-pending").addEventListener("click", () => measureNodes(pendingNodes().map((node) => node.id), "待检测节点延迟已更新"));
$("measure-visible").addEventListener("click", () => measureNodes(filteredNodes().map((node) => node.id), "当前列表延迟已更新"));
$("switch-fastest").addEventListener("click", async () => {
  const candidate = availableNodes().sort((a, b) => (a.latency || 999999) - (b.latency || 999999))[0];
  if (!candidate) return toast("当前没有可切换的健康节点");
  try { await switchNode(candidate); } catch (_) { /* operation already reported */ }
});
$("disconnect-active").addEventListener("click", disconnect); $("refresh-nodes").addEventListener("click", refreshNodes);
$("open-settings").addEventListener("click", openSettings); $("close-settings").addEventListener("click", closeSettings);
document.querySelectorAll("[data-close-settings]").forEach((button) => button.addEventListener("click", closeSettings));
document.querySelectorAll("[data-settings-tab]").forEach((button) => button.addEventListener("click", () => activateSettingsTab(button.dataset.settingsTab)));
document.querySelectorAll('input[name="routing-mode"]').forEach((input) => input.addEventListener("change", updateRoutingFields));
$("routing-fixed-ip").addEventListener("change", updateFixedIpSummary); $("proxy-port").addEventListener("input", updateNetworkPreview);
$("admin-port").addEventListener("input", updateAdminPreview); $("admin-secret").addEventListener("input", updateAdminPreview);
$("generate-secret").addEventListener("click", generateSecret);
$("settings-backdrop").addEventListener("click", (event) => { if (event.target === event.currentTarget) closeSettings(); });
document.addEventListener("keydown", (event) => { if (event.key === "Escape" && $("settings-backdrop").classList.contains("is-open")) closeSettings(); });
$("routing-form").addEventListener("submit", saveRouting); $("source-form").addEventListener("submit", saveSourceFilters);
$("network-form").addEventListener("submit", saveNetwork); $("security-form").addEventListener("submit", saveSecurity);
$("logout-session").addEventListener("click", logout);
window.addEventListener("beforeunload", () => window.clearTimeout(store.pollTimer));
window.addEventListener("DOMContentLoaded", initialize);
