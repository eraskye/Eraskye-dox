(() => {
  "use strict";

  // ⚠️ ОСЫ ЖЕРГЕ ӨЗІҢІЗДІҢ RENDER СІЛТЕМЕҢІЗДІ ҚОЙЫҢЫЗ (соңында / болмауы керек)
  const API_BASE_URL = "https://YOUR-RENDER-APP.onrender.com";

  const $ = (id) => document.getElementById(id);

  function setState(signed) {
    const el = $("adminState");
    el.classList.remove("ok", "err");
    if (signed) { el.classList.add("ok"); el.innerHTML = '<span class="dot"></span> SIGNED IN'; }
    else { el.classList.add("err"); el.innerHTML = '<span class="dot"></span> SIGNED OUT'; }
  }

  async function api(path, opts = {}) {
    const r = await fetch(API_BASE_URL + path, {
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      ...opts,
    });
    let data = null;
    try { data = await r.json(); } catch {}
    return { status: r.status, ok: r.ok, data };
  }

  async function refreshMe() {
    const { data } = await api("/api/admin/me");
    setState(data && data.admin);
    if (data && data.admin) refreshLicenses();
  }

  async function login() {
    const username = $("au").value.trim();
    const password = $("ap").value;
    const { ok, data } = await api("/api/admin/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    if (!ok) { alert("Login failed: " + (data?.error || "unknown")); return; }
    setState(true);
    refreshLicenses();
  }

  async function logout() {
    await api("/api/admin/logout", { method: "POST" });
    setState(false);
    $("licTbody").innerHTML = "";
  }

  async function generate() {
    const duration = parseInt($("duration").value, 10);
    const { ok, data } = await api("/api/admin/license/create", {
      method: "POST",
      body: JSON.stringify({ duration }),
    });
    if (!ok || !data?.ok) { alert("Failed: " + (data?.error || "unknown")); return; }
    $("lastKey").textContent = data.license.key;
    refreshLicenses();
  }

  function fmt(iso) {
    if (!iso) return "—";
    return iso.replace("T", " ").replace("+00:00", "Z");
  }

  function fmtRemain(sec) {
    if (sec == null) return "—";
    if (sec <= 0) return "expired";
    const d = Math.floor(sec / 86400);
    const h = Math.floor((sec % 86400) / 3600);
    const m = Math.floor((sec % 3600) / 60);
    if (d > 0) return `${d}d ${h}h`;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  }

  async function refreshLicenses() {
    const { ok, data } = await api("/api/admin/licenses");
    if (!ok || !data?.ok) return;
    const tbody = $("licTbody");
    tbody.innerHTML = "";
    data.licenses.forEach((l) => {
      const tr = document.createElement("tr");

      const tdKey = document.createElement("td");
      tdKey.textContent = l.key;

      const tdStatus = document.createElement("td");
      tdStatus.textContent = l.status.toUpperCase();
      tdStatus.className = "s-" + l.status;

      const tdDur = document.createElement("td");
      tdDur.textContent = l.duration + "d";

      const tdCreated = document.createElement("td");
      tdCreated.textContent = fmt(l.created_at);

      const tdExpires = document.createElement("td");
      tdExpires.textContent = fmt(l.expires_at);

      const tdRemain = document.createElement("td");
      tdRemain.textContent = fmtRemain(l.remaining_seconds);

      const tdDev = document.createElement("td");
      tdDev.textContent = l.bound ? l.device_id_short : "unbound";

      const tdAct = document.createElement("td");
      const wrap = document.createElement("div");
      wrap.className = "act";

      const bCopy = document.createElement("button");
      bCopy.textContent = "COPY";
      bCopy.addEventListener("click", () => navigator.clipboard.writeText(l.key));

      const bRev = document.createElement("button");
      bRev.textContent = "REVOKE";
      bRev.className = "danger";
      bRev.addEventListener("click", async () => {
        if (!confirm("Revoke " + l.key + "?")) return;
        await api("/api/admin/license/revoke", {
          method: "POST",
          body: JSON.stringify({ key: l.key }),
        });
        refreshLicenses();
      });

      const bDel = document.createElement("button");
      bDel.textContent = "DELETE";
      bDel.className = "danger";
      bDel.addEventListener("click", async () => {
        if (!confirm("Delete " + l.key + " permanently?")) return;
        await api("/api/admin/license/delete", {
          method: "POST",
          body: JSON.stringify({ key: l.key }),
        });
        refreshLicenses();
      });

      wrap.appendChild(bCopy);
      wrap.appendChild(bRev);
      wrap.appendChild(bDel);
      tdAct.appendChild(wrap);

      tr.append(tdKey, tdStatus, tdDur, tdCreated, tdExpires, tdRemain, tdDev, tdAct);
      tbody.appendChild(tr);
    });
  }

  $("btnLogin").addEventListener("click", login);
  $("btnLogout").addEventListener("click", logout);
  $("btnGen").addEventListener("click", generate);
  $("btnRefresh").addEventListener("click", refreshLicenses);
  $("btnCopyKey").addEventListener("click", () => {
    const k = $("lastKey").textContent;
    if (k && k !== "—") navigator.clipboard.writeText(k);
  });

  refreshMe();
})();
