# Argo · Banco de dados

Gerado por `scripts/gerar_esquema.py` a partir dos modelos do Django e da migração Flyway do faturamento.
Cada serviço tem o próprio banco no mesmo MySQL (database per service).
Nenhum serviço lê o banco de outro: os dados de outros domínios chegam por HTTP ou pela fila e são guardados como cópia do momento.

As tabelas dos serviços Python são criadas pelas migrações do Django (`python manage.py migrate`, que o comando
`serve` roda sozinho ao subir). As do faturamento, pelo Flyway na partida do Spring Boot.
Os bancos usam utf8mb4 com a collation utf8mb4_0900_ai_ci: comparações de texto não diferenciam maiúsculas nem acentos.

## Identidade · `argo_identity`

_Python · Django · Django REST Framework (migrações do Django)_

### `users`

| Campo | Tipo | Nulo | Chaves |
|---|---|---|---|
| `id` | varchar(36) | não | PK |
| `name` | varchar(120) | não |  |
| `email` | varchar(160) | não | UNIQUE |
| `password_hash` | varchar(128) | não |  |
| `role` | varchar(12) | não |  |
| `active` | bool | não |  |
| `failed_attempts` | integer | não |  |
| `locked_until` | datetime(6) | sim |  |
| `last_login_at` | datetime(6) | sim |  |
| `created_at` | datetime(6) | não |  |
| `updated_at` | datetime(6) | não |  |

- CHECK ck_users_role: role IN ('ADMIN', 'SELLER', 'CUSTOMER')

### `refresh_tokens`

| Campo | Tipo | Nulo | Chaves |
|---|---|---|---|
| `id` | varchar(36) | não | PK |
| `user_id` | varchar(36) | não | FK → users.id |
| `family_id` | varchar(36) | não |  |
| `token_hash` | varchar(64) | não | UNIQUE |
| `created_at` | datetime(6) | não |  |
| `expires_at` | datetime(6) | não |  |
| `revoked_at` | datetime(6) | sim |  |
| `replaced_by` | varchar(36) | sim |  |

- Índice ix_refresh_tokens_family (family_id)
- Índice ix_refresh_tokens_user_id (user_id)

## Catálogo e estoque · `argo_catalog`

_Python · Django · Django REST Framework (migrações do Django)_

### `products`

| Campo | Tipo | Nulo | Chaves |
|---|---|---|---|
| `id` | varchar(36) | não | PK |
| `seller_id` | varchar(36) | não |  |
| `seller_name` | varchar(120) | não |  |
| `sku` | varchar(40) | não | UNIQUE |
| `name` | varchar(140) | não |  |
| `description` | longtext | não |  |
| `category` | varchar(60) | não |  |
| `price_cents` | integer | não |  |
| `stock` | integer | não |  |
| `low_stock_threshold` | integer | não |  |
| `active` | bool | não |  |
| `version` | integer | não |  |
| `created_at` | datetime(6) | não |  |
| `updated_at` | datetime(6) | não |  |

- CHECK ck_products_stock_non_negative: stock >= 0
- CHECK ck_products_price_positive: price_cents > 0
- Índice ix_products_category (category)
- Índice ix_products_seller (seller_id)

### `stock_movements`

| Campo | Tipo | Nulo | Chaves |
|---|---|---|---|
| `id` | bigint AUTO_INCREMENT | não | PK |
| `product_id` | varchar(36) | não | FK → products.id |
| `kind` | varchar(10) | não |  |
| `delta` | integer | não |  |
| `stock_after` | integer | não |  |
| `reason` | varchar(200) | não |  |
| `order_id` | bigint | sim |  |
| `actor_id` | varchar(36) | sim |  |
| `created_at` | datetime(6) | não |  |

- CHECK ck_stock_movements_kind: kind IN ('IN', 'OUT', 'COUNT', 'SALE', 'RELEASE')
- UNIQUE uq_stock_movements_order_product_kind: order_id, product_id, kind
- Índice ix_movements_product_created (product_id, created_at)

## Pedidos · `argo_orders`

_Python · Django · Django REST Framework (migrações do Django)_

### `orders`

