const http = require("http");
const fs = require("fs");
const path = require("path");
const root = path.resolve("webui");
let state = {
  active_openvpn_node_id: "jp-01", active_openvpn_interface: "tun0", is_connecting: false,
  maintenance_running: false, proxy_ok: true, proxy_ip: "103.156.22.48", proxy_latency_ms: 42,
  routing_mode: "auto", force_country: "", routing_ip_type: "all", connection_enabled: true,
  fixed_node_id: "", favorite_node_ids: ["kr-02"], proxy_port: 7928,
  username: "admin", port: 8787, secret_path: "EJsW2EeBo9lY",
  node_filters: { node_source: "all", filter_source: "", filter_country: "", filter_protocol: "", min_speed_mbps: 0, max_latency_ms: 0, ip_purity: "any", only_verified: false, only_downloadable: true },
  last_check_message: "出口稳定"
};
let nodes = [
  { id: "jp-01", probe_status: "available", active: true, ip: "103.156.22.48", location: "日本 东京", country: "日本", ip_type: "residential", quality: "normal", source: "PublicVPNList", proto: "tcp", latency_ms: 42, speed_mbps: 92, downloadable: true, verified: true },
  { id: "kr-02", probe_status: "available", ip: "211.216.68.73", location: "韩国 首尔", country: "韩国", ip_type: "residential", quality: "normal", source: "VPNGate", proto: "udp", latency_ms: 58, speed_mbps: 84, downloadable: true, verified: true },
  { id: "jp-03", probe_status: "available", ip: "126.88.14.201", location: "日本 大阪", country: "日本", ip_type: "hosting", quality: "datacenter", source: "PublicVPNList", proto: "tcp", latency_ms: 66, speed_mbps: 110, downloadable: true, verified: true },
  { id: "sg-04", probe_status: "not_checked", ip: "45.118.132.17", location: "新加坡", country: "新加坡", ip_type: "hosting", quality: "datacenter", source: "VPNGate", proto: "tcp", latency_ms: 0, reported_latency_ms: 92, speed_mbps: 74, downloadable: true },
  { id: "de-05", probe_status: "unavailable", ip: "185.104.184.22", location: "德国 法兰克福", country: "德国", ip_type: "hosting", quality: "proxy", source: "VPNGate", proto: "tcp", latency_ms: 312, speed_mbps: 46, downloadable: true }
];
function json(res, body, status = 200) { const data = Buffer.from(JSON.stringify(body)); res.writeHead(status, { "Content-Type": "application/json", "Content-Length": data.length }); res.end(data); }
function readBody(req) { return new Promise((resolve) => { let body = ""; req.on("data", (c) => body += c); req.on("end", () => resolve(body ? JSON.parse(body) : {})); }); }
function serve(res, file, type) { const data = fs.readFileSync(path.join(root, file)); res.writeHead(200, { "Content-Type": type, "Content-Length": data.length }); res.end(data); }
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://127.0.0.1:4178");
  if (req.method === "GET" && (url.pathname === "/" || url.pathname === "/index.html")) return serve(res, "index.html", "text/html; charset=utf-8");
  if (req.method === "GET" && url.pathname === "/assets/app.css") return serve(res, "assets/app.css", "text/css; charset=utf-8");
  if (req.method === "GET" && url.pathname === "/assets/app.js") return serve(res, "assets/app.js", "application/javascript; charset=utf-8");
  if (req.method === "GET" && url.pathname === "/api/state") return json(res, { state });
  if (req.method === "GET" && url.pathname === "/api/node_source_options") return json(res, { catalogs: ["vpngate", "publicvpnlist", "all"], protocols: ["tcp", "udp"], publicvpnlist_sources: ["community", "curated"] });
  if (req.method === "GET" && url.pathname === "/api/v2/nodes") return json(res, { items: nodes, pagination: { page: 1, page_size: 100, total: nodes.length }, state });
  const body = await readBody(req);
  if (url.pathname === "/api/v2/latency") {
    const results = (body.ids || []).map((id, i) => ({ id, latency_ms: 48 + i * 7 }));
    for (const result of results) { const node = nodes.find((n) => n.id === result.id); if (node) node.latency_ms = result.latency_ms; }
    return json(res, { ok: true, results });
  }
  if (url.pathname === "/api/connect_async") {
    const job = `job-${Date.now()}`; state = { ...state, is_connecting: true, connect_job_id: job, connect_job_status: "running" };
    setTimeout(() => {
      nodes = nodes.map((n) => ({ ...n, active: n.id === body.id }));
      const node = nodes.find((n) => n.id === body.id);
      state = { ...state, is_connecting: false, active_openvpn_node_id: body.id, active_openvpn_interface: "tun1", proxy_ip: node.ip, proxy_latency_ms: node.latency_ms, connect_job_status: "completed" };
    }, 450);
    return json(res, { ok: true, accepted: true, job_id: job }, 202);
  }
  if (url.pathname === "/api/disconnect") { state = { ...state, active_openvpn_node_id: "", active_openvpn_interface: "", connection_enabled: false, proxy_ok: false }; nodes = nodes.map((n) => ({ ...n, active: false })); return json(res, { ok: true }); }
  if (url.pathname === "/api/toggle_favorite") { const ids = new Set(state.favorite_node_ids); ids.has(body.id) ? ids.delete(body.id) : ids.add(body.id); state.favorite_node_ids = [...ids]; return json(res, { ok: true, favorite_node_ids: state.favorite_node_ids }); }
  if (url.pathname === "/api/update_routing") { state = { ...state, routing_mode: body.routing_mode, force_country: body.force_country, routing_ip_type: body.routing_ip_type, fixed_node_id: body.routing_mode === "fixed_ip" ? state.active_openvpn_node_id : state.fixed_node_id }; return json(res, { ok: true, message: "出站路由配置更新成功" }); }
  if (url.pathname === "/api/update_node_filters") { state.node_filters = { ...state.node_filters, ...body }; return json(res, { ok: true, accepted: true, filters: state.node_filters, message: "筛选条件已保存" }, 202); }
  if (url.pathname === "/api/update_settings") { state.proxy_port = body.proxy_port; return json(res, { ok: true, restart_needed: false, message: "代理设置已保存" }); }
  if (url.pathname === "/api/update_credentials") return json(res, { ok: true, restart_needed: false, reauth_required: false, message: "账号设置已保存" });
  if (url.pathname === "/api/refresh_nodes") return json(res, { ok: true, message: "已启动节点更新" });
  if (url.pathname === "/api/logout") return json(res, { ok: true });
  json(res, { error: "not found" }, 404);
});
server.listen(4178, "127.0.0.1", () => console.log("mock webui http://127.0.0.1:4178"));