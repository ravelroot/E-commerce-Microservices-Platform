#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  echo "Instale o Docker (com Docker Compose) e rode de novo: https://docs.docker.com/get-docker/"
  exit 1
fi

if [ ! -f .env ]; then
  cp .env.example .env
  segredo() { head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 48; }
  sed -i.bak \
    -e "s|^ARGO_DB_PASSWORD=.*|ARGO_DB_PASSWORD=$(segredo)|" \
    -e "s|^ARGO_JWT_SECRET=.*|ARGO_JWT_SECRET=$(segredo)|" \
    -e "s|^ARGO_INTERNAL_TOKEN=.*|ARGO_INTERNAL_TOKEN=$(segredo)|" .env
  rm -f .env.bak
  echo "Arquivo .env criado com segredos aleatórios."
fi

docker compose up -d --build

valor() { grep -E "^$1=" .env | cut -d= -f2- ; }
porta=$(valor ARGO_PORT); porta=${porta:-8080}
mailpit=$(valor ARGO_MAILPIT_PORT); mailpit=${mailpit:-8025}
flower=$(valor ARGO_FLOWER_PORT); flower=${flower:-5555}
printf "Aguardando os serviços"
for _ in $(seq 1 120); do
  if curl -fsS "http://localhost:${porta}/api/billing/health" >/dev/null 2>&1 \
    && curl -fsS "http://localhost:${porta}/api/orders/health" >/dev/null 2>&1; then
    echo
    echo "Pronto!"
    echo "  Aplicação:         http://localhost:${porta}"
    echo "  Documentação API:  http://localhost:${porta}/docs/"
    echo "  E-mails (Mailpit): http://localhost:${mailpit}"
    echo "  Filas (Flower):    http://localhost:${flower}"
    echo "  Contas: admin@argo.dev, vendedor@argo.dev ou cliente@argo.dev, senha Argo@2026"
    echo "  Outros comandos:   make ajuda"
    if command -v xdg-open >/dev/null 2>&1; then xdg-open "http://localhost:${porta}" >/dev/null 2>&1 || true
    elif command -v open >/dev/null 2>&1; then open "http://localhost:${porta}" || true
    fi
    exit 0
  fi
  printf "."
  sleep 2
done
echo
echo "Os serviços ainda estão subindo. Acompanhe com: docker compose logs -f (ou make logs)"
