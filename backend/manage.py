#!/usr/bin/env python
"""Utilitário do Django. O serviço ativo vem de ARGO_SERVICE (identity, catalog, orders, worker ou all)."""

import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "argo.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
