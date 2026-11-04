import { endSession, restoreSession, session, stream } from "./api.js";
import { live } from "./bus.js";
import { cart } from "./cart.js";
import { openPalette, openShortcuts } from "./palette.js";
import { clear, h, icon, initials, logo, paletteOptions, ROLE, toast } from "./ui.js";
import { renderLogin } from "./pages/login.js";
import { renderOverview } from "./pages/overview.js";
import { renderStore } from "./pages/store.js";
import { renderOrders, renderOrder } from "./pages/orders.js";
import { renderProducts, renderProductForm } from "./pages/products.js";
import { renderLive } from "./pages/live.js";
import { renderInvoices, renderInvoice } from "./pages/invoices.js";
import { renderUsers } from "./pages/users.js";
import { renderAccount } from "./pages/account.js";
import { renderSystem } from "./pages/system.js";

const MOD_K = /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘ K" : "Ctrl K";
const ALL = ["ADMIN", "SELLER", "CUSTOMER"];
const STAFF = ["ADMIN", "SELLER"];

const ROUTES = [
  { path: /^\/$/, render: renderOverview, roles: ALL, nav: "/", title: "Visão geral" },
  { path: /^\/loja$/, render: renderStore, roles: ALL, nav: "/loja", title: "Loja" },
  { path: /^\/pedidos$/, render: renderOrders, roles: ALL, nav: "/pedidos", title: "Pedidos" },
  { path: /^\/pedidos\/(\d+)$/, render: renderOrder, roles: ALL, nav: "/pedidos", title: "Pedido" },
  { path: /^\/produtos$/, render: renderProducts, roles: STAFF, nav: "/produtos", title: "Produtos" },
  { path: /^\/produtos\/novo$/, render: renderProductForm, roles: STAFF, nav: "/produtos", title: "Novo produto" },
  { path: /^\/produtos\/([\w-]+)$/, render: renderProductForm, roles: STAFF, nav: "/produtos", title: "Produto" },
  { path: /^\/estoque$/, render: renderLive, roles: STAFF, nav: "/estoque", title: "Estoque ao vivo" },
  { path: /^\/notas$/, render: renderInvoices, roles: ALL, nav: "/notas", title: "Notas fiscais" },
  { path: /^\/notas\/([\w-]+)$/, render: renderInvoice, roles: ALL, nav: "/notas", title: "Nota fiscal" },
  { path: /^\/usuarios$/, render: renderUsers, roles: ["ADMIN"], nav: "/usuarios", title: "Usuários" },
  { path: /^\/sistema$/, render: renderSystem, roles: ["ADMIN"], nav: "/sistema", title: "Sistema" },
  { path: /^\/conta$/, render: renderAccount, roles: ALL, nav: null, title: "Minha conta" },
];

const NAV = [
  ["/", "Visão geral", "overview", ALL, "v"],
  ["/loja", "Loja", "store", ALL, "l"],
  ["/pedidos", "Pedidos", "orders", ALL, "p"],
  ["/produtos", "Produtos", "products", STAFF, "r"],
  ["/estoque", "Estoque ao vivo", "live", STAFF, "e"],
  ["/notas", "Notas fiscais", "invoice", ALL, "n"],
  ["/usuarios", "Usuários", "users", ["ADMIN"], "u"],
  ["/sistema", "Sistema", "server", ["ADMIN"], "s"],
];

const root = document.getElementById("app");
let shell = null;
let cleanup = null;
let stopStream = null;
let loginNotice = null;
let booted = false;

export function navigate(path) {
  if (location.hash === `#${path}`) route();
  else location.hash = path;
}

