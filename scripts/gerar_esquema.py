"""Gera database/*.sql e docs/banco-de-dados.md a partir dos modelos do Django.

O SQL sai do próprio schema editor do Django (o mesmo que as migrações usam), então precisa
de um MySQL acessível só para montar o texto: nada é criado nem alterado no banco.

    docker compose up -d mysql
    ARGO_ESQUEMA_DATABASE_URL=mysql://argo:SENHA@localhost:3306/argo_identity python scripts/gerar_esquema.py
"""

import argparse
import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "backend"))

URL = os.environ.get("ARGO_ESQUEMA_DATABASE_URL", "mysql://argo:argo@localhost:3306/argo_identity")
os.environ.update(
    {
        "DJANGO_SETTINGS_MODULE": "argo.settings",
        "ARGO_SERVICE": "all",
        "ARGO_DATABASE_URL": URL,
        "ARGO_CATALOG_DATABASE_URL": URL,
        "ARGO_ORDERS_DATABASE_URL": URL,
    }
)

import django  # noqa: E402

django.setup()

from django.apps import apps  # noqa: E402
from django.db import connections, models  # noqa: E402

SERVICOS = [
    ("argo_identity", "Identidade", "identity", "default"),
    ("argo_catalog", "Catálogo e estoque", "catalog", "catalog"),
    ("argo_orders", "Pedidos", "orders", "orders"),
]
STACK = "Python · Django · Django REST Framework (migrações do Django)"
FLYWAY = RAIZ / "billing" / "src" / "main" / "resources" / "db" / "migration" / "V1__invoices.sql"


def bonito(sql: str) -> str:
    """Quebra o CREATE TABLE do Django em uma coluna por linha e tira as crases desnecessárias."""
    sql = re.sub(r"`([a-z_][a-z0-9_]*)`", r"\1", sql.strip().rstrip(";"))
    m = re.match(r"CREATE TABLE (\w+) \((.*)\)$", sql, re.S)
    if not m:
        return sql.rstrip(";") + ";"
    partes, nivel, atual = [], 0, ""
    for ch in m.group(2):
        if ch == "," and nivel == 0:
            partes.append(atual.strip())
            atual = ""
            continue
        nivel += ch == "("
        nivel -= ch == ")"
        atual += ch
    partes.append(atual.strip())
    return f"CREATE TABLE {m.group(1)} (\n" + ",\n".join(f"    {p}" for p in partes) + "\n);"


def ddl(app_label: str, alias: str) -> list[str]:
    connection = connections[alias]
    with connection.schema_editor(collect_sql=True, atomic=False) as editor:
        for model in apps.get_app_config(app_label).get_models():
            editor.create_model(model)
    return [bonito(s) for s in editor.collected_sql]


def tabelas(app_label: str, alias: str, sql: list[str]):
    connection = connections[alias]
    for model in apps.get_app_config(app_label).get_models():
        meta = model._meta
        colunas = []
        for campo in meta.local_fields:
            chaves = []
            if campo.primary_key:
                chaves.append("PK")
            if isinstance(campo, models.ForeignKey):
                alvo = campo.related_model._meta
                chaves.append(f"FK → {alvo.db_table}.{alvo.pk.column}")
            if campo.unique and not campo.primary_key:
                chaves.append("UNIQUE")
            tipo = campo.db_type(connection)
            if isinstance(campo, models.BigAutoField):
                tipo = "bigint AUTO_INCREMENT"
            colunas.append(
                {
                    "nome": campo.column,
                    "tipo": tipo,
                    "nulo": "sim" if campo.null else "não",
                    "chaves": ", ".join(chaves),
                }
            )
        create = next(s for s in sql if s.startswith(f"CREATE TABLE {meta.db_table} ("))
        restricoes = [
            f"{tipo} {nome}: {regra}"
            for nome, tipo, regra in re.findall(r"CONSTRAINT (\w+) (CHECK|UNIQUE) \((.*)\)", create)
        ]
        indices = [
            f"{i.name} ({', '.join(meta.get_field(f.lstrip('-')).column for f in i.fields)})"
            for i in sorted(meta.indexes, key=lambda i: i.name)
        ]
        yield meta.db_table, colunas, restricoes, indices


