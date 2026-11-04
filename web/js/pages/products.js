import { api, download, session } from "../api.js";
import { live } from "../bus.js";
import { clear, dateTime, debounce, empty, fieldErrors, h, icon, int, modal, money, pagination, readQuery, segmented, skeletonRows, toast, writeQuery } from "../ui.js";

const KIND = { IN: "Entrada", OUT: "Saída", COUNT: "Contagem", SALE: "Venda", RELEASE: "Devolução" };

const PRODUCT_SORTS = [["name", "Nome"], ["stock", "Menor estoque"], ["price_desc", "Maior preço"], ["price_asc", "Menor preço"], ["newest", "Mais recentes"]];

export async function renderProducts(view) {
  const admin = session.is("ADMIN");
  const q = readQuery();
  const filter = ["low", "inactive"].includes(q.get("filtro")) ? q.get("filtro") : "all";
  const state = {
    q: q.get("q") || "",
    page: Math.max(1, Number(q.get("pagina")) || 1),
    low: filter === "low",
    inactive: filter === "inactive",
    sort: PRODUCT_SORTS.some(([v]) => v === q.get("ordem")) ? q.get("ordem") : "name",
  };
  const list = h("section", { class: "card table-card" });
  const exportBtn = h("button", { class: "btn ghost", onclick: exportCsv }, icon("download", 16), "Exportar CSV");
  view.append(
    h(
      "div",
      { class: "wrap" },
      h(
        "div",
        { class: "page-header" },
        h("div", { class: "page-header-text" }, h("h1", {}, "Produtos"), h("p", { class: "muted" }, admin ? "Todos os produtos da plataforma." : "Seus produtos e o estoque de cada um.")),
        h("div", { class: "page-header-actions" }, exportBtn, h("a", { class: "btn", href: "#/produtos/novo" }, icon("plus", 16), "Novo produto")),
      ),
      h(
        "div",
        { class: "toolbar" },
        h("input", {
          class: "input search",
          type: "search",
          value: state.q,
          placeholder: "Buscar por nome ou SKU",
          "aria-label": "Buscar",
          oninput: debounce((e) => ((state.q = e.target.value.trim()), (state.page = 1), load())),
        }),
        h("span", { class: "spacer" }),
        h(
          "select",
          { class: "select compact", "aria-label": "Ordenar", onchange: (e) => ((state.sort = e.target.value), (state.page = 1), load()) },
          PRODUCT_SORTS.map(([v, l]) => h("option", { value: v, selected: v === state.sort }, l)),
        ),
        segmented([["all", "Todos"], ["low", "Estoque baixo"], ["inactive", "Com inativos"]], filter, (v) => {
          state.low = v === "low";
          state.inactive = v === "inactive";
          state.page = 1;
          load();
        }),
      ),
      list,
    ),
  );

  function params(extra = {}) {
    const params = new URLSearchParams({ sort: state.low && state.sort === "name" ? "stock" : state.sort, ...extra });
    if (!admin) params.set("mine", "true");
    if (state.q) params.set("q", state.q);
    if (state.low) params.set("low_stock", "true");
    if (state.inactive) params.set("include_inactive", "true");
    return params;
  }

  async function exportCsv() {
    exportBtn.disabled = true;
    try {
      toast(`${await download("catalog", `/products/export?${params()}`, "argo-produtos.csv")} baixado.`);
    } catch (err) {
      toast(err.message, "error");
    } finally {
      exportBtn.disabled = false;
    }
  }

  const rows = new Map();
  async function load() {
    writeQuery({ q: state.q, pagina: state.page, filtro: state.low ? "low" : state.inactive ? "inactive" : "", ordem: state.sort === "name" ? "" : state.sort });
    clear(list, skeletonRows(8));
    const data = await api("catalog", `/products?${params({ page: state.page, size: 20 })}`);
    rows.clear();
    if (!data.items.length) {
      clear(list, empty("Nenhum produto", "Cadastre o primeiro produto para começar a vender.", "products"));
      return;
    }
    clear(list, 
      h(
        "div",
        { class: "table-wrap" },
        h(
          "table",
          { class: "table" },
          h("thead", {}, h("tr", {}, h("th", {}, "Produto"), admin ? h("th", {}, "Loja") : null, h("th", {}, "Categoria"), h("th", { class: "right" }, "Preço"), h("th", { class: "right" }, "Estoque"), h("th", {}), h("th", {}))),
          h("tbody", {}, data.items.map((p, i) => row(p, i))),
        ),
      ),
      data.total > data.size ? pagination(data.page, data.size, data.total, (pg) => ((state.page = pg), load())) : null,
    );
  }

  function stockCell(p) {
    const tone = p.stock === 0 ? "danger" : p.stock <= p.low_stock_threshold ? "warn" : "";
    return h("span", { class: `pill ${tone || "line"} num` }, int(p.stock));
  }

  function row(p, i) {
    const cell = h("td", { class: "right" }, stockCell(p));
    const tr = h(
      "tr",
      { class: "reveal", style: { "--i": Math.min(i, 12) } },
      h("td", {}, h("a", { class: "strong", href: `#/produtos/${p.id}` }, p.name), h("div", { class: "small muted mono" }, p.sku)),
      admin ? h("td", { class: "muted" }, p.seller_name) : null,
      h("td", { class: "muted" }, p.category),
      h("td", { class: "right num" }, money(p.price_cents)),
      cell,
      h("td", {}, p.active ? null : h("span", { class: "pill" }, "Inativo")),
      h(
        "td",
        { class: "right" },
        h(
          "div",
          { class: "row-actions" },
          h("button", { class: "btn ghost sm", onclick: () => stockModal(p, (np) => update(np)) }, "Movimentar"),
          h("a", { class: "btn quiet sm", href: `#/produtos/novo?de=${encodeURIComponent(p.id)}`, title: "Cadastrar um produto parecido" }, icon("copy", 15), "Duplicar"),
        ),
      ),
    );
    const update = (np) => {
      Object.assign(p, np);
      clear(cell, stockCell(p));
      tr.style.animation = "none";
      void tr.offsetWidth;
      tr.style.animation = "highlight 1.6s var(--ease)";
    };
    rows.set(p.id, update);
    return tr;
  }

  const onStock = (e) => rows.get(e.detail.product_id)?.({ stock: e.detail.stock });
  live.addEventListener("stock", onStock);
  await load();
  return () => live.removeEventListener("stock", onStock);
}

