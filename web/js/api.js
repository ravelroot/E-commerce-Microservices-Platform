const IDLE_MINUTES = 20;
const REMEMBER_KEY = "argo:refresh";
const FALLBACK = {
  429: "Muitas tentativas. Aguarde um minuto e tente de novo.",
  502: "Serviço temporariamente indisponível. Tente de novo em instantes.",
  503: "Serviço temporariamente indisponível. Tente de novo em instantes.",
  504: "O serviço demorou para responder. Tente de novo.",
};

const state = { access: null, refresh: null, user: null, expiresAt: 0, refreshing: null, remember: false };
const listeners = new Set();
let idleTimer;

export class ApiError extends Error {
  constructor(status, body) {
    super(body?.message || "Não foi possível concluir. Tente de novo.");
    this.status = status;
    this.code = body?.code;
    this.fields = body?.fields || {};
  }
}

function storage() {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

function remembered() {
  try {
    return storage()?.getItem(REMEMBER_KEY) || null;
  } catch {
    return null;
  }
}

function persist(token) {
  try {
    if (token && state.remember) storage()?.setItem(REMEMBER_KEY, token);
    else storage()?.removeItem(REMEMBER_KEY);
  } catch {
    return;
  }
}

export const session = {
  get user() {
    return state.user;
  },
  get token() {
    return state.access;
  },
  get remembered() {
    return state.remember;
  },
  onChange(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  },
  is(...roles) {
    return !!state.user && roles.includes(state.user.role);
  },
};

function setPair(pair, reason = "login") {
  state.access = pair.access_token;
  state.refresh = pair.refresh_token;
  state.user = pair.user;
  state.expiresAt = Date.now() + (pair.expires_in - 30) * 1000;
  persist(state.refresh);
  touch();
  listeners.forEach((fn) => fn(state.user, reason));
}

export function endSession(reason) {
  const hadUser = !!state.user;
  const refresh = state.refresh;
  Object.assign(state, { access: null, refresh: null, user: null, expiresAt: 0 });
  persist(null);
  state.remember = false;
  clearTimeout(idleTimer);
  if (refresh) fetch("/api/identity/auth/logout", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: refresh }) }).catch(() => {});
  if (hadUser) listeners.forEach((fn) => fn(null, reason));
}

function touch() {
  clearTimeout(idleTimer);
  if (state.user) idleTimer = setTimeout(() => endSession("idle"), IDLE_MINUTES * 60 * 1000);
}
["pointerdown", "keydown", "scroll"].forEach((ev) => addEventListener(ev, () => state.user && touch(), { passive: true }));

async function raw(path, { method = "GET", body, token, headers: extra = {}, accept = "application/json" } = {}) {
  const headers = { Accept: accept, ...extra };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  let res;
  try {
    res = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new ApiError(0, { message: navigator.onLine === false ? "Você está sem internet. Confira a conexão." : "Sem conexão com o servidor." });
  }
  if (res.status === 204) return null;
  if (accept !== "application/json" && res.ok) return res;
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, data?.message ? data : { ...data, message: FALLBACK[res.status] });
  return data;
}

export async function login(email, password, remember = false) {
  state.remember = remember;
  setPair(await raw("/api/identity/auth/login", { method: "POST", body: { email, password } }));
}

export async function register(body, remember = false) {
  state.remember = remember;
  setPair(await raw("/api/identity/auth/register", { method: "POST", body }));
}

async function refresh(reason = "refresh") {
  if (!state.refresh) throw new ApiError(401, { message: "Sessão encerrada." });
  state.refreshing ??= raw("/api/identity/auth/refresh", { method: "POST", body: { refresh_token: state.refresh } })
    .then((pair) => setPair(pair, reason))
    .finally(() => (state.refreshing = null));
  return state.refreshing;
}

export async function refreshSession() {
  await refresh("update");
}

export async function restoreSession() {
  const token = remembered();
  if (!token || state.user) return !!state.user;
  state.remember = true;
  state.refresh = token;
  try {
    await refresh("restore");
    return true;
  } catch {
    Object.assign(state, { access: null, refresh: null, user: null, expiresAt: 0, remember: false });
    persist(null);
    return false;
  }
}

async function validToken() {
  if (!state.access) throw new ApiError(401, { message: "Entre para continuar." });
  if (Date.now() >= state.expiresAt) await refresh();
  return state.access;
}

async function authorized(url, opts) {
  try {
    return await raw(url, { ...opts, token: await validToken() });
  } catch (err) {
    if (err.status !== 401) throw err;
    try {
      await refresh();
      return await raw(url, { ...opts, token: state.access });
    } catch (again) {
      endSession("expired");
      throw again;
    }
  }
}

export async function api(service, path, opts = {}) {
  return authorized(`/api/${service}${path}`, opts);
}

export async function download(service, path, fallbackName) {
  const res = await authorized(`/api/${service}${path}`, { accept: "*/*" });
  const disposition = res.headers.get("Content-Disposition") || "";
  const name = /filename="?([^";]+)"?/.exec(disposition)?.[1] || fallbackName;
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return name;
}

export async function health(service) {
  const start = performance.now();
  try {
    const res = await fetch(`/api/${service}/health`, { headers: { Accept: "application/json" }, cache: "no-store" });
    const data = await res.json().catch(() => ({}));
    return { ...data, ok: res.ok, http: res.status, latency: Math.round(performance.now() - start) };
  } catch {
    return { ok: false, http: 0, latency: Math.round(performance.now() - start), status_text: "sem resposta" };
  }
}

export function stream(service, path, onEvent, onStatus = () => {}) {
  let stopped = false;
  let controller;
  async function connect(attempt = 0) {
    if (stopped || !state.user) return;
    controller = new AbortController();
    try {
      const res = await fetch(`/api/${service}${path}`, {
        headers: { Authorization: `Bearer ${await validToken()}`, Accept: "text/event-stream" },
        signal: controller.signal,
      });
      if (!res.ok || !res.body) throw new Error(String(res.status));
      onStatus(true);
      attempt = 0;
      const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
      let buffer = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += value;
        let idx;
        while ((idx = buffer.indexOf("\n\n")) >= 0) {
          const chunk = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          const type = /^event: (.+)$/m.exec(chunk)?.[1];
          const data = /^data: (.+)$/m.exec(chunk)?.[1];
          if (type === "stock" && data) onEvent(JSON.parse(data));
        }
      }
    } catch {
      if (stopped) return;
    }
    onStatus(false);
    if (!stopped) setTimeout(() => connect(attempt + 1), Math.min(15000, 1000 * 2 ** attempt));
  }
  connect();
  return () => {
    stopped = true;
    controller?.abort();
  };
}
