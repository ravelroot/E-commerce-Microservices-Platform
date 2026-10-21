import { login, register } from "../api.js";
import { clear, fieldErrors, h, icon, logo, segmented } from "../ui.js";

const DEMO_PASSWORD = "Argo@2026";
const DEMOS = [
  ["Administrador", "admin@argo.dev", "Tudo, incluindo usuários"],
  ["Vendedor", "vendedor@argo.dev", "Produtos, estoque e vendas"],
  ["Cliente", "cliente@argo.dev", "Loja, pedidos e notas"],
];

export function renderLogin(notice, onDone) {
  let mode = "login";
  const alert = h("div", { role: "alert" });
  const title = h("h1", {}, "Entrar na sua conta");
  const form = h("form", { class: "stack", novalidate: true, onsubmit: submit });
  const box = h("div", { class: "login-box" });

  const nameField = field("Nome ou nome da loja", h("input", { class: "input", name: "name", autocomplete: "name", placeholder: "Como você quer aparecer" }));
  const roleField = field(
    "Tipo de conta",
    h("select", { class: "select", name: "role" }, h("option", { value: "CUSTOMER" }, "Cliente: quero comprar"), h("option", { value: "SELLER" }, "Vendedor: quero vender")),
  );
  const email = h("input", { class: "input", name: "email", type: "email", autocomplete: "username", placeholder: "voce@exemplo.com", required: true });
  const password = h("input", { class: "input", name: "password", type: "password", autocomplete: "current-password", required: true });
  const eye = h("button", { type: "button", class: "icon-btn", "aria-label": "Mostrar senha", onclick: () => {
    const show = password.type === "password";
    password.type = show ? "text" : "password";
    clear(eye, icon(show ? "eyeOff" : "eye"));
  } }, icon("eye"));
  const submitBtn = h("button", { class: "btn lg block", type: "submit" }, "Entrar");
  const pwdHint = h("span", { class: "hint", hidden: true }, "Ao menos 8 caracteres, com letras e números.");

  const demos = h(
    "div",
    { class: "stack sm" },
    h("hr", { class: "divider" }),
    h("p", { class: "small muted", style: { marginTop: "8px" } }, `Contas de demonstração (senha ${DEMO_PASSWORD})`),
    h(
      "div",
      { class: "demo-list" },
      DEMOS.map(([role, mail, what], i) =>
        h(
          "button",
          { type: "button", class: "demo reveal", style: { "--i": i + 2 }, onclick: () => fill(mail) },
          h("strong", {}, role),
          h("span", { class: "what" }, what),
          h("span", { class: "who" }, mail),
        ),
      ),
    ),
  );

  function fill(mail) {
    email.value = mail;
    password.value = DEMO_PASSWORD;
    submitBtn.focus();
  }

  function draw() {
    const isLogin = mode === "login";
    title.textContent = isLogin ? "Entrar na sua conta" : "Criar conta";
    submitBtn.textContent = isLogin ? "Entrar" : "Criar conta";
    password.autocomplete = isLogin ? "current-password" : "new-password";
    pwdHint.hidden = isLogin;
    clear(form, 
      ...(isLogin ? [] : [nameField, roleField]),
      field("E-mail", email),
      field("Senha", h("div", { class: "input-affix" }, password, eye), pwdHint),
      submitBtn,
    );
    demos.hidden = !isLogin;
    clear(alert);
    fieldErrors(form, null);
    form.animate([{ opacity: 0, transform: "translateY(6px)" }, { opacity: 1, transform: "none" }], { duration: 260, easing: "cubic-bezier(.16,1,.3,1)" });
  }

  async function submit(e) {
    e.preventDefault();
    clear(alert);
    fieldErrors(form, null);
    submitBtn.disabled = true;
    const label = submitBtn.textContent;
    clear(submitBtn, h("span", { class: "spinner" }), label === "Entrar" ? "Entrando…" : "Criando…");
    try {
      if (mode === "login") await login(email.value.trim(), password.value);
      else await register({ name: form.name.value, email: email.value.trim(), password: password.value, role: form.role.value });
      onDone();
    } catch (err) {
      fieldErrors(form, err);
      clear(alert, h("div", { class: "alert" }, err.message));
      submitBtn.disabled = false;
      submitBtn.textContent = label;
    }
  }

  box.append(
    ...[segmented([["login", "Entrar"], ["register", "Criar conta"]], mode, (v) => ((mode = v), draw()), true),
    title,
    notice ? h("div", { class: "alert info" }, notice) : null,
    alert,
    form,
    demos,
  ].filter(Boolean));
  draw();

  return h(
    "div",
    { class: "login" },
    h(
      "div",
      { class: "login-panel view" },
      h("div", { class: "login-brand" }, logo(28)),
      box,
      h("p", { class: "login-foot" }, "A sessão fica só nesta aba: recarregar a página ou ficar 20 minutos sem uso pede um novo login."),
    ),
  );
}

let seq = 0;
function field(label, control, ...extra) {
  const target = control.matches?.("input, select") ? control : control.querySelector?.("input, select");
  const id = target?.id || `f${++seq}`;
  if (target) target.id = id;
  return h("div", { class: "field" }, h("label", { for: id }, label), control, ...extra);
}
