from __future__ import annotations

import argparse
import json
from pathlib import Path

from .model_gateway import GatewayRequest, demo_gateway


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cost-aware model gateway demo")
    parser.add_argument("--db", type=Path, default=Path("data/gateway.db"))
    commands = parser.add_subparsers(dest="command", required=True)
    complete = commands.add_parser("complete")
    complete.add_argument("prompt")
    complete.add_argument("--tenant", default="demo")
    complete.add_argument("--quality", choices=["balanced", "fast", "high"], default="balanced")
    complete.add_argument("--privacy", choices=["any", "local"], default="any")
    complete.add_argument("--request-id", default="")
    complete.add_argument("--max-cost", type=float)
    complete.add_argument("--shadow-model")
    commands.add_parser("inspect")
    args = parser.parse_args(argv)
    gateway = demo_gateway(args.db)
    try:
        if args.command == "complete":
            request = GatewayRequest(args.tenant, args.prompt, args.request_id, args.quality, args.privacy, args.max_cost)
            print(json.dumps(gateway.complete(request, args.shadow_model).__dict__, indent=2))
        else:
            print(json.dumps(gateway.inspect(), indent=2))
        return 0
    finally:
        gateway.close()


if __name__ == "__main__":
    raise SystemExit(main())

