"""CLI entrypoint for the job-seeker repo.

Discovery, CV generation, and application review are slash commands in
`.claude/commands/` - invoked via Claude Code (or scheduled via `/schedule`).
The only Python CLI surface is Google Drive sync, which needs OAuth.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Job-seeker CLI - runs Google Drive sync. Discovery and CV generation are Claude slash commands.",
    )
    subparsers = parser.add_subparsers(dest="command")

    sync = subparsers.add_parser(
        "sync",
        help="Sync posting artefacts to Google Drive.",
    )
    sync.add_argument(
        "--postings-dir",
        type=Path,
        default=Path("postings"),
        help="Path to the postings directory (default: postings/).",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    if args.command == "sync":
        from integrations.google_drive import sync_postings
        sync_postings(args.postings_dir)


if __name__ == "__main__":
    main()
