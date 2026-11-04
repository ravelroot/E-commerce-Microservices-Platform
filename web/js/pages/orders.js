import { api, download, session } from "../api.js";
import { openCart, reorder } from "../cart.js";
import { clear, confirmBox, dateTime, debounce, empty, h, icon, modal, money, pagination, readQuery, skeletonRows, STATUS, statusPill, toast, writeQuery } from "../ui.js";
import { ordersTable } from "./overview.js";

const ORDER_SORTS = [["newest", "Mais recentes"], ["oldest", "Mais antigos"], ["total_desc", "Maior valor"], ["total_asc", "Menor valor"]];

export async function renderOrders(view) {
  const q = readQuery();
  const state = {
    status: STATUS[q.get("situacao")] ? q.get("situacao") : "",
    q: q.get("q") || "",
    from: q.get("de") || "",
    to: q.get("ate") || "",
    sort: ORDER_SORTS.some(([v]) => v === q.get("ordem")) ? q.get("ordem") : "newest",
    page: Math.max(1, Number(q.get("pagina")) || 1),
  };
  const list = h("section", { class: "card table-card" });
  const chips = h(
    "div",
    { class: "chips", role: "tablist", "aria-label": "Situação" },
    [["", "Todos"], ...Object.entries(STATUS).map(([k, v]) => [k, v.label])].map(([v, label]) =>
      h("button", { class: "chip", role: "tab", "aria-pressed": String(v === state.status), onclick: (e) => {
        chips.querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-pressed", "false"));
        e.currentTarget.setAttribute("aria-pressed", "true");
        state.status = v;
        reload();
      } }, label),
    ),
  );
  const scope = { ADMIN: "Todos os pedidos da plataforma.", SELLER: "Pedidos que têm produtos seus.", CUSTOMER: "Seus pedidos." }[session.user.role];
  const reload = () => ((state.page = 1), load());
  const dateInput = (key, label) =>
    h("input", { class: "input compact", type: "date", value: state[key], "aria-label": label, onchange: (e) => ((state[key] = e.target.value), reload()) });
  const exportBtn = h("button", { class: "btn ghost", onclick: exportCsv }, icon("download", 16), "Exportar CSV");
  view.append(
    h(
      "div",
      { class: "wrap" },
      h(
        "div",
        { class: "page-header" },
        h("div", { class: "page-header-text" }, h("h1", {}, "Pedidos"), h("p", { class: "muted" }, scope)),
        h("div", { class: "page-header-actions" }, exportBtn),
      ),
      chips,
      h(
        "div",
        { class: "toolbar" },
        h("input", {
          class: "input search",
          type: "search",
          value: state.q,
          placeholder: "Número do pedido ou cliente",
          "aria-label": "Buscar pedidos",
          oninput: debounce((e) => ((state.q = e.target.value.trim()), reload())),
        }),
        h("span", { class: "range" }, dateInput("from", "Data inicial"), "até", dateInput("to", "Data final")),
        h("span", { class: "spacer" }),
        h(
          "select",
          { class: "select compact", "aria-label": "Ordenar", onchange: (e) => ((state.sort = e.target.value), reload()) },
          ORDER_SORTS.map(([v, l]) => h("option", { value: v, selected: v === state.sort }, l)),
        ),
      ),
      list,
    ),
  );

  function params(extra = {}) {
    const params = new URLSearchParams({ sort: state.sort, ...extra });
    if (state.status) params.set("status", state.status);
    if (state.q) params.set("q", state.q);
    if (state.from) params.set("date_from", state.from);
    if (state.to) params.set("date_to", state.to);
    return params;
  }

  async function exportCsv() {
    exportBtn.disabled = true;
    try {
      const name = await download("orders", `/orders/export?${params()}`, "argo-pedidos.csv");
      toast(`${name} baixado.`);
    } catch (err) {
      toast(err.message, "error");
    } finally {
      exportBtn.disabled = false;
    }
  }

  async function load() {
    writeQuery({ situacao: state.status, q: state.q, de: state.from, ate: state.to, ordem: state.sort === "newest" ? "" : state.sort, pagina: state.page });
    clear(list, skeletonRows(6));
    try {
      const data = await api("orders", `/orders?${params({ page: state.page, size: 15 })}`);
      clear(list,
        data.items.length ? ordersTable(data.items) : empty("Nenhum pedido encontrado", "Ajuste os filtros ou faça uma compra na loja.", "orders"),
        data.total > data.size ? pagination(data.page, data.size, data.total, (p) => ((state.page = p), load())) : null,
      );
    } catch (err) {
      clear(list, empty("Não foi possível carregar", err.message, "orders"));
    }
  }
  await load();
}

