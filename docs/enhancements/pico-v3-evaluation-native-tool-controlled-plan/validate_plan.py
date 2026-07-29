from __future__ import annotations

import json
import re
from pathlib import Path

root = Path(__file__).resolve().parent
plan = json.loads((root / "PLAN.json").read_text(encoding="utf-8"))
tickets = plan["tickets"]
errors: list[str] = []

for obsolete in ("EVAL-010-I", "EVAL-010-D", "EVAL-010-Q", "EVAL-010-S"):
    if obsolete in tickets:
        errors.append(f"obsolete text-protocol ticket remains: {obsolete}")

for ticket_id, ticket in tickets.items():
    ticket_file = root / ticket["ticket_file"]
    if not ticket_file.exists():
        errors.append(f"missing ticket file: {ticket_id}: {ticket_file}")
    for dep in ticket["depends_on"]:
        if dep not in tickets:
            errors.append(f"unknown dependency: {ticket_id} -> {dep}")
    for shared_state in (".codex/eval/state/STATUS.json", ".codex/eval/state/FREEZE.json"):
        if shared_state in ticket["allowed_write_paths"]:
            errors.append(
                f"ticket may not write Wave Integrator state directly: {ticket_id}: {shared_state}"
            )

if ".pico.toml.example" not in tickets["TOOL-021-P"]["allowed_write_paths"]:
    errors.append("TOOL-021-P must own .pico.toml.example provider migration")

for required_control_file in (
    "templates/WAVE_INTEGRATOR_PROMPT.md",
    "state/WAVE_HANDOFF.template.json",
    "state/TICKET_INSTANCE.template.json",
    "state/INSTALLATION_HANDOFF.template.json",
):
    if not (root / required_control_file).exists():
        errors.append(f"missing control-plane file: {required_control_file}")

wave_members: dict[str, set[str]] = {}
for wave in plan["waves"]:
    members: set[str] = set()
    for raw in wave["tickets"]:
        base = re.sub(r"\[x[^\]]+\]$", "", raw)
        if base not in tickets:
            errors.append(f"unknown wave ticket: {wave['id']} -> {raw}")
            continue
        members.add(base)
        if tickets[base]["wave"] != wave["id"]:
            errors.append(f"wave mismatch: {base}: ticket={tickets[base]['wave']} wave-list={wave['id']}")
    wave_members[wave["id"]] = members

state: dict[str, int] = {}
def visit(node: str, stack: list[str]) -> None:
    flag = state.get(node, 0)
    if flag == 1:
        errors.append("dependency cycle: " + " -> ".join(stack + [node]))
        return
    if flag == 2:
        return
    state[node] = 1
    for dep in tickets[node]["depends_on"]:
        visit(dep, stack + [node])
    state[node] = 2
for node in tickets:
    visit(node, [])

def depends_transitively(ticket_id: str, required: str) -> bool:
    seen: set[str] = set()
    stack = [ticket_id]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        for dep in tickets[node]["depends_on"]:
            if dep == required:
                return True
            stack.append(dep)
    return False

for online in ("EVAL-021-R", "EVAL-050-P", "EVAL-050-F", "EVAL-061-R", "EVAL-070-R"):
    if online in tickets and not depends_transitively(online, "TOOL-050-S"):
        errors.append(f"formal online ticket lacks Gate N1 dependency: {online}")
for resume in ("EVAL-061-P", "EVAL-061-R"):
    if resume in tickets and not depends_transitively(resume, "TOOL-062-G"):
        errors.append(f"resume ticket lacks Gate N2 dependency: {resume}")

if errors:
    print("INVALID")
    for error in errors:
        print("-", error)
    raise SystemExit(1)

print(f"VALID: {len(tickets)} ticket templates, {len(plan['waves'])} waves")
