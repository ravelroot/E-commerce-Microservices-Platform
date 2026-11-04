import { api, session } from "../api.js";
import { live } from "../bus.js";
import { clear, countUp, dateTime, empty, h, icon, int, money, segmented, time } from "../ui.js";

const KIND = { IN: "Entrada", OUT: "Saída", COUNT: "Contagem", SALE: "Venda", RELEASE: "Devolução" };
const FILTERS = [["", "Tudo"], ["SALE", "Vendas"], ["RELEASE", "Devoluções"], ["IN", "Entradas"], ["OUT", "Saídas"], ["COUNT", "Contagens"]];

export async function renderLive(view) {
  const admin = session.is("ADMIN");
  const [summary, recent] = await Promise.all([api("catalog", "/stock/summary"), api("catalog", "/stock/movements?size=25")]);
  const feed = h("ul", { class: "feed", "aria-live": "polite" });
  const placeholder = empty("Aguardando movimentações", "Cada venda, cancelamento ou ajuste aparece aqui na hora. Faça uma compra com a conta de Cliente em outra aba para ver.", "live");
  const unitsEl = h("strong", { class: "num" }, "0");
  const lowEl = h("strong", { class: "num" }, "0");
  const outEl = h("strong", { class: "num" }, "0");
  const eventsEl = h("strong", { class: "num" }, "0");
  let events = 0;
  let units = summary.units;
  let kind = "";
  let paused = false;
  const queued = [];
  countUp(unitsEl, summary.units);
  countUp(lowEl, summary.low_stock);
  countUp(outEl, summary.out_of_stock);

  const pill = h("span", { class: "pill accent pulse" }, h("span", { class: "dot" }), "ao vivo");
  const pauseBtn = h("button", { class: "btn ghost sm", onclick: togglePause }, icon("pause", 15), "Pausar");

  view.append(
    h(
      "div",
      { class: "wrap" },
      h("div", { class: "page-header" }, h("div", { class: "page-header-text" }, h("h1", {}, "Estoque ao vivo"), h("p", { class: "muted" }, `Server-Sent Events alimentados por Redis Pub/Sub · ${admin ? "todos os vendedores" : "somente seus produtos"}`))),
      h(
        "div",
        { class: "stack lg" },
        h(
          "div",
          { class: "kpis reveal" },
          h("div", { class: "kpi" }, h("span", { class: "kpi-label" }, "Unidades em estoque"), unitsEl),
          h("div", { class: "kpi" }, h("span", { class: "kpi-label" }, "Com estoque baixo"), lowEl),
          h("div", { class: "kpi" }, h("span", { class: "kpi-label" }, "Esgotados"), outEl),
          h("div", { class: "kpi" }, h("span", { class: "kpi-label" }, "Eventos nesta tela"), eventsEl),
        ),
        h(
          "section",
          { class: "card pad reveal", style: { "--i": 1 } },
          h("div", { class: "panel-title" }, h("h3", {}, "Movimentações"), pill, pauseBtn),
          h("div", { style: { marginBottom: "12px", overflowX: "auto" } }, segmented(FILTERS, kind, (v) => ((kind = v), applyFilter()))),
          feed,
          placeholder,
        ),
        h("p", { class: "hint reveal", style: { "--i": 2 } }, `Valor do estoque: ${money(summary.inventory_value_cents)}. As últimas ${recent.items.length} movimentações aparecem ao abrir a tela.`),
      ),
    ),
  );

  function row(ev, fresh) {
    const at = ev.at || ev.created_at;
    const order = ev.order_id ? ` · pedido AR-${String(ev.order_id).padStart(6, "0")}` : "";
    const reason = !fresh && ev.reason && !ev.order_id ? ` · ${ev.reason}` : "";
    const li = h(
      "li",
      { class: fresh ? "new" : "", "data-kind": ev.kind, title: dateTime(at) },
      h("span", { class: "muted num small" }, time(at)),
      h("div", {}, h("div", { class: "strong" }, ev.name || ev.product_name), h("div", { class: "small muted" }, `${KIND[ev.kind]}${order}${reason} · saldo ${ev.stock}${ev.low ? " · estoque baixo" : ""}`)),
      h("span", { class: `delta ${ev.delta > 0 ? "up" : "down"}` }, ev.delta > 0 ? `+${ev.delta}` : ev.delta),
    );
    li.hidden = !!kind && ev.kind !== kind;
    return li;
  }

  function applyFilter() {
    feed.querySelectorAll("li").forEach((li) => (li.hidden = !!kind && li.dataset.kind !== kind));
    placeholder.hidden = feed.querySelector("li:not([hidden])") !== null;
  }

  function show(ev) {
    feed.prepend(row(ev, true));
    while (feed.children.length > 60) feed.lastChild.remove();
    applyFilter();
  }

  function togglePause() {
    paused = !paused;
    clear(pauseBtn, icon(paused ? "play" : "pause", 15), paused ? `Continuar${queued.length ? ` (${queued.length})` : ""}` : "Pausar");
    clear(pill, h("span", { class: "dot" }), paused ? "pausado" : "ao vivo");
    pill.className = paused ? "pill warn" : "pill accent pulse";
    if (!paused) queued.splice(0).forEach(show);
  }

  recent.items.forEach((m) => feed.append(row(m, false)));
  applyFilter();

  const onStock = (e) => {
    const ev = e.detail;
    if (!admin && ev.seller_id !== session.user.id) return;
    events += 1;
    units += ev.delta;
    eventsEl.textContent = int(events);
    unitsEl.textContent = int(units);
    if (paused) {
      queued.push(ev);
      clear(pauseBtn, icon("play", 15), `Continuar (${queued.length})`);
      return;
    }
    show(ev);
  };
  live.addEventListener("stock", onStock);
  return () => live.removeEventListener("stock", onStock);
}
