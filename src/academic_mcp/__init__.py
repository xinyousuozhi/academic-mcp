"""Academic MCP - 한국 학술/문화유산 기관 API 통합 MCP 서버"""

import asyncio

from mcp.server.stdio import stdio_server

from academic_mcp.server import create_server, cleanup_providers

__version__ = "0.1.0"


def main() -> None:
    """MCP 서버 진입점"""
    asyncio.run(run_server())


async def run_server() -> None:
    """MCP 서버 실행"""
    server, providers = create_server()

    async with stdio_server() as (read_stream, write_stream):
        try:
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
        finally:
            await cleanup_providers(providers)


if __name__ == "__main__":
    main()
