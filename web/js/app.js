import { endSession, session, stream } from "./api.js";
import { live } from "./bus.js";
import { cart } from "./cart.js";
import { clear, h, icon, initials, logo, ROLE, toast } from "./ui.js";
import { renderLogin } from "./pages/login.js";
import { renderOverview } from "./pages/overview.js";
import { renderStore } from "./pages/store.js";
import { renderOrders, renderOrder } from "./pages/orders.js";
import { renderProducts, renderProductForm } from "./pages/products.js";
import { renderLive } from "./pages/live.js";
import { renderInvoices, renderInvoice } from "./pages/invoices.js";
import { renderUsers } from "./pages/users.js";
import { renderAccount } from "./pages/account.js";

const ALL = ["ADMIN", "SELLER", "CUSTOMER"];
const STAFF = ["ADMIN", "SELLER"];

const ROUTES = [
  { path: /^\/$/, render: renderOverview, roles: ALL, nav: "/" },
  { path: /^\/loja$/, render: renderStore, roles: ALL, nav: "/loja" },
  { path: /^\/pedidos$/, render: renderOrders, roles: ALL, nav: "/pedidos" },
  { path: /^\/pedidos\/(\d+)$/, render: renderOrder, roles: ALL, nav: "/pedidos" },
  { path: /^\/produtos$/, render: renderProducts, roles: STAFF, nav: "/produtos" },
  { path: /^\/produtos\/novo$/, render: renderProductForm, roles: STAFF, nav: "/produtos" },
  { path: /^\/produtos\/([\w-]+)$/, render: renderProductForm, roles: STAFF, nav: "/produtos" },
  { path: /^\/estoque$/, render: renderLive, roles: STAFF, nav: "/estoque" },
  { path: /^\/notas$/, render: renderInvoices, roles: ALL, nav: "/notas" },
  { path: /^\/notas\/([\w-]+)$/, render: renderInvoice, roles: ALL, nav: "/notas" },
  { path: /^\/usuarios$/, render: renderUsers, roles: ["ADMIN"], nav: "/usuarios" },
  { path: /^\/conta$/, render: renderAccount, roles: ALL, nav: null },
];

const NAV = [
  ["/", "Visão geral", "overview", ALL],
  ["/loja", "Loja", "store", ALL],
  ["/pedidos", "Pedidos", "orders", ALL],
  ["/produtos", "Produtos", "products", STAFF],
  ["/estoque", "Estoque ao vivo", "live", STAFF],
  ["/notas", "Notas fiscais", "invoice", ALL],
  ["/usuarios", "Usuários", "users", ["ADMIN"]],
];

const root = document.getElementById("app");
let shell = null;
let cleanup = null;
let stopStream = null;
let loginNotice = null;

export function navigate(path) {
  if (location.hash === `#${path}`) route();
  else location.hash = path;
}

