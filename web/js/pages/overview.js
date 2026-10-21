import { api, session } from "../api.js";
import { clear, countUp, dateTime, empty, h, int, money, segmented, shortDate, STATUS, statusPill } from "../ui.js";

export async function renderOverview(view) {
  const user = session.user;
  const staff = user.role !== "CUSTOMER";
  let days = 30;
  const body = h("div", { class: "stack lg" });
  const subtitle = h("p", { class: "muted" });
  view.append(
    h(
      "div",
      { class: "wrap" },
      h(
        "div",
        { class: "page-header" },
        h("div", { class: "page-header-text" }, h("h1", {}, `Olá, ${user.name.split(" ")[0]}`), subtitle),
        h("div", { class: "page-header-actions" }, segmented([[7, "7 dias"], [30, "30 dias"], [90, "90 dias"]], days, (v) => ((days = v), load()))),
      ),
      body,
    ),
  );

  async function load() {
    subtitle.textContent = `Últimos ${days} dias${user.role === "SELLER" ? " · somente os seus produtos" : user.role === "CUSTOMER" ? " · suas compras" : ""}`;
    clear(body, h("div", { class: "skeleton", style: { height: "86px" } }), h("div", { class: "skeleton", style: { height: "320px" } }));
    const [stats, recent, stock, invoices] = await Promise.all([
      api("orders", `/orders/stats?days=${days}`),
      api("orders", "/orders?size=6"),
      staff ? api("catalog", "/stock/summary") : null,
      api("billing", "/invoices/summary").catch(() => null),
    ]);
    draw(stats, recent, stock, invoices);
  }

  function draw(stats, recent, stock, invoices) {
    const labels = {
      ADMIN: ["Faturamento", "Pedidos confirmados", "Ticket médio", "Na fila agora"],
      SELLER: ["Suas vendas", "Pedidos com seus produtos", "Ticket médio", "Na fila agora"],
      CUSTOMER: ["Total em compras", "Pedidos confirmados", "Ticket médio", "Processando"],
    }[user.role];
    const values = [
      [stats.revenue_cents, money],
      [stats.orders, int],
      [stats.average_ticket_cents, money],
      [stats.processing, int],
    ];
    const kpis = h(
      "div",
      { class: "kpis reveal" },
      labels.map((label, i) => {
        const strong = h("strong", { class: "num" }, "0");
        countUp(strong, values[i][0], values[i][1]);
        return h("div", { class: "kpi" }, h("span", { class: "kpi-label" }, label), strong);
      }),
    );

    const attention = staff
      ? h(
          "div",
          { class: "attention reveal", style: { "--i": 1 } },
          h("a", { class: "attention-item", href: "#/produtos" }, h("strong", { class: "num" }, int(stock.low_stock)), "produtos com estoque baixo"),
          h("a", { class: "attention-item", href: "#/produtos" }, h("strong", { class: "num" }, int(stock.out_of_stock)), "sem estoque"),
          h("a", { class: "attention-item", href: "#/estoque" }, h("strong", { class: "num" }, money(stock.inventory_value_cents)), "em estoque"),
        )
      : h(
          "div",
          { class: "attention reveal", style: { "--i": 1 } },
          h("a", { class: "attention-item", href: "#/loja" }, h("strong", {}, "Loja"), "ver produtos disponíveis"),
          h("a", { class: "attention-item", href: "#/pedidos" }, h("strong", { class: "num" }, int(stats.by_status.SHIPPED)), "pedidos a caminho"),
          h("a", { class: "attention-item", href: "#/notas" }, h("strong", { class: "num" }, int(invoices?.issued || 0)), "notas fiscais emitidas"),
        );

    clear(body, 
      kpis,
      attention,
      h("section", { class: "card pad reveal", style: { "--i": 2 } }, h("div", { class: "panel-title" }, h("h3", {}, staff ? "Vendas por dia" : "Compras por dia")), barChart(stats.daily)),
      h(
        "div",
        { class: "grid-2" },
        h("section", { class: "card pad reveal", style: { "--i": 3 } }, h("div", { class: "panel-title" }, h("h3", {}, "Mais vendidos")), ranking(stats.top_products)),
        h("section", { class: "card pad reveal", style: { "--i": 4 } }, h("div", { class: "panel-title" }, h("h3", {}, "Pedidos por situação")), statusBlock(stats.by_status)),
      ),
      h(
        "section",
        { class: "card table-card reveal", style: { "--i": 5 } },
        h("div", { class: "panel-title", style: { padding: "0 14px" } }, h("h3", {}, "Pedidos recentes"), h("a", { class: "btn ghost sm", href: "#/pedidos" }, "Ver todos")),
        recent.items.length ? ordersTable(recent.items) : empty("Nenhum pedido ainda", "Os pedidos aparecem aqui assim que forem feitos.", "orders"),
      ),
    );
  }

  await load();
}

