import stat

import pytest

import run


class FakeProcess:
    def __init__(self, returncode=None):
        self.returncode = returncode
        self.terminated = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True

    def wait(self):
        return self.returncode


@pytest.fixture
def steps(monkeypatch):
    """Replace every demo step with one that only records that it ran."""
    calls = []

    def recorded(name):
        def step(*args):
            calls.append(name)
            return 0

        return step

    for name in ("cmd_up", "cmd_register", "cmd_rooms", "cmd_scenario", "watch_agents"):
        monkeypatch.setattr(run, name, recorded(name))
    monkeypatch.setattr(run, "AGENT_START_SECONDS", 0)
    return calls


def use_agents(monkeypatch, steps, process):
    def start():
        steps.append("start_agents")
        return {"agents.test": process}

    monkeypatch.setattr(run, "start_agents", start)


def test_demo_starts_the_agents_before_the_complaint(steps, monkeypatch):
    process = FakeProcess()
    use_agents(monkeypatch, steps, process)

    assert run.cmd_demo() == 0
    assert steps == [
        "cmd_up", "cmd_register", "cmd_rooms", "start_agents", "cmd_scenario", "watch_agents",
    ]
    assert process.terminated


def test_demo_posts_no_complaint_if_an_agent_dies_at_the_start(steps, monkeypatch):
    use_agents(monkeypatch, steps, FakeProcess(returncode=3))

    assert run.cmd_demo() == 3
    assert "cmd_scenario" not in steps


def test_demo_stops_the_agents_if_the_scenario_fails(steps, monkeypatch):
    process = FakeProcess()
    use_agents(monkeypatch, steps, process)
    monkeypatch.setattr(run, "cmd_scenario", lambda: 1)

    assert run.cmd_demo() == 1
    assert "watch_agents" not in steps
    assert process.terminated


def test_demo_stops_before_the_agents_if_a_setup_step_fails(steps, monkeypatch):
    use_agents(monkeypatch, steps, FakeProcess())
    monkeypatch.setattr(run, "cmd_rooms", lambda: 1)

    assert run.cmd_demo() == 1
    assert "start_agents" not in steps


def test_agent_that_exits_cleanly_is_still_reported_as_stopped(capsys):
    assert run.stopped_agent_code({"agents.test": FakeProcess(returncode=0)}) == 1
    assert "agents.test stopped" in capsys.readouterr().out


def test_running_agents_report_nothing():
    assert run.stopped_agent_code({"agents.test": FakeProcess()}) is None


def test_empty_workspace_keeps_the_folder_and_clears_read_only_files(tmp_path, monkeypatch):
    workspace = tmp_path / "demo-workspace" / "payments-service"
    objects = workspace / ".git" / "objects"
    objects.mkdir(parents=True)
    read_only = objects / "abc"
    read_only.write_text("object")
    read_only.chmod(stat.S_IREAD)
    (workspace / "leftover.py").write_text("old")
    monkeypatch.setattr(run, "SERVICE_WORKSPACE", workspace)

    run.empty_workspace()

    assert workspace.is_dir()
    assert list(workspace.iterdir()) == []


def test_empty_workspace_creates_a_missing_folder(tmp_path, monkeypatch):
    workspace = tmp_path / "demo-workspace" / "payments-service"
    monkeypatch.setattr(run, "SERVICE_WORKSPACE", workspace)

    run.empty_workspace()

    assert workspace.is_dir()


def test_create_workspace_gives_a_fresh_repo_in_the_same_folder(tmp_path, monkeypatch):
    workspace = tmp_path / "demo-workspace" / "payments-service"
    workspace.mkdir(parents=True)
    (workspace / "leftover.py").write_text("old")
    monkeypatch.setattr(run, "SERVICE_WORKSPACE", workspace)

    run.create_workspace()

    assert not (workspace / "leftover.py").exists()
    assert (workspace / "service" / "charge_client.py").exists()
    assert (workspace / ".git").is_dir()


def test_reset_archives_the_old_room_and_reminds_about_the_agents(monkeypatch, capsys, tmp_path):
    scripts = []
    monkeypatch.setattr(run, "SERVICE_WORKSPACE", tmp_path / "payments-service")
    monkeypatch.setattr(run, "empty_mailpit", lambda: None)
    monkeypatch.setattr(run, "cmd_seed", lambda: 0)
    monkeypatch.setattr(run, "run_optional_script", scripts.append)

    assert run.cmd_reset() == 0
    assert scripts == ["switch/archive_rooms.py"]
    assert "!reset-all-agents" in capsys.readouterr().out
