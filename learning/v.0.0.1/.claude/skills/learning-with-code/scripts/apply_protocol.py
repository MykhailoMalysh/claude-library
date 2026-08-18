#!/usr/bin/env python3
"""Idempotently write or update the learning-with-code protocol block inside
a project's CLAUDE.md (or another agent-instructions file).

Safe to re-run: if the delimited block already exists, its contents are
replaced in place rather than duplicated, so re-running this after the
learning/mastered scope changes just updates the block.

Usage:
    python apply_protocol.py \\
        --path /path/to/repo \\
        --learning "LangGraph: StateGraph, reducers, conditional edges, checkpointing" \\
        --mastered "retrieval, chunking, generation — already built and measured" \\
        --default-posture learning \\
        [--file CLAUDE.md] [--dry-run]
"""
import argparse
import sys
from pathlib import Path

START = "<!-- learning-with-code:start -->"
END = "<!-- learning-with-code:end -->"


def build_block(learning: str, mastered: str, default_posture: str) -> str:
    template_path = Path(__file__).resolve().parent.parent / "references" / "protocol-block.md"
    template = template_path.read_text()
    posture_text = {
        "learning": "part of the learning surface — default to hints and Socratic questions",
        "mastered": "already-mastered ground — default to writing it normally",
    }.get(default_posture, default_posture)
    return (
        template
        .replace("{{LEARNING_SURFACE}}", learning)
        .replace("{{MASTERED_SURFACE}}", mastered or "the rest of the codebase")
        .replace("{{DEFAULT_POSTURE}}", posture_text)
    )


def merge(existing: str, block: str) -> str:
    if START in existing and END in existing:
        start_i = existing.index(START)
        end_i = existing.index(END) + len(END)
        return existing[:start_i] + block.strip() + existing[end_i:]
    sep = "\n\n" if existing.strip() else ""
    return existing.rstrip("\n") + sep + block.strip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--path", default=".", help="Repo root (default: current directory)")
    ap.add_argument("--file", default="CLAUDE.md", help="Instructions filename (default: CLAUDE.md)")
    ap.add_argument("--learning", required=True, help="What's being learned by hand in this repo")
    ap.add_argument("--mastered", default="", help="What's already solid and should stay full-speed")
    ap.add_argument("--default-posture", default="learning", choices=["learning", "mastered"],
                     help="How to treat new/ambiguous code (default: learning)")
    ap.add_argument("--dry-run", action="store_true", help="Print the result instead of writing it")
    args = ap.parse_args()

    target = Path(args.path).expanduser().resolve() / args.file
    existing = target.read_text() if target.exists() else ""
    block = build_block(args.learning, args.mastered, args.default_posture)
    result = merge(existing, block)

    if args.dry_run:
        print(result)
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(result)
    action = "Updated" if START in existing else "Added"
    print(f"{action} the learning-with-code protocol block in {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
