import { api, download, session } from "../api.js";
import { clear, countUp, dateTime, debounce, empty, h, icon, int, money, pagination, readQuery, segmented, skeletonRows, toast, writeQuery } from "../ui.js";

export async function renderInvoices(view) {
  const query = readQuery();
  const state = {
    status: ["ISSUED", "CANCELED"].includes(query.get("situacao")) ? query.get("situacao") : "",
    q: query.get("q") || "",
    from: query.get("de") || "",
    to: query.get("ate") || "",
    page: Math.max(1, Number(query.get("pagina")) || 1),
  };
  const list = h("section", { class: "card table-card" });
  const totals = await api("billing", "/invoices/summary");
  const k = (label, value, fmt) => {
    const s = h("strong", { class: "num" }, "0");
    countUp(s, value, fmt);
    return h("div", { class: "kpi" }, h("span", { class: "kpi-label" }, label), s);
  };
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
        h("div", { class: "page-header-text" }, h("h1", {}, "Notas fiscais"), h("p", { class: "muted" }, "Emitidas pelo serviço de faturamento em Java (Spring Boot) a partir da fila de pedidos.")),
        h("div", { class: "page-header-actions" }, exportBtn),
      ),
      h(
        "div",
        { class: "stack lg" },
        h("div", { class: "kpis reveal" }, k("Notas emitidas", totals.issued, int), k("Canceladas", totals.canceled, int), k("Valor faturado", totals.totalCents, money), k("Tributos aproximados", totals.taxCents, money)),
        h(
          "div",
          {},
          h(
            "div",
            { class: "toolbar" },
            h("input", {
              class: "input search",
              type: "search",
              value: state.q,
              placeholder: "Número da nota, pedido ou cliente",
              "aria-label": "Buscar notas",
              oninput: debounce((e) => ((state.q = e.target.value.trim()), reload())),
            }),
            h("span", { class: "range" }, dateInput("from", "Emitidas a partir de"), "até", dateInput("to", "Emitidas até")),
            h("span", { class: "spacer" }),
            segmented([["", "Todas"], ["ISSUED", "Emitidas"], ["CANCELED", "Canceladas"]], state.status, (v) => ((state.status = v), reload())),
          ),
          list,
        ),
      ),
    ),
  );

  function params(extra = {}) {
    const params = new URLSearchParams(extra);
    if (state.status) params.set("status", state.status);
    if (state.q) params.set("q", state.q);
    if (state.from) params.set("from", state.from);
    if (state.to) params.set("to", state.to);
    return params;
  }

  async function exportCsv() {
    exportBtn.disabled = true;
    try {
      toast(`${await download("billing", `/invoices/export?${params()}`, "argo-notas.csv")} baixado.`);
    } catch (err) {
      toast(err.message, "error");
    } finally {
      exportBtn.disabled = false;
    }
  }

  async function load() {
    writeQuery({ situacao: state.status, q: state.q, de: state.from, ate: state.to, pagina: state.page });
    clear(list, skeletonRows(6));
    let data;
    try {
      data = await api("billing", `/invoices?${params({ page: state.page, size: 15 })}`);
    } catch (err) {
      clear(list, empty("Não foi possível carregar", err.message, "invoice"));
      return;
    }
    if (!data.items.length) {
      const filtered = state.status || state.q || state.from || state.to;
      clear(list, empty(filtered ? "Nenhuma nota com esses filtros" : "Nenhuma nota ainda", filtered ? "Ajuste a busca, a situação ou o período." : session.is("CUSTOMER") ? "A nota é emitida sozinha alguns segundos depois que o pedido é confirmado." : "As notas aparecem aqui conforme os pedidos são confirmados.", "invoice"));
      return;
    }
    clear(list,
      h(
        "div",
        { class: "table-wrap" },
        h(
          "table",
          { class: "table" },
          h("thead", {}, h("tr", {}, h("th", {}, "Nota"), h("th", {}, "Pedido"), h("th", {}, "Cliente"), h("th", {}, "Emissão"), h("th", {}, "Situação"), h("th", { class: "right" }, "Total"))),
          h(
            "tbody",
            {},
            data.items.map((n, i) =>
              h(
                "tr",
                { class: "link reveal", style: { "--i": i }, onclick: () => (location.hash = `/notas/${n.number}`) },
                h("td", { class: "strong" }, h("a", { href: `#/notas/${n.number}`, onclick: (e) => e.stopPropagation() }, n.number)),
                h("td", {}, n.orderCode),
                h("td", {}, n.customerName),
                h("td", { class: "muted" }, dateTime(n.issuedAt)),
                h("td", {}, n.status === "ISSUED" ? h("span", { class: "pill ok" }, h("span", { class: "dot" }), "Emitida") : h("span", { class: "pill danger" }, h("span", { class: "dot" }), "Cancelada")),
                h("td", { class: "right num strong" }, money(n.totalCents)),
              ),
            ),
          ),
        ),
      ),
      data.total > data.size ? pagination(data.page, data.size, data.total, (pg) => ((state.page = pg), load())) : null,
    );
  }
  await load();
}

export async function renderInvoice(view, number) {
  const n = await api("billing", `/invoices/${number}`);
  view.append(
    h(
      "div",
      { class: "wrap" },
      h("a", { class: "back-link", href: "#/notas" }, icon("back", 16), "Notas fiscais"),
      h(
        "div",
        { class: "page-header" },
        h("div", { class: "page-header-text" }, h("div", { class: "row" }, h("h1", {}, `Nota ${n.number}`), n.status === "ISSUED" ? h("span", { class: "pill ok" }, "Emitida") : h("span", { class: "pill danger" }, "Cancelada")), h("p", { class: "muted" }, `${n.customerName} · ${dateTime(n.issuedAt)}`)),
        h(
          "div",
          { class: "page-header-actions" },
          h("button", { class: "btn ghost", onclick: () => print() }, icon("print", 16), "Imprimir"),
          h("a", { class: "btn ghost", href: `#/pedidos/${n.orderId}` }, `Ver pedido ${n.orderCode}`),
        ),
      ),
      h(
        "div",
        { class: "grid-main" },
        h(
          "section",
          { class: "card table-card reveal" },
          h(
            "table",
            { class: "table" },
            h("thead", {}, h("tr", {}, h("th", {}, "Descrição"), h("th", { class: "right" }, "Qtd."), h("th", { class: "right" }, "Unitário"), h("th", { class: "right" }, "Total"))),
            h("tbody", {}, n.items.map((i) => h("tr", {}, h("td", {}, i.description), h("td", { class: "right num" }, i.quantity), h("td", { class: "right num" }, money(i.unitPriceCents)), h("td", { class: "right num strong" }, money(i.totalCents))))),
          ),
        ),
        h(
          "section",
          { class: "card pad reveal", style: { "--i": 1 } },
          h(
            "dl",
            { class: "kv" },
            h("dt", {}, "Valor total"), h("dd", { class: "num strong" }, money(n.totalCents)),
            h("dt", {}, "Tributos aproximados"), h("dd", { class: "num" }, `${money(n.taxCents)} (${(n.taxRate * 100).toFixed(2).replace(".", ",")}%)`),
            n.canceledAt ? [h("dt", {}, "Cancelada em"), h("dd", {}, dateTime(n.canceledAt))] : null,
          ),
          h("p", { class: "hint", style: { marginTop: "14px" } }, "Valor aproximado dos tributos conforme a Lei 12.741/2012. Nota de demonstração, sem validade fiscal."),
        ),
      ),
    ),
  );
}
