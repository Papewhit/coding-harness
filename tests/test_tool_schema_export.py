"""Golden coverage for canonical registered-tool schemas."""

from coda.core.runtime import Coda
from coda.core.session_store import SessionStore
from coda.core.workspace import WorkspaceContext
from tests.native_fixtures import scripted_client
from coda.tools.definitions import TOOL_DEFINITIONS
from coda.tools.schemas import (
    AgentArgs,
    AskUserArgs,
    ReadFileArgs,
    normalized_json_schema,
)


def build_agent(tmp_path):
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")
    return Coda(
        workspace=WorkspaceContext.build(tmp_path),
        session_store=SessionStore(tmp_path / ".coda" / "sessions"),
        model_client=scripted_client(),
    )


def test_registered_tool_holds_the_canonical_parameter_model(tmp_path):
    agent = build_agent(tmp_path)
    tool = agent.tools["read_file"]

    assert tool.args_model is ReadFileArgs
    assert tool.parameter_model is ReadFileArgs
    assert tool.schema == {"path": "str", "start": "int=1", "end": "int=200"}
    assert tool.input_schema == normalized_json_schema(ReadFileArgs)
    assert tool.parameters_schema == tool.input_schema


def test_required_and_default_fields_have_a_stable_golden_schema():
    assert normalized_json_schema(ReadFileArgs) == {
        "additionalProperties": False,
        "properties": {
            "end": {"default": 200, "type": "integer"},
            "path": {"type": "string"},
            "start": {"default": 1, "type": "integer"},
        },
        "required": ["path"],
        "type": "object",
    }


def test_nullable_fields_have_a_stable_golden_schema():
    assert normalized_json_schema(AskUserArgs) == {
        "additionalProperties": False,
        "properties": {
            "choices": {
                "anyOf": [
                    {"items": {"type": "string"}, "type": "array"},
                    {"type": "null"},
                ],
                "default": None,
            },
            "question": {"type": "string"},
        },
        "required": ["question"],
        "type": "object",
    }


def test_union_and_nullable_human_signature_is_model_derived():
    assert TOOL_DEFINITIONS["agent"].schema == {
        "description": "str",
        "prompt": "str",
        "subagent_type": "str='worker'",
        "write_scope": "(list[str] | str)?",
    }
    assert TOOL_DEFINITIONS["agent"].input_schema == normalized_json_schema(AgentArgs)


def test_all_object_schemas_forbid_additional_properties():
    assert TOOL_DEFINITIONS
    for definition in TOOL_DEFINITIONS.values():
        assert definition.input_schema["additionalProperties"] is False


def test_schema_fingerprint_is_stable_and_sensitive_to_the_model():
    read_file = TOOL_DEFINITIONS["read_file"]
    assert read_file.schema_fingerprint == (
        "3265d798bfa3c433e051b238a328ded7bad8ff603726c026832a7a17622653bd"
    )
    assert (
        read_file.schema_fingerprint
        != TOOL_DEFINITIONS["list_files"].schema_fingerprint
    )


def test_runtime_tool_signature_is_stable(tmp_path):
    agent = build_agent(tmp_path)

    assert agent.tool_signature() == (
        "e55a7c4d9bb3988c0d1a2701c15f8d95735ea0de077e0c6489e4b068ec916328"
    )


def test_extra_fields_are_rejected_by_local_validation(tmp_path):
    agent = build_agent(tmp_path)

    try:
        agent.tools["list_files"].validate({"path": ".", "unexpected": True})
    except ValueError as exc:
        assert "Extra inputs are not permitted" in str(exc)
    else:
        raise AssertionError("local validation accepted an undeclared field")
