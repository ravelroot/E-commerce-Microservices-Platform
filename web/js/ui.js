export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === "html") el.innerHTML = v;
    else if (v === true) el.setAttribute(k, "");
    else el.setAttribute(k, v);
  }
  append(el, children);
  return el;
}

function append(el, children) {
  for (const c of children.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
}

export function clear(el, ...children) {
  el.replaceChildren();
  append(el, children);
  return el;
}

const PATHS = {
  overview: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  store: '<path d="M3 9l1.5-5h15L21 9M3 9h18M3 9v11h18V9M9 20v-6h6v6"/>',
  orders: '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2zM9 8h6M9 12h6"/>',
  products: '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9zM12 12l8-4.5M12 12v9M12 12L4 7.5"/>',
  live: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
  invoice: '<path d="M7 3h7l5 5v13H7zM14 3v5h5M10 13h6M10 17h6"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5M16 4.8a3.5 3.5 0 0 1 0 6.4M18 14.8c1.8.8 3 2.5 3.5 5.2"/>',
  api: '<path d="M8 6l-6 6 6 6M16 6l6 6-6 6M14 4l-4 16"/>',
  cart: '<path d="M3 4h2l2.4 11h10.2L20 7H6.2M9 20a1 1 0 1 0 0-.01M17 20a1 1 0 1 0 0-.01"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  minus: '<path d="M5 12h14"/>',
  close: '<path d="M6 6l12 12M18 6L6 18"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7"/>',
  x: '<path d="M7 7l10 10M17 7L7 17"/>',
  back: '<path d="M15 6l-6 6 6 6"/>',
  chevron: '<path d="M8 10l4 4 4-4"/>',
  eye: '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  eyeOff: '<path d="M3 3l18 18M10.6 5.1A10 10 0 0 1 12 5c6.4 0 10 7 10 7a17 17 0 0 1-3 3.9M6.6 6.6C3.9 8.3 2 12 2 12s3.6 7 10 7a9.9 9.9 0 0 0 5.4-1.6M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
  logout: '<path d="M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10"/>',
  key: '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M17 6l3 3M15 8l2 2"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  box: '<path d="M4 8l8-4 8 4v8l-8 4-8-4zM4 8l8 4 8-4M12 12v8"/>',
  external: '<path d="M14 4h6v6M20 4l-9 9M18 14v6H4V6h6"/>',
};

export function icon(name, size = 18) {
  const span = document.createElement("span");
  span.style.display = "inline-flex";
  span.innerHTML = `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${PATHS[name] || ""}</svg>`;
  return span.firstChild;
}

export const MARK_PATHS =
  '<path d="M73 0A54 40 0 0 0 73 80Z"/><rect x="81" width="20" height="80" rx="3"/><path d="M0 94H120L110 110H10Z"/>';

export function logo(size = 22) {
  const wrap = h("span", { class: "logo", "aria-label": "Argo" });
  wrap.innerHTML = `<svg height="${size}" viewBox="0 0 120 110" fill="currentColor" aria-hidden="true">${MARK_PATHS}</svg>`;
  wrap.append(h("span", { class: "wordmark", style: { fontSize: `${Math.round(size * 0.95)}px` } }, "Argo"));
  return wrap;
}

const BRL = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const INT = new Intl.NumberFormat("pt-BR");
export const money = (cents) => BRL.format((cents || 0) / 100);
export const int = (n) => INT.format(n || 0);
export const dateTime = (iso) =>
  iso ? new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—";
export const shortDate = (iso) => new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "short" }).replace(".", "");
export const time = (iso) => new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
export const initials = (name) =>
  (name || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join("");

export const STATUS = {
  PENDING: { label: "Processando", tone: "accent pulse", color: "#c99a3f" },
  CONFIRMED: { label: "Confirmado", tone: "ok", color: "#5fa58c" },
  SHIPPED: { label: "Enviado", tone: "info", color: "#2e7a66" },
  DELIVERED: { label: "Entregue", tone: "", color: "#1f5c4c" },
  REJECTED: { label: "Recusado", tone: "danger", color: "#c6cacc" },
  CANCELED: { label: "Cancelado", tone: "danger", color: "#959b9f" },
};

export const ROLE = { ADMIN: "Administrador", SELLER: "Vendedor", CUSTOMER: "Cliente" };

export function statusPill(status) {
  const s = STATUS[status] || { label: status, tone: "" };
  return h("span", { class: `pill ${s.tone}` }, h("span", { class: "dot" }), s.label);
}

export function countUp(el, target, format = int, duration = 900) {
  const start = performance.now();
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce) {
    el.textContent = format(target);
    return;
  }
  const step = (now) => {
    const t = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - t, 4);
    el.textContent = format(Math.round(target * eased));
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

let toastHost;
export function toast(message, kind = "ok") {
  toastHost ??= document.body.appendChild(h("div", { class: "toasts", role: "status", "aria-live": "polite" }));
  const el = h("div", { class: `toast ${kind}` }, h("span", { class: "dot" }), message);
  toastHost.append(el);
  setTimeout(() => {
    el.classList.add("leaving");
    el.addEventListener("animationend", () => el.remove(), { once: true });
  }, 3600);
}

export function modal({ title, body, actions }) {
  const close = () => {
    overlay.classList.add("leaving");
    overlay.addEventListener("animationend", () => overlay.remove(), { once: true });
    document.removeEventListener("keydown", onKey);
  };
  const onKey = (e) => e.key === "Escape" && close();
  const box = h("div", { class: "modal", role: "dialog", "aria-modal": "true", "aria-label": title }, h("h2", {}, title), body);
  const overlay = h("div", { class: "overlay", onclick: (e) => e.target === overlay && close() }, box);
  box.append(h("div", { class: "actions" }, actions(close)));
  document.body.append(overlay);
  document.addEventListener("keydown", onKey);
  setTimeout(() => box.querySelector("input, select, textarea, button.btn:not(.ghost)")?.focus(), 50);
  return close;
}

export function confirmBox(title, text, confirmLabel = "Confirmar", danger = false) {
  return new Promise((resolve) => {
    modal({
      title,
      body: h("p", { class: "muted" }, text),
      actions: (close) => [
        h("button", { class: "btn ghost", onclick: () => (close(), resolve(false)) }, "Voltar"),
        h("button", { class: `btn ${danger ? "danger" : ""}`, onclick: () => (close(), resolve(true)) }, confirmLabel),
      ],
    });
  });
}

export function empty(title, text, iconName = "box") {
  return h("div", { class: "empty" }, h("div", { class: "mark" }, icon(iconName, 20)), h("h3", {}, title), text && h("p", { class: "muted small" }, text));
}

export function skeletonRows(n = 5, height = 44) {
  return h("div", { class: "stack sm", style: { padding: "8px" } }, Array.from({ length: n }, () => h("div", { class: "skeleton", style: { height: `${height}px` } })));
}

export function segmented(options, value, onChange, block = false) {
  const wrap = h("div", { class: `segmented ${block ? "block" : ""}`, role: "group" });
  const thumb = h("span", { class: "thumb", "aria-hidden": "true" });
  wrap.append(thumb);
  const buttons = options.map(([v, label]) =>
    h("button", { type: "button", "aria-pressed": String(v === value), onclick: () => select(v) }, label),
  );
  wrap.append(...buttons);
  function place() {
    const active = buttons.find((b) => b.getAttribute("aria-pressed") === "true");
    if (!active) return;
    thumb.style.left = `${active.offsetLeft}px`;
    thumb.style.width = `${active.offsetWidth}px`;
  }
  function select(v) {
    buttons.forEach((b, i) => b.setAttribute("aria-pressed", String(options[i][0] === v)));
    place();
    onChange(v);
  }
  requestAnimationFrame(() => requestAnimationFrame(place));
  new ResizeObserver(place).observe(wrap);
  return wrap;
}

export function pagination(page, size, total, go) {
  const pages = Math.max(1, Math.ceil(total / size));
  return h(
    "div",
    { class: "pagination" },
    h("span", { class: "muted small" }, `${int(total)} ${total === 1 ? "registro" : "registros"} · página ${page} de ${pages}`),
    h(
      "div",
      { class: "row" },
      h("button", { class: "btn ghost sm", disabled: page <= 1, onclick: () => go(page - 1) }, "Anterior"),
      h("button", { class: "btn ghost sm", disabled: page >= pages, onclick: () => go(page + 1) }, "Próxima"),
    ),
  );
}

export function fieldErrors(form, error) {
  form.querySelectorAll(".field-error").forEach((e) => e.remove());
  form.querySelectorAll("[aria-invalid]").forEach((e) => e.removeAttribute("aria-invalid"));
  for (const [name, msg] of Object.entries(error?.fields || {})) {
    const input = form.querySelector(`[name="${name.split(".").pop()}"]`);
    if (!input) continue;
    input.setAttribute("aria-invalid", "true");
    input.closest(".field")?.append(h("span", { class: "field-error" }, translate(msg)));
  }
}

function translate(msg) {
  if (/at least|ao menos|precisa/i.test(msg) && /8/.test(msg)) return "A senha precisa ter ao menos 8 caracteres, com letras e números.";
  if (/valid email|e-mail/i.test(msg)) return "Informe um e-mail válido.";
  if (/greater than/i.test(msg)) return "Informe um valor maior que zero.";
  if (/at least \d+ character/i.test(msg)) return "Campo muito curto.";
  if (/required/i.test(msg)) return "Campo obrigatório.";
  return msg.replace(/^Value error, /, "");
}
