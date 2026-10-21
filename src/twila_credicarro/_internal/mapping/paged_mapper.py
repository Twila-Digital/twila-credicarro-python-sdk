from typing import Any, Callable, TypeVar

from ...paged_result import PagedResult
from .wire import as_dict, as_list, req_int

T = TypeVar("T")


def paged_result_from_wire(wire: Any, item_mapper: Callable[[dict[str, Any]], T]) -> PagedResult[T]:
    root = as_dict(wire, "a listagem paginada")
    pagina = as_dict(root.get("pagina"), "'pagina'")
    itens = as_list(root.get("itens"), "'itens'")

    return PagedResult(
        items=[item_mapper(as_dict(item, "um item da listagem")) for item in itens],
        has_next=bool(pagina.get("tem_proximo", False)),
        has_previous=bool(pagina.get("tem_anterior", False)),
        page=req_int(pagina, "numero"),
        page_size=req_int(pagina, "tamanho"),
        total_count=req_int(pagina, "total"),
    )
