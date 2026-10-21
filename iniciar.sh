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

porta=$(grep -E '^ARGO_PORT=' .env | cut -d= -f2)
porta=${porta:-8080}
printf "Aguardando os serviços"
for _ in $(seq 1 90); do
  if curl -fsS "http://localhost:${porta}/api/billing/health" >/dev/null 2>&1; then
    echo
    echo "Pronto!"
    echo "  Aplicação:        http://localhost:${porta}"
    echo "  Documentação API: http://localhost:${porta}/docs/"
    echo "  E-mails (Mailpit): http://localhost:8025"
    echo "  Filas (Flower):    http://localhost:5555"
    echo "  Contas: admin@argo.dev, vendedor@argo.dev ou cliente@argo.dev, senha Argo@2026"
    exit 0
  fi
  printf "."
  sleep 2
done
echo
echo "Os serviços ainda estão subindo. Acompanhe com: docker compose logs -f"
