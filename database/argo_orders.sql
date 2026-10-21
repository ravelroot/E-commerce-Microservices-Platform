USE argo_orders;

-- Gerado por scripts/gerar_esquema.py a partir dos modelos do Django.
-- Na aplicação, quem cria estas tabelas são as migrações (python manage.py migrate).

CREATE TABLE orders (
    id bigint AUTO_INCREMENT NOT NULL PRIMARY KEY,
    customer_id varchar(36) NOT NULL,
    customer_name varchar(120) NOT NULL,
    customer_email varchar(160) NOT NULL,
    status varchar(12) NOT NULL,
    total_cents integer NOT NULL,
    items_count integer NOT NULL,
    rejection_reason varchar(300) NULL,
    invoice_number varchar(30) NULL,
    email_sent_at datetime(6) NULL,
    created_at datetime(6) NOT NULL,
    updated_at datetime(6) NOT NULL,
    CONSTRAINT ck_orders_status CHECK (status IN ('PENDING', 'CONFIRMED', 'REJECTED', 'SHIPPED', 'DELIVERED', 'CANCELED')),
    CONSTRAINT ck_orders_total CHECK (total_cents >= 0)
);

CREATE TABLE order_items (
    id bigint AUTO_INCREMENT NOT NULL PRIMARY KEY,
    order_id bigint NOT NULL,
    product_id varchar(36) NOT NULL,
    seller_id varchar(36) NOT NULL,
    seller_name varchar(120) NOT NULL,
    sku varchar(40) NOT NULL,
    product_name varchar(140) NOT NULL,
    unit_price_cents integer NOT NULL,
    quantity integer NOT NULL,
    subtotal_cents integer NOT NULL,
    CONSTRAINT ck_order_items_quantity CHECK (quantity > 0)
);

CREATE TABLE order_status_history (
    id bigint AUTO_INCREMENT NOT NULL PRIMARY KEY,
    order_id bigint NOT NULL,
    status varchar(12) NOT NULL,
    note varchar(300) NOT NULL,
    actor varchar(120) NOT NULL,
    created_at datetime(6) NOT NULL
);

CREATE INDEX ix_orders_customer_created ON orders (customer_id, created_at);

CREATE INDEX ix_orders_status ON orders (status);

ALTER TABLE order_items ADD CONSTRAINT order_items_order_id_412ad78b_fk_orders_id FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE;

CREATE INDEX ix_order_items_seller ON order_items (seller_id);

CREATE INDEX ix_order_items_order ON order_items (order_id);

ALTER TABLE order_status_history ADD CONSTRAINT order_status_history_order_id_d33fdfde_fk_orders_id FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE;

CREATE INDEX ix_order_status_history_order ON order_status_history (order_id);