const STEPS = [
  ["PENDING", "Recebido"],
  ["CONFIRMED", "Confirmado"],
  ["SHIPPED", "Enviado"],
  ["DELIVERED", "Entregue"],
];

export async function renderOrder(view, id) {
  const wrap = h("div", { class: "wrap" });
  view.append(wrap);
  let poll;
  let lastStatus;
  let lastHistory = 0;
  let signature = "";

  async function load(first = false) {
    const order = await api("orders", `/orders/${id}`);
    const sig = [order.status, order.history.length, order.invoice_number, order.email_sent_at].join("|");
    if (!first && sig === signature) return order;
    signature = sig;
    const changed = lastStatus && order.status !== lastStatus;
    lastStatus = order.status;
    lastHistory = order.history.length;
    draw(order, !first);
    if (changed) toast(`Pedido ${order.code}: ${STATUS[order.status].label.toLowerCase()}.`, order.status === "REJECTED" ? "error" : "ok");
    return order;
  }

  let delay = 1200;
  function schedule(order) {
    clearTimeout(poll);
    const busy = order.status === "PENDING" || (["CONFIRMED", "SHIPPED", "DELIVERED"].includes(order.status) && !order.invoice_number);
    if (!busy) return;
    poll = setTimeout(async () => {
      try {
        schedule(await load());
      } catch {
        schedule(order);
      }
    }, delay);
    delay = Math.min(10000, Math.round(delay * 1.5));
  }

  function draw(o, quiet = false) {
    wrap.classList.toggle("quiet", quiet);
    const user = session.user;
    const canCancel = ["PENDING", "CONFIRMED"].includes(o.status) && (user.role === "ADMIN" || o.customer_id === user.id);
    const next = o.status === "CONFIRMED" ? "SHIPPED" : o.status === "SHIPPED" ? "DELIVERED" : null;
    const canMove = next && user.role !== "CUSTOMER";
    const canReorder = user.role === "CUSTOMER" && o.customer_id === user.id && o.status !== "PENDING";
    const reached = STEPS.findIndex(([s]) => s === o.status);
    const failed = ["REJECTED", "CANCELED"].includes(o.status);

    const steps = h(
      "div",
      { class: "steps" },
      STEPS.map(([s, label], i) => {
        const on = !failed && reached >= i;
        const working = o.status === "PENDING" && i === 1;
        return h("div", { class: `step ${on ? "on" : ""} ${working ? "working" : ""}` }, h("div", { class: "bar" }, h("span")), label);
      }),
    );

    const timeline = h(
      "ol",
      { class: "timeline" },
      o.history.map((ev, i) => {
        const bad = ["REJECTED", "CANCELED"].includes(ev.status);
        return h(
          "li",
          { style: { animationDelay: `${i * 70}ms` } },
          h("span", { class: `node ${bad ? "bad" : "done"}` }, icon(bad ? "x" : "check")),
          h("div", {}, h("div", { class: "strong" }, ev.note), h("div", { class: "small muted" }, `${dateTime(ev.created_at)} · ${ev.actor}`)),
        );
      }),
      o.status === "PENDING"
        ? h("li", {}, h("span", { class: "node wait" }), h("div", {}, h("div", { class: "strong" }, "Na fila: reservando estoque…"), h("div", { class: "small muted" }, "Celery + Redis")))
        : null,
    );

    const items = h(
      "table",
      { class: "table" },
      h("thead", {}, h("tr", {}, h("th", {}, "Produto"), h("th", {}, "Loja"), h("th", { class: "right" }, "Qtd."), h("th", { class: "right" }, "Unitário"), h("th", { class: "right" }, "Subtotal"))),
      h(
        "tbody",
        {},
        o.items.map((it) =>
          h("tr", {}, h("td", {}, h("div", { class: "strong" }, it.product_name), h("div", { class: "small muted mono" }, it.sku)), h("td", { class: "muted" }, it.seller_name), h("td", { class: "right num" }, it.quantity), h("td", { class: "right num" }, money(it.unit_price_cents)), h("td", { class: "right num strong" }, money(it.subtotal_cents))),
        ),
      ),
    );

    clear(wrap, 
      h("a", { class: "back-link", href: "#/pedidos" }, icon("back", 16), "Pedidos"),
      h(
        "div",
        { class: "page-header" },
        h("div", { class: "page-header-text" }, h("div", { class: "row" }, h("h1", {}, `Pedido ${o.code}`), statusPill(o.status)), h("p", { class: "muted" }, `${o.customer_name} · ${dateTime(o.created_at)}`)),
        h(
          "div",
          { class: "page-header-actions" },
          h("button", { class: "btn ghost", onclick: () => print() }, icon("print", 16), "Imprimir"),
          canReorder ? h("button", { class: "btn ghost", onclick: () => buyAgain(o) }, icon("repeat", 16), "Comprar de novo") : null,
          canMove ? h("button", { class: "btn", onclick: () => move(o, next) }, next === "SHIPPED" ? "Marcar como enviado" : "Marcar como entregue") : null,
          canCancel ? h("button", { class: "btn danger", onclick: () => cancel(o) }, "Cancelar pedido") : null,
        ),
      ),
      h(
        "div",
        { class: "grid-main" },
        h(
          "div",
          { class: "stack" },
          h("section", { class: "card pad reveal" }, failed ? h("div", { class: "alert", style: { animation: "none" } }, o.rejection_reason || "Pedido cancelado.") : steps),
          h("section", { class: "card table-card reveal", style: { "--i": 1 } }, h("div", { class: "table-wrap" }, items)),
        ),
        h(
          "div",
          { class: "stack" },
          h(
            "section",
            { class: "card pad reveal", style: { "--i": 2 } },
            h("h3", { style: { marginBottom: "14px" } }, "Resumo"),
            h(
              "dl",
              { class: "kv" },
              h("dt", {}, "Itens"), h("dd", { class: "num" }, o.items_count),
              h("dt", {}, "Total"), h("dd", { class: "num strong" }, money(o.total_cents)),
              h("dt", {}, "E-mail de confirmação"), h("dd", {}, o.email_sent_at ? `Enviado ${dateTime(o.email_sent_at).split(" ")[1] || ""}` : "—"),
              h("dt", {}, "Nota fiscal"), h("dd", {}, o.invoice_number ? h("a", { class: "strong", style: { color: "var(--accent)" }, href: `#/notas/${o.invoice_number}` }, o.invoice_number) : o.status === "PENDING" || o.status === "CONFIRMED" ? h("span", { class: "muted" }, "emitindo…") : "—"),
            ),
          ),
          h("section", { class: "card pad reveal", style: { "--i": 3 } }, h("h3", { style: { marginBottom: "14px" } }, "Linha do tempo"), timeline),
        ),
      ),
    );
  }

  async function buyAgain(o) {
    try {
      const { added, missing } = await reorder(o);
      if (missing.length) toast(`Indisponível agora: ${missing.join(", ")}.`, "error");
      if (added) openCart((order) => (location.hash = `/pedidos/${order.id}`));
      else if (!missing.length) toast("Os itens já estão no carrinho com todo o estoque disponível.", "error");
    } catch (err) {
      toast(err.message, "error");
    }
  }

  async function cancel(o) {
    let reason = "";
    const ok = await new Promise((resolve) =>
      modal({
        title: `Cancelar ${o.code}?`,
        body: h("div", { class: "stack" }, h("p", { class: "muted" }, "Os itens voltam para o estoque e a nota fiscal, se houver, é cancelada pela fila."), h("div", { class: "field" }, h("label", {}, "Motivo (opcional)"), h("input", { class: "input", maxlength: 300, oninput: (e) => (reason = e.target.value) }))),
        actions: (close) => [h("button", { class: "btn ghost", onclick: () => (close(), resolve(false)) }, "Voltar"), h("button", { class: "btn danger", onclick: () => (close(), resolve(true)) }, "Cancelar pedido")],
      }),
    );
    if (!ok) return;
    try {
      draw(await api("orders", `/orders/${o.id}/cancel`, { method: "POST", body: { reason } }));
      lastStatus = "CANCELED";
      toast("Pedido cancelado. Devolvendo itens ao estoque…");
      setTimeout(() => load(true), 1500);
    } catch (err) {
      toast(err.message, "error");
    }
  }

  async function move(o, status) {
    let note = "";
    const ok =
      status === "SHIPPED"
        ? await new Promise((resolve) =>
            modal({
              title: "Marcar como enviado",
              body: h("div", { class: "field" }, h("label", {}, "Código de rastreio ou observação"), h("input", { class: "input", maxlength: 300, placeholder: "BR123456789BR", oninput: (e) => (note = e.target.value) })),
              actions: (close) => [h("button", { class: "btn ghost", onclick: () => (close(), resolve(false)) }, "Voltar"), h("button", { class: "btn", onclick: () => (close(), resolve(true)) }, "Confirmar envio")],
            }),
          )
        : await confirmBox("Marcar como entregue?", "O cliente verá o pedido como entregue.", "Confirmar entrega");
    if (!ok) return;
    try {
      const order = await api("orders", `/orders/${o.id}/status`, { method: "PATCH", body: { status, note } });
      lastStatus = order.status;
      lastHistory = order.history.length;
      draw(order);
      toast(status === "SHIPPED" ? "Pedido marcado como enviado." : "Pedido entregue.");
    } catch (err) {
      toast(err.message, "error");
    }
  }

  wrap.append(skeletonRows(4, 90));
  schedule(await load(true));
  return () => clearTimeout(poll);
}
