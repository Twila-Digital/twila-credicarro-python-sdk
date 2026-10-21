import uuid
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import pytest

from twila_credicarro._internal.http.query_string import QueryStringBuilder
from twila_credicarro._internal.http.retry_after import retry_after_seconds
from twila_credicarro._internal.path import path_segment


@pytest.mark.parametrize(
    "headers,expected",
    [
        ({}, None),
        ({"retry-after": ""}, None),
        ({"retry-after": "7"}, 7.0),
        ({"retry-after": "1.5"}, 1.5),
        ({"retry-after": "-3"}, None),
        ({"retry-after": "0"}, None),
        ({"retry-after": "nan"}, None),
        ({"retry-after": "inf"}, None),
        ({"retry-after": "1e999"}, None),
        ({"retry-after": "999999999"}, 86_400.0),
        ({"retry-after": "amanhã"}, None),
    ],
)
def test_retry_after_in_seconds(headers: dict[str, str], expected: object) -> None:
    assert retry_after_seconds(headers) == expected


def test_retry_after_as_http_date() -> None:
    future = datetime.now(timezone.utc) + timedelta(seconds=30)
    past = datetime.now(timezone.utc) - timedelta(seconds=30)

    in_future = retry_after_seconds({"retry-after": format_datetime(future, usegmt=True)})
    in_past = retry_after_seconds({"retry-after": format_datetime(past, usegmt=True)})

    assert in_future is not None and 20 <= in_future <= 31
    assert in_past is None


def test_query_string_encodes_and_skips_none() -> None:
    path = (
        QueryStringBuilder().add("placa", "ABC 1&2").add("cnpjLoja", "11.222.333/0001-81").add("x", None).build("v2/x")
    )

    assert path == "v2/x?placa=ABC%201%262&cnpjLoja=11.222.333%2F0001-81"
    assert QueryStringBuilder().build("v2/x") == "v2/x"


def test_path_segment_quotes_and_accepts_uuid() -> None:
    value = uuid.UUID("bea8d060-f93d-48eb-b6c4-45f64483cdd9")

    assert path_segment(value) == "bea8d060-f93d-48eb-b6c4-45f64483cdd9"
    assert path_segment("../admin") == "..%2Fadmin"
    with pytest.raises(ValueError):
        path_segment("  ")
