from __future__ import annotations

import json
import re
from pathlib import Path

root = Path(__file__).resolve().parent
repo_root = root.parents[1]
plan = json.loads((root / "PLAN.json").read_text(encoding="utf-8"))
tickets: dict[str, dict[str, object]] = plan["tickets"]
errors: list[str] = []

EXPECTED_CONTROL_REVISION = "eval-control-v4"
EXPECTED_ENUMS = {
    "roles": ["program_supervisor", "integrator", "implementer", "reviewer"],
    "workflow_actions": [
        "dispatch",
        "execute",
        "review",
        "integrate",
        "accept",
        "mark_not_applicable",
        "remediate",
        "close",
    ],
    "thread_types": [
        "implementer",
        "fixture_builder",
        "reviewer",
        "integrator",
        "run_shard",
    ],
    "execution_modes": ["model_thread", "local_process", "current_integrator"],
    "ticket_states": [
        "pending",
        "running",
        "needs_remediation",
        "accepted",
        "not_applicable",
        "blocked",
    ],
    "wave_states": ["not_started", "running", "waiting", "passed", "blocked"],
    "gate_states": ["pending", "accepted", "rejected"],
    "waiting_reasons": [
        "none",
        "user_decision",
        "credential_or_access",
        "external_service",
    ],
    "not_applicable_reasons": [
        "required_gate_rejected",
        "optional_branch_not_selected",
    ],
    "finding_types": [
        "implementation_defect",
        "measurement_defect",
        "evaluation_failure",
        "change_request",
    ],
    "review_verdicts": ["accepted", "findings"],
}
EXPECTED_EXECUTION_BY_THREAD_TYPE = {
    "implementer": "model_thread",
    "fixture_builder": "model_thread",
    "reviewer": "model_thread",
    "integrator": "current_integrator",
    "run_shard": "local_process",
}
FUTURE_WAVES = {"W7", "W8", "W9", "W10"}


