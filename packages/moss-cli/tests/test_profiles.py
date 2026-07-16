import json

from typer.testing import CliRunner

from moss_cli import config, documents
from moss_cli.commands import init_cmd
from moss_cli.commands import index as index_cmd
from moss_cli.commands import search as search_cmd
from moss_cli.commands import doc as doc_cmd
from moss_cli.main import app


runner = CliRunner()


def _write_config(tmp_path, data):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_resolve_credentials_legacy_config_shape(monkeypatch, tmp_path):
    path = _write_config(
        tmp_path,
        {
            "project_id": "legacy-id",
            "project_key": "legacy-key",
        },
    )
    monkeypatch.setattr(config, "get_config_path", lambda: path)

    pid, pkey = config.resolve_credentials()
    assert pid == "legacy-id"
    assert pkey == "legacy-key"


def test_resolve_credentials_uses_explicit_profile(monkeypatch, tmp_path):
    path = _write_config(
        tmp_path,
        {
            "active_profile": "default",
            "profiles": {
                "default": {"project_id": "default-id", "project_key": "default-key"},
                "staging": {"project_id": "staging-id", "project_key": "staging-key"},
            },
        },
    )
    monkeypatch.setattr(config, "get_config_path", lambda: path)

    pid, pkey = config.resolve_credentials(profile="staging")
    assert pid == "staging-id"
    assert pkey == "staging-key"


def test_resolve_credentials_uses_moss_profile_env(monkeypatch, tmp_path):
    path = _write_config(
        tmp_path,
        {
            "active_profile": "default",
            "profiles": {
                "default": {"project_id": "default-id", "project_key": "default-key"},
                "prod": {"project_id": "prod-id", "project_key": "prod-key"},
            },
        },
    )
    monkeypatch.setattr(config, "get_config_path", lambda: path)
    monkeypatch.setenv("MOSS_PROFILE", "prod")

    pid, pkey = config.resolve_credentials()
    assert pid == "prod-id"
    assert pkey == "prod-key"


def test_resolve_credentials_cli_or_env_creds_override_profile(monkeypatch, tmp_path):
    path = _write_config(
        tmp_path,
        {
            "active_profile": "default",
            "profiles": {
                "default": {"project_id": "default-id", "project_key": "default-key"},
                "staging": {"project_id": "staging-id", "project_key": "staging-key"},
            },
        },
    )
    monkeypatch.setattr(config, "get_config_path", lambda: path)

    pid, pkey = config.resolve_credentials("flag-id", "flag-key", profile="staging")
    assert pid == "flag-id"
    assert pkey == "flag-key"


def test_set_profile_credentials_preserves_active_profile(monkeypatch, tmp_path):
    path = _write_config(
        tmp_path,
        {
            "active_profile": "default",
            "profiles": {
                "default": {"project_id": "default-id", "project_key": "default-key"},
            },
        },
    )
    monkeypatch.setattr(config, "get_config_path", lambda: path)

    config.set_profile_credentials("staging", "staging-id", "staging-key")
    cfg = json.loads(path.read_text(encoding="utf-8"))

    assert cfg["active_profile"] == "default"
    assert cfg["profiles"]["staging"]["project_id"] == "staging-id"
    assert cfg["profiles"]["staging"]["project_key"] == "staging-key"


def test_set_profile_credentials_initializes_active_when_missing(monkeypatch, tmp_path):
    path = tmp_path / "config.json"
    monkeypatch.setattr(config, "get_config_path", lambda: path)

    config.set_profile_credentials("staging", "staging-id", "staging-key")
    cfg = json.loads(path.read_text(encoding="utf-8"))

    assert cfg["active_profile"] == "staging"


def test_profile_list_command_shows_profiles(monkeypatch, tmp_path):
    path = _write_config(
        tmp_path,
        {
            "active_profile": "default",
            "profiles": {
                "default": {"project_id": "default-id", "project_key": "default-key"},
                "staging": {"project_id": "staging-id", "project_key": "staging-key"},
            },
        },
    )
    monkeypatch.setattr(config, "get_config_path", lambda: path)

    result = runner.invoke(app, ["profile", "list"])

    assert result.exit_code == 0
    assert "Profiles" in result.stdout
    assert "* default" in result.stdout
    assert "staging" in result.stdout


