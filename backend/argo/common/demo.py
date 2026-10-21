import uuid

DEMO_PASSWORD = "Argo@2026"
_NS = uuid.UUID("6f1c2a52-3d1e-4c55-9a1b-0000f0000000")


def demo_id(key: str) -> str:
    return str(uuid.uuid5(_NS, key))


DEMO_USERS = [
    {"key": "admin", "name": "Administração Argo", "email": "admin@argo.dev", "role": "ADMIN"},
    {"key": "vendedor", "name": "Loja Aurora", "email": "vendedor@argo.dev", "role": "SELLER"},
    {"key": "vendedor2", "name": "Ateliê Norte", "email": "atelie@argo.dev", "role": "SELLER"},
    {"key": "cliente", "name": "Cliente Demonstração", "email": "cliente@argo.dev", "role": "CUSTOMER"},
    {"key": "c1", "name": "Bruna Teixeira", "email": "bruna@argo.dev", "role": "CUSTOMER"},
    {"key": "c2", "name": "Caio Moraes", "email": "caio@argo.dev", "role": "CUSTOMER"},
    {"key": "c3", "name": "Diana Lopes", "email": "diana@argo.dev", "role": "CUSTOMER"},
    {"key": "c4", "name": "Eduardo Ramos", "email": "eduardo@argo.dev", "role": "CUSTOMER"},
]


DEMO_PRODUCTS = [
    ("p01", "AUR-CAF-01", "Café especial em grãos 500 g", "Mercearia", 6290, 48, "vendedor"),
    ("p02", "AUR-CHA-02", "Chá verde orgânico 100 g", "Mercearia", 2890, 35, "vendedor"),
    ("p03", "AUR-MEL-03", "Mel silvestre 450 g", "Mercearia", 3990, 22, "vendedor"),
    ("p04", "AUR-AZE-04", "Azeite extravirgem 500 ml", "Mercearia", 5490, 4, "vendedor"),
    ("p05", "AUR-GRA-05", "Granola artesanal 800 g", "Mercearia", 3590, 30, "vendedor"),
    ("p06", "AUR-CAN-06", "Caneca de cerâmica 350 ml", "Casa", 4900, 18, "vendedor"),
    ("p07", "AUR-PRE-07", "Prensa francesa 600 ml", "Casa", 12900, 9, "vendedor"),
    ("p08", "AUR-MOE-08", "Moedor manual de café", "Casa", 18900, 3, "vendedor"),
    ("p09", "NOR-CAD-01", "Caderno pontilhado A5", "Papelaria", 3490, 60, "vendedor2"),
    ("p10", "NOR-CAN-02", "Caneta tinteiro", "Papelaria", 8990, 14, "vendedor2"),
    ("p11", "NOR-BOL-03", "Bolsa de lona encerada", "Acessórios", 21900, 7, "vendedor2"),
    ("p12", "NOR-CAR-04", "Carteira de couro vegetal", "Acessórios", 11900, 12, "vendedor2"),
    ("p13", "NOR-VEL-05", "Vela aromática de soja", "Casa", 5990, 26, "vendedor2"),
    ("p14", "NOR-VAS-06", "Vaso de barro pequeno", "Casa", 4590, 2, "vendedor2"),
    ("p15", "NOR-AGE-07", "Agenda semanal 2027", "Papelaria", 6990, 40, "vendedor2"),
    ("p16", "NOR-MAR-08", "Marcadores de página em latão", "Papelaria", 2490, 0, "vendedor2"),
]


def demo_user(key: str) -> dict:
    return next(u for u in DEMO_USERS if u["key"] == key)
