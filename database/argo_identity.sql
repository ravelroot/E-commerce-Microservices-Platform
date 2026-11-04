USE argo_identity;

CREATE TABLE users (
    id varchar(36) NOT NULL PRIMARY KEY,
    name varchar(120) NOT NULL,
    email varchar(160) NOT NULL UNIQUE,
    password_hash varchar(128) NOT NULL,
    role varchar(12) NOT NULL,
    active bool NOT NULL,
    failed_attempts integer NOT NULL,
    locked_until datetime(6) NULL,
    last_login_at datetime(6) NULL,
    created_at datetime(6) NOT NULL,
    updated_at datetime(6) NOT NULL,
    CONSTRAINT ck_users_role CHECK (role IN ('ADMIN', 'SELLER', 'CUSTOMER'))
);

CREATE TABLE refresh_tokens (
    id varchar(36) NOT NULL PRIMARY KEY,
    user_id varchar(36) NOT NULL,
    family_id varchar(36) NOT NULL,
    token_hash varchar(64) NOT NULL UNIQUE,
    created_at datetime(6) NOT NULL,
    expires_at datetime(6) NOT NULL,
    revoked_at datetime(6) NULL,
    replaced_by varchar(36) NULL,
    user_agent varchar(200) NOT NULL,
    ip_address varchar(45) NULL,
    session_started_at datetime(6) NULL
);

ALTER TABLE refresh_tokens ADD CONSTRAINT refresh_tokens_user_id_b02a6331_fk_users_id FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE;

CREATE INDEX ix_refresh_tokens_family ON refresh_tokens (family_id);

CREATE INDEX ix_refresh_tokens_user_id ON refresh_tokens (user_id);

CREATE INDEX ix_refresh_tokens_expires ON refresh_tokens (expires_at);
