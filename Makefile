SHELL := /bin/bash
COMPOSE := docker compose
SERVICOS_DJANGO := identity catalog orders

.DEFAULT_GOAL := ajuda
.PHONY: ajuda subir parar reiniciar logs situacao saude testes testes-java lint diagnostico admin recuperar limpar-sessoes backup restaurar esquema atualizar zerar

ajuda:
	@printf "%s\n" \
	"Argo · comandos (make <comando>)" \
	"" \
	"  subir            sobe os contêineres (cria o .env na primeira vez)" \
	"  parar            para os contêineres, mantendo os dados" \
	"  reiniciar        reinicia os contêineres" \
	"  logs             acompanha os logs (S=orders para um serviço só)" \
	"  situacao         lista os contêineres e o estado de saúde" \
	"  saude            consulta /health de cada serviço pelo gateway" \
	"  testes           roda a suíte Python (pytest)" \
	"  testes-java      roda a suíte Java (Maven)" \
	"  lint             confere o código Python (ruff) e a sintaxe do JavaScript" \
	"  diagnostico      roda o manage.py doctor em cada serviço" \
	"  admin            cria ou promove um Administrador (pergunta e-mail e senha)" \
	"  recuperar        põe na fila de novo pedidos parados ou sem nota" \
	"  limpar-sessoes   apaga refresh tokens antigos" \
	"  backup           gera backups/argo-<data>.sql.gz com os quatro bancos" \
	"  restaurar        restaura um backup (ARQUIVO=backups/argo-....sql.gz)" \
	"  esquema          gera database/*.sql e docs/banco-de-dados.md" \
	"  atualizar        git pull, reconstrói as imagens e sobe de novo" \
	"  zerar            apaga contêineres e volumes (pede confirmação)"

subir:
	@./iniciar.sh

parar:
	$(COMPOSE) stop

reiniciar:
	$(COMPOSE) restart

logs:
	$(COMPOSE) logs -f --tail 200 $(S)

situacao:
	$(COMPOSE) ps

saude:
	@porta=$$(grep -E '^ARGO_PORT=' .env 2>/dev/null | cut -d= -f2); porta=$${porta:-8080}; \
	for s in identity catalog orders billing; do \
	  printf "%-10s " "$$s"; curl -fsS "http://localhost:$$porta/api/$$s/health" || printf "fora do ar"; echo; \
	done

testes:
	cd backend && python -m pytest

testes-java:
	cd billing && mvn -B verify

lint:
	cd backend && ruff check .
	@for f in $$(find web/js -name '*.js'); do node --check "$$f" || exit 1; done; echo "JavaScript ok"

diagnostico:
	@for s in $(SERVICOS_DJANGO); do echo "== $$s"; $(COMPOSE) exec -T $$s python manage.py doctor; done

admin:
	$(COMPOSE) exec identity python manage.py create_admin

recuperar:
	$(COMPOSE) exec orders python manage.py recover_orders

limpar-sessoes:
	$(COMPOSE) exec identity python manage.py cleanup_tokens

backup:
	@bash scripts/backup.sh

restaurar:
	@bash scripts/restaurar.sh "$(ARQUIVO)"

esquema:
	python scripts/gerar_esquema.py

atualizar:
	git pull --ff-only
	$(COMPOSE) up -d --build

zerar:
	@read -r -p "Isso apaga TODOS os dados (pedidos, usuários, notas). Digite ZERAR para confirmar: " r; \
	[ "$$r" = "ZERAR" ] && $(COMPOSE) down -v || echo "Nada foi apagado."
