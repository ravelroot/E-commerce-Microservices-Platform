import csv
import json
from collections.abc import Iterable, Iterator
from datetime import datetime
from zoneinfo import ZoneInfo

from django.http import StreamingHttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse
from rest_framework.renderers import BaseRenderer, JSONRenderer

LOCAL_TZ = ZoneInfo("America/Sao_Paulo")
MAX_ROWS = 50_000


class CSVRenderer(BaseRenderer):
    media_type = "text/csv"
    format = "csv"
    charset = "utf-8"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if data is None:
            return b""
        return json.dumps(data, ensure_ascii=False).encode("utf-8")


EXPORT_RENDERERS = [JSONRenderer, CSVRenderer]
CSV_RESPONSE = {(200, "text/csv"): OpenApiResponse(OpenApiTypes.STR, description="Arquivo CSV (separador ;) em UTF-8")}


class _Echo:
    def write(self, value: str) -> str:
        return value


def decimal_brl(cents: int | None) -> str:
    value = (cents or 0) / 100
    return f"{value:.2f}".replace(".", ",")


def local_datetime(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(LOCAL_TZ).strftime("%d/%m/%Y %H:%M")


def yes_no(value: bool) -> str:
    return "sim" if value else "não"


def _lines(header: list[str], rows: Iterable[list]) -> Iterator[str]:
    writer = csv.writer(_Echo(), delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    yield "﻿" + writer.writerow(header)
    for index, row in enumerate(rows):
        if index >= MAX_ROWS:
            break
        yield writer.writerow(["" if v is None else v for v in row])


def csv_response(filename: str, header: list[str], rows: Iterable[list]) -> StreamingHttpResponse:
    response = StreamingHttpResponse(_lines(header, rows), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "no-store"
    return response
