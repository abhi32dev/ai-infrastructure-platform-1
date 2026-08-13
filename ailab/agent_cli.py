from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_runtime import ApprovalRequired, DurableAgentRuntime, demo_plan, demo_registry


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Durable agent runtime demo")
    result.add_argument("--db", type=Path, default=Path("data/agents.db"))
    commands = result.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start")
    start.add_argument("--incident", default="INC-1001")
    inspect = commands.add_parser("inspect")
    inspect.add_argument("run_id")
    approve = commands.add_parser("approve")
    approve.add_argument("run_id")
    approve.add_argument("step_id")
    approve.add_argument("--actor", default="local-user")
    approve.add_argument("--reason", default="approved during learning exercise")
    deny = commands.add_parser("deny")
    deny.add_argument("run_id")
    deny.add_argument("step_id")
    deny.add_argument("--actor", default="local-user")
    deny.add_argument("--reason", default="denied during learning exercise")
    resume = commands.add_parser("resume")
    resume.add_argument("run_id")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    runtime = DurableAgentRuntime(args.db, demo_registry(), {"lookup_incident", "draft_remediation", "apply_remediation"})
    try:
        if args.command == "start":
            try:
                result = runtime.start(demo_plan(args.incident))
                print(json.dumps(result.__dict__, indent=2))
            except ApprovalRequired as required:
                print(json.dumps({"run_id": required.run_id, "status": "waiting_approval", "step_id": required.step_id}, indent=2))
        elif args.command == "inspect":
            print(json.dumps(runtime.inspect(args.run_id), indent=2))
        elif args.command in {"approve", "deny"}:
            decision = runtime.approve if args.command == "approve" else runtime.deny
            decision(args.run_id, args.step_id, args.actor, args.reason)
            print(json.dumps({"run_id": args.run_id, "step_id": args.step_id, "decision": "approved" if args.command == "approve" else "denied"}))
        elif args.command == "resume":
            try:
                result = runtime.resume(args.run_id)
                print(json.dumps(result.__dict__, indent=2))
            except ApprovalRequired as required:
                print(json.dumps({"run_id": required.run_id, "status": "waiting_approval", "step_id": required.step_id}, indent=2))
        return 0
    finally:
        runtime.close()


if __name__ == "__main__":
    raise SystemExit(main())
