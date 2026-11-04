import { api, session } from "./api.js";
import { clear, h, icon, money, toast, empty, trapFocus } from "./ui.js";

const items = new Map();
const subs = new Set();
let checkoutKey = null;
let owner = null;

function storageKey() {
  return owner ? `argo:cart:${owner}` : null;
}

function save() {
  const key = storageKey();
  if (!key) return;
  try {
    if (items.size) sessionStorage.setItem(key, JSON.stringify([...items.values()]));
    else sessionStorage.removeItem(key);
  } catch {
    return;
  }
}

function removeStored(key) {
  if (!key) return;
  try {
    sessionStorage.removeItem(key);
  } catch {
    return;
  }
}

const emit = () => {
  save();
  subs.forEach((fn) => fn());
};

function newKey() {
  if (crypto.randomUUID) return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

export const cart = {
  subscribe(fn) {
    subs.add(fn);
    fn();
    return () => subs.delete(fn);
  },
  load(userId) {
    owner = userId;
    items.clear();
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey()) || "[]");
      for (const line of saved) if (line?.product?.id && line.qty > 0) items.set(line.product.id, line);
    } catch {
      items.clear();
    }
    subs.forEach((fn) => fn());
  },
  add(product, qty = 1) {
    const line = items.get(product.id);
    const next = Math.min((line?.qty || 0) + qty, product.stock);
    if (next <= 0) return 0;
    items.set(product.id, { product, qty: next });
    emit();
    return next;
  },
  set(id, qty) {
    const line = items.get(id);
    if (!line) return;
    if (qty <= 0) items.delete(id);
    else line.qty = Math.min(qty, line.product.stock);
    emit();
  },
  updateStock(id, stock) {
    const line = items.get(id);
    if (!line) return;
    line.product = { ...line.product, stock };
    if (line.qty > stock) line.qty = stock;
    if (line.qty === 0) items.delete(id);
    emit();
  },
  clear() {
    items.clear();
    checkoutKey = null;
    emit();
  },
  forget() {
    const key = storageKey();
    items.clear();
    owner = null;
    checkoutKey = null;
    removeStored(key);
    subs.forEach((fn) => fn());
  },
  lines: () => [...items.values()],
  count: () => [...items.values()].reduce((n, l) => n + l.qty, 0),
  total: () => [...items.values()].reduce((n, l) => n + l.qty * l.product.price_cents, 0),
};

export async function reorder(order) {
  const results = await Promise.all(order.items.map((it) => api("catalog", `/products/${it.product_id}`).catch(() => null)));
  let added = 0;
  const missing = [];
  order.items.forEach((it, i) => {
    const product = results[i];
    if (!product || !product.active || product.stock <= 0) {
      missing.push(it.product_name);
      return;
    }
    if (cart.add(product, it.quantity) > 0) added += 1;
  });
  return { added, missing };
}

export function openCart(onOrdered) {
  const opener = document.activeElement;
  const body = h("div", { class: "drawer-body" });
  const totalEl = h("strong", { class: "num", style: { fontSize: "18px" } });
  const buy = h("button", { class: "btn lg block", onclick: checkout }, "Fechar pedido");
  const overlay = h("div", { class: "drawer-overlay", onclick: close });
  const drawer = h(
    "aside",
    { class: "drawer", role: "dialog", "aria-modal": "true", "aria-label": "Carrinho" },
    h("div", { class: "drawer-head" }, h("h2", {}, "Carrinho"), h("button", { class: "icon-btn", "aria-label": "Fechar", onclick: close }, icon("close"))),
    body,
    h(
      "div",
      { class: "drawer-foot" },
      h("div", { class: "row" }, h("span", { class: "muted" }, "Total"), h("span", { class: "spacer" }), totalEl),
      buy,
      h("p", { class: "hint", style: { textAlign: "center" } }, "A reserva do estoque, o e-mail e a nota fiscal são feitos pela fila, sem travar a compra."),
    ),
  );
  const onKey = (e) => {
    if (e.key === "Escape") close();
    else trapFocus(drawer, e);
  };
  document.addEventListener("keydown", onKey);
  document.body.append(overlay, drawer);
  setTimeout(() => drawer.querySelector("button")?.focus(), 50);

  const unsub = cart.subscribe(() => {
    const lines = cart.lines();
    totalEl.textContent = money(cart.total());
    buy.disabled = lines.length === 0;
    clear(body,
      ...(lines.length
        ? lines.map(({ product: p, qty }, i) =>
            h(
              "div",
              { class: "cart-line", style: { animationDelay: `${i * 40}ms` } },
              h("div", {}, h("div", { class: "strong" }, p.name), h("div", { class: "small muted" }, `${money(p.price_cents)} · ${p.seller_name}`)),
              h("div", { class: "num strong", style: { textAlign: "right" } }, money(p.price_cents * qty)),
              h(
                "div",
                { class: "qty" },
                h("button", { "aria-label": `Diminuir ${p.name}`, onclick: () => cart.set(p.id, qty - 1) }, "−"),
                h("span", { "aria-live": "polite" }, qty),
                h("button", { "aria-label": `Aumentar ${p.name}`, disabled: qty >= p.stock, onclick: () => cart.set(p.id, qty + 1) }, "+"),
              ),
              h("button", { class: "btn quiet sm", style: { justifySelf: "end" }, onclick: () => cart.set(p.id, 0) }, "Remover"),
            ),
          )
        : [empty("Seu carrinho está vazio", "Adicione produtos da loja para fechar um pedido.", "cart")]),
    );
  });

  function close() {
    unsub();
    document.removeEventListener("keydown", onKey);
    drawer.classList.add("leaving");
    overlay.classList.add("leaving");
    drawer.addEventListener("animationend", () => (drawer.remove(), overlay.remove()), { once: true });
    if (opener && document.contains(opener)) opener.focus();
  }

  async function checkout() {
    if (!session.user) return;
    buy.disabled = true;
    clear(buy, h("span", { class: "spinner" }), "Enviando pedido…");
    checkoutKey ??= newKey();
    try {
      const order = await api("orders", "/orders", {
        method: "POST",
        headers: { "Idempotency-Key": checkoutKey },
        body: { items: cart.lines().map((l) => ({ product_id: l.product.id, quantity: l.qty })) },
      });
      cart.clear();
      close();
      toast(`Pedido ${order.code} recebido. Processando na fila…`);
      onOrdered?.(order);
    } catch (err) {
      if (err.status && err.status < 500 && err.status !== 429) checkoutKey = null;
      toast(err.message, "error");
      buy.disabled = false;
      clear(buy, "Fechar pedido");
    }
  }
}