function currentPath() {
  return location.hash.replace(/^#/, "") || "/";
}

function buildShell() {
  const user = session.user;
  const navEl = h("nav", { "aria-label": "Principal" });
  const thumb = h("span", { class: "nav-thumb", "aria-hidden": "true" });
  navEl.append(thumb);
  for (const [path, label, ic, roles] of NAV) {
    if (!roles.includes(user.role)) continue;
    const badge = path === "/loja" && user.role === "CUSTOMER" ? h("span", { class: "badge", hidden: true }) : null;
    navEl.append(h("a", { href: `#${path}`, "data-path": path }, icon(ic), label, badge));
  }
  const liveTag = h("span", { class: "live" }, h("span", { class: "dot" }), "Conectando ao estoque…");
  const menuHost = h("div", { class: "user-menu" });
  const trigger = h(
    "button",
    { class: "user-trigger", "aria-expanded": "false", onclick: () => toggleMenu() },
    h("span", { class: "avatar" }, initials(user.name)),
    h("span", { class: "user-trigger-text" }, h("span", { class: "strong" }, user.name), h("span", { class: "small muted" }, ROLE[user.role])),
    icon("chevron", 16),
  );
  menuHost.append(trigger);
  function toggleMenu(force) {
    const open = force ?? trigger.getAttribute("aria-expanded") !== "true";
    trigger.setAttribute("aria-expanded", String(open));
    menuHost.querySelector(".menu")?.remove();
    if (!open) return;
    const menu = h(
      "div",
      { class: "menu", role: "menu" },
      h("div", { class: "menu-head" }, h("span", { class: "strong" }, user.name), h("span", { class: "muted small" }, user.email)),
      h("a", { href: "#/conta", onclick: () => toggleMenu(false) }, icon("key", 16), "Minha conta"),
      h("button", { onclick: () => endSession("logout") }, icon("logout", 16), "Sair"),
    );
    menuHost.prepend(menu);
    setTimeout(() => document.addEventListener("click", function off(e) {
      if (!menuHost.contains(e.target)) {
        toggleMenu(false);
        document.removeEventListener("click", off);
      }
    }), 0);
  }

  const sidebar = h(
    "aside",
    { class: "sidebar" },
    h("a", { class: "brand", href: "#/" }, logo(20)),
    h("span", { class: "sidebar-tag" }, "Plataforma de pedidos"),
    navEl,
    h("hr"),
    h("nav", {}, h("a", { href: "/docs/", target: "_blank", rel: "noopener" }, icon("api"), "Documentação da API")),
    h("div", { class: "spacer" }),
    liveTag,
    menuHost,
  );
  const main = h("main", { class: "main", id: "conteudo" });
  const mobile = h(
    "div",
    { class: "mobile-bar" },
    logo(18),
    h("button", { class: "icon-btn", "aria-label": "Abrir menu", onclick: () => el.classList.toggle("nav-open") }, icon("menu")),
  );
  const el = h("div", { class: "shell" }, sidebar, h("div", { class: "main-col" }, mobile, main));
  navEl.addEventListener("click", () => el.classList.remove("nav-open"));

  const cartBadge = navEl.querySelector(".badge");
  const unsubCart = cart.subscribe(() => {
    if (!cartBadge) return;
    const n = cart.count();
    cartBadge.hidden = n === 0;
    cartBadge.textContent = n;
    cartBadge.style.animation = "none";
    void cartBadge.offsetWidth;
    cartBadge.style.animation = "";
  });

  stopStream = stream(
    "catalog",
    "/stock/stream",
    (event) => live.dispatchEvent(new CustomEvent("stock", { detail: event })),
    (on) => {
      liveTag.classList.toggle("on", on);
      liveTag.lastChild.textContent = on ? "Estoque em tempo real" : "Reconectando…";
    },
  );

  function setActive(path) {
    let active = null;
    navEl.querySelectorAll("a").forEach((a) => {
      const on = a.dataset.path === path;
      a.classList.toggle("active", on);
      if (on) active = a;
    });
    if (active) {
      thumb.style.opacity = "1";
      thumb.style.top = `${active.offsetTop}px`;
      thumb.style.height = `${active.offsetHeight}px`;
    } else thumb.style.opacity = "0";
  }

  return { el, main, setActive, destroy: () => (unsubCart(), stopStream?.()) };
}

async function route() {
  const path = currentPath();
  if (!session.user) {
    shell?.destroy();
    shell = null;
    cleanup?.();
    cleanup = null;
    if (path !== "/entrar") {
      sessionStorage.setItem("argo:after-login", path);
      location.hash = "/entrar";
      return;
    }
    clear(root, renderLogin(loginNotice, () => navigate(sessionStorage.getItem("argo:after-login") || "/")));
    loginNotice = null;
    return;
  }
  if (path === "/entrar") {
    navigate("/");
    return;
  }
  const match = ROUTES.map((r) => [r, r.path.exec(path)]).find(([, m]) => m);
  if (!shell) {
    shell = buildShell();
    clear(root, shell.el);
  }
  cleanup?.();
  cleanup = null;
  const view = h("div", { class: "page view" });
  clear(shell.main, view);
  window.scrollTo({ top: 0 });
  if (!match) {
    shell.setActive(null);
    view.append(h("div", { class: "wrap" }, h("h1", {}, "Página não encontrada"), h("p", { class: "muted" }, "Confira o endereço ou volte para a visão geral.")));
    return;
  }
  const [r, m] = match;
  shell.setActive(r.nav);
  if (!r.roles.includes(session.user.role)) {
    view.append(h("div", { class: "wrap" }, h("h1", {}, "Acesso restrito"), h("p", { class: "muted", style: { marginTop: "8px" } }, `Seu perfil (${ROLE[session.user.role]}) não tem acesso a esta tela.`)));
    return;
  }
  try {
    cleanup = (await r.render(view, ...m.slice(1))) || null;
  } catch (err) {
    if (err.status === 401) return;
    view.append(h("div", { class: "wrap" }, h("h1", {}, "Algo deu errado"), h("p", { class: "muted" }, err.message)));
  }
}

session.onChange((user, reason) => {
  if (user) return;
  cart.clear();
  loginNotice = {
    idle: "Sua sessão terminou após 20 minutos sem uso. Entre novamente.",
    expired: "Sua sessão expirou. Entre novamente.",
    logout: null,
  }[reason];
  if (reason === "logout") toast("Você saiu da sua conta.");
  if (location.hash === "#/entrar") route();
  else location.hash = "/entrar";
});

addEventListener("hashchange", route);
route();

