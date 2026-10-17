"""Postipalvelin (oletusportti 8701): vain Gmail-lukutyokalut yhdelle asiakkaalle.

Erillinen prosessi ja portti, jotta sahkopostia lukeva agentti ei koskaan nae
GitHub-tyokaluja. Oikea raja on palomuuri (esimerkit/nftables.example.conf).
"""
import os

from mcp.server.fastmcp import FastMCP

from . import gmail, ydin

NIMI = os.environ.get("HOLVI_POSTI_AGENTTI", "posti-agentti")

mcp = FastMCP(
    "holvi-posti",
    host=os.environ.get("HOLVI_POSTI_HOST", "127.0.0.1"),
    port=int(os.environ.get("HOLVI_POSTI_PORT", "8701")),
    stateless_http=True,
    json_response=True,
)

TYOKALUT = gmail.rekisteroi(mcp, ydin.tarkista_kiintea(NIMI, "Holvi-posti"))


def main():
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
