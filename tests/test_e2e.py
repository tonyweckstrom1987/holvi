"""Kokonaistesti: oikea palvelinprosessi, oikea MCP-asiakas HTTP:n yli, vale-GitHub paikallisesti.

Varmistaa, etta kutsujan IP, oikeudet, tyokalujen parametrit ja loki toimivat yhdessa
(yksikkotestit ohittavat MCP:n kontekstin).
"""
import asyncio
import base64
import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

SRC = str(Path(__file__).resolve().parent.parent / "src")


class ValeGitHub(BaseHTTPRequestHandler):
    def do_GET(self):
        assert self.headers["Authorization"] == "Bearer testi-token"
        if self.path.startswith("/user/repos"):
            runko = [{"name": "demo", "description": "d", "language": "Python", "private": False, "pushed_at": "t", "html_url": "u"}]
        elif self.path == "/user":
            runko = {"login": "o"}
        elif self.path.startswith("/repos/o/demo/contents/README.md"):
            runko = {"type": "file", "encoding": "base64", "size": 6, "content": base64.b64encode(b"moikka").decode()}
        else:
            runko = {}
        data = json.dumps(runko).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def vapaa_portti():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def palvelin(tmp_path):
    etc = tmp_path / "etc"
    etc.mkdir()
    (etc / "saannot.json").write_text(
        json.dumps({"agentit": {"127.0.0.1": {"nimi": "e2e", "tyokalut": ["github_repot", "github_tiedosto"]}}})
    )
    (etc / "salaisuudet.env").write_text("GITHUB_TOKEN=testi-token\n")
    loki = tmp_path / "audit.log"
    github = HTTPServer(("127.0.0.1", 0), ValeGitHub)
    threading.Thread(target=github.serve_forever, daemon=True).start()
    portti = vapaa_portti()
    ymparisto = {
        **os.environ,
        "PYTHONPATH": SRC,
        "HOLVI_DIR": str(etc),
        "HOLVI_LOKI": str(loki),
        "HOLVI_GITHUB_API": f"http://127.0.0.1:{github.server_port}",
        "HOLVI_HOST": "127.0.0.1",
        "HOLVI_PORT": str(portti),
    }
    prosessi = subprocess.Popen([sys.executable, "-m", "holvi.palvelin"], env=ymparisto, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        loppu = time.time() + 20
        while time.time() < loppu:
            try:
                socket.create_connection(("127.0.0.1", portti), timeout=0.5).close()
                break
            except OSError:
                time.sleep(0.2)
        else:
            pytest.fail("palvelin ei kaynnistynyt")
        yield portti, loki
    finally:
        prosessi.terminate()
        prosessi.wait(timeout=10)
        github.shutdown()


async def kutsu(portti, nimi, args):
    async with streamablehttp_client(f"http://127.0.0.1:{portti}/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            return await s.call_tool(nimi, args)


def test_sallittu_kutsu_onnistuu_ja_estetyt_estetaan_oikealla_kutsujalla(palvelin):
    portti, loki = palvelin
    ok = asyncio.run(kutsu(portti, "github_repot", {}))
    assert not ok.isError and "demo" in ok.content[0].text
    luettu = asyncio.run(kutsu(portti, "github_tiedosto", {"repo": "demo", "polku": "README.md"}))
    assert not luettu.isError and "moikka" in luettu.content[0].text
    arka = asyncio.run(kutsu(portti, "github_tiedosto", {"repo": "demo", "polku": ".env"}))
    assert arka.isError
    kielletty = asyncio.run(kutsu(portti, "gmail_haku", {"kysely": "x"}))
    assert kielletty.isError and "ei oikeutta" in kielletty.content[0].text

    rivit = [json.loads(r) for r in loki.read_text().splitlines()]
    assert [(r["agentti"], r["tyokalu"], r["tulos"]) for r in rivit] == [
        ("e2e", "github_repot", "ok"),
        ("e2e", "github_tiedosto", "ok"),
        ("e2e", "github_tiedosto", "estetty"),
        ("e2e", "gmail_haku", "estetty"),
    ]
    assert "testi-token" not in loki.read_text() and "moikka" not in loki.read_text()
