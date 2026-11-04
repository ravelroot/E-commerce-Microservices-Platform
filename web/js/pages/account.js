import { api, refreshSession, session } from "../api.js";
import { clear, confirmBox, date, dateTime, deviceLabel, empty, fieldErrors, h, icon, initials, paletteOptions, relative, ROLE, segmented, skeletonRows, toast } from "../ui.js";

export async function renderAccount(view) {
  const me = await api("identity", "/auth/me");
  const sessionsBox = h("div");

  const nameInput = h("input", { class: "input", id: "acc-name", name: "name", value: me.name, maxlength: 120, autocomplete: "name" });
  const profile = h(
    "form",
    { class: "stack", novalidate: true, onsubmit: saveName },
    h("div", { class: "field" }, h("label", { for: "acc-name" }, me.role === "SELLER" ? "Nome da loja" : "Nome"), nameInput, h("span", { class: "hint" }, "Aparece nos pedidos, nas notas e no menu. Pedidos antigos mantêm o nome da época.")),
    h("div", {}, h("button", { class: "btn", type: "submit" }, "Salvar nome")),
  );

  const passwordForm = h(
    "form",
    { class: "stack", novalidate: true, onsubmit: savePassword },
    h("div", { class: "field" }, h("label", { for: "cur" }, "Senha atual"), h("input", { class: "input", id: "cur", name: "current_password", type: "password", autocomplete: "current-password" })),
    h("div", { class: "field" }, h("label", { for: "new" }, "Nova senha"), h("input", { class: "input", id: "new", name: "new_password", type: "password", autocomplete: "new-password" }), h("span", { class: "hint" }, "Ao menos 8 caracteres, com letras e números. As outras sessões abertas são encerradas; esta continua.")),
    h("div", {}, h("button", { class: "btn", type: "submit" }, "Trocar senha")),
  );

  const themeChoice = window.argoTheme?.get() || "light";
  const theme = segmented([["light", "Claro"], ["dark", "Escuro"], ["system", "Sistema"]], themeChoice, (v) => window.argoTheme?.set(v), true);

  async function saveName(e) {
    e.preventDefault();
    fieldErrors(profile, null);
    try {
      await api("identity", "/auth/me", { method: "PATCH", body: { name: nameInput.value } });
      toast("Nome atualizado.");
      await refreshSession();
    } catch (err) {
      fieldErrors(profile, err);
      toast(err.message, "error");
    }
  }

  async function savePassword(e) {
    e.preventDefault();
    fieldErrors(passwordForm, null);
    try {
      await api("identity", "/auth/me/password", { method: "PUT", body: { current_password: passwordForm.current_password.value, new_password: passwordForm.new_password.value } });
      passwordForm.reset();
      toast("Senha alterada. As outras sessões foram encerradas.");
      loadSessions();
    } catch (err) {
      fieldErrors(passwordForm, err);
      toast(err.message, "error");
    }
  }

  async function revoke(s) {
    if (!(await confirmBox("Encerrar esta sessão?", `${deviceLabel(s.user_agent)} perde o acesso quando o token atual expirar (até 15 minutos).`, "Encerrar", true))) return;
    try {
      await api("identity", `/auth/sessions/${s.id}`, { method: "DELETE" });
      toast("Sessão encerrada.");
      loadSessions();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  async function revokeOthers() {
    if (!(await confirmBox("Sair de todos os outros aparelhos?", "Só esta aba continua conectada.", "Encerrar as outras", true))) return;
    try {
      const { revoked } = await api("identity", "/auth/sessions/revoke-others", { method: "POST" });
      toast(revoked ? `${revoked} sessão(ões) encerrada(s).` : "Não havia outras sessões abertas.");
      loadSessions();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  async function loadSessions() {
    clear(sessionsBox, skeletonRows(2, 48));
    let rows;
    try {
      rows = await api("identity", "/auth/sessions");
    } catch (err) {
      clear(sessionsBox, empty("Não foi possível carregar as sessões", err.message, "devices"));
      return;
    }
    const others = rows.filter((s) => !s.current).length;
    clear(
      sessionsBox,
      h(
        "ul",
        { class: "sessions" },
        rows.map((s) =>
          h(
            "li",
            {},
            h("span", { class: "device", "aria-hidden": "true" }, icon("devices", 18)),
            h(
              "div",
              {},
              h("div", { class: "strong" }, deviceLabel(s.user_agent), s.current ? h("span", { class: "pill accent", style: { marginLeft: "8px" } }, "Esta sessão") : null),
              h("div", { class: "small muted" }, `${s.ip_address || "IP desconhecido"} · entrou ${dateTime(s.started_at)} · usada ${relative(s.last_used_at)}`),
            ),
            s.current ? h("span") : h("button", { class: "btn ghost sm", onclick: () => revoke(s) }, "Encerrar"),
          ),
        ),
      ),
      others ? h("div", { style: { marginTop: "14px" } }, h("button", { class: "btn danger sm", onclick: revokeOthers }, "Sair de todos os outros aparelhos")) : null,
    );
  }

  view.append(
    h(
      "div",
      { class: "wrap", style: { maxWidth: "760px" } },
      h("div", { class: "page-header" }, h("div", { class: "page-header-text" }, h("h1", {}, "Minha conta"), h("p", { class: "muted" }, "Perfil, aparência, sessões abertas e senha."))),
      h(
        "div",
        { class: "stack" },
        h(
          "section",
          { class: "card pad reveal" },
          h("div", { class: "row", style: { marginBottom: "18px" } }, h("span", { class: "avatar", style: { width: "44px", height: "44px", fontSize: "14px" } }, initials(me.name)), h("div", {}, h("div", { class: "strong" }, me.name), h("div", { class: "muted small" }, `${me.email} · ${ROLE[me.role]} · conta criada em ${date(me.created_at)}`))),
          profile,
        ),
        h(
          "section",
          { class: "card pad reveal", style: { "--i": 1 } },
          h("h3", { style: { marginBottom: "6px" } }, "Aparência"),
          h("p", { class: "muted small", style: { marginBottom: "14px" } }, "Vale só para este navegador. “Sistema” segue o tema do seu computador. Atalho: tecla T."),
          h("div", { class: "theme-picker" }, theme),
          h("h3", { style: { margin: "20px 0 6px" } }, "Paleta de cores"),
          h("p", { class: "muted small", style: { marginBottom: "12px" } }, "Combina com o tema claro ou escuro. Atalho: tecla P troca para a próxima."),
          paletteOptions(),
        ),
        h(
          "section",
          { class: "card pad reveal", style: { "--i": 2 } },
          h("h3", { style: { marginBottom: "6px" } }, "Sessões abertas"),
          h("p", { class: "muted small", style: { marginBottom: "6px" } }, session.remembered ? "Esta aba está com “Manter conectado” ligado: recarregar a página não pede login." : "Cada login em um navegador ou aparelho abre uma sessão de até 7 dias."),
          sessionsBox,
        ),
        h("section", { class: "card pad reveal", style: { "--i": 3 } }, h("h3", { style: { marginBottom: "16px" } }, "Trocar senha"), passwordForm),
      ),
    ),
  );
  await loadSessions();
}
