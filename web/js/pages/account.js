import { api, endSession } from "../api.js";
import { fieldErrors, h, initials, ROLE, toast } from "../ui.js";

export async function renderAccount(view) {
  const me = await api("identity", "/auth/me");
  const form = h(
    "form",
    { class: "stack", novalidate: true, onsubmit: save },
    h("div", { class: "field" }, h("label", { for: "cur" }, "Senha atual"), h("input", { class: "input", id: "cur", name: "current_password", type: "password", autocomplete: "current-password" })),
    h("div", { class: "field" }, h("label", { for: "new" }, "Nova senha"), h("input", { class: "input", id: "new", name: "new_password", type: "password", autocomplete: "new-password" }), h("span", { class: "hint" }, "Ao menos 8 caracteres, com letras e números. Todas as sessões abertas serão encerradas.")),
    h("div", {}, h("button", { class: "btn", type: "submit" }, "Trocar senha")),
  );
  async function save(e) {
    e.preventDefault();
    fieldErrors(form, null);
    try {
      await api("identity", "/auth/me/password", { method: "PUT", body: { current_password: form.current_password.value, new_password: form.new_password.value } });
      toast("Senha alterada. Entre de novo com a nova senha.");
      endSession("logout");
    } catch (err) {
      fieldErrors(form, err);
      toast(err.message, "error");
    }
  }
  view.append(
    h(
      "div",
      { class: "wrap", style: { maxWidth: "760px" } },
      h("div", { class: "page-header" }, h("div", { class: "page-header-text" }, h("h1", {}, "Minha conta"))),
      h(
        "div",
        { class: "stack" },
        h(
          "section",
          { class: "card pad reveal" },
          h("div", { class: "row" }, h("span", { class: "avatar", style: { width: "44px", height: "44px", fontSize: "14px" } }, initials(me.name)), h("div", {}, h("div", { class: "strong" }, me.name), h("div", { class: "muted small" }, `${me.email} · ${ROLE[me.role]}`))),
        ),
        h("section", { class: "card pad reveal", style: { "--i": 1 } }, h("h3", { style: { marginBottom: "16px" } }, "Trocar senha"), form),
      ),
    ),
  );
}
