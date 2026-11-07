"""Official manual: safe PDF download + pages to PNG (docs/04 F3)."""
from __future__ import annotations

import ipaddress
import socket
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

MAX_BYTES = 30 * 1024 * 1024
MAX_PAGES = 80
DPI = 150


class ManualError(ValueError):
    pass


def check_url(url: str) -> str:
    """https only, and the host must not resolve to a private/loopback address."""
    u = urlparse(url or "")
    if u.scheme != "https" or not u.hostname:
        raise ManualError("Only https links to a PDF are accepted.")
    try:
        infos = socket.getaddrinfo(u.hostname, 443)
    except OSError:
        raise ManualError(f"Can't reach {u.hostname}.")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if getattr(ip, "ipv4_mapped", None):
            ip = ip.ipv4_mapped
        if not ip.is_global:  # private, loopback, link-local, CGNAT, reserved, multicast...
            raise ManualError("That link points to a private network address.")
    return u.hostname


class _CheckedRedirect(urllib.request.HTTPRedirectHandler):
    """Re-run check_url on every redirect hop, so a public URL can't bounce to an internal one.
    ponytail: DNS could still change between this check and the connect (rebinding); pinning the
    resolved IP would close that, at the cost of breaking SNI/virtual hosts."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_CheckedRedirect)


def download(url: str, dest: Path, opener=_OPENER.open) -> Path:
    """Fetch a PDF with a 30 MB cap. `opener` is injectable for tests."""
    check_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": "no-manual-hermes-plugin/0.1",
                                               "Accept": "application/pdf,*/*;q=0.5"})
    with opener(req, timeout=30) as resp:
        final = getattr(resp, "geturl", lambda: url)()
        if not str(final).startswith("https://"):
            raise ManualError("The link redirected to a non-https address.")
        ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        length = resp.headers.get("Content-Length")
        if length and int(length) > MAX_BYTES:
            raise ManualError("The PDF is larger than 30 MB.")
        data = b""
        while chunk := resp.read(1024 * 256):
            data += chunk
            if len(data) > MAX_BYTES:
                raise ManualError("The PDF is larger than 30 MB.")
    is_pdf = data.startswith(b"%PDF")
    # Some servers send PDFs as octet-stream; accept that only when the bytes are a PDF.
    if not is_pdf or ctype not in ("application/pdf", "application/x-pdf", "application/octet-stream",
                                   "binary/octet-stream", ""):
        raise ManualError(f"That link isn't a PDF (got {ctype or 'unknown type'}).")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return dest


def render_pages(pdf_path: Path, out_dir: Path) -> list[str]:
    try:
        import pypdfium2 as pdfium
    except ImportError:  # deps installed after the gateway started (seen in E2E, docs/03 §11)
        raise ManualError("PDF support isn't loaded yet: run `hermes gateway restart` once after "
                          "installing No Manual, then try again.")
    if not Path(pdf_path).read_bytes()[:4] == b"%PDF":
        raise ManualError("That file isn't a PDF.")
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        paths = []
        for i in range(min(len(pdf), MAX_PAGES)):
            img = pdf[i].render(scale=DPI / 72).to_pil().convert("RGB")
            p = out_dir / f"page_{i + 1:03d}.png"
            img.save(p, "PNG", optimize=True)
            paths.append(str(p))
        return paths
    finally:
        pdf.close()


def pages_to_steps(pages: list[str]) -> list[dict]:
    n = len(pages)
    return [{"index": i, "title": f"Manual page {i} of {n}",
             "instruction": f"Follow page {i} of the official manual.",
             "hardware_used": [], "image_path": p, "source_photo": p,
             "expected_state": f"As shown at the end of manual page {i}.",
             "checks": [], "confidence": 0.95} for i, p in enumerate(pages, 1)]
