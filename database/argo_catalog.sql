USE argo_catalog;

-- Gerado por scripts/gerar_esquema.py a partir dos modelos do Django.
-- Na aplicação, quem cria estas tabelas são as migrações (python manage.py migrate).

CREATE TABLE products (
    id varchar(36) NOT NULL PRIMARY KEY,
    seller_id varchar(36) NOT NULL,
    seller_name varchar(120) NOT NULL,
    sku varchar(40) NOT NULL UNIQUE,
    name varchar(140) NOT NULL,
    description longtext NOT NULL,
    category varchar(60) NOT NULL,
    price_cents integer NOT NULL,
    stock integer NOT NULL,
    low_stock_threshold integer NOT NULL,
    active bool NOT NULL,
    version integer NOT NULL,
    created_at datetime(6) NOT NULL,
    updated_at datetime(6) NOT NULL,
    CONSTRAINT ck_products_stock_non_negative CHECK (stock >= 0),
    CONSTRAINT ck_products_price_positive CHECK (price_cents > 0)
);

CREATE TABLE stock_movements (
    id bigint AUTO_INCREMENT NOT NULL PRIMARY KEY,
    product_id varchar(36) NOT NULL,
    kind varchar(10) NOT NULL,
    delta integer NOT NULL,
    stock_after integer NOT NULL,
    reason varchar(200) NOT NULL,
    order_id bigint NULL,
    actor_id varchar(36) NULL,
    created_at datetime(6) NOT NULL,
    CONSTRAINT ck_stock_movements_kind CHECK (kind IN ('IN', 'OUT', 'COUNT', 'SALE', 'RELEASE')),
    CONSTRAINT uq_stock_movements_order_product_kind UNIQUE (order_id, product_id, kind)
);

CREATE INDEX ix_products_seller ON products (seller_id);

CREATE INDEX ix_products_category ON products (category);

ALTER TABLE stock_movements ADD CONSTRAINT stock_movements_product_id_5bacd6d9_fk_products_id FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE;

CREATE INDEX ix_movements_product_created ON stock_movements (product_id, created_at);
