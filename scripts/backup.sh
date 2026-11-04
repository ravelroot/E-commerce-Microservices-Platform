#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "Arquivo .env não encontrado. Rode ./iniciar.sh primeiro."
  exit 1
fi
usuario=$(grep -E '^ARGO_DB_USER=' .env | cut -d= -f2-)
senha=$(grep -E '^ARGO_DB_PASSWORD=' .env | cut -d= -f2-)
usuario=${usuario:-argo}
destino=${ARGO_BACKUP_DIR:-backups}
mkdir -p "$destino"
arquivo="$destino/argo-$(date +%Y%m%d-%H%M%S).sql.gz"

docker compose exec -T -e MYSQL_PWD="$senha" mysql mysqldump -u "$usuario" \
  --single-transaction --no-tablespaces --set-gtid-purged=OFF --routines --triggers \
  --databases argo_identity argo_catalog argo_orders argo_billing | gzip > "$arquivo"

echo "Backup salvo em $arquivo ($(du -h "$arquivo" | cut -f1))."
