import { api, session } from "./api.js";
import { clear, debounce, h, icon, modal, money } from "./ui.js";

const normalize = (text) => text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export function openPalette(commands) {
  let results = [];
  let selected = 0;
  let seq = 0;
  const input = h("input", {
    type: "search",
    placeholder: "Ir para uma tela, buscar produto ou pedido…",
    "aria-label": "Buscar comandos",
    autocomplete: "off",
    autofocus: true,
  });
  const list = h("ul", { role: "listbox", "aria-label": "Resultados" });
  const body = h(
    "div",
    {},
    h("div", { class: "search-row" }, icon("search"), input, h("span", { class: "kbd" }, "Esc")),
    list,
    h("div", { class: "foot" }, h("span", {}, h("span", { class: "kbd" }, "↑"), " ", h("span", { class: "kbd" }, "↓"), " navegar"), h("span", {}, h("span", { class: "kbd" }, "Enter"), " abrir")),
  );
  const close = modal({ title: "", label: "Busca rápida", body, className: "palette", overlayClass: "palette-overlay" });

  function run(item) {
    close();
    item.run();
  }

  function paint() {
    if (!results.length) {
      clear(list, h("li", { class: "empty-row" }, input.value ? "Nada encontrado." : "Digite para buscar."));
      return;
    }
    clear(
      list,
      results.map((item, i) =>
        h(
          "li",
          {
            role: "option",
            "aria-selected": String(i === selected),
            onmouseenter: () => {
              selected = i;
              list.querySelectorAll("li").forEach((li, j) => li.setAttribute("aria-selected", String(j === selected)));
            },
            onclick: () => run(item),
          },
          icon(item.icon || "chevron", 16),
          h("span", {}, item.label),
          h("span", { class: "group" }, item.group),
        ),
      ),
    );
    list.children[selected]?.scrollIntoView({ block: "nearest" });
  }

  function staticMatches(term) {
    const t = normalize(term);
    return commands.filter((c) => !t || normalize(`${c.label} ${c.keywords || ""}`).includes(t));
  }

  const remote = debounce(async (term, ticket) => {
    if (term.length < 2) return;
    const found = [];
    const digits = term.replace(/\D/g, "");
    try {
      const [products, orders] = await Promise.all([
        api("catalog", `/products?${new URLSearchParams({ q: term, size: 5 })}`),
        digits || session.user.role !== "CUSTOMER" ? api("orders", `/orders?${new URLSearchParams({ q: term, size: 5 })}`) : { items: [] },
      ]);
      for (const p of products.items) {
        found.push({
          label: `${p.name} · ${money(p.price_cents)}`,
          group: "Produto",
          icon: "products",
          run: () => (location.hash = session.user.role === "CUSTOMER" ? `/loja?q=${encodeURIComponent(p.name)}` : `/produtos/${p.id}`),
        });
      }
      for (const o of orders.items) {
        found.push({ label: `${o.code} · ${o.customer_name}`, group: "Pedido", icon: "orders", run: () => (location.hash = `/pedidos/${o.id}`) });
      }
    } catch {
      return;
    }
    if (ticket !== seq) return;
    results = [...staticMatches(term), ...found];
    paint();
  }, 220);

  input.addEventListener("input", () => {
    const term = input.value.trim();
    seq += 1;
    selected = 0;
    results = staticMatches(term);
    paint();
    remote(term, seq);
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!results.length) return;
      selected = (selected + (e.key === "ArrowDown" ? 1 : -1) + results.length) % results.length;
      paint();
    } else if (e.key === "Enter" && results[selected]) {
      e.preventDefault();
      run(results[selected]);
    }
  });

  results = staticMatches("");
  paint();
}

export function openShortcuts() {
  const mod = /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘" : "Ctrl";
  const rows = [
    [[mod, "K"], "Abrir a busca rápida e os atalhos de telas"],
    [["/"], "Ir para a busca da tela atual"],
    [["G", "V"], "Visão geral"],
    [["G", "L"], "Loja"],
    [["G", "P"], "Pedidos"],
    [["G", "N"], "Notas fiscais"],
    [["G", "C"], "Minha conta"],
    [["T"], "Alternar tema claro e escuro"],
    [["P"], "Trocar a paleta de cores"],
    [["?"], "Mostrar esta lista"],
  ];
  modal({
    title: "Atalhos de teclado",
    body: h("dl", { class: "shortcuts" }, rows.map(([keys, text]) => [h("dt", {}, keys.map((k) => h("span", { class: "kbd" }, k))), h("dd", {}, text)])),
    actions: (close) => [h("button", { class: "btn", onclick: close }, "Fechar")],
  });
}
