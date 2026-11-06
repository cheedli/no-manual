"""Manual finder: URL safety, download limits, PDF -> page PNGs, identify flow."""
import io
import socket

import pytest
from conftest import make_jpeg

from core import manual


def make_pdf(path, pages=12):
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument.new()
    for _ in range(pages):
        pdf.new_page(595, 842)
    pdf.save(str(path))
    pdf.close()
    return path


class FakeResp(io.BytesIO):
    def __init__(self, body, ctype="application/pdf", url="https://ex.com/m.pdf", length=None):
        super().__init__(body)
        self.headers = {"Content-Type": ctype, **({"Content-Length": str(length)} if length else {})}
        self._url = url

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def public_dns(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])


def test_render_12_pages(tmp_path):
    pages = manual.render_pages(make_pdf(tmp_path / "m.pdf"), tmp_path / "pages")
    assert len(pages) == 12 and all(p.endswith(".png") for p in pages)


def test_rejects_http_and_private(monkeypatch, tmp_path):
    with pytest.raises(manual.ManualError, match="https"):
        manual.check_url("http://ex.com/m.pdf")
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("127.0.0.1", 443))])
    with pytest.raises(manual.ManualError, match="private"):
        manual.check_url("https://localhost/m.pdf")


def test_download_ok_and_limits(public_dns, tmp_path):
    body = make_pdf(tmp_path / "src.pdf", 2).read_bytes()
    out = manual.download("https://ex.com/m.pdf", tmp_path / "o.pdf", opener=lambda r, timeout: FakeResp(body))
    assert out.read_bytes().startswith(b"%PDF")
    octet = lambda r, timeout: FakeResp(body, ctype="application/octet-stream")
    assert manual.download("https://ex.com/m.pdf", tmp_path / "o2.pdf", opener=octet)
    with pytest.raises(manual.ManualError, match="isn't a PDF"):
        manual.download("https://ex.com/m.pdf", tmp_path / "x.pdf",
                        opener=lambda r, timeout: FakeResp(b"<html>hi</html>", ctype="text/html"))
    with pytest.raises(manual.ManualError, match="30 MB"):
        manual.download("https://ex.com/m.pdf", tmp_path / "x.pdf",
                        opener=lambda r, timeout: FakeResp(b"%PDF", length=manual.MAX_BYTES + 1))
    with pytest.raises(manual.ManualError, match="non-https"):
        manual.download("https://ex.com/m.pdf", tmp_path / "x.pdf",
                        opener=lambda r, timeout: FakeResp(body, url="http://ex.com/m.pdf"))


def test_attach_local_manual_tool(plugin, tmp_path):
    _, call = plugin
    pid = call("nm_start_project", category="crib")["project_id"]   # manual is allowed even when blocked
    r = call("nm_attach_manual", project_id=pid, pdf_path=str(make_pdf(tmp_path / "m.pdf")),
             source_page="https://maker.example/support")
    assert r["pages"] == 12 and "maker.example" in r["next"]
    s = call("nm_get_step", project_id=pid)
    assert s["total"] == 12 and s["image_path"].endswith("page_001.png")
    st = call("nm_status", project_id=pid)["project"]
    assert st["mode"] == "manual"
    assert "error" in call("nm_attach_manual", project_id=pid, pdf_url="http://x.com/a.pdf")


def test_identify_tool(plugin, tmp_path):
    ctx, call = plugin
    ctx.llm.responses = [{"brand": "IKEA", "product_name": "BILLY", "article_numbers": ["AA-2289541-3"],
                          "category_guess": "bookcase", "confidence": 0.9,
                          "search_queries": ["IKEA AA-2289541-3 assembly instructions pdf"]},
                         {"brand": "", "product_name": "", "article_numbers": [], "category_guess": "crib",
                          "confidence": 0.7, "search_queries": []}]
    pid = call("nm_start_project", category="bookcase")["project_id"]
    assert "error" in call("nm_identify", project_id=pid)  # no photos yet
    r = call("nm_identify", project_id=pid, image_paths=[str(make_jpeg(tmp_path / "label.jpg"))])
    assert r["article_numbers"] == ["AA-2289541-3"] and "web_search" in r["next"]
    pid2 = call("nm_start_project", category="other")["project_id"]
    r2 = call("nm_identify", project_id=pid2, image_paths=[str(make_jpeg(tmp_path / "c.jpg", (5, 5, 5)))])
    assert r2["safety_status"] == "blocked_child_or_load" and r2["safety_note"]
    assert "official manual" in r2["next"]
