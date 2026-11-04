import { api, session } from "../api.js";
import { live } from "../bus.js";
import { cart, openCart } from "../cart.js";
import { clear, debounce, empty, h, icon, modal, money, pagination, readQuery, skeletonRows, toast, writeQuery } from "../ui.js";
import { parsePrice } from "./products.js";

const SORTS = [["name", "Nome"], ["price_asc", "Menor preço"], ["price_desc", "Maior preço"], ["newest", "Mais recentes"]];

export async function renderStore(view) {
  const buyer = session.is("CUSTOMER");
  const q = readQuery();
  const state = {
    q: q.get("q") || "",
    category: q.get("categoria") || "",
    sort: SORTS.some(([v]) => v === q.get("ordem")) ? q.get("ordem") : "name",
    page: Math.max(1, Number(q.get("pagina")) || 1),
    min: q.get("de") || "",
    max: q.get("ate") || "",
    inStock: q.get("disponivel") === "1",
  };
  const grid = h("div");
  const chips = h("div", { class: "chips", role: "tablist", "aria-label": "Categorias" });
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

  const sync = () =>
    writeQuery({ q: state.q, categoria: state.category, ordem: state.sort === "name" ? "" : state.sort, pagina: state.page, de: state.min, ate: state.max, disponivel: state.inStock });
  const reload = () => ((state.page = 1), load());
  const search = h("input", {
    class: "input search",
    type: "search",
    value: state.q,
    placeholder: "Buscar por nome, SKU ou loja",
    "aria-label": "Buscar produtos",
    oninput: debounce((e) => ((state.q = e.target.value.trim()), reload())),
  });
  const sort = h(
    "select",
    { class: "select compact", "aria-label": "Ordenar", onchange: (e) => ((state.sort = e.target.value), load()) },
    SORTS.map(([v, l]) => h("option", { value: v, selected: v === state.sort }, l)),
  );
  const priceInput = (key, label) =>
    h("input", {
      class: "input compact price",
      inputmode: "decimal",
      placeholder: label,
      "aria-label": `Preço ${label.toLowerCase()} em reais`,
      value: state[key],
      oninput: debounce((e) => ((state[key] = e.target.value.trim()), reload()), 400),
    });
  const stockToggle = h("label", { class: "check" }, h("input", { type: "checkbox", checked: state.inStock, onchange: (e) => ((state.inStock = e.target.checked), reload()) }), "Só com estoque");

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
      h(
        "div",
        { class: "toolbar" },
        search,
        h("span", { class: "range" }, "R$", priceInput("min", "Mínimo"), "a", priceInput("max", "Máximo")),
        stockToggle,
        h("span", { class: "spacer" }),
        sort,
      ),
      grid,
    ),
  );

  const cats = await api("catalog", "/products/categories");
  const allCats = [["", "Todas"], ...cats.map((c) => [c.name, c.name])];
  chips.append(
    ...allCats.map(([v, label]) =>
      h("button", { class: "chip", role: "tab", "aria-pressed": String(v === state.category), onclick: (e) => {
        chips.querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-pressed", "false"));
        e.currentTarget.setAttribute("aria-pressed", "true");
        state.category = v;
        reload();
      } }, label),
    ),
  );

  async function load() {
    sync();
    clear(grid, skeletonRows(3, 120));
    const params = new URLSearchParams({ page: state.page, size: 12, sort: state.sort });
    if (state.q) params.set("q", state.q);
    if (state.category) params.set("category", state.category);
    if (state.inStock) params.set("in_stock", "true");
    if (state.min && parsePrice(state.min) > 0) params.set("min_price", parsePrice(state.min));
    if (state.max && parsePrice(state.max) > 0) params.set("max_price", parsePrice(state.max));
    let data;
    try {
      data = await api("catalog", `/products?${params}`);
    } catch (err) {
      clear(grid, empty("Não foi possível carregar", err.message, "search"));
      return;
    }
    if (!data.items.length) {
      clear(grid, empty("Nenhum produto encontrado", "Tente outra busca, faixa de preço ou categoria.", "search"));
      return;
    }
    clear(grid,
      h("div", { class: "products" }, data.items.map((p, i) => card(p, i))),
      pagination(data.page, data.size, data.total, (pg) => ((state.page = pg), load())),
    );
  }

  function stockText(p) {
    const s = p.stock;
    return [s === 0 ? "out" : s <= p.low_stock_threshold ? "low" : "", s === 0 ? "Esgotado" : s <= p.low_stock_threshold ? `Últimas ${s} un` : `${s} em estoque`];
  }

  function addToCart(product, qty = 1) {
    const inCart = cart.lines().find((l) => l.product.id === product.id)?.qty || 0;
    if (inCart >= product.stock) {
      toast("Você já adicionou todo o estoque disponível.", "error");
      return false;
    }
    const total = cart.add(product, qty);
    toast(total - inCart < qty ? `${product.name}: só ${product.stock} disponível(is), ${total} no carrinho.` : `${product.name} no carrinho.`);
    return true;
  }

  function details(product) {
    let qty = 1;
    const qtyEl = h("span", { "aria-live": "polite" }, "1");
    const [tone, text] = stockText(product);
    const setQty = (n) => {
      qty = Math.max(1, Math.min(n, product.stock));
      qtyEl.textContent = qty;
    };
    const body = h(
      "div",
      { class: "product-sheet" },
      h("div", { class: "product-art", "aria-hidden": "true" }, h("span", {}, monogram(product.name))),
      h(
        "div",
        { class: "stack sm" },
        h("span", { class: "small muted" }, `${product.category} · ${product.seller_name}`),
        h("span", { class: "price", style: { fontSize: "20px" } }, money(product.price_cents)),
        h("span", { class: `stock-tag ${tone}` }, text),
        h("p", { class: "desc", style: { marginTop: "8px" } }, product.description || "Sem descrição."),
        h("span", { class: "small muted mono", style: { marginTop: "6px" } }, `SKU ${product.sku}`),
      ),
    );
    modal({
      title: product.name,
      body,
      actions: (close) =>
        buyer && product.stock > 0
          ? [
              h(
                "div",
                { class: "qty lg", style: { marginRight: "auto" } },
                h("button", { "aria-label": "Diminuir", onclick: () => setQty(qty - 1) }, "−"),
                qtyEl,
                h("button", { "aria-label": "Aumentar", onclick: () => setQty(qty + 1) }, "+"),
              ),
              h("button", { class: "btn ghost", onclick: close }, "Fechar"),
              h("button", { class: "btn", onclick: () => addToCart(product, qty) && close() }, icon("plus", 15), "Adicionar ao carrinho"),
            ]
          : [h("button", { class: "btn", onclick: close }, "Fechar")],
    });
  }

  function card(p, i) {
    const stockEl = h("span", { class: "stock-tag" });
    let product = p;
    const add = buyer
      ? h("button", { class: "btn sm", onclick: (e) => (e.stopPropagation(), addToCart(product)) }, icon("plus", 15), "Adicionar")
      : null;
    function paint() {
      const [tone, text] = stockText(product);
      stockEl.className = `stock-tag ${tone}`;
      stockEl.textContent = text;
      if (add) add.disabled = product.stock === 0;
    }
    paint();
    const el = h(
      "article",
      {
        class: "product reveal",
        style: { "--i": i },
        "data-id": p.id,
        tabindex: "0",
        "aria-label": `${p.name}, ${money(p.price_cents)}`,
        onclick: () => details(product),
        onkeydown: (e) => (e.key === "Enter" && e.target === el ? details(product) : null),
      },
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
