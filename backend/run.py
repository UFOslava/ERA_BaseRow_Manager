import sys
import os
import argparse
import logging
from dotenv import load_dotenv

load_dotenv()

def main():
    parser = argparse.ArgumentParser(description="ERA ERP Backend & MCP Server Runner")
    parser.add_argument(
        "--NoMCP", "--no-mcp", "--nomcp",
        action="store_true",
        dest="no_mcp",
        help="Disable running the MCP server alongside the Flask backend."
    )
    parser.add_argument(
        "--mcp", "--stdio", "--mcp-stdio",
        action="store_true",
        dest="mcp_stdio",
        help="Run the MCP server in stdio mode (dedicated to AI agents / CLI)."
    )
    parser.add_argument(
        "--mcp-sse",
        action="store_true",
        dest="mcp_sse",
        help="Run only the standalone MCP SSE server (without Flask backend)."
    )
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("HOST", "127.0.0.1"),
        help="Host address for the Flask backend (default 127.0.0.1)."
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", 5000)),
        help="Port for the Flask backend (default 5000)."
    )
    parser.add_argument(
        "--mcp-host",
        type=str,
        default=os.getenv("MCP_HOST", "127.0.0.1"),
        help="Host address for the MCP SSE server (default 127.0.0.1)."
    )
    parser.add_argument(
        "--mcp-port",
        type=int,
        default=int(os.getenv("MCP_PORT", 8001)),
        help="Port for the MCP SSE server (default 8001)."
    )
    parser.add_argument(
        "--no-debug",
        action="store_true",
        help="Disable debug mode."
    )

    args, unknown = parser.parse_known_args()

    # Case 1: Pure stdio MCP server for agent integration
    if args.mcp_stdio:
        from app.mcp_server import run_mcp_stdio
        run_mcp_stdio()
        return

    # Case 2: Standalone MCP SSE server
    if args.mcp_sse:
        from app.mcp_server import run_mcp_sse
        print(f"Starting standalone ERA MCP SSE Server on http://{args.mcp_host}:{args.mcp_port}/sse")
        run_mcp_sse(host=args.mcp_host, port=args.mcp_port)
        return

    # Case 3: Default behavior - Start Flask and start MCP in background unless --NoMCP is passed
    if not args.no_mcp:
        try:
            from app.mcp_server import start_mcp_background
            print(f"[ERA ERP] Starting MCP SSE Server on http://{args.mcp_host}:{args.mcp_port}/sse (Use --NoMCP to disable)")
            start_mcp_background(host=args.mcp_host, port=args.mcp_port)
        except Exception as e:
            print(f"[ERA ERP] Warning: Failed to start background MCP server: {e}")
    else:
        print("[ERA ERP] Running backend without MCP server (--NoMCP flagged).")

    from app.main import create_app
    app = create_app()
    debug_flag = not args.no_debug
    # When MCP is spawned in background, avoid dual-spawning under werkzeug reloader
    app.run(host=args.host, port=args.port, debug=debug_flag, use_reloader=False if not args.no_mcp else debug_flag)


if __name__ == '__main__':
    main()