function barChart(daily) {
  const W = 720;
  const H = 220;
  const pad = { l: 8, r: 8, t: 10, b: 24 };
  const max = Math.max(1, ...daily.map((d) => d.revenue_cents));
  const total = daily.reduce((n, d) => n + d.revenue_cents, 0);
  const bw = (W - pad.l - pad.r) / daily.length;
  const readout = h("div", { class: "chart-readout" }, h("strong", { class: "num" }, money(total)), h("span", { class: "muted small" }, "no período"));
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("class", "chart-svg");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Gráfico de barras com o valor de cada dia");
  for (let i = 0; i <= 3; i++) {
    const y = pad.t + ((H - pad.t - pad.b) * i) / 4;
    const line = document.createElementNS(ns, "line");
    Object.entries({ x1: pad.l, x2: W - pad.r, y1: y, y2: y, class: "grid-line" }).forEach(([k, v]) => line.setAttribute(k, v));
    svg.append(line);
  }
  const step = Math.ceil(daily.length / 7);
  daily.forEach((d, i) => {
    const hgt = ((H - pad.t - pad.b) * d.revenue_cents) / max;
    const rect = document.createElementNS(ns, "rect");
    const x = pad.l + i * bw + bw * 0.18;
    Object.entries({ x, y: H - pad.b - hgt, width: bw * 0.64, height: Math.max(hgt, d.revenue_cents ? 2 : 0), rx: 2, class: "bar" }).forEach(([k, v]) => rect.setAttribute(k, v));
    rect.style.animationDelay = `${i * (500 / daily.length)}ms`;
    rect.addEventListener("mouseenter", () => {
      svg.querySelectorAll(".bar").forEach((b) => b.classList.toggle("dim", b !== rect));
      clear(readout, h("strong", { class: "num" }, money(d.revenue_cents)), h("span", { class: "muted small" }, `${shortDate(d.day + "T12:00")} · ${d.orders} ${d.orders === 1 ? "pedido" : "pedidos"}`));
    });
    svg.append(rect);
    if (i % step === 0 || i === daily.length - 1) {
      const t = document.createElementNS(ns, "text");
      t.setAttribute("x", x + bw * 0.32);
      t.setAttribute("y", H - 6);
      t.setAttribute("text-anchor", "middle");
      t.setAttribute("class", "axis");
      t.textContent = shortDate(d.day + "T12:00");
      svg.append(t);
    }
  });
  svg.addEventListener("mouseleave", () => {
    svg.querySelectorAll(".bar").forEach((b) => b.classList.remove("dim"));
    clear(readout, h("strong", { class: "num" }, money(total)), h("span", { class: "muted small" }, "no período"));
  });
  return h("div", { class: "chart" }, readout, svg);
}

function ranking(top) {
  if (!top.length) return empty("Sem vendas no período", null, "overview");
  const max = Math.max(...top.map((t) => t.revenue_cents));
  const list = h(
    "ol",
    { class: "rank" },
    top.map((t) => {
      const fill = h("span");
      requestAnimationFrame(() => requestAnimationFrame(() => (fill.style.width = `${(t.revenue_cents / max) * 100}%`)));
      return h(
        "li",
        {},
        h("div", { class: "row" }, h("span", { class: "grow" }, t.name), h("span", { class: "muted small num" }, `${t.quantity} un · ${money(t.revenue_cents)}`)),
        h("div", { class: "meter" }, fill),
      );
    }),
  );
  return list;
}

function statusBlock(byStatus) {
  const order = ["PENDING", "CONFIRMED", "SHIPPED", "DELIVERED", "REJECTED", "CANCELED"];
  const total = order.reduce((n, s) => n + (byStatus[s] || 0), 0) || 1;
  const track = h("div", { class: "status-track" });
  order.forEach((s) => {
    const seg = h("span", { style: { background: STATUS[s].color }, title: STATUS[s].label });
    track.append(seg);
    requestAnimationFrame(() => requestAnimationFrame(() => (seg.style.width = `${((byStatus[s] || 0) / total) * 100}%`)));
  });
  return h(
    "div",
    { class: "stack" },
    track,
    h("ul", { class: "legend" }, order.map((s) => h("li", {}, h("span", { class: "swatch", style: { background: STATUS[s].color } }), STATUS[s].label, h("span", { class: "num muted" }, byStatus[s] || 0)))),
  );
}

export function ordersTable(items) {
  return h(
    "div",
    { class: "table-wrap" },
    h(
      "table",
      { class: "table" },
      h("thead", {}, h("tr", {}, h("th", {}, "Pedido"), h("th", {}, "Cliente"), h("th", {}, "Situação"), h("th", {}, "Data"), h("th", { class: "right" }, "Total"))),
      h(
        "tbody",
        {},
        items.map((o, i) =>
          h(
            "tr",
            { class: "link reveal", style: { "--i": i }, onclick: () => (location.hash = `/pedidos/${o.id}`) },
            h("td", { class: "strong" }, o.code),
            h("td", {}, o.customer_name),
            h("td", {}, statusPill(o.status)),
            h("td", { class: "muted" }, dateTime(o.created_at)),
            h("td", { class: "right num strong" }, money(o.total_cents)),
          ),
        ),
      ),
    ),
  );
}
