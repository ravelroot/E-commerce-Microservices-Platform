import { health } from "../api.js";
import { clear, dateTime, h, icon, time } from "../ui.js";

const SERVICES = [
  ["identity", "Identidade", "Python · Django"],
  ["catalog", "Catálogo e estoque", "Python · Django"],
  ["orders", "Pedidos", "Python · Django"],
  ["billing", "Faturamento", "Java · Spring Boot"],
];

export async function renderSystem(view) {
  const grid = h("div", { class: "status-grid" });
  const stamp = h("span", { class: "muted small" });
  const refreshBtn = h("button", { class: "btn ghost", onclick: () => load() }, icon("refresh", 16), "Atualizar");
  let timer;

  view.append(
    h(
      "div",
      { class: "wrap" },
      h(
        "div",
        { class: "page-header" },
        h("div", { class: "page-header-text" }, h("h1", {}, "Sistema"), h("p", { class: "muted" }, "Saúde de cada serviço consultada pelo gateway. Atualiza sozinha a cada 15 segundos.")),
        h("div", { class: "page-header-actions" }, stamp, refreshBtn),
      ),
      h("div", { class: "stack lg" }, grid, tools()),
    ),
  );

  function card([key, name, stack], result, i) {
    const ok = result.ok && result.status === "ok";
    const checks = Object.entries(result.checks || {});
    return h(
      "section",
      { class: "card pad service-card reveal", style: { "--i": i } },
      h(
        "div",
        { class: "head" },
        h("div", {}, h("h3", {}, name), h("span", { class: "small muted" }, stack)),
        h("span", { class: `pill ${ok ? "ok" : "danger"}` }, h("span", { class: "dot" }), ok ? "No ar" : result.status === "degraded" ? "Com problema" : "Fora do ar"),
      ),
      h(
        "dl",
        { class: "kv" },
        h("dt", {}, "Versão"), h("dd", { class: "num" }, result.version || "—"),
        h("dt", {}, "Ambiente"), h("dd", {}, result.environment || "—"),
        h("dt", {}, "Resposta"), h("dd", { class: "num" }, `${result.latency} ms`),
        checks.length ? checks.map(([k, v]) => [h("dt", {}, k === "database" ? "Banco de dados" : k.replace("database:", "Banco ")), h("dd", { class: v === "ok" ? "" : "strong", style: v === "ok" ? {} : { color: "var(--danger)" } }, v)]) : [h("dt", {}, "Situação"), h("dd", {}, result.status_text || result.message || `HTTP ${result.http}`)],
      ),
      h("a", { class: "small", style: { color: "var(--accent)", fontWeight: 600 }, href: `/docs/?servico=${key}`, target: "_blank", rel: "noopener" }, "Documentação da API →"),
    );
  }

  function tools() {
    const rows = [
      ["Fila e agendador", "Flower mostra workers, tarefas e falhas. Fica em http://localhost:5555 no servidor (ARGO_FLOWER_PORT)."],
      ["E-mails de teste", "Mailpit recebe os e-mails quando o SMTP real não está configurado: http://localhost:8025 (ARGO_MAILPIT_PORT)."],
      ["Diagnóstico completo", "make diagnostico (ou argo diagnostico no Windows) confere bancos, migrações, Redis, SMTP e segredos."],
      ["Recuperação automática", "O agendador põe de novo na fila, a cada 5 minutos, pedidos parados em Processando ou sem e-mail e nota."],
    ];
    return h(
      "section",
      { class: "card pad reveal", style: { "--i": 5 } },
      h("h3", { style: { marginBottom: "14px" } }, "Ferramentas de operação"),
      h("dl", { class: "kv", style: { gridTemplateColumns: "minmax(140px, auto) 1fr" } }, rows.map(([k, v]) => [h("dt", {}, k), h("dd", { style: { textAlign: "left" } }, v)])),
    );
  }

  async function load() {
    clearTimeout(timer);
    refreshBtn.disabled = true;
    const results = await Promise.all(SERVICES.map(([key]) => health(key)));
    clear(grid, SERVICES.map((s, i) => card(s, results[i], i)));
    stamp.textContent = `Atualizado às ${time(new Date().toISOString())}`;
    stamp.title = dateTime(new Date().toISOString());
    refreshBtn.disabled = false;
    timer = setTimeout(load, 15000);
  }

  await load();
  return () => clearTimeout(timer);
}
