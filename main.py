#!/usr/bin/env python3
"""
Mao Card Game - Multiplayer CLI Implementation

A multiplayer card game where players discover rules through play.
Supports LAN multiplayer with a client-server architecture.

Usage:
    python -m mao_game server [--host HOST] [--port PORT] [--decks DECKS] [--max-players MAX]
    python -m mao_game client [--host HOST] [--port PORT] --name NAME
    python -m mao_game --help

Examples:
    # Start a server on default port 5555
    python -m mao_game server

    # Start a server with custom settings
    python -m mao_game server --port 8080 --decks 2 --max-players 8

    # Connect as a client
    python -m mao_game client --name Alice

    # Connect to a remote server
    python -m mao_game client --host 192.168.1.100 --name Bob
"""

import argparse
import sys


def main():
    """Main entry point for the Mao game."""
    parser = argparse.ArgumentParser(
        description="Mao Card Game - Multiplayer CLI Implementation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s server                        Start a server on default port
  %(prog)s server --port 8080 --decks 2  Custom server settings
  %(prog)s client --name Alice           Connect as Alice to localhost
  %(prog)s client --host 192.168.1.5 -n Bob  Connect to remote server

For more information, see: https://github.com/example/mao-game
        """
    )

    subparsers = parser.add_subparsers(dest="mode", help="Run as server or client")

    # Server arguments
    server_parser = subparsers.add_parser(
        "server",
        help="Start a game server",
        description="Start the Mao game server. Other players can connect to this server over LAN."
    )
    server_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host address to bind to (default: 0.0.0.0 for all interfaces)"
    )
    server_parser.add_argument(
        "--port",
        type=int,
        default=5555,
        help="Port to listen on (default: 5555)"
    )
    server_parser.add_argument(
        "--decks",
        type=int,
        default=1,
        help="Number of card decks to use (default: 1)"
    )
    server_parser.add_argument(
        "--max-players",
        type=int,
        default=10,
        help="Maximum number of players (default: 10)"
    )
    server_parser.add_argument(
        "--rules",
        type=str,
        default=None,
        help="Path to custom rules JSON file"
    )

    # Client arguments
    client_parser = subparsers.add_parser(
        "client",
        help="Connect to a game server",
        description="Connect to a Mao game server as a player."
    )
    client_parser.add_argument(
        "--host",
        default="localhost",
        help="Server host address (default: localhost)"
    )
    client_parser.add_argument(
        "--port",
        type=int,
        default=5555,
        help="Server port (default: 5555)"
    )
    client_parser.add_argument(
        "--name", "-n",
        required=True,
        help="Your player name"
    )

    args = parser.parse_args()

    if args.mode == "server":
        from network.server import GameServer

        print(f"""
╔══════════════════════════════════════╗
║         MAO GAME SERVER              ║
╚══════════════════════════════════════╝
        """)

        server = GameServer(
            host=args.host,
            port=args.port,
            num_decks=args.decks,
            max_players=args.max_players
        )

        # Load custom rules if provided
        if args.rules:
            from core.rule_engine import RuleEngine
            server.rule_engine = RuleEngine(args.rules)

        try:
            server.start()
        except KeyboardInterrupt:
            print("\nShutting down...")
            server.stop()

    elif args.mode == "client":
        from network.client import GameClient

        client = GameClient(
            host=args.host,
            port=args.port
        )

        print(f"""
╔══════════════════════════════════════╗
║         MAO GAME CLIENT              ║
╚══════════════════════════════════════╝
        """)

        if client.connect(args.name):
            client.run()
        else:
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()