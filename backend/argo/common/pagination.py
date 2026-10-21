def page_bounds(page: int, size: int) -> tuple[int, int]:
    page = max(1, page)
    size = min(max(1, size), 100)
    return page, size


def pages(total: int, size: int) -> int:
    return max(1, -(-total // size))


def paginate(queryset, page: int, size: int, serialize) -> dict:
    """Resposta paginada padrão: ``{"items", "page", "size", "total"}``."""
    page, size = page_bounds(page, size)
    total = queryset.count()
    rows = queryset[(page - 1) * size : page * size]
    return {"items": [serialize(r) for r in rows], "page": page, "size": size, "total": total}