export function stockModal(p, done) {
  let kind = "IN";
  const qty = h("input", { class: "input", name: "quantity", type: "number", min: 0, step: 1, value: 1 });
  const reason = h("input", { class: "input", name: "reason", maxlength: 200, placeholder: "Ex.: reposição do fornecedor" });
  const hint = h("p", { class: "hint" });
  const paint = () => (hint.textContent = { IN: `Soma ao estoque atual (${p.stock}).`, OUT: `Subtrai do estoque atual (${p.stock}).`, COUNT: "Define o estoque com o valor contado no inventário." }[kind]);
  paint();
  const form = h(
    "form",
    { class: "stack", onsubmit: (e) => e.preventDefault() },
    h("p", { class: "muted" }, p.name),
    segmented([["IN", "Entrada"], ["OUT", "Saída"], ["COUNT", "Contagem"]], kind, (v) => ((kind = v), paint()), true),
    h("div", { class: "field" }, h("label", {}, "Quantidade"), qty, hint),
    h("div", { class: "field" }, h("label", {}, "Motivo"), reason),
  );
  modal({
    title: "Movimentar estoque",
    body: form,
    actions: (close) => [
      h("button", { class: "btn ghost", onclick: close }, "Cancelar"),
      h("button", { class: "btn", onclick: async (e) => {
        e.currentTarget.disabled = true;
        try {
          const np = await api("catalog", `/products/${p.id}/stock`, { method: "POST", body: { kind, quantity: Number(qty.value), reason: reason.value } });
          close();
          toast(`Estoque de ${np.name}: ${np.stock} un.`);
          done?.(np);
        } catch (err) {
          fieldErrors(form, err);
          toast(err.message, "error");
          e.currentTarget.disabled = false;
        }
      } }, "Salvar"),
    ],
  });
}

