(() => {
  "use strict";

  // ⚠️ ОСЫ ЖЕРГЕ ӨЗІҢІЗДІҢ RENDER СІЛТЕМЕҢІЗДІ ҚОЙЫҢЫЗ (соңында / болмауы керек)
  const API_BASE_URL = "https://YOUR-RENDER-APP.onrender.com";

  const DEVICE_KEY = "cloviss.device_id";
  const LICENSE_KEY = "cloviss.license_key";

  const $ = (id) => document.getElementById(id);
  const term = $("terminal");
  const progress = $("progress");

  // ---------- device id ----------
  function getDeviceId() {
    let id = localStorage.getItem(DEVICE_KEY);
    if (!id) {
      id = (crypto.randomUUID && crypto.randomUUID()) ||
           ("dev-" + Date.now() + "-" + Math.random().toString(36).slice(2, 10));
      localStorage.setItem(DEVICE_KEY, id);
    }
    return id;
  }

  // ---------- terminal ----------
  function clearTerm() { term.innerHTML = ""; }
  function line(text, cls) {
    const d = document.createElement("div");
    d.className = "term-line" + (cls ? " " + cls : "");
    d.textContent = text;
    term.appendChild(d);
    term.scrollTop = term.scrollHeight;
  }
  function json(data) {
    const text = typeof data === "string" ? data : JSON.stringify(data, null, 2);
    line(text);
  }
  function busy(on) {
    progress.classList.toggle("on", on);
  }

  // ---------- license UI ----------
  function setLicPill(status) {
    const p = $("licStatusPill");
    p.classList.remove("ok", "err", "warn");
    const dot = '<span class="dot"></span>';
    if (status === "ACTIVE") { p.classList.add("ok");   p.innerHTML = dot + " LICENSE ACTIVE"; }
    else if (status === "EXPIRED") { p.classList.add("err"); p.innerHTML = dot + " EXPIRED"; }
    else if (status === "DEVICE_MISMATCH") { p.classList.add("err"); p.innerHTML = dot + " DEVICE MISMATCH"; }
    else if (status === "INVALID") { p.classList.add("err"); p.innerHTML = dot + " INVALID"; }
    else { p.innerHTML = dot + " NO LICENSE"; }
  }

  function setLicState(v) {
    const el = $("licState");
    el.textContent = v || "—";
    el.classList.remove("ok","err","warn");
    if (v === "ACTIVE") el.classList.add("ok");
    else if (v === "EXPIRED" || v === "INVALID" || v === "DEVICE_MISMATCH") el.classList.add("err");
  }

  function fmtDuration(sec) {
    if (sec == null || sec < 0) return "—";
    const d = Math.floor(sec / 86400);
    const h = Math.floor((sec % 86400) / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = Math.floor(sec % 60);
    if (d > 0) return `${d}d ${h}h ${m}m`;
    if (h > 0) return `${h}h ${m}m ${s}s`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
  }

  let countdownTimer = null;
  function startCountdown(remainingSeconds) {
    if (countdownTimer) clearInterval(countdownTimer);
    let rem = remainingSeconds;
    const tick = () => {
      $("licRemaining").textContent = fmtDuration(rem);
      if (rem <= 0) {
        clearInterval(countdownTimer);
        setLicState("EXPIRED");
        setLicPill("EXPIRED");
        return;
      }
      rem -= 1;
    };
    tick();
    countdownTimer = setInterval(tick, 1000);
  }

  function applyLicenseResponse(info) {
    const status = info.status || (info.ok ? "ACTIVE" : "INVALID");
    setLicPill(status);
    setLicState(status);
    if (info.expires_at) $("licExpires").textContent = info.expires_at.replace("T"," ").replace("+00:00"," UTC");
    else $("licExpires").textContent = "—";
    $("devState").textContent = info.device_status || "UNBOUND";
    if (status === "ACTIVE" && typeof info.remaining_seconds === "number") {
      startCountdown(info.remaining_seconds);
    } else {
      if (countdownTimer) clearInterval(countdownTimer);
      $("licRemaining").textContent = "—";
    }
  }

  async function checkLicense(silent = false) {
    const key = (localStorage.getItem(LICENSE_KEY) || "").trim();
    if (!key) {
      setLicPill(null);
      setLicState(null);
      return false;
    }
    const device_id = getDeviceId();
    if (!silent) line("[license] checking…", "info");
    try {
      const r = await fetch(API_BASE_URL + "/api/license/check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key, device_id }),
      });
      const data = await r.json();
      applyLicenseResponse(data);
      if (!silent) {
        if (data.ok) line(`[license] ACTIVE — expires ${data.expires_at}`, "ok");
        else line(`[license] ${data.status || "ERROR"}: ${data.error || ""}`, "err");
      }
      return !!data.ok;
    } catch (e) {
      setLicPill(null);
      if (!silent) line("[license] network error", "err");
      return false;
    }
  }

  // ---------- search ----------
  async function doSearch() {
    const key = (localStorage.getItem(LICENSE_KEY) || "").trim();
    if (!key) { line("[error] no license key. Activate first.", "err"); return; }

    const type = $("searchType").value;
    const query = $("query").value.trim();
    const page = parseInt($("page").value || "1", 10);

    if (!query) { line("[error] query is empty.", "err"); return; }

    line(`[search] type=${type} page=${page} query=${query}`, "info");
    line("SEARCHING...", "warn");
    busy(true);
    $("btnSearch").disabled = true;

    try {
      const r = await fetch(API_BASE_URL + "/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          key,
          device_id: getDeviceId(),
          type,
          query,
          page,
        }),
      });
      const data = await r.json();

      if (!r.ok || !data.ok) {
        line(`[error] ${data.error || ("HTTP " + r.status)}`, "err");
        if (data.detail) json(data.detail);
        if (data.status) applyLicenseResponse(data);
        busy(false);
        $("btnSearch").disabled = false;
        return;
      }
      line("RESULT RECEIVED", "ok");
      json(data.data);
    } catch (e) {
      line("[error] network / server error", "err");
    } finally {
      busy(false);
      $("btnSearch").disabled = false;
    }
  }

  async function fetchMe() {
    const key = (localStorage.getItem(LICENSE_KEY) || "").trim();
    if (!key) { line("[error] no license key.", "err"); return; }
    line("[account] requesting /me…", "info");
    busy(true);
    try {
      const r = await fetch(API_BASE_URL + "/api/account/me", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key, device_id: getDeviceId() }),
      });
      const data = await r.json();
      if (!r.ok || !data.ok) { line(`[error] ${data.error || r.status}`, "err"); if (data.detail) json(data.detail); return; }
      json(data.data);
    } catch (e) {
      line("[error] network / server error", "err");
    } finally {
      busy(false);
    }
  }

  // ---------- events ----------
  $("btnActivate").addEventListener("click", async () => {
    const key = $("licKey").value.trim();
    if (!key) { line("[error] enter a license key.", "err"); return; }
    localStorage.setItem(LICENSE_KEY, key);
    line("[license] activating…", "info");
    await checkLicense(false);
  });

  $("btnClearLic").addEventListener("click", () => {
    localStorage.removeItem(LICENSE_KEY);
    $("licKey").value = "";
    if (countdownTimer) clearInterval(countdownTimer);
    setLicPill(null); setLicState(null);
    $("licExpires").textContent = "—";
    $("licRemaining").textContent = "—";
    $("devState").textContent = "UNBOUND";
    line("[license] cleared.", "muted");
  });

  $("btnSearch").addEventListener("click", doSearch);
  $("query").addEventListener("keydown", (e) => { if (e.key === "Enter") doSearch(); });

  $("btnClearSearch").addEventListener("click", () => {
    $("query").value = "";
    $("page").value = "1";
  });

  $("btnMe").addEventListener("click", fetchMe);

  $("btnCopy").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(term.innerText);
      line("[ui] output copied.", "ok");
    } catch { line("[ui] copy failed.", "err"); }
  });

  $("btnClearOut").addEventListener("click", () => {
    clearTerm();
    line("[cloviss] ready.", "muted");
  });

  // ---------- init ----------
  (async () => {
    const stored = localStorage.getItem(LICENSE_KEY);
    if (stored) $("licKey").value = stored;

    try {
      const r = await fetch(API_BASE_URL + "/api/health");
      const h = await r.json();
      $("sysStatus").classList.add("ok");
      $("sysStatus").innerHTML = '<span class="dot"></span> ONLINE';
      $("buildInfo").textContent = h.api_configured ? "API CONFIGURED" : "API KEY MISSING";
    } catch {
      $("sysStatus").classList.add("err");
      $("sysStatus").innerHTML = '<span class="dot"></span> OFFLINE';
    }

    if (stored) await checkLicense(true);
  })();
})();
