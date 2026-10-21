import base64
import io
from pathlib import Path

import pytest

from twila_credicarro import DocumentFile

MAX_BYTES = 10 * 1024 * 1024


def test_from_bytes_encodes_pure_base64() -> None:
    file = DocumentFile.from_bytes(b"%PDF-1.7 conteudo", "cnh.pdf")

    assert file.file_name == "cnh.pdf"
    assert file.base64_content == base64.b64encode(b"%PDF-1.7 conteudo").decode("ascii")
    assert not file.base64_content.startswith("data:")
    assert "\n" not in file.base64_content


def test_repr_does_not_dump_the_content() -> None:
    assert "conteudo" not in repr(DocumentFile.from_bytes(b"conteudo", "cnh.pdf"))
    assert "Y29udGV1ZG8" not in repr(DocumentFile.from_bytes(b"conteudo", "cnh.pdf"))


@pytest.mark.parametrize("name", ["a.pdf", "A.PDF", "foto.jpg", "foto.JPEG", "scan.png", "x" * 251 + ".pdf"])
def test_accepted_names(name: str) -> None:
    assert DocumentFile.from_bytes(b"x", name).file_name == name


@pytest.mark.parametrize(
    "name",
    [
        "",
        "   ",
        "arquivo",
        "arquivo.txt",
        "arquivo.pdf.exe",
        "arquivo.gif",
        "pasta/arquivo.pdf",
        "pasta\\arquivo.pdf",
        "../arquivo.pdf",
        "C:\\docs\\arquivo.pdf",
        "x" * 252 + ".pdf",
    ],
)
def test_rejected_names(name: str) -> None:
    with pytest.raises(ValueError):
        DocumentFile.from_bytes(b"x", name)


def test_empty_content_is_rejected() -> None:
    with pytest.raises(ValueError, match="vazio"):
        DocumentFile.from_bytes(b"", "a.pdf")


def test_size_limit_is_10_mib() -> None:
    assert DocumentFile.from_bytes(b"\x00" * MAX_BYTES, "a.pdf").file_name == "a.pdf"

    with pytest.raises(ValueError, match="10 MiB"):
        DocumentFile.from_bytes(b"\x00" * (MAX_BYTES + 1), "a.pdf")


def test_from_stream_reads_the_stream_and_enforces_the_limit() -> None:
    assert (
        DocumentFile.from_stream(io.BytesIO(b"\x89PNG"), "a.png").base64_content
        == base64.b64encode(b"\x89PNG").decode()
    )

    with pytest.raises(ValueError, match="10 MiB"):
        DocumentFile.from_stream(io.BytesIO(b"\x00" * (MAX_BYTES + 5)), "a.png")


def test_from_file_uses_the_basename_by_default(tmp_path: Path) -> None:
    path = tmp_path / "documento.pdf"
    path.write_bytes(b"%PDF-1.4")

    assert DocumentFile.from_file(path).file_name == "documento.pdf"
    assert DocumentFile.from_file(str(path), file_name="cnh-comprador.pdf").file_name == "cnh-comprador.pdf"
    assert DocumentFile.from_file(path).base64_content == base64.b64encode(b"%PDF-1.4").decode()


def test_from_file_rejects_empty_files_and_missing_files(tmp_path: Path) -> None:
    empty = tmp_path / "vazio.pdf"
    empty.write_bytes(b"")

    with pytest.raises(ValueError):
        DocumentFile.from_file(empty)

    with pytest.raises(FileNotFoundError):
        DocumentFile.from_file(tmp_path / "nao-existe.pdf")


def test_direct_construction_validates_the_name() -> None:
    with pytest.raises(ValueError):
        DocumentFile(file_name="arquivo.exe", base64_content="eA==")