export async function renderProductForm(view, id) {
  const editing = !!id;
  const sourceId = editing ? null : readQuery().get("de");
  const product = editing ? await api("catalog", `/products/${id}`) : null;
  const source = sourceId ? await api("catalog", `/products/${sourceId}`).catch(() => null) : null;
  const base = product || (source ? { ...source, sku: "", name: `${source.name} (cópia)` } : null);
  const categories = await api("catalog", "/products/categories");
  const wrap = h("div", { class: "wrap" });
  view.append(wrap);

  const f = (name, label, control, hint) => h("div", { class: "field" }, h("label", { for: name }, label), control, hint && h("span", { class: "hint" }, hint));
  const input = (name, attrs = {}) => h("input", { class: "input", id: name, name, ...attrs });
  const price = input("price", { inputmode: "decimal", placeholder: "0,00", value: base ? (base.price_cents / 100).toFixed(2).replace(".", ",") : "" });
  const form = h(
    "form",
    { class: "stack", novalidate: true, onsubmit: save },
    h(
      "div",
      { class: "grid-2" },
      f("sku", "SKU", input("sku", { value: product?.sku || "", disabled: editing, placeholder: "LOJ-CAM-01", maxlength: 40 }), editing ? "O SKU não muda depois do cadastro." : "Código único do produto."),
      f("category", "Categoria", input("category", { value: base?.category || "", list: "cats", maxlength: 60 })),
    ),
    h("datalist", { id: "cats" }, categories.map((c) => h("option", { value: c.name }))),
    f("name", "Nome", input("name", { value: base?.name || "", maxlength: 140 })),
    f("description", "Descrição", h("textarea", { class: "textarea", id: "description", name: "description", maxlength: 2000 }, base?.description || "")),
    h(
      "div",
      { class: "grid-2" },
      f("price", "Preço (R$)", price),
      f("low_stock_threshold", "Avisar com estoque em", input("low_stock_threshold", { type: "number", min: 0, value: base?.low_stock_threshold ?? 5 }), "Abaixo disso o produto aparece como estoque baixo."),
    ),
    editing ? null : f("stock", "Estoque inicial", input("stock", { type: "number", min: 0, value: 0 })),
    editing
      ? h("label", { class: "row small" }, h("input", { type: "checkbox", name: "active", checked: product.active }), "Produto ativo na loja")
      : null,
    h("div", { class: "row" }, h("button", { class: "btn", type: "submit" }, editing ? "Salvar alterações" : "Cadastrar produto"), h("a", { class: "btn ghost", href: "#/produtos" }, "Cancelar")),
  );

  async function save(e) {
    e.preventDefault();
    fieldErrors(form, null);
    const cents = parsePrice(price.value);
    const body = {
      name: form.name.value,
      description: form.description.value,
      category: form.category.value,
      price_cents: Number.isFinite(cents) ? cents : 0,
      low_stock_threshold: Number(form.low_stock_threshold.value),
    };
    try {
      if (editing) {
        await api("catalog", `/products/${id}`, { method: "PUT", body: { ...body, active: form.active.checked, version: product.version } });
        toast("Produto atualizado.");
      } else {
        const created = await api("catalog", "/products", { method: "POST", body: { ...body, sku: form.sku.value, stock: Number(form.stock.value) } });
        toast(`${created.name} cadastrado.`);
      }
      location.hash = "/produtos";
    } catch (err) {
      if (err.fields?.price_cents) err.fields.price = "Informe um preço maior que zero.";
      fieldErrors(form, err);
      toast(err.message, "error");
    }
  }

  const history = h("section", { class: "card table-card reveal", style: { "--i": 1 } });
  wrap.append(
    h("a", { class: "back-link", href: "#/produtos" }, icon("back", 16), "Produtos"),
    h(
      "div",
      { class: "page-header" },
      h(
        "div",
        { class: "page-header-text" },
        h("h1", {}, editing ? product.name : "Novo produto"),
        editing ? h("p", { class: "muted" }, `Estoque atual: ${product.stock} un · versão ${product.version}`) : source ? h("p", { class: "muted" }, `Baseado em ${source.name}. Informe um SKU novo.`) : null,
      ),
      editing
        ? h(
            "div",
            { class: "page-header-actions" },
            h("a", { class: "btn ghost", href: `#/produtos/novo?de=${encodeURIComponent(product.id)}` }, icon("copy", 16), "Duplicar"),
            h("button", { class: "btn ghost", onclick: () => stockModal(product, (np) => (Object.assign(product, np), renderHistory())) }, "Movimentar estoque"),
          )
        : null,
    ),
    h("div", { class: editing ? "grid-main" : "" }, h("section", { class: "card pad reveal" }, form), editing ? history : null),
  );

  async function renderHistory() {
    clear(history, skeletonRows(5, 36));
    const data = await api("catalog", `/products/${id}/movements?size=12`);
    clear(history, 
      h("div", { class: "panel-title", style: { padding: "0 14px" } }, h("h3", {}, "Histórico de estoque")),
      h(
        "div",
        { class: "table-wrap" },
        h(
          "table",
          { class: "table" },
          h("thead", {}, h("tr", {}, h("th", {}, "Movimento"), h("th", { class: "right" }, "Qtd."), h("th", { class: "right" }, "Saldo"))),
          h(
            "tbody",
            {},
            data.items.map((m) =>
              h("tr", {}, h("td", {}, h("div", { class: "strong" }, KIND[m.kind]), h("div", { class: "small muted" }, `${dateTime(m.created_at)} · ${m.reason}`)), h("td", { class: `right num delta ${m.delta > 0 ? "up" : "down"}` }, m.delta > 0 ? `+${m.delta}` : m.delta), h("td", { class: "right num" }, m.stock_after)),
            ),
          ),
        ),
      ),
    );
  }
  if (editing) await renderHistory();
}

export function parsePrice(text) {
  let v = String(text).trim().replace(/[R$\s]/g, "");
  if (v.includes(",")) v = v.replace(/\./g, "").replace(",", ".");
  else if (!/^\d+\.\d{1,2}$/.test(v)) v = v.replace(/\./g, "");
  const n = Number(v);
  return Number.isFinite(n) && v !== "" ? Math.round(n * 100) : 0;
}
