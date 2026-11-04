import { api, session } from "../api.js";
import { clear, confirmBox, dateTime, debounce, empty, fieldErrors, h, icon, initials, modal, pagination, readQuery, relative, ROLE, segmented, skeletonRows, time, toast, writeQuery } from "../ui.js";

const SITUATIONS = [["", "Qualquer situação"], ["true", "Ativos"], ["false", "Inativos"], ["locked", "Bloqueados agora"]];

export async function renderUsers(view) {
  const query = readQuery();
  const state = {
    q: query.get("q") || "",
    role: ROLE[query.get("papel")] ? query.get("papel") : "",
    situation: SITUATIONS.some(([v]) => v && v === query.get("situacao")) ? query.get("situacao") : "",
    page: Math.max(1, Number(query.get("pagina")) || 1),
  };
  const list = h("section", { class: "card table-card" });
  view.append(
    h(
      "div",
      { class: "wrap" },
      h(
        "div",
        { class: "page-header" },
        h("div", { class: "page-header-text" }, h("h1", {}, "Usuários"), h("p", { class: "muted" }, "Papéis e acesso. Desativar uma conta encerra as sessões dela na hora.")),
        h("div", { class: "page-header-actions" }, h("button", { class: "btn", onclick: create }, icon("plus", 16), "Novo usuário")),
      ),
      h(
        "div",
        { class: "toolbar" },
        h("input", {
          class: "input search",
          type: "search",
          value: state.q,
          placeholder: "Nome ou e-mail",
          "aria-label": "Buscar usuários",
          oninput: debounce((e) => ((state.q = e.target.value.trim()), (state.page = 1), load())),
        }),
        h(
          "select",
          { class: "select compact", "aria-label": "Situação", onchange: (e) => ((state.situation = e.target.value), (state.page = 1), load()) },
          SITUATIONS.map(([v, l]) => h("option", { value: v, selected: v === state.situation }, l)),
        ),
        h("span", { class: "spacer" }),
        segmented([["", "Todos"], ["ADMIN", "Administradores"], ["SELLER", "Vendedores"], ["CUSTOMER", "Clientes"]], state.role, (v) => ((state.role = v), (state.page = 1), load())),
      ),
      list,
    ),
  );

  async function load() {
    writeQuery({ q: state.q, papel: state.role, situacao: state.situation, pagina: state.page });
    clear(list, skeletonRows(6));
    const params = new URLSearchParams({ page: state.page, size: 20 });
    if (state.q) params.set("q", state.q);
    if (state.role) params.set("role", state.role);
    if (state.situation === "locked") params.set("locked", "true");
    else if (state.situation) params.set("active", state.situation);
    const data = await api("identity", `/users?${params}`);
    if (!data.items.length) {
      clear(list, empty("Nenhum usuário encontrado", "Ajuste a busca, o papel ou a situação.", "users"));
      return;
    }
    clear(list, 
      h(
        "div",
        { class: "table-wrap" },
        h(
          "table",
          { class: "table" },
          h("thead", {}, h("tr", {}, h("th", {}, "Usuário"), h("th", {}, "Papel"), h("th", {}, "Último acesso"), h("th", {}, "Situação"), h("th", {}))),
          h("tbody", {}, data.items.map((u, i) => row(u, i))),
        ),
      ),
      data.total > data.size ? pagination(data.page, data.size, data.total, (p) => ((state.page = p), load())) : null,
    );
  }

  function row(u, i) {
    const self = u.id === session.user.id;
    const role = h(
      "select",
      { class: "select compact", disabled: self, "aria-label": `Papel de ${u.name}`, onchange: (e) => patch(u, { role: e.target.value }) },
      Object.entries(ROLE).map(([v, l]) => h("option", { value: v, selected: v === u.role }, l)),
    );
    const toggle = h(
      "button",
      {
        class: `btn sm ${u.active ? "ghost" : ""}`,
        disabled: self,
        onclick: async () => {
          if (u.active && !(await confirmBox(`Desativar ${u.name}?`, "A pessoa perde o acesso na hora e todas as sessões dela são encerradas.", "Desativar", true))) return;
          patch(u, { active: !u.active });
        },
      },
      u.active ? "Desativar" : "Reativar",
    );
    const locked = u.locked_until && new Date(u.locked_until) > new Date();
    return h(
      "tr",
      { class: "reveal", style: { "--i": Math.min(i, 12) } },
      h("td", {}, h("div", { class: "row" }, h("span", { class: "avatar" }, initials(u.name)), h("div", {}, h("div", { class: "strong" }, u.name, self ? h("span", { class: "muted small" }, " (você)") : null), h("div", { class: "small muted" }, u.email)))),
      h("td", {}, role),
      h("td", { class: "muted", title: dateTime(u.last_login_at) }, u.last_login_at ? relative(u.last_login_at) : "nunca"),
      h(
        "td",
        {},
        h(
          "div",
          { class: "row", style: { gap: "8px" } },
          u.active ? h("span", { class: "pill ok" }, "Ativo") : h("span", { class: "pill danger" }, "Inativo"),
          locked ? h("span", { class: "pill warn", title: `Bloqueado por tentativas até ${dateTime(u.locked_until)}` }, icon("lock", 12), `até ${time(u.locked_until).slice(0, 5)}`) : null,
          toggle,
        ),
      ),
      h(
        "td",
        { class: "right" },
        h(
          "div",
          { class: "row-actions" },
          locked ? h("button", { class: "btn ghost sm", onclick: () => unlock(u) }, "Desbloquear") : null,
          h("button", { class: "btn quiet sm", onclick: () => resetPassword(u) }, icon("key", 15), "Nova senha"),
        ),
      ),
    );
  }

  async function patch(u, body) {
    try {
      await api("identity", `/users/${u.id}`, { method: "PATCH", body });
      toast("Usuário atualizado.");
      load();
    } catch (err) {
      toast(err.message, "error");
      load();
    }
  }

  async function unlock(u) {
    try {
      await api("identity", `/users/${u.id}/unlock`, { method: "POST" });
      toast(`${u.name} pode entrar de novo.`);
      load();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  function resetPassword(u) {
    const input = h("input", { class: "input", name: "password", type: "text", autocomplete: "new-password" });
    const form = h(
      "form",
      { class: "stack", onsubmit: (e) => e.preventDefault() },
      h("p", { class: "muted" }, `${u.name} (${u.email}) entra com a senha nova. As sessões abertas dela são encerradas e o bloqueio por tentativas é removido.`),
      h("div", { class: "field" }, h("label", {}, "Nova senha"), input, h("span", { class: "hint" }, "Ao menos 8 caracteres, com letras e números.")),
    );
    modal({
      title: "Definir nova senha",
      body: form,
      actions: (close) => [
        h("button", { class: "btn ghost", onclick: close }, "Cancelar"),
        h("button", { class: "btn", onclick: async () => {
          try {
            await api("identity", `/users/${u.id}/password`, { method: "POST", body: { password: input.value } });
            close();
            toast("Senha definida. Avise a pessoa por um canal seguro.");
            load();
          } catch (err) {
            fieldErrors(form, err);
          }
        } }, "Salvar senha"),
      ],
    });
  }

  function create() {
    const form = h(
      "form",
      { class: "stack", onsubmit: (e) => e.preventDefault() },
      h("div", { class: "field" }, h("label", {}, "Nome"), h("input", { class: "input", name: "name" })),
      h("div", { class: "field" }, h("label", {}, "E-mail"), h("input", { class: "input", name: "email", type: "email" })),
      h("div", { class: "field" }, h("label", {}, "Senha inicial"), h("input", { class: "input", name: "password", type: "text" }), h("span", { class: "hint" }, "Ao menos 8 caracteres, com letras e números.")),
      h("div", { class: "field" }, h("label", {}, "Papel"), h("select", { class: "select", name: "role" }, Object.entries(ROLE).map(([v, l]) => h("option", { value: v, selected: v === "SELLER" }, l)))),
    );
    modal({
      title: "Novo usuário",
      body: form,
      actions: (close) => [
        h("button", { class: "btn ghost", onclick: close }, "Cancelar"),
        h("button", { class: "btn", onclick: async () => {
          try {
            await api("identity", "/users", { method: "POST", body: { name: form.name.value, email: form.email.value, password: form.password.value, role: form.role.value } });
            close();
            toast("Usuário criado.");
            load();
          } catch (err) {
            fieldErrors(form, err);
          }
        } }, "Criar"),
      ],
    });
  }
  await load();
}
