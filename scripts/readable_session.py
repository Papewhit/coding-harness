#!/usr/bin/env python3
"""将 pico session JSON 转换为人类可读的 Markdown 文本。

用法:
  uv run python scripts/readable_session.py .pico/sessions/20260513-183158-56c28c.json
  uv run python scripts/readable_session.py .pico/sessions/20260513-183158-56c28c.json -o session.md
  uv run python scripts/readable_session.py --all   # 转换所有 session
  uv run python scripts/readable_session.py --all -o sessions/   # 输出到目录
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


def format_timestamp(ts):
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return str(ts)[:19]


def format_content(content):
    """将内容截断为可读长度，保留完整文本。"""
    if content is None:
        return "(empty)"
    text = str(content)
    return text


def convert_session(session_path: Path, output_path: Path):
    session = json.loads(session_path.read_text(encoding="utf-8"))

    lines = []
    sid = session.get("id", session_path.stem)
    created = format_timestamp(session.get("created_at", ""))
    workspace = session.get("workspace_root", "")

    lines.append(f"# Session: {sid}")
    lines.append(f"")
    lines.append(f"- **创建时间**: {created}")
    lines.append(f"- **工作目录**: `{workspace}`")
    lines.append(f"- **对话轮数**: {len(session.get('history', []))}")
    lines.append(f"")

    history = session.get("history", [])
    for i, item in enumerate(history):
        role = item.get("role", "unknown")
        name = item.get("name", "")
        created_at = format_timestamp(item.get("created_at", ""))
        args = item.get("args")

        lines.append(f"---")
        lines.append(f"### [{i}] {role}" + (f" `{name}`" if name else ""))
        lines.append(f"*{created_at}*")
        lines.append(f"")

        if args:
            lines.append(f"**参数**: `{json.dumps(args, ensure_ascii=False)}`")
            lines.append(f"")

        content = item.get("content")
        if content:
            lines.append(format_content(content))
            lines.append(f"")

    # Memory section
    memory = session.get("memory", {})
    if memory:
        lines.append(f"---")
        lines.append(f"## Memory")
        lines.append(f"")

        durable_topics = memory.get("durable_topics", [])
        if durable_topics:
            for topic in durable_topics:
                name = topic.get("name", "unknown")
                summary = topic.get("summary", "")
                lines.append(f"- **{name}**: {summary}")
            lines.append(f"")

        notes = memory.get("episodic_notes") or memory.get("notes") or []
        if notes:
            lines.append(f"### Episodic Notes")
            for note in notes:
                lines.append(f"- {note}")
            lines.append(f"")

    lines.append(f"---")
    lines.append(f"*Generated from `{session_path}`*")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="将 pico session JSON 转换为可读 Markdown")
    parser.add_argument("input", nargs="?", help="session JSON 文件路径（--all 时可选）")
    parser.add_argument("-o", "--output", help="输出文件路径（默认: <input>.md）")
    parser.add_argument("--all", action="store_true", help="转换 .pico/sessions/ 下所有 session")
    parser.add_argument("--sessions-dir", default=".pico/sessions", help="sessions 目录（默认 .pico/sessions）")
    args = parser.parse_args()

    if args.all:
        sessions_dir = Path(args.sessions_dir)
        if not sessions_dir.is_dir():
            print(f"错误: sessions 目录不存在: {sessions_dir}")
            sys.exit(1)

        json_files = sorted(sessions_dir.glob("*.json"))
        if not json_files:
            print(f"没有找到 session JSON 文件在: {sessions_dir}")
            sys.exit(1)

        out_dir = Path(args.output) if args.output else Path("sessions_readable")
        out_dir.mkdir(parents=True, exist_ok=True)
        for jf in json_files:
            out = out_dir / f"{jf.stem}.md"
            convert_session(jf, out)
            print(f"  -> {out}")
        print(f"\n转换完成: {len(json_files)} 个 session -> {out_dir}/")
    else:
        if not args.input:
            parser.error("请指定输入文件，或使用 --all 批量转换")
        input_path = Path(args.input)
        if not input_path.is_file():
            print(f"错误: 文件不存在: {input_path}")
            sys.exit(1)

        output_path = Path(args.output) if args.output else input_path.with_suffix(".md")
        convert_session(input_path, output_path)
        print(f"转换完成: {input_path} -> {output_path}")


if __name__ == "__main__":
    main()
