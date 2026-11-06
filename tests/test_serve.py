"""Start-up (gowhere.serve): the options a host passes, what they reach, and the one
process the app depends on. The Dockerfile starts it with --host and --port, so a change
here is a change to deployment. Waitress is stood in for, so no port is opened."""
import logging

import pytest
import waitress

from gowhere import config, serve


@pytest.fixture
def started(tmp_path, monkeypatch):
    """Runs main() up to the moment Waitress would start. Yields what it was given."""
    served, ingesting = [], []
    monkeypatch.setattr(waitress, "serve", lambda app, **options: served.append((app, options)))
    monkeypatch.setattr(serve, "start_ingestion", ingesting.append)
    monkeypatch.setattr(config, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(serve.logging, "FileHandler", lambda path: logging.NullHandler())
    monkeypatch.setattr(serve.logging, "basicConfig", lambda **kw: None)

    def start(*argv):
        serve.main(list(argv))
        return served, ingesting
    return start


def test_by_default_it_serves_locally_on_port_8000_with_threads(started):
    served, ingesting = started()
    (_, options), = served                     # exactly one server: sessions live in it
    assert options == {"host": "127.0.0.1", "port": 8000, "threads": 8}
    assert ingesting == []                     # the schedule is off unless asked for


def test_the_app_it_serves_answers(started):
    served, _ = started()
    (app, _), = served
    assert app.test_client().get("/").status_code == 200


def test_the_options_the_dockerfile_passes_reach_the_server(started):
    served, _ = started("--host", "0.0.0.0", "--port", "10000")
    (_, options), = served
    assert options["host"] == "0.0.0.0" and options["port"] == 10000


def test_threads_can_be_set(started):
    served, _ = started("--threads", "4")
    (_, options), = served
    assert options["threads"] == 4


def test_the_ingestion_schedule_starts_only_when_asked_and_the_server_still_runs(started):
    served, ingesting = started("--ingest-every-hours", "6")
    assert ingesting == [6.0] and len(served) == 1


def test_a_port_that_is_not_a_number_stops_before_serving(started, capsys):
    with pytest.raises(SystemExit) as stopped:
        started("--port", "abc")
    assert stopped.value.code == 2 and "invalid int value" in capsys.readouterr().err


def test_the_log_folder_is_created(started, tmp_path):
    started()
    assert (tmp_path / "logs").is_dir()
