import { api, session } from "../api.js";
import { live } from "../bus.js";
import { cart, openCart } from "../cart.js";
import { clear, empty, h, icon, money, pagination, skeletonRows, toast } from "../ui.js";

export async function renderStore(view) {
  const buyer = session.is("CUSTOMER");
  const state = { q: "", category: "", sort: "name", page: 1 };
  const grid = h("div");
  const chips = h("div", { class: "chips", role: "tablist" });
  const cartBtn = buyer
    ? h("button", { class: "btn ghost cart-fab", style: { position: "relative" }, onclick: () => openCart((o) => (location.hash = `/pedidos/${o.id}`)) }, icon("cart", 18), "Carrinho")
    : null;
  let countEl = null;
  const unsub = buyer
    ? cart.subscribe(() => {
        countEl?.remove();
        const n = cart.count();
        if (n) cartBtn.append((countEl = h("span", { class: "count" }, n)));
      })
    : () => {};

  let timer;
  const search = h("input", {
    class: "input search",
    type: "search",
    placeholder: "Buscar por nome, SKU ou loja",
    "aria-label": "Buscar produtos",
    oninput: (e) => {
      clearTimeout(timer);
      timer = setTimeout(() => ((state.q = e.target.value.trim()), (state.page = 1), load()), 250);
    },
  });
  const sort = h(
    "select",
    { class: "select compact", "aria-label": "Ordenar", onchange: (e) => ((state.sort = e.target.value), load()) },
    [["name", "Nome"], ["price_asc", "Menor preço"], ["price_desc", "Maior preço"], ["newest", "Mais recentes"]].map(([v, l]) => h("option", { value: v }, l)),
  );

  view.append(
    h(
      "div",
      { class: "wrap" },
      h(
        "div",
        { class: "page-header" },
        h("div", { class: "page-header-text" }, h("h1", {}, "Loja"), h("p", { class: "muted" }, buyer ? "Estoque atualizado em tempo real. A compra é confirmada pela fila em segundos." : "Visão da vitrine. Só contas de Cliente fazem pedidos.")),
        h("div", { class: "page-header-actions" }, cartBtn),
      ),
      chips,
      h("div", { class: "toolbar" }, search, h("span", { class: "spacer" }), sort),
      grid,
    ),
  );

  const cats = await api("catalog", "/products/categories");
  const allCats = [["", "Todas"], ...cats.map((c) => [c.name, c.name])];
  chips.append(
    ...allCats.map(([v, label]) =>
      h("button", { class: "chip", "aria-pressed": String(v === state.category), onclick: (e) => {
        chips.querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-pressed", "false"));
        e.currentTarget.setAttribute("aria-pressed", "true");
        state.category = v;
        state.page = 1;
        load();
      } }, label),
    ),
  );

  async function load() {
    clear(grid, skeletonRows(3, 120));
    const params = new URLSearchParams({ page: state.page, size: 12, sort: state.sort });
    if (state.q) params.set("q", state.q);
    if (state.category) params.set("category", state.category);
    const data = await api("catalog", `/products?${params}`);
    if (!data.items.length) {
      clear(grid, empty("Nenhum produto encontrado", "Tente outra busca ou categoria.", "search"));
      return;
    }
    clear(grid, 
      h("div", { class: "products" }, data.items.map((p, i) => card(p, i))),
      pagination(data.page, data.size, data.total, (pg) => ((state.page = pg), load())),
    );
  }

  function card(p, i) {
    const stockEl = h("span", { class: "stock-tag" });
    const add = buyer ? h("button", { class: "btn sm", onclick: () => addToCart() }, icon("plus", 15), "Adicionar") : null;
    let product = p;
    function paint() {
      const s = product.stock;
      stockEl.className = `stock-tag ${s === 0 ? "out" : s <= product.low_stock_threshold ? "low" : ""}`;
      stockEl.textContent = s === 0 ? "Esgotado" : s <= product.low_stock_threshold ? `Últimas ${s} un` : `${s} em estoque`;
      if (add) add.disabled = s === 0;
    }
    function addToCart() {
      const inCart = cart.lines().find((l) => l.product.id === product.id)?.qty || 0;
      if (inCart >= product.stock) return toast("Você já adicionou todo o estoque disponível.", "error");
      cart.add(product);
      toast(`${product.name} no carrinho.`);
    }
    paint();
    const el = h(
      "article",
      { class: "product reveal", style: { "--i": i }, "data-id": p.id },
      h("div", { class: "product-art", "aria-hidden": "true" }, h("span", {}, monogram(p.name))),
      h(
        "div",
        { class: "product-body" },
        h("span", { class: "small muted" }, `${p.category} · ${p.seller_name}`),
        h("h3", {}, p.name),
        stockEl,
        h("div", { class: "product-foot" }, h("span", { class: "price" }, money(p.price_cents)), add),
      ),
    );
    el.update = (stock) => {
      product = { ...product, stock };
      paint();
      stockEl.classList.remove("flash");
      void stockEl.offsetWidth;
      stockEl.classList.add("flash");
    };
    return el;
  }

  const onStock = (e) => {
    const ev = e.detail;
    grid.querySelector(`[data-id="${ev.product_id}"]`)?.update(ev.stock);
    cart.updateStock(ev.product_id, ev.stock);
  };
  live.addEventListener("stock", onStock);
  await load();
  return () => {
    unsub();
    live.removeEventListener("stock", onStock);
  };
}

function monogram(name) {
  return name.split(/\s+/).filter((w) => w.length > 2).slice(0, 2).map((w) => w[0].toUpperCase()).join("");
}
