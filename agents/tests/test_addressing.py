"""Who may instruct each Python agent is the safety rule of the whole demo."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "register_agents.py"


def load_register_agents():
    spec = importlib.util.spec_from_file_location("register_agents", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def addressing() -> dict:
    return {name: choice for name, _, _, choice in load_register_agents().AGENTS}


def test_only_the_owner_can_instruct_the_treasurer():
    module = load_register_agents()
    assert addressing()["treasurer"] == "owner_only"
    # The same rule as switch_core.addressing.owner_only_policy([]): no other person or agent.
    assert module.ADDRESSING_POLICIES["owner_only"] == {
        "rules": [{"users": [], "agents": [], "owner": True}]
    }


def test_the_investigator_answers_anyone():
    module = load_register_agents()
    assert addressing()["investigator"] == "anyone"
    # A cleared policy is what Switch reads as open to anyone.
    assert module.ADDRESSING_POLICIES["anyone"] is None


def test_every_agent_has_a_policy_switch_understands():
    module = load_register_agents()
    assert set(addressing().values()) <= set(module.ADDRESSING_POLICIES)
