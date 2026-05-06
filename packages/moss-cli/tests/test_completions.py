"""Tests for the completions command."""

from typer.testing import CliRunner

from moss_cli.commands.completions import Shell, completions_command
from moss_cli.main import app

runner = CliRunner()


# ------------------------------------------------------------------
# completions command
# ------------------------------------------------------------------


def test_completions_bash_outputs_script() -> None:
    """``moss completions bash`` should output the bash completion script."""
    result = runner.invoke(app, ["completions", "bash"])
    assert result.exit_code == 0
    assert "complete -F _moss moss" in result.output


def test_completions_zsh_outputs_script() -> None:
    """``moss completions zsh`` should output the zsh completion script."""
    result = runner.invoke(app, ["completions", "zsh"])
    assert result.exit_code == 0
    assert "#compdef moss" in result.output


def test_completions_no_arg_shows_error() -> None:
    """``moss completions`` with no shell argument should fail."""
    result = runner.invoke(app, ["completions"])
    assert result.exit_code != 0


def test_completions_invalid_shell_shows_error() -> None:
    """``moss completions fish`` (unsupported) should fail."""
    result = runner.invoke(app, ["completions", "fish"])
    assert result.exit_code != 0


# ------------------------------------------------------------------
# Lazy-loading / command registration
# ------------------------------------------------------------------


def test_sdk_commands_registered() -> None:
    """When the moss SDK is available, SDK-dependent commands should be registered."""
    command_names = [cmd.name for cmd in app.registered_commands]
    group_names = [
        grp.typer_instance.info.name or grp.name
        for grp in app.registered_groups
        if grp.typer_instance
    ]

    # SDK-independent commands are always present
    assert "version" in command_names
    assert "completions" in command_names

    # If the SDK is available in the test env these will be present.
    # We import to check availability and assert accordingly.
    try:
        from moss_cli.commands.index import index_app  # noqa: F401

        sdk_available = True
    except Exception:
        sdk_available = False

    if sdk_available:
        assert "query" in command_names
        assert "init" in command_names
        assert "index" in group_names
        assert "doc" in group_names
        assert "job" in group_names


def test_app_no_args_shows_help() -> None:
    """Running ``moss`` with no arguments should show the help text."""
    result = runner.invoke(app, [])
    # Typer/Click exits with 0 when --help is explicit; no_args_is_help may
    # use exit-code 0 or 2 depending on the Typer version, so just check output.
    assert "Moss Semantic Search CLI" in result.output


def test_typer_builtin_completion_disabled() -> None:
    """Typer's built-in --install-completion / --show-completion should be disabled."""
    result = runner.invoke(app, ["--help"])
    assert "--install-completion" not in result.output
    assert "--show-completion" not in result.output
