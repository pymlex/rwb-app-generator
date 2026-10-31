import argparse
import getpass
import json
import re
import sys
import time
from pathlib import Path

from generator.config import Settings
from generator.knowledge import build_index, extract
from generator.models import Analysis
from generator.pipeline import Pipeline
from generator.verification import report, verify


def read_answers(path: Path) -> str:
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Answers must not contain duplicate keys")
            result[key] = value
        return result

    try:
        answers = json.loads(extract(path), object_pairs_hook=unique_object)
    except json.JSONDecodeError:
        raise ValueError("Answers must be a JSON object") from None
    if not isinstance(answers, dict):
        raise ValueError("Answers must be a JSON object")
    if any(not re.fullmatch(r"Q-[0-9]{3}", key) for key in answers):
        raise ValueError("Answers may contain only Q-nnn keys")
    for value in answers.values():
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Every answer must be a nonempty string")
        if len(value.encode("utf-8")) > 4 * 1024:
            raise ValueError("Every answer must be at most 4 KiB")
    return json.dumps(answers, ensure_ascii=False)


def docker_password(enabled: bool) -> str | None:
    if not enabled:
        return None
    return (
        getpass.getpass("Docker sudo password: ")
        if sys.stdin.isatty()
        else sys.stdin.readline().rstrip("\r\n")
    )


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
    generate.add_argument("--data", type=Path, help="Directory of reference JSON files")
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
        try:
            requirements = extract(args.requirements)
            answers = read_answers(args.answers) if args.answers else ""
        except (ValueError, OSError) as exc:
            parser.error(str(exc))
        sudo_password = docker_password(args.sudo)
        result = Pipeline(Settings.from_env(), args.output, args.knowledge).run(
            requirements,
            answers,
            execute=args.execute,
            deploy=args.deploy,
            sudo_password=sudo_password,
            data=args.data,
        )
        print(json.dumps(result, indent=2))
        if result["status"] == "failed":
            raise SystemExit(1)
    else:
        sudo_password = docker_password(args.sudo)
        started = time.monotonic()
        checks = verify(args.output, args.execute, args.deploy, sudo_password)
        analysis = Analysis.model_validate_json(
            (args.output / "docs" / "analysis.json").read_text(encoding="utf-8")
        )
        result = report(args.output, analysis, checks, time.monotonic() - started)
        print(json.dumps(result, indent=2))
        if result["status"] == "failed":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
