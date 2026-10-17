"""Paapalvelin (oletusportti 8700): GitHub- ja Gmail-tyokalut, oikeudet saannot.json:sta."""
import os

from mcp.server.fastmcp import FastMCP

from . import github, gmail, ydin

mcp = FastMCP(
    "holvi",
    host=os.environ.get("HOLVI_HOST", "127.0.0.1"),
    port=int(os.environ.get("HOLVI_PORT", "8700")),
    stateless_http=True,
    json_response=True,
)

TYOKALUT = {}
TYOKALUT.update(github.rekisteroi(mcp, ydin.tarkista_saannoilla))
TYOKALUT.update(gmail.rekisteroi(mcp, ydin.tarkista_saannoilla))


def main():
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