def tabelas_flyway():
    sql = FLYWAY.read_text(encoding="utf-8")
    for nome, corpo in re.findall(r"CREATE TABLE (\w+) \((.*?)\n\);", sql, re.S):
        colunas, restricoes = [], []
        pks, fks, uniques = set(), {}, set()
        for linha in [linha.strip().rstrip(",") for linha in corpo.strip().splitlines()]:
            if linha.startswith("CONSTRAINT"):
                if " PRIMARY KEY " in linha:
                    pks |= set(re.search(r"\((.*?)\)", linha).group(1).replace(" ", "").split(","))
                elif " FOREIGN KEY " in linha:
                    col, alvo, colalvo = re.search(r"FOREIGN KEY \((\w+)\) REFERENCES (\w+) \((\w+)\)", linha).groups()
                    fks[col] = f"FK → {alvo}.{colalvo}"
                elif " UNIQUE " in linha:
                    uniques.add(re.search(r"\((.*?)\)", linha).group(1))
                elif " CHECK " in linha:
                    restricoes.append("CHECK " + linha.split("CONSTRAINT ")[1].replace(" CHECK ", ": ", 1))
                continue
            partes = linha.split()
            nome_col, resto = partes[0], " ".join(partes[1:])
            tipo = re.split(r" NOT NULL| DEFAULT| AUTO_INCREMENT", resto)[0].strip()
            if "AUTO_INCREMENT" in resto:
                tipo += " AUTO_INCREMENT"
            colunas.append({"nome": nome_col, "tipo": tipo, "nulo": "não" if "NOT NULL" in resto else "sim"})
        for c in colunas:
            chaves = []
            if c["nome"] in pks:
                chaves.append("PK")
                c["nulo"] = "não"
            if c["nome"] in fks:
                chaves.append(fks[c["nome"]])
            if c["nome"] in uniques:
                chaves.append("UNIQUE")
            c["chaves"] = ", ".join(chaves)
        indices = [
            f"{n} ({c})" for n, t, c in re.findall(r"CREATE INDEX (\w+) ON (\w+) \((.*?)\);", sql) if t == nome
        ]
        yield nome, colunas, restricoes, indices


def markdown(grupos) -> str:
    linhas = [
        "# Argo · Banco de dados",
        "",
        "Gerado por `scripts/gerar_esquema.py` a partir dos modelos do Django e da migração Flyway do faturamento.",
        "Cada serviço tem o próprio banco no mesmo MySQL (database per service).",
        "Nenhum serviço lê o banco de outro: os dados de outros domínios chegam por HTTP ou pela fila e são guardados como cópia do momento.",
        "",
        "As tabelas dos serviços Python são criadas pelas migrações do Django (`python manage.py migrate`, que o comando",
        "`serve` roda sozinho ao subir). As do faturamento, pelo Flyway na partida do Spring Boot.",
        "Os bancos usam utf8mb4 com a collation utf8mb4_0900_ai_ci: comparações de texto não diferenciam maiúsculas nem acentos.",
        "",
    ]
    for banco, nome, stack, lista in grupos:
        linhas += [f"## {nome} · `{banco}`", "", f"_{stack}_", ""]
        for tabela, colunas, restricoes, indices in lista:
            linhas += [f"### `{tabela}`", "", "| Campo | Tipo | Nulo | Chaves |", "|---|---|---|---|"]
            linhas += [f"| `{c['nome']}` | {c['tipo']} | {c['nulo']} | {c['chaves']} |" for c in colunas]
            if restricoes or indices:
                linhas.append("")
            linhas += [f"- {r}" for r in restricoes]
            linhas += [f"- Índice {i}" for i in indices]
            linhas.append("")
    return "\n".join(linhas)


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera o SQL do MySQL e o guia do banco a partir dos modelos do Django.")
    parser.parse_args()
    destino = RAIZ / "database"
    grupos = []
    for banco, nome, app_label, alias in SERVICOS:
        sql = ddl(app_label, alias)
        cabecalho = (
            f"USE {banco};\n\n"
            "-- Gerado por scripts/gerar_esquema.py a partir dos modelos do Django.\n"
            "-- Na aplicação, quem cria estas tabelas são as migrações (python manage.py migrate).\n\n"
        )
        (destino / f"{banco}.sql").write_text(cabecalho + "\n\n".join(sql) + "\n", encoding="utf-8")
        grupos.append((banco, nome, STACK, list(tabelas(app_label, alias, sql))))
    (destino / "argo_billing.sql").write_text(
        "USE argo_billing;\n\n" + FLYWAY.read_text(encoding="utf-8"), encoding="utf-8"
    )
    grupos.append(("argo_billing", "Faturamento", "Java · Spring Boot · JPA · Flyway", list(tabelas_flyway())))
    (RAIZ / "docs" / "banco-de-dados.md").write_text(markdown(grupos), encoding="utf-8")
    print("Esquemas gerados em database/ e guia em docs/banco-de-dados.md")


if __name__ == "__main__":
    main()
