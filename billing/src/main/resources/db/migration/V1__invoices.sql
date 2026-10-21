-- Contador da numeração das notas. O MySQL não tem SEQUENCE: a linha única é travada
-- (SELECT ... FOR UPDATE) na mesma transação que grava a nota, então a numeração não pula.
CREATE TABLE invoice_number_seq (
    id       TINYINT NOT NULL,
    next_val BIGINT  NOT NULL,
    CONSTRAINT pk_invoice_number_seq PRIMARY KEY (id),
    CONSTRAINT ck_invoice_number_seq_single CHECK (id = 1)
);

INSERT INTO invoice_number_seq (id, next_val) VALUES (1, 1);

CREATE TABLE invoices (
    id            BIGINT       NOT NULL AUTO_INCREMENT,
    number        VARCHAR(30)  NOT NULL,
    order_id      BIGINT       NOT NULL,
    order_code    VARCHAR(20)  NOT NULL,
    customer_id   VARCHAR(36)  NOT NULL,
    customer_name VARCHAR(120) NOT NULL,
    status        VARCHAR(10)  NOT NULL DEFAULT 'ISSUED',
    total_cents   BIGINT       NOT NULL,
    tax_cents     BIGINT       NOT NULL,
    tax_rate      DECIMAL(5,4) NOT NULL,
    issued_at     DATETIME(6)  NOT NULL,
    canceled_at   DATETIME(6),
    CONSTRAINT pk_invoices PRIMARY KEY (id),
    CONSTRAINT uq_invoices_number UNIQUE (number),
    CONSTRAINT uq_invoices_order UNIQUE (order_id),
    CONSTRAINT ck_invoices_status CHECK (status IN ('ISSUED', 'CANCELED')),
    CONSTRAINT ck_invoices_total CHECK (total_cents >= 0 AND tax_cents >= 0)
);

CREATE INDEX ix_invoices_customer ON invoices (customer_id);

CREATE TABLE invoice_items (
    id               BIGINT       NOT NULL AUTO_INCREMENT,
    invoice_id       BIGINT       NOT NULL,
    product_id       VARCHAR(36)  NOT NULL,
    seller_id        VARCHAR(36)  NOT NULL,
    description      VARCHAR(140) NOT NULL,
    quantity         INTEGER      NOT NULL,
    unit_price_cents BIGINT       NOT NULL,
    total_cents      BIGINT       NOT NULL,
    CONSTRAINT pk_invoice_items PRIMARY KEY (id),
    CONSTRAINT fk_invoice_items_invoice FOREIGN KEY (invoice_id) REFERENCES invoices (id) ON DELETE CASCADE,
    CONSTRAINT ck_invoice_items_quantity CHECK (quantity > 0)
);

CREATE INDEX ix_invoice_items_invoice ON invoice_items (invoice_id);
CREATE INDEX ix_invoice_items_seller ON invoice_items (seller_id);
