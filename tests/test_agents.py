from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from utils.logger import log_interaction
from utils.model_selector import FALLBACK_MODEL, DEFAULT_MODEL_MAP, select_model
import main


@pytest.mark.parametrize(
    "task,input_text,expected",
    [
        ({"type": "sms"}, "Hello", DEFAULT_MODEL_MAP["sms"]),
        ({"type": "comps"}, "Compare comps", DEFAULT_MODEL_MAP["comps"]),
        ({"type": "unknown"}, "Hello", FALLBACK_MODEL),
    ],
)
def test_select_model_for_known_task_types(task, input_text, expected):
    assert select_model(task, input_text) == expected


def test_select_model_falls_back_for_long_input():
    long_input = "x" * (main.model_selector.DEFAULT_MAX_INPUT_LENGTH + 1)
    assert select_model({"type": "sms"}, long_input) == FALLBACK_MODEL


def test_log_interaction_appends_file(tmp_path: Path):
    log_path = tmp_path / "agent.log"
    entry = log_interaction("sms", "Hey I'm interested", "Great!", log_file_path=log_path)

    assert log_path.read_text(encoding="utf-8").endswith(entry)
    assert "Agent: SMS" in entry


class DummyAirtable:
    def __init__(self):
        self.records = []

    def create(self, payload):
        self.records.append(payload)


def test_log_interaction_airtable():
    table = DummyAirtable()
    entry = log_interaction(
        "comps",
        "Need comps",
        "On it",
        destination="airtable",
        airtable_table=table,
    )

    assert table.records
    assert table.records[0]["Agent"] == "COMPS"
    assert "Agent: COMPS" in entry


@pytest.fixture()
def agent_registry():
    return main.load_agents()


def test_agents_return_expected_shape(agent_registry):
    sample_input = "Schedule a showing"
    for agent_name, agent in agent_registry.items():
        result = agent.run(sample_input)
        assert set(result) == {"agent", "model", "response"}
        assert result["agent"] == agent_name
        assert result["model"] in set(DEFAULT_MODEL_MAP.values()) | {FALLBACK_MODEL}


def test_fastapi_healthcheck():
    app = main.create_app()
    client = TestClient(app)

    response = client.get("/ping")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_agent_endpoint(tmp_path, monkeypatch):
    app = main.create_app()
    client = TestClient(app)

    log_path = tmp_path / "agent.log"

    def fake_logger(agent, input_text, output_text, **kwargs):
        return log_interaction(
            agent,
            input_text,
            output_text,
            destination="file",
            log_file_path=log_path,
        )

    monkeypatch.setattr(main, "LOGGER", fake_logger)

    payload = {"agent": "sms", "input": "Ping"}
    response = client.post("/agents/run", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["agent"] == "sms"
    assert data["model"] in set(DEFAULT_MODEL_MAP.values()) | {FALLBACK_MODEL}
    assert data["response"].startswith("sms agent")
    log_content = log_path.read_text(encoding="utf-8")
    assert "Agent: SMS" in log_content
