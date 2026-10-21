import { api, session } from "../api.js";
import { live } from "../bus.js";
import { countUp, empty, h, int, money, time } from "../ui.js";

const KIND = { IN: "Entrada", OUT: "Saída", COUNT: "Contagem", SALE: "Venda", RELEASE: "Devolução" };

export async function renderLive(view) {
  const admin = session.is("ADMIN");
  const summary = await api("catalog", "/stock/summary");
  const feed = h("ul", { class: "feed" });
  const placeholder = empty("Aguardando movimentações", "Cada venda, cancelamento ou ajuste aparece aqui na hora. Faça uma compra com a conta de Cliente em outra aba para ver.", "live");
  const unitsEl = h("strong", { class: "num" }, "0");
  const lowEl = h("strong", { class: "num" }, "0");
  const outEl = h("strong", { class: "num" }, "0");
  const eventsEl = h("strong", { class: "num" }, "0");
  let events = 0;
  countUp(unitsEl, summary.units);
  countUp(lowEl, summary.low_stock);
  countUp(outEl, summary.out_of_stock);

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
        h("section", { class: "card pad reveal", style: { "--i": 1 } }, h("div", { class: "panel-title" }, h("h3", {}, "Movimentações"), h("span", { class: "pill accent pulse" }, h("span", { class: "dot" }), "ao vivo")), feed, placeholder),
        h("p", { class: "hint reveal", style: { "--i": 2 } }, `Valor do estoque: ${money(summary.inventory_value_cents)}.`),
      ),
    ),
  );

  const onStock = (e) => {
    const ev = e.detail;
    if (!admin && ev.seller_id !== session.user.id) return;
    placeholder.remove();
    events += 1;
    eventsEl.textContent = int(events);
    unitsEl.textContent = int(Number(unitsEl.textContent.replace(/\D/g, "")) + ev.delta);
    feed.prepend(
      h(
        "li",
        { class: "new" },
        h("span", { class: "muted num small" }, time(ev.at)),
        h("div", {}, h("div", { class: "strong" }, ev.name), h("div", { class: "small muted" }, `${KIND[ev.kind]}${ev.order_id ? ` · pedido AR-${String(ev.order_id).padStart(6, "0")}` : ""} · saldo ${ev.stock}${ev.low ? " · estoque baixo" : ""}`)),
        h("span", { class: `delta ${ev.delta > 0 ? "up" : "down"}` }, ev.delta > 0 ? `+${ev.delta}` : ev.delta),
      ),
    );
    while (feed.children.length > 40) feed.lastChild.remove();
  };
  live.addEventListener("stock", onStock);
  return () => live.removeEventListener("stock", onStock);
}
