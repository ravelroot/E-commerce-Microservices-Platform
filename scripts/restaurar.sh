#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

arquivo=${1:-}
if [ -z "$arquivo" ] || [ ! -f "$arquivo" ]; then
  echo "Uso: ./scripts/restaurar.sh backups/argo-AAAAMMDD-HHMMSS.sql.gz"
  ls -1t backups/*.sql* 2>/dev/null | head -5 | sed 's/^/  /'
  exit 1
fi
usuario=$(grep -E '^ARGO_DB_USER=' .env | cut -d= -f2-)
senha=$(grep -E '^ARGO_DB_PASSWORD=' .env | cut -d= -f2-)
usuario=${usuario:-argo}

read -r -p "Restaurar $arquivo substitui os dados atuais. Digite RESTAURAR para continuar: " resposta
if [ "$resposta" != "RESTAURAR" ]; then
  echo "Nada foi alterado."
  exit 0
fi

docker compose stop worker scheduler identity catalog orders billing >/dev/null
case "$arquivo" in
  *.gz) gunzip -c "$arquivo" ;;
  *) cat "$arquivo" ;;
esac | docker compose exec -T -e MYSQL_PWD="$senha" mysql mysql -u "$usuario"
docker compose up -d >/dev/null
echo "Backup restaurado. Os serviços estão subindo de novo."
