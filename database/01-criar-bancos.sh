#!/bin/bash
for banco in argo_identity argo_catalog argo_orders argo_billing; do
  mysql --protocol=socket -uroot -p"${MYSQL_ROOT_PASSWORD}" <<SQL
CREATE DATABASE IF NOT EXISTS \`${banco}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
GRANT ALL PRIVILEGES ON \`${banco}\`.* TO '${MYSQL_USER}'@'%';
SQL
done