def test_profile_list_json_output(monkeypatch, tmp_path):
    path = _write_config(
        tmp_path,
        {
            "active_profile": "staging",
            "profiles": {
                "default": {"project_id": "default-id", "project_key": "default-key"},
                "staging": {"project_id": "staging-id", "project_key": "staging-key"},
            },
        },
    )
    monkeypatch.setattr(config, "get_config_path", lambda: path)

    result = runner.invoke(app, ["--json", "profile", "list"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["active_profile"] == "staging"
    assert payload["profiles"] == ["default", "staging"]


def test_profile_delete_preserves_other_active_profile(monkeypatch, tmp_path):
    path = _write_config(
        tmp_path,
        {
            "active_profile": "default",
            "profiles": {
                "default": {"project_id": "default-id", "project_key": "default-key"},
                "staging": {"project_id": "staging-id", "project_key": "staging-key"},
            },
        },
    )
    monkeypatch.setattr(config, "get_config_path", lambda: path)

    result = runner.invoke(app, ["profile", "delete", "staging", "--force"])

    assert result.exit_code == 0
    cfg = json.loads(path.read_text(encoding="utf-8"))
    assert cfg["active_profile"] == "default"
    assert "staging" not in cfg["profiles"]


def test_profile_delete_falls_back_when_active_deleted(monkeypatch, tmp_path):
    path = _write_config(
        tmp_path,
        {
            "active_profile": "staging",
            "profiles": {
                "default": {"project_id": "default-id", "project_key": "default-key"},
                "staging": {"project_id": "staging-id", "project_key": "staging-key"},
            },
        },
    )
    monkeypatch.setattr(config, "get_config_path", lambda: path)

    result = runner.invoke(app, ["profile", "delete", "staging", "--force"])

    assert result.exit_code == 0
    cfg = json.loads(path.read_text(encoding="utf-8"))
    assert cfg["active_profile"] == "default"
    assert "staging" not in cfg["profiles"]


def test_profile_delete_json_output(monkeypatch, tmp_path):
    path = _write_config(
        tmp_path,
        {
            "active_profile": "default",
            "profiles": {
                "default": {"project_id": "default-id", "project_key": "default-key"},
                "staging": {"project_id": "staging-id", "project_key": "staging-key"},
            },
        },
    )
    monkeypatch.setattr(config, "get_config_path", lambda: path)

    result = runner.invoke(app, ["--json", "profile", "delete", "staging", "--force"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["deleted_profile"] == "staging"
    assert payload["active_profile"] == "default"


def test_index_list_accepts_profile_option_after_subcommand(monkeypatch, tmp_path):
    path = _write_config(
        tmp_path,
        {
            "active_profile": "default",
            "profiles": {
                "default": {"project_id": "default-id", "project_key": "default-key"},
                "staging": {"project_id": "staging-id", "project_key": "staging-key"},
            },
        },
    )
    monkeypatch.setattr(config, "get_config_path", lambda: path)

    seen = {}

    class FakeClient:
        def __init__(self, project_id, project_key):
            seen["project_id"] = project_id
            seen["project_key"] = project_key

        async def list_indexes(self):
            return []

    monkeypatch.setattr(index_cmd, "MossClient", FakeClient)

    result = runner.invoke(app, ["index", "list", "--profile", "staging"])

    assert result.exit_code == 0
    assert seen["project_id"] == "staging-id"
    assert seen["project_key"] == "staging-key"


def test_query_accepts_profile_option_after_subcommand(monkeypatch, tmp_path):
    path = _write_config(
        tmp_path,
        {
            "active_profile": "default",
            "profiles": {
                "default": {"project_id": "default-id", "project_key": "default-key"},
                "staging": {"project_id": "staging-id", "project_key": "staging-key"},
            },
        },
    )
    monkeypatch.setattr(config, "get_config_path", lambda: path)

    seen = {}

    class FakeClient:
        def __init__(self, project_id, project_key):
            seen["project_id"] = project_id
            seen["project_key"] = project_key

        async def load_index(self, index_name):
            return None

        async def query(self, index_name, query_text, options):
            return type(
                "_Result",
                (),
                {
                    "query": query_text,
                    "index_name": index_name,
                    "time_taken_ms": 1,
                    "docs": [],
                },
            )()

    monkeypatch.setattr(search_cmd, "MossClient", FakeClient)

    result = runner.invoke(app, ["query", "my-index", "hello", "--profile", "staging"])

    assert result.exit_code == 0
    assert seen["project_id"] == "staging-id"
    assert seen["project_key"] == "staging-key"


def test_global_profile_overrides_environment(monkeypatch, tmp_path):
    path = _write_config(
        tmp_path,
        {
            "active_profile": "default",
            "profiles": {
                "default": {"project_id": "default-id", "project_key": "default-key"},
                "staging": {"project_id": "staging-id", "project_key": "staging-key"},
                "prod": {"project_id": "prod-id", "project_key": "prod-key"},
            },
        },
    )
    monkeypatch.setattr(config, "get_config_path", lambda: path)
    monkeypatch.setenv("MOSS_PROFILE", "prod")

    seen = {}

    class FakeClient:
        def __init__(self, project_id, project_key):
            seen["project_id"] = project_id
            seen["project_key"] = project_key

        async def list_indexes(self):
            return []

    monkeypatch.setattr(index_cmd, "MossClient", FakeClient)

    result = runner.invoke(app, ["--profile", "staging", "index", "list"])

    assert result.exit_code == 0
    assert seen["project_id"] == "staging-id"
    assert seen["project_key"] == "staging-key"


def test_init_uses_global_profile_context(monkeypatch, tmp_path):
    path = tmp_path / "config.json"
    monkeypatch.setattr(config, "get_config_path", lambda: path)
    prompt_answers = iter(["project-123", "secret-456"])
    monkeypatch.setattr(init_cmd.Prompt, "ask", lambda *args, **kwargs: next(prompt_answers))

    seen = {}

    class FakeClient:
        def __init__(self, project_id, project_key):
            seen["project_id"] = project_id
            seen["project_key"] = project_key

        async def list_indexes(self):
            return []

    monkeypatch.setattr(init_cmd, "MossClient", FakeClient)

    result = runner.invoke(
        app,
        ["--profile", "staging", "init"],
    )

    assert result.exit_code == 0
    assert seen["project_id"] == "project-123"
    assert seen["project_key"] == "secret-456"
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["active_profile"] == "staging"
    assert saved["profiles"]["staging"]["project_id"] == "project-123"


def test_set_active_profile_success(monkeypatch, tmp_path):
    path = _write_config(
        tmp_path,
        {
            "active_profile": "default",
            "profiles": {
                "default": {"project_id": "default-id", "project_key": "default-key"},
                "staging": {"project_id": "staging-id", "project_key": "staging-key"},
            },
        },
    )
    monkeypatch.setattr(config, "get_config_path", lambda: path)

    assert config.set_active_profile("staging") is True
    cfg = json.loads(path.read_text(encoding="utf-8"))
    assert cfg["active_profile"] == "staging"


def test_set_active_profile_failure(monkeypatch, tmp_path):
    path = _write_config(
        tmp_path,
        {
            "active_profile": "default",
            "profiles": {
                "default": {"project_id": "default-id", "project_key": "default-key"},
            },
        },
    )
    monkeypatch.setattr(config, "get_config_path", lambda: path)

    assert config.set_active_profile("non-existent") is False
    cfg = json.loads(path.read_text(encoding="utf-8"))
    assert cfg["active_profile"] == "default"


def test_profile_use_command(monkeypatch, tmp_path):
    path = _write_config(
        tmp_path,
        {
            "active_profile": "default",
            "profiles": {
                "default": {"project_id": "default-id", "project_key": "default-key"},
                "staging": {"project_id": "staging-id", "project_key": "staging-key"},
            },
        },
    )
    monkeypatch.setattr(config, "get_config_path", lambda: path)

    result = runner.invoke(app, ["profile", "use", "staging"])
    assert result.exit_code == 0
    assert "Active profile is now" in result.stdout
    assert "staging" in result.stdout

    cfg = json.loads(path.read_text(encoding="utf-8"))
    assert cfg["active_profile"] == "staging"


def test_profile_use_command_not_found(monkeypatch, tmp_path):
    path = _write_config(
        tmp_path,
        {
            "active_profile": "default",
            "profiles": {
                "default": {"project_id": "default-id", "project_key": "default-key"},
            },
        },
    )
    monkeypatch.setattr(config, "get_config_path", lambda: path)

    result = runner.invoke(app, ["profile", "use", "non-existent"])
    assert result.exit_code != 0
    assert "Profile" in result.stdout
    assert "non-existent" in result.stdout
    assert "not found" in result.stdout


def test_profile_set_default_command(monkeypatch, tmp_path):
    path = _write_config(
        tmp_path,
        {
            "active_profile": "default",
            "profiles": {
                "default": {"project_id": "default-id", "project_key": "default-key"},
                "staging": {"project_id": "staging-id", "project_key": "staging-key"},
            },
        },
    )
    monkeypatch.setattr(config, "get_config_path", lambda: path)

    result = runner.invoke(app, ["profile", "set-default", "staging"])
    assert result.exit_code == 0
    assert "Active profile is now" in result.stdout
    assert "staging" in result.stdout

    cfg = json.loads(path.read_text(encoding="utf-8"))
    assert cfg["active_profile"] == "staging"


def test_profile_current_command(monkeypatch, tmp_path):
    path = _write_config(
        tmp_path,
        {
            "active_profile": "staging",
            "profiles": {
                "default": {"project_id": "default-id", "project_key": "default-key"},
                "staging": {"project_id": "staging-id", "project_key": "staging-key"},
            },
        },
    )
    monkeypatch.setattr(config, "get_config_path", lambda: path)

    result = runner.invoke(app, ["profile", "current"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "staging"


def test_profile_current_command_json(monkeypatch, tmp_path):
    path = _write_config(
        tmp_path,
        {
            "active_profile": "staging",
            "profiles": {
                "default": {"project_id": "default-id", "project_key": "default-key"},
                "staging": {"project_id": "staging-id", "project_key": "staging-key"},
            },
        },
    )
    monkeypatch.setattr(config, "get_config_path", lambda: path)

    result = runner.invoke(app, ["--json", "profile", "current"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["active_profile"] == "staging"


def test_import_csv_docs_column_mapping():
    csv_content = (
        "user_id,message,age,city\n"
        "u1,hello world,25,new york\n"
        "u2,foo bar,30,san francisco\n"
    )
    docs = documents.import_csv_docs(
        csv_content,
        id_column="user_id",
        text_column="message",
        include_all_metadata=True,
    )
    assert len(docs) == 2
    assert docs[0].id == "u1"
    assert docs[0].text == "hello world"
    assert docs[0].metadata == {"age": "25", "city": "new york"}
    assert docs[1].id == "u2"
    assert docs[1].text == "foo bar"
    assert docs[1].metadata == {"age": "30", "city": "san francisco"}


def test_import_csv_docs_specific_metadata():
    csv_content = (
        "user_id,message,age,city\n"
        "u1,hello world,25,new york\n"
    )
    docs = documents.import_csv_docs(
        csv_content,
        id_column="user_id",
        text_column="message",
        metadata_columns=["city"],
        include_all_metadata=False,
    )
    assert len(docs) == 1
    assert docs[0].id == "u1"
    assert docs[0].text == "hello world"
    assert docs[0].metadata == {"city": "new york"}


def test_import_json_docs_column_mapping():
    json_content = json.dumps([
        {"custom_id": "j1", "content": "json doc 1", "category": "A"},
        {"custom_id": "j2", "content": "json doc 2", "category": "B"},
    ])
    docs = documents.import_json_docs(
        json_content,
        id_column="custom_id",
        text_column="content",
        include_all_metadata=True,
    )
    assert len(docs) == 2
    assert docs[0].id == "j1"
    assert docs[0].text == "json doc 1"
    assert docs[0].metadata == {"category": "A"}


def test_import_jsonl_docs_column_mapping():
    jsonl_content = (
        '{"custom_id": "jl1", "content": "jsonl doc 1", "tags": ["t1", "t2"]}\n'
        '{"custom_id": "jl2", "content": "jsonl doc 2", "tags": ["t3"]}\n'
    )
    docs = documents.import_jsonl_docs(
        jsonl_content,
        id_column="custom_id",
        text_column="content",
        include_all_metadata=True,
    )
    assert len(docs) == 2
    assert docs[0].id == "jl1"
    assert docs[0].text == "jsonl doc 1"
    assert docs[0].metadata == {"tags": '["t1", "t2"]'}


def test_doc_import_command_cli(monkeypatch, tmp_path):
    # Mock resolve_credentials
    monkeypatch.setattr(doc_cmd, "resolve_credentials", lambda *args, **kwargs: ("proj-id", "proj-key"))

    # Write a test CSV file
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(
        "custom_id,custom_text,extra_field\n"
        "id123,hello mapped text,extra_val\n",
        encoding="utf-8"
    )

    seen_docs = []

    class FakeClient:
        def __init__(self, project_id, project_key):
            assert project_id == "proj-id"
            assert project_key == "proj-key"

        async def add_docs(self, index_name, docs, options):
            assert index_name == "my-index"
            seen_docs.extend(docs)
            return type(
                "_Result",
                (),
                {
                    "job_id": "job-123",
                    "doc_count": len(docs),
                    "index_name": "my-index",
                },
            )()

    monkeypatch.setattr(doc_cmd, "MossClient", FakeClient)

    result = runner.invoke(
        app,
        [
            "doc",
            "import",
            "my-index",
            "-f",
            str(csv_file),
            "-i",
            "custom_id",
            "-t",
            "custom_text",
        ],
    )

    assert result.exit_code == 0
    assert len(seen_docs) == 1
    assert seen_docs[0].id == "id123"
    assert seen_docs[0].text == "hello mapped text"
    assert seen_docs[0].metadata == {"extra_field": "extra_val"}