| Campo | Tipo | Nulo | Chaves |
|---|---|---|---|
| `id` | bigint AUTO_INCREMENT | não | PK |
| `customer_id` | varchar(36) | não |  |
| `customer_name` | varchar(120) | não |  |
| `customer_email` | varchar(160) | não |  |
| `status` | varchar(12) | não |  |
| `total_cents` | bigint | não |  |
| `items_count` | integer | não |  |
| `rejection_reason` | varchar(300) | sim |  |
| `invoice_number` | varchar(30) | sim |  |
| `email_sent_at` | datetime(6) | sim |  |
| `created_at` | datetime(6) | não |  |
| `updated_at` | datetime(6) | não |  |

- CHECK ck_orders_status: status IN ('PENDING', 'CONFIRMED', 'REJECTED', 'SHIPPED', 'DELIVERED', 'CANCELED')
- CHECK ck_orders_total: total_cents >= 0
- Índice ix_orders_created (created_at)
- Índice ix_orders_customer_created (customer_id, created_at)
- Índice ix_orders_status (status)

### `order_items`

| Campo | Tipo | Nulo | Chaves |
|---|---|---|---|
| `id` | bigint AUTO_INCREMENT | não | PK |
| `order_id` | bigint | não | FK → orders.id |
| `product_id` | varchar(36) | não |  |
| `seller_id` | varchar(36) | não |  |
| `seller_name` | varchar(120) | não |  |
| `sku` | varchar(40) | não |  |
| `product_name` | varchar(140) | não |  |
| `unit_price_cents` | integer | não |  |
| `quantity` | integer | não |  |
| `subtotal_cents` | bigint | não |  |

- CHECK ck_order_items_quantity: quantity > 0
- Índice ix_order_items_order (order_id)
- Índice ix_order_items_seller (seller_id)

### `order_status_history`

| Campo | Tipo | Nulo | Chaves |
|---|---|---|---|
| `id` | bigint AUTO_INCREMENT | não | PK |
| `order_id` | bigint | não | FK → orders.id |
| `status` | varchar(12) | não |  |
| `note` | varchar(300) | não |  |
| `actor` | varchar(120) | não |  |
| `created_at` | datetime(6) | não |  |

- Índice ix_order_status_history_order (order_id)

## Faturamento · `argo_billing`

_Java · Spring Boot · JPA · Flyway_

### `invoice_number_seq`

| Campo | Tipo | Nulo | Chaves |
|---|---|---|---|
| `id` | TINYINT | não | PK |
| `next_val` | BIGINT | não |  |

- CHECK ck_invoice_number_seq_single: (id = 1)

### `invoices`

| Campo | Tipo | Nulo | Chaves |
|---|---|---|---|
| `id` | BIGINT AUTO_INCREMENT | não | PK |
| `number` | VARCHAR(30) | não | UNIQUE |
| `order_id` | BIGINT | não | UNIQUE |
| `order_code` | VARCHAR(20) | não |  |
| `customer_id` | VARCHAR(36) | não |  |
| `customer_name` | VARCHAR(120) | não |  |
| `status` | VARCHAR(10) | não |  |
| `total_cents` | BIGINT | não |  |
| `tax_cents` | BIGINT | não |  |
| `tax_rate` | DECIMAL(5,4) | não |  |
| `issued_at` | DATETIME(6) | não |  |
| `canceled_at` | DATETIME(6) | sim |  |

- CHECK ck_invoices_status: (status IN ('ISSUED', 'CANCELED'))
- CHECK ck_invoices_total: (total_cents >= 0 AND tax_cents >= 0)
- Índice ix_invoices_customer (customer_id)

### `invoice_items`

| Campo | Tipo | Nulo | Chaves |
|---|---|---|---|
| `id` | BIGINT AUTO_INCREMENT | não | PK |
| `invoice_id` | BIGINT | não | FK → invoices.id |
| `product_id` | VARCHAR(36) | não |  |
| `seller_id` | VARCHAR(36) | não |  |
| `description` | VARCHAR(140) | não |  |
| `quantity` | INTEGER | não |  |
| `unit_price_cents` | BIGINT | não |  |
| `total_cents` | BIGINT | não |  |

- CHECK ck_invoice_items_quantity: (quantity > 0)
- Índice ix_invoice_items_invoice (invoice_id)
- Índice ix_invoice_items_seller (seller_id)
