const select = document.getElementById("spec");
const fromHash = new URLSearchParams(location.search).get("servico");
if (fromHash) select.value = `/api/${fromHash}/openapi.json`;
function load() {
  window.ui = SwaggerUIBundle({
    url: select.value,
    dom_id: "#swagger",
    deepLinking: false,
    persistAuthorization: true,
    displayRequestDuration: true,
    docExpansion: "list",
    defaultModelsExpandDepth: 0,
    filter: true,
  });
  history.replaceState(null, "", "?servico=" + select.value.split("/")[2]);
}
select.addEventListener("change", load);
load();
