from __future__ import annotations

import sys

from coda.cli import build_agent, build_arg_parser
from coda.tui.app import CodaTuiApp


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.prompt:
        print("coda-tui does not accept one-shot prompts; start the TUI and type there.", file=sys.stderr)
        return 2
    agent = build_agent(args)
    CodaTuiApp(agent).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