function currentPath() {
  return (location.hash.replace(/^#/, "") || "/").split("?")[0] || "/";
}

function themeLabel() {
  return window.argoTheme?.current() === "dark" ? ["Tema claro", "sun"] : ["Tema escuro", "moon"];
}

function commands() {
  const role = session.user.role;
  const items = NAV.filter(([, , , roles]) => roles.includes(role)).map(([path, label, ic]) => ({
    label,
    group: "Ir para",
    icon: ic,
    keywords: path,
    run: () => navigate(path),
  }));
  items.push({ label: "Minha conta", group: "Ir para", icon: "key", keywords: "senha sessões perfil", run: () => navigate("/conta") });
  if (role !== "CUSTOMER") items.push({ label: "Novo produto", group: "Ação", icon: "plus", keywords: "cadastrar", run: () => navigate("/produtos/novo") });
  items.push(
    { label: "Alternar tema claro e escuro", group: "Ação", icon: "moon", keywords: "dark escuro claro", run: () => window.argoTheme?.toggle() },
    { label: "Trocar a paleta de cores", group: "Ação", icon: "sun", keywords: "cores paleta aparência", run: () => window.argoTheme?.nextPalette() },
    { label: "Documentação da API", group: "Ação", icon: "api", keywords: "swagger openapi", run: () => window.open("/docs/", "_blank", "noopener") },
    { label: "Atalhos de teclado", group: "Ajuda", icon: "command", keywords: "teclado ajuda", run: openShortcuts },
    { label: "Sair", group: "Conta", icon: "logout", keywords: "logout", run: () => endSession("logout") },
  );
  return items;
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
  const liveTag = h("span", { class: "live", role: "status" }, h("span", { class: "dot" }), "Conectando ao estoque…");
  const menuHost = h("div", { class: "user-menu" });
  const trigger = h(
    "button",
    { class: "user-trigger", "aria-expanded": "false", "aria-haspopup": "menu", onclick: () => toggleMenu() },
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
    const [themeText, themeIcon] = themeLabel();
    const menu = h(
      "div",
      { class: "menu", role: "menu" },
      h("div", { class: "menu-head" }, h("span", { class: "strong" }, user.name), h("span", { class: "muted small" }, user.email)),
      paletteOptions(),
      h("a", { href: "#/conta", role: "menuitem", onclick: () => toggleMenu(false) }, icon("key", 16), "Minha conta"),
      h("button", { role: "menuitem", onclick: () => (toggleMenu(false), window.argoTheme?.toggle()) }, icon(themeIcon, 16), themeText),
      h("button", { role: "menuitem", onclick: () => (toggleMenu(false), openPalette(commands())) }, icon("command", 16), "Busca rápida", h("span", { class: "spacer" }), h("span", { class: "kbd" }, MOD_K)),
      h("button", { role: "menuitem", onclick: () => endSession("logout") }, icon("logout", 16), "Sair"),
    );
    menuHost.prepend(menu);
    menu.querySelector("a, button")?.focus();
    setTimeout(() => document.addEventListener("click", function off(e) {
      if (!menuHost.contains(e.target)) {
        toggleMenu(false);
        document.removeEventListener("click", off);
      }
    }), 0);
  }
  menuHost.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && trigger.getAttribute("aria-expanded") === "true") {
      toggleMenu(false);
      trigger.focus();
    }
  });

  const sidebar = h(
    "aside",
    { class: "sidebar" },
    h("a", { class: "brand", href: "#/" }, logo(20)),
    h("span", { class: "sidebar-tag" }, "Plataforma de pedidos"),
    navEl,
    h("hr"),
    h(
      "nav",
      { "aria-label": "Ferramentas" },
      h("a", { href: "/docs/", target: "_blank", rel: "noopener" }, icon("api"), "Documentação da API"),
      h("a", { href: "#", onclick: (e) => (e.preventDefault(), openPalette(commands())) }, icon("search"), "Busca rápida", h("span", { class: "kbd", style: { marginLeft: "auto" } }, MOD_K)),
    ),
    h("div", { class: "spacer" }),
    liveTag,
    menuHost,
  );
  const main = h("main", { class: "main", id: "conteudo", tabindex: "-1" });
  const mobile = h(
    "div",
    { class: "mobile-bar" },
    logo(18),
    h(
      "div",
      { class: "row", style: { gap: "4px" } },
      h("button", { class: "icon-btn", "aria-label": "Busca rápida", onclick: () => openPalette(commands()) }, icon("search")),
      h("button", { class: "icon-btn", "aria-label": "Abrir menu", onclick: () => el.classList.toggle("nav-open") }, icon("menu")),
    ),
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
      if (on) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
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

function teardownShell() {
  shell?.destroy();
  shell = null;
  cleanup?.();
  cleanup = null;
}

function problem(view, title, text, retry) {
  view.append(
    h(
      "div",
      { class: "wrap" },
      h("h1", {}, title),
      h("p", { class: "muted", style: { marginTop: "8px" } }, text),
      retry ? h("div", { class: "row", style: { marginTop: "16px" } }, h("button", { class: "btn", onclick: retry }, icon("refresh", 16), "Tentar de novo"), h("a", { class: "btn ghost", href: "#/" }, "Visão geral")) : null,
    ),
  );
}

async function route() {
  if (!booted) return;
  const path = currentPath();
  if (!session.user) {
    teardownShell();
    if (path !== "/entrar") {
      sessionStorage.setItem("argo:after-login", location.hash.replace(/^#/, "") || "/");
      location.hash = "/entrar";
      return;
    }
    document.title = "Entrar · Argo";
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
    document.title = "Página não encontrada · Argo";
    problem(view, "Página não encontrada", "Confira o endereço ou volte para a visão geral.");
    return;
  }
  const [r, m] = match;
  shell.setActive(r.nav);
  document.title = `${r.title} · Argo`;
  if (!r.roles.includes(session.user.role)) {
    problem(view, "Acesso restrito", `Seu perfil (${ROLE[session.user.role]}) não tem acesso a esta tela.`);
    return;
  }
  try {
    cleanup = (await r.render(view, ...m.slice(1))) || null;
  } catch (err) {
    if (err.status === 401) return;
    clear(view);
    const text = err.status === 404 ? "Este item não existe ou você não tem acesso a ele." : err.message;
    problem(view, err.status === 404 ? "Não encontrado" : "Algo deu errado", text, () => route());
  }
}

session.onChange((user, reason) => {
  if (user) {
    if (reason === "login" || reason === "restore") cart.load(user.id);
    if (reason === "update" && shell) {
      teardownShell();
      route();
    }
    return;
  }
  cart.forget();
  loginNotice = {
    idle: "Sua sessão terminou após 20 minutos sem uso. Entre novamente.",
    expired: "Sua sessão expirou. Entre novamente.",
    logout: null,
  }[reason];
  if (reason === "logout") toast("Você saiu da sua conta.");
  if (location.hash === "#/entrar") route();
  else location.hash = "/entrar";
});

let pendingG = 0;
addEventListener("keydown", (e) => {
  if (!session.user || !shell) return;
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) || e.target.isContentEditable;
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    if (!document.querySelector(".palette")) openPalette(commands());
    return;
  }
  if (typing || e.ctrlKey || e.metaKey || e.altKey || document.querySelector(".overlay")) return;
  if (e.key === "/") {
    const search = shell.main.querySelector("input[type=search]");
    if (search) {
      e.preventDefault();
      search.focus();
      search.select();
    }
  } else if (e.key === "?") {
    openShortcuts();
  } else if (e.key.toLowerCase() === "t") {
    window.argoTheme?.toggle();
  } else if (e.key.toLowerCase() === "p" && Date.now() - pendingG >= 1200) {
    window.argoTheme?.nextPalette();
  } else if (e.key.toLowerCase() === "g") {
    pendingG = Date.now();
  } else if (Date.now() - pendingG < 1200) {
    const key = e.key.toLowerCase();
    pendingG = 0;
    if (key === "c") navigate("/conta");
    else {
      const target = NAV.find((n) => n[4] === key && n[3].includes(session.user.role));
      if (target) navigate(target[0]);
    }
  }
});

let offlineBanner = null;
function connectivity() {
  if (navigator.onLine) {
    if (offlineBanner) {
      offlineBanner.remove();
      offlineBanner = null;
      toast("Conexão restabelecida.");
    }
    return;
  }
  if (!offlineBanner) {
    offlineBanner = h("div", { class: "banner", role: "status" }, h("span", { class: "dot" }), "Sem internet. As alterações voltam a funcionar quando a conexão voltar.");
    document.body.prepend(offlineBanner);
  }
}
addEventListener("online", connectivity);
addEventListener("offline", connectivity);
addEventListener("hashchange", route);

(async function boot() {
  root.replaceChildren(h("div", { class: "login" }, h("span", { class: "spinner", "aria-label": "Carregando" })));
  await restoreSession();
  booted = true;
  connectivity();
  route();
})();
