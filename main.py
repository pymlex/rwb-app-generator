import argparse
import getpass
import json
import time
from pathlib import Path

from generator.config import Settings
from generator.knowledge import build_index, extract
from generator.pipeline import Pipeline
from generator.models import Analysis
from generator.verification import report, verify


def main():
    parser = argparse.ArgumentParser(description="TLE requirements-driven application generator")
    sub = parser.add_subparsers(dest="command", required=True)
    index = sub.add_parser("index")
    index.add_argument("sources", type=Path)
    index.add_argument("--database", type=Path, default=Path("knowledge/index.sqlite"))
    generate = sub.add_parser("generate")
    generate.add_argument("requirements", type=Path)
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--knowledge", type=Path, default=Path("knowledge/index.sqlite"))
    generate.add_argument("--answers", type=Path)
    generate.add_argument("--execute", action="store_true")
    generate.add_argument("--deploy", action="store_true")
    generate.add_argument("--sudo", action="store_true")
    check = sub.add_parser("verify")
    check.add_argument("output", type=Path)
    check.add_argument("--execute", action="store_true")
    check.add_argument("--deploy", action="store_true")
    check.add_argument("--sudo", action="store_true")
    args = parser.parse_args()
    if args.command == "index":
        print(json.dumps({"indexed_chunks": build_index(args.sources, args.database)}))
    elif args.command == "generate":
        sudo_password = getpass.getpass("Docker sudo password: ") if args.sudo else None
        answers = extract(args.answers) if args.answers else ""
        result = Pipeline(Settings.from_env(), args.output, args.knowledge).run(
            extract(args.requirements), answers, execute=args.execute, deploy=args.deploy, sudo_password=sudo_password,
        )
        print(json.dumps(result, indent=2))
    else:
        sudo_password = getpass.getpass("Docker sudo password: ") if args.sudo else None
        started = time.monotonic()
        checks = verify(args.output, args.execute, args.deploy, sudo_password)
        analysis = Analysis.model_validate_json((args.output / "docs" / "analysis.json").read_text(encoding="utf-8"))
        print(json.dumps(report(args.output, analysis, checks, time.monotonic() - started), indent=2))


if __name__ == "__main__":
    main()
