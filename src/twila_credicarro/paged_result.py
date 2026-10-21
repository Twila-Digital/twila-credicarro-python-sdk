from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")

MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class PagedResult(Generic[T]):
    items: list[T]
    has_next: bool
    has_previous: bool
    page: int
    page_size: int
    total_count: int


@dataclass(frozen=True)
class ListRequest:
    """Paginação das listagens (`pagina_inicial` e `limite`). `page_size` aceita de 1 a 100."""

    page: int = 1
    page_size: int = 10

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("page deve ser maior ou igual a 1.")
        if not 1 <= self.page_size <= MAX_PAGE_SIZE:
            raise ValueError(f"page_size deve estar entre 1 e {MAX_PAGE_SIZE}.")