def markdown_section(text: str, heading: str) -> str:
    match = re.search(
        rf"^## {re.escape(heading)}\s*$\n(.*?)(?=^## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def code_bullets(section: str) -> list[str]:
    return re.findall(r"^- `([^`]+)`\s*$", section, flags=re.MULTILINE)


def wave_by_id(wave_id: str) -> dict[str, object] | None:
    return next((wave for wave in plan["waves"] if wave["id"] == wave_id), None)


if plan.get("schema_version") != "pico-eval-plan-v4":
    errors.append("PLAN schema_version must be pico-eval-plan-v4")
if plan.get("control_revision") != EXPECTED_CONTROL_REVISION:
    errors.append(f"PLAN control_revision must be {EXPECTED_CONTROL_REVISION}")
for name, expected in EXPECTED_ENUMS.items():
    if plan.get("enums", {}).get(name) != expected:
        errors.append(f"closed enum mismatch: {name}")

thread_type_execution = plan.get("enums", {}).get("thread_type_execution", {})
if set(thread_type_execution) != set(EXPECTED_EXECUTION_BY_THREAD_TYPE):
    errors.append("thread_type_execution keys must match thread_types")
for thread_type, mode in EXPECTED_EXECUTION_BY_THREAD_TYPE.items():
    if mode not in str(thread_type_execution.get(thread_type, "")):
        errors.append(f"thread_type_execution lacks {mode}: {thread_type}")

for obsolete in ("EVAL-010-I", "EVAL-010-D", "EVAL-010-Q", "EVAL-010-S"):
    if obsolete in tickets:
        errors.append(f"obsolete text-protocol Ticket remains: {obsolete}")

for required_control_file in (
    "CONTROL.md",
    "CURRENT.md",
    "README.md",
    "templates/CURRENT.md",
    "templates/HUMAN_REVIEW.md",
    "templates/WAVE_INTEGRATOR_PROMPT.md",
    "templates/THREAD_PROMPT.md",
    "templates/HANDOFF.md",
    "templates/REVIEW.md",
    "templates/RUN_SHARD.md",
    "state/FREEZE.template.json",
    "state/STATUS.template.json",
    "state/WAVE_HANDOFF.template.json",
    "state/TICKET_INSTANCE.template.json",
    "state/INSTALLATION_HANDOFF.template.json",
    "waves/W6R4-profile-reselection-human-smoke.md",
):
    if not (root / required_control_file).exists():
        errors.append(f"missing control-plane file: {required_control_file}")

for template_path in sorted((root / "state").glob("*.template.json")):
    try:
        json.loads(template_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON template: {template_path.relative_to(root)}: {exc}")

installation_handoff = json.loads(
    (root / "state/INSTALLATION_HANDOFF.template.json").read_text(encoding="utf-8")
)
private_config_locator = installation_handoff.get("private_config_locator", {})
if "local_config_path" in installation_handoff:
    errors.append("installation handoff must not persist local_config_path")
if private_config_locator != {
    "environment_variable": "PICO_NATIVE_PROVIDER_CONFIG",
    "provided_out_of_band": True,
    "value_persisted": False,
}:
    errors.append("installation handoff must preserve the out-of-band private config contract")

current_path = root / "CURRENT.md"
if current_path.exists():
    current_text = current_path.read_text(encoding="utf-8")
    if len(current_text.splitlines()) >= 100:
        errors.append("CURRENT.md must remain below 100 lines")
    for required_text in (
        "Control revision",
        "Current Wave",
        "Wave state",
        "Waiting reason",
        "## Gates",
        "## Next action",
        "## Authoritative references",
    ):
        if required_text not in current_text:
            errors.append(f"CURRENT.md missing required field: {required_text}")
    wave_state = re.search(r"\*\*Wave state:\*\* `([^`]+)`", current_text)
    waiting_reason = re.search(r"\*\*Waiting reason:\*\* `([^`]+)`", current_text)
    if wave_state and wave_state.group(1) not in EXPECTED_ENUMS["wave_states"]:
        errors.append(f"CURRENT.md invalid Wave state: {wave_state.group(1)}")
    if waiting_reason and waiting_reason.group(1) not in EXPECTED_ENUMS["waiting_reasons"]:
        errors.append(f"CURRENT.md invalid waiting reason: {waiting_reason.group(1)}")
    if wave_state and waiting_reason:
        if wave_state.group(1) == "waiting" and waiting_reason.group(1) == "none":
            errors.append("CURRENT.md waiting Wave must have a non-none waiting reason")
        if wave_state.group(1) != "waiting" and waiting_reason.group(1) != "none":
            errors.append("CURRENT.md non-waiting Wave must use waiting reason none")
    if (
        "provides the private config locator value out of band" not in current_text
        or "public locator environment-variable name" not in current_text
    ):
        errors.append("CURRENT.md must keep the private config locator value out of band")

wave_members: dict[str, set[str]] = {}
wave_ids: set[str] = set()
ticket_wave_occurrences: dict[str, int] = {ticket_id: 0 for ticket_id in tickets}
for wave in plan["waves"]:
    wave_id = wave["id"]
    if wave_id in wave_ids:
        errors.append(f"duplicate Wave ID: {wave_id}")
    wave_ids.add(wave_id)
    members: set[str] = set()
    for raw in wave["tickets"]:
        base = re.sub(r"\[x[^\]]+\]$", "", raw)
        if base not in tickets:
            errors.append(f"unknown Wave Ticket: {wave_id} -> {raw}")
            continue
        members.add(base)
        ticket_wave_occurrences[base] += 1
        if tickets[base]["wave"] != wave_id:
            errors.append(
                f"Wave mismatch: {base}: ticket={tickets[base]['wave']} wave-list={wave_id}"
            )
    wave_members[wave_id] = members
    for gate in wave.get("entry_gates", []):
        if gate not in plan.get("gates", {}):
            errors.append(f"unknown Wave entry Gate: {wave_id} -> {gate}")

for ticket_id, count in ticket_wave_occurrences.items():
    if count != 1:
        errors.append(f"Ticket must appear in exactly one Wave list: {ticket_id}: {count}")

w6r4 = wave_by_id("W6R4")
if w6r4 is None:
    errors.append("W6R4 control Wave is missing")
elif w6r4.get("tickets") != [] or w6r4.get("execution_owner") != "integrator":
    errors.append("W6R4 must have no Tickets and execution_owner=integrator")
else:
    w6r4_text = (root / str(w6r4["procedure_file"])).read_text(encoding="utf-8")
    for required_private_config_rule in (
        "`program_supervisor` 另行带外提供 private config locator value",
        "`PICO_NATIVE_PROVIDER_CONFIG`",
        "`private_config_locator_provided_out_of_band=true`",
        ' --config "$PICO_NATIVE_PROVIDER_CONFIG" ',
        "不得记录 shell 展开后的 `--config` 值",
    ):
        if required_private_config_rule not in w6r4_text:
            errors.append(
                "W6R4 lacks out-of-band private config rule: "
                f"{required_private_config_rule}"
            )

for ticket_id, ticket in tickets.items():
    ticket_file = root / str(ticket["ticket_file"])
    if not ticket_file.exists():
        errors.append(f"missing Ticket file: {ticket_id}: {ticket_file}")
        continue
    thread_type = ticket.get("thread_type")
    if thread_type not in EXPECTED_ENUMS["thread_types"]:
        errors.append(f"unknown thread_type: {ticket_id}: {thread_type}")
    for dep in ticket["depends_on"]:
        if dep not in tickets:
            errors.append(f"unknown dependency: {ticket_id} -> {dep}")
    allowed_not_applicable = ticket.get("allowed_not_applicable_dependencies", [])
    for dep in allowed_not_applicable:
        if dep not in ticket["depends_on"]:
            errors.append(
                f"allowed_not_applicable dependency is not a direct dependency: {ticket_id} -> {dep}"
            )
    for gate in ticket.get("required_gates", []):
        if gate not in plan.get("gates", {}):
            errors.append(f"unknown required Gate: {ticket_id} -> {gate}")
    for forbidden_state_path in (
        ".codex/eval/CURRENT.md",
        ".codex/eval/state/STATUS.json",
    ):
        if forbidden_state_path in ticket["allowed_write_paths"]:
            errors.append(
                f"Ticket may not write live/current state directly: {ticket_id}: {forbidden_state_path}"
            )
    if ".codex/eval/state/FREEZE.json" in ticket["allowed_write_paths"]:
        if thread_type != "integrator":
            errors.append(f"only current-integrator Tickets may write FREEZE: {ticket_id}")

    if ticket["wave"] not in FUTURE_WAVES:
        continue
    text = ticket_file.read_text(encoding="utf-8")
    if f"**Plan type:** `{thread_type}`" not in text:
        errors.append(f"future Ticket Plan type mismatch: {ticket_id}")
    for dep in ticket["depends_on"]:
        if f"- Dependency Ticket: `{dep}`" not in text:
            errors.append(f"future Ticket file missing dependency: {ticket_id} -> {dep}")
    for gate in ticket.get("required_gates", []):
        if f"- Required Gate: `{gate}=accepted`" not in text:
            errors.append(f"future Ticket file missing required Gate: {ticket_id} -> {gate}")
    file_allowed = code_bullets(markdown_section(text, "Allowed write paths"))
    file_forbidden = code_bullets(markdown_section(text, "Forbidden write paths"))
    if file_allowed != ticket["allowed_write_paths"]:
        errors.append(f"allowed_write_paths mismatch: {ticket_id}")
    if file_forbidden != ticket["forbidden_write_paths"]:
        errors.append(f"forbidden_write_paths mismatch: {ticket_id}")
    for phrase in (
        "完成验收、提交有意图清晰的 commit（run/reviewer ticket 除外）并生成",
        "完成验收并生成 `.codex/eval/templates/HANDOFF.md` 格式的 handoff 后立即停止",
        "ownership_change_request",
        "status_proposal",
        "Accepted source commit",
        "canonical commit",
    ):
        if phrase in text:
            errors.append(f"future Ticket retains obsolete rule/term: {ticket_id}: {phrase}")

if ".pico.toml.example" not in tickets["TOOL-021-P"]["allowed_write_paths"]:
    errors.append("TOOL-021-P must own .pico.toml.example provider migration")

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


formal_online = ("EVAL-021-R", "EVAL-050-P", "EVAL-050-F", "EVAL-061-R", "EVAL-070-R")
for ticket_id in formal_online:
    if "native_eval_ready" not in tickets[ticket_id].get("required_gates", []):
        errors.append(f"formal online Ticket lacks native_eval_ready Gate: {ticket_id}")
    if not depends_transitively(ticket_id, "TOOL-050-S-R1"):
        errors.append(f"formal online Ticket lacks recovered native_eval_ready lineage: {ticket_id}")

for ticket_id in ("EVAL-061-P", "EVAL-061-R", "EVAL-061-M", "EVAL-070-S", "EVAL-070-R", "EVAL-070-M"):
    if "native_resume_ready" not in tickets[ticket_id].get("required_gates", []):
        errors.append(f"Resume-dependent Ticket lacks native_resume_ready Gate: {ticket_id}")

for ticket_id in ("EVAL-061-P", "EVAL-061-R", "EVAL-061-M"):
    if not depends_transitively(ticket_id, "TOOL-062-G"):
        errors.append(f"Resume Ticket lacks native_resume_ready lineage: {ticket_id}")

process_tickets = ("EVAL-021-R", "EVAL-050-P", "EVAL-050-F", "TOOL-062-R", "EVAL-061-R", "EVAL-070-R")
for process_ticket in process_tickets:
    handoff_paths = [
        path
        for path in tickets[process_ticket]["allowed_write_paths"]
        if path.startswith(".codex/eval/handoffs/")
    ]
    expected = [f".codex/eval/handoffs/{process_ticket}.json"]
    if handoff_paths != expected:
        errors.append(
            f"Process Ticket must have one logical Ticket handoff: {process_ticket}: {handoff_paths}"
        )
    text = (root / tickets[process_ticket]["ticket_file"]).read_text(encoding="utf-8")
    if "Process manifest" not in text or "不为每个 Process 创建单独 handoff" not in text:
        errors.append(f"Process Ticket lacks v4 Process/handoff rule: {process_ticket}")

for ticket_id, ticket in tickets.items():
    if ticket["wave"] not in FUTURE_WAVES or ticket["thread_type"] != "integrator":
        continue
    proposal_paths = [
        path for path in ticket["allowed_write_paths"] if path.startswith(".codex/eval/proposals/")
    ]
    if proposal_paths:
        errors.append(f"current-integrator Ticket must not emit state proposals: {ticket_id}: {proposal_paths}")

for recovered_gate_consumer in (
    "TOOL-050-QO-R2",
    "TOOL-050-QA-R2",
    "TOOL-050-DA-R2",
    "TOOL-060-R",
):
    if not depends_transitively(recovered_gate_consumer, "TOOL-042-G-R2"):
        errors.append(
            f"post-W5 consumer lacks recovered deterministic Gate dependency: {recovered_gate_consumer}"
        )

for wsl_conformance_consumer in ("TOOL-050-QO-R2", "TOOL-050-QA-R2", "TOOL-050-DA-R2"):
    if not depends_transitively(wsl_conformance_consumer, "TOOL-058-G"):
        errors.append(
            f"W6R2 live Process lacks WSL canonical preflight dependency: {wsl_conformance_consumer}"
        )

# Explicit forward-control invariants.
w10 = wave_by_id("W10")
if not w10 or w10.get("entry_gates") != ["native_eval_ready"]:
    errors.append("W10 must require native_eval_ready but allow native_resume_ready=rejected")
if tickets["EVAL-081-A"].get("required_gates") != ["native_eval_ready"]:
    errors.append("EVAL-081-A must not require native_resume_ready=accepted")
if tickets["EVAL-081-A"].get("allowed_not_applicable_dependencies") != ["EVAL-061-M"]:
    errors.append("EVAL-081-A must explicitly allow EVAL-061-M=not_applicable")
if tickets["EVAL-081-G"].get("required_gates") != ["native_eval_ready"]:
    errors.append("EVAL-081-G must not require native_resume_ready=accepted")

tracked_change_tickets = (
    "TOOL-060-R",
    "TOOL-061-T",
    "EVAL-060",
    "EVAL-070-I",
    "EVAL-070-S",
    "EVAL-081-A",
    "EVAL-081-R",
)
for ticket_id in tracked_change_tickets:
    text = (root / tickets[ticket_id]["ticket_file"]).read_text(encoding="utf-8")
    completion = markdown_section(text, "Completion rule")
    if ".codex/eval/**" not in completion or "commit" not in completion:
        errors.append(f"Git-tracked-change Ticket lacks commit/control separation: {ticket_id}")

resume_pilot_text = (root / tickets["EVAL-061-P"]["ticket_file"]).read_text(encoding="utf-8")
if "Process manifest" not in resume_pilot_text or "`integrator`" not in markdown_section(resume_pilot_text, "Commands"):
    errors.append("EVAL-061-P must delegate live Process execution to integrator")

resume_command = (
    "uv run python scripts/run_native_resume_contract.py --live-selected-profile "
    "--output <ARTIFACT_ROOT>/native-resume-conformance/<RUN_SHA>/selected-profile"
)
if resume_command not in (root / tickets["TOOL-062-R"]["ticket_file"]).read_text(encoding="utf-8"):
    errors.append("TOOL-062-R exact selected-profile command was lost")

active_files = [
    root / "CONTROL.md",
    root / "CURRENT.md",
    root / "README.md",
    root / "AGENTS.addendum.md",
    root / "templates/WAVE_INTEGRATOR_PROMPT.md",
    root / "templates/THREAD_PROMPT.md",
    root / "templates/HANDOFF.md",
    root / "templates/REVIEW.md",
    root / "templates/RUN_SHARD.md",
    root / "waves/W6R4-profile-reselection-human-smoke.md",
    root / "waves/W7-evaluation-pilots-resume.md",
    root / "waves/W8-final-baseline-resume-gate.md",
    root / "waves/W9-resume-ablation.md",
    root / "waves/W10-release.md",
]
active_files.extend(root / tickets[ticket_id]["ticket_file"] for ticket_id, ticket in tickets.items() if ticket["wave"] in FUTURE_WAVES)
for path in active_files:
    text = path.read_text(encoding="utf-8")
    for ad_hoc in (r"\blane\b", r"\bcampaign controller\b", r"\bcanary\b"):
        if re.search(ad_hoc, text, flags=re.IGNORECASE):
            errors.append(f"undefined ad-hoc term in active control file: {path.relative_to(root)}: {ad_hoc}")

if errors:
    print("INVALID")
    for error in errors:
        print("-", error)
    raise SystemExit(1)

print(
    f"VALID: {len(tickets)} Ticket templates, {len(plan['waves'])} Waves, "
    f"control revision {plan['control_revision']}"
)
