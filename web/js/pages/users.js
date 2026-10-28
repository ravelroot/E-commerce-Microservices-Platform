import { api, session } from "../api.js";
import { clear, confirmBox, dateTime, fieldErrors, h, icon, initials, modal, pagination, ROLE, segmented, skeletonRows, toast } from "../ui.js";

export async function renderUsers(view) {
  const state = { q: "", role: "", page: 1 };
  const list = h("section", { class: "card table-card" });
  let timer;
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
        h("input", { class: "input search", type: "search", placeholder: "Nome ou e-mail", "aria-label": "Buscar usuários", oninput: (e) => {
          clearTimeout(timer);
          timer = setTimeout(() => ((state.q = e.target.value.trim()), (state.page = 1), load()), 250);
        } }),
        h("span", { class: "spacer" }),
        segmented([["", "Todos"], ["ADMIN", "Administradores"], ["SELLER", "Vendedores"], ["CUSTOMER", "Clientes"]], "", (v) => ((state.role = v), (state.page = 1), load())),
      ),
      list,
    ),
  );

  async function load() {
    clear(list, skeletonRows(6));
    const params = new URLSearchParams({ page: state.page, size: 20 });
    if (state.q) params.set("q", state.q);
    if (state.role) params.set("role", state.role);
    const data = await api("identity", `/users?${params}`);
    clear(list, 
      h(
        "div",
        { class: "table-wrap" },
        h(
          "table",
          { class: "table" },
          h("thead", {}, h("tr", {}, h("th", {}, "Usuário"), h("th", {}, "Papel"), h("th", {}, "Último acesso"), h("th", {}, "Situação"))),
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
    return h(
      "tr",
      { class: "reveal", style: { "--i": Math.min(i, 12) } },
      h("td", {}, h("div", { class: "row" }, h("span", { class: "avatar" }, initials(u.name)), h("div", {}, h("div", { class: "strong" }, u.name, self ? h("span", { class: "muted small" }, " (você)") : null), h("div", { class: "small muted" }, u.email)))),
      h("td", {}, role),
      h("td", { class: "muted" }, dateTime(u.last_login_at)),
      h("td", {}, h("div", { class: "row" }, u.active ? h("span", { class: "pill ok" }, "Ativo") : h("span", { class: "pill danger" }, "Inativo"), toggle)),
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
