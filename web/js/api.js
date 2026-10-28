const IDLE_MINUTES = 20;
const FALLBACK = {
  429: "Muitas tentativas. Aguarde um minuto e tente de novo.",
  502: "Serviço temporariamente indisponível. Tente de novo em instantes.",
  503: "Serviço temporariamente indisponível. Tente de novo em instantes.",
  504: "O serviço demorou para responder. Tente de novo.",
};

const state = { access: null, refresh: null, user: null, expiresAt: 0, refreshing: null };
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

export const session = {
  get user() {
    return state.user;
  },
  get token() {
    return state.access;
  },
  onChange(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  },
  is(...roles) {
    return !!state.user && roles.includes(state.user.role);
  },
};

function setPair(pair) {
  state.access = pair.access_token;
  state.refresh = pair.refresh_token;
  state.user = pair.user;
  state.expiresAt = Date.now() + (pair.expires_in - 30) * 1000;
  touch();
  listeners.forEach((fn) => fn(state.user));
}

export function endSession(reason) {
  const hadUser = !!state.user;
  const refresh = state.refresh;
  Object.assign(state, { access: null, refresh: null, user: null, expiresAt: 0 });
  clearTimeout(idleTimer);
  if (refresh) fetch("/api/identity/auth/logout", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: refresh }) }).catch(() => {});
  if (hadUser) listeners.forEach((fn) => fn(null, reason));
}

function touch() {
  clearTimeout(idleTimer);
  if (state.user) idleTimer = setTimeout(() => endSession("idle"), IDLE_MINUTES * 60 * 1000);
}
["pointerdown", "keydown", "scroll"].forEach((ev) => addEventListener(ev, () => state.user && touch(), { passive: true }));

async function raw(path, { method = "GET", body, token } = {}) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  let res;
  try {
    res = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new ApiError(0, { message: "Sem conexão com o servidor." });
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, data?.message ? data : { ...data, message: FALLBACK[res.status] });
  return data;
}

export async function login(email, password) {
  setPair(await raw("/api/identity/auth/login", { method: "POST", body: { email, password } }));
}

export async function register(body) {
  setPair(await raw("/api/identity/auth/register", { method: "POST", body }));
}

async function refresh() {
  if (!state.refresh) throw new ApiError(401, { message: "Sessão encerrada." });
  state.refreshing ??= raw("/api/identity/auth/refresh", { method: "POST", body: { refresh_token: state.refresh } })
    .then(setPair)
    .finally(() => (state.refreshing = null));
  return state.refreshing;
}

async function validToken() {
  if (!state.access) throw new ApiError(401, { message: "Entre para continuar." });
  if (Date.now() >= state.expiresAt) await refresh();
  return state.access;
}

export async function api(service, path, opts = {}) {
  const url = `/api/${service}${path}`;
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
