"""Tests for the CLI commands."""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from claudephant.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def _make_claude_dir(tmp_path: Path) -> Path:
    """Set up a temp dir mimicking ~/.claude/projects/<project>/."""
    projects_dir = tmp_path / "projects" / "test-project"
    projects_dir.mkdir(parents=True)
    shutil.copy(
        FIXTURES / "full_session.jsonl",
        projects_dir / "aaaa1111-2222-3333-4444-555566667777.jsonl",
    )
    shutil.copy(
        FIXTURES / "with_compaction.jsonl",
        projects_dir / "bbbb1111-2222-3333-4444-555566667777.jsonl",
    )
    shutil.copy(
        FIXTURES / "error_result.jsonl",
        projects_dir / "eeee1111-2222-3333-4444-555566667777.jsonl",
    )
    shutil.copy(
        FIXTURES / "assistant_first.jsonl",
        projects_dir / "gggg1111-2222-3333-4444-555566667777.jsonl",
    )
    return tmp_path


class TestListCommand:
    def test_list_basic(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(main, ["list"])
                assert result.exit_code == 0
                assert "aaaa1111" in result.output
                assert "bbbb1111" in result.output
                assert "sessions total" in result.output

    def test_list_json(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(main, ["list", "--json"])
                assert result.exit_code == 0
                data = json.loads(result.output)
                assert isinstance(data, list)
                assert len(data) >= 2

    def test_list_project_filter(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(main, ["list", "--project", "test-project"])
                assert result.exit_code == 0
                assert "aaaa1111" in result.output

    def test_list_since_filter(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                # Far future date — no sessions
                result = runner.invoke(main, ["list", "--since", "2030-01-01"])
                assert result.exit_code == 0
                assert "No sessions found" in result.output

    def test_list_no_sessions(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "projects").mkdir()
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", Path(tmp)):
                result = runner.invoke(main, ["list"])
                assert result.exit_code == 0
                assert "No sessions found" in result.output


class TestPromptsCommand:
    def test_prompts_basic(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(main, ["prompts"])
                assert result.exit_code == 0
                assert "Fix the login bug" in result.output

    def test_prompts_project_filter(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(main, ["prompts", "--project", "nonexistent"])
                assert result.exit_code == 0
                assert result.output.strip() == ""


class TestSessionCommand:
    def test_session_default_view(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(main, ["session", "aaaa1111"])
                assert result.exit_code == 0
                assert "Session:" in result.output
                assert "Project:" in result.output
                assert "Turn" in result.output

    def test_session_not_found(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "projects").mkdir()
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", Path(tmp)):
                result = runner.invoke(main, ["session", "zzzzzzzz"])
                assert result.exit_code == 1

    def test_session_tools(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(main, ["session", "aaaa1111", "--tools"])
                assert result.exit_code == 0
                assert (
                    "[Read]" in result.output
                    or "[Edit]" in result.output
                    or "[Bash]" in result.output
                )

    def test_session_edits(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(main, ["session", "aaaa1111", "--edits"])
                assert result.exit_code == 0
                assert "Edit" in result.output or "Write" in result.output

    def test_session_bash(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(main, ["session", "aaaa1111", "--bash"])
                assert result.exit_code == 0
                assert "pytest" in result.output

    def test_session_full(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(main, ["session", "aaaa1111", "--full"])
                assert result.exit_code == 0
                assert "Result:" in result.output

    def test_session_json(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(main, ["session", "aaaa1111", "--json"])
                assert result.exit_code == 0
                data = json.loads(result.output)
                assert isinstance(data, list)

    def test_session_turn_index(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(main, ["session", "aaaa1111", "--turn", "0"])
                assert result.exit_code == 0
                assert "Turn 0" in result.output

    def test_session_turn_out_of_range(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(main, ["session", "aaaa1111", "--turn", "9999"])
                assert result.exit_code == 1

    def test_session_turn_range(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(main, ["session", "aaaa1111", "--turns", "0-1"])
                assert result.exit_code == 0

    def test_session_grep(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(main, ["session", "aaaa1111", "--grep", "login"])
                assert result.exit_code == 0
                assert "login" in result.output.lower()

    def test_session_grep_no_match(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(
                    main, ["session", "aaaa1111", "--grep", "xyznonexistent"]
                )
                assert result.exit_code == 0

    def test_session_file_filter(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(
                    main, ["session", "aaaa1111", "--file", "auth.py", "--tools"]
                )
                assert result.exit_code == 0
                assert "auth.py" in result.output

    def test_session_tool_filter(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(
                    main, ["session", "aaaa1111", "--tool", "Edit", "--tools"]
                )
                assert result.exit_code == 0

    def test_session_head(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(main, ["session", "aaaa1111", "--head", "1"])
                assert result.exit_code == 0
                assert "Turn 0" in result.output

    def test_session_tail(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(main, ["session", "aaaa1111", "--tail", "1"])
                assert result.exit_code == 0

    def test_session_no_results(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(
                    main, ["session", "aaaa1111", "--bash", "--no-results"]
                )
                assert result.exit_code == 0
                assert "$" in result.output

    def test_session_compact_segment(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                # with_compaction has a compact boundary
                result = runner.invoke(
                    main, ["session", "bbbb1111", "--compact-segment", "0"]
                )
                assert result.exit_code == 0

    def test_session_compact_segment_out_of_range(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(
                    main, ["session", "bbbb1111", "--compact-segment", "99"]
                )
                assert result.exit_code == 1

    def test_session_after_filter(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(
                    main, ["session", "aaaa1111", "--after", "2026-02-20"]
                )
                assert result.exit_code == 0

    def test_session_before_filter(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(
                    main, ["session", "aaaa1111", "--before", "2026-02-21"]
                )
                assert result.exit_code == 0

    def test_session_json_no_results(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(
                    main, ["session", "aaaa1111", "--json", "--no-results"]
                )
                assert result.exit_code == 0
                data = json.loads(result.output)
                # No tool_results key when --no-results
                for turn in data:
                    assert "tool_results" not in turn

    def test_session_full_with_error_results(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(main, ["session", "eeee1111", "--full"])
                assert result.exit_code == 0
                assert "ERROR:" in result.output

    def test_session_tools_shows_unknown_tool_type(self):
        """Unknown tool types (not Read/Edit/Write/Bash/Glob/Grep) show JSON input."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(main, ["session", "gggg1111", "--tools"])
                assert result.exit_code == 0
                assert "[SomeUnknownTool]" in result.output

    def test_session_bash_no_results_omits_output(self):
        """--bash --no-results shows commands but not their output."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(
                    main, ["session", "aaaa1111", "--bash", "--no-results"]
                )
                assert result.exit_code == 0
                assert "$ pytest" in result.output
                # The result "PASSED 3/3" should NOT appear
                assert "PASSED 3/3" not in result.output


class TestSummaryCommand:
    def test_summary_basic(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(main, ["summary"])
                assert result.exit_code == 0
                assert "Tool Usage" in result.output
                assert "Most Common Prompts" in result.output

    def test_summary_shows_repeated_prompts_and_files(self):
        """When the same prompt or file appears in multiple sessions, summary shows counts."""
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = Path(tmp)
            projects_dir = claude_dir / "projects" / "test-project"
            projects_dir.mkdir(parents=True)
            # Copy the same session twice so prompts and files repeat
            shutil.copy(FIXTURES / "full_session.jsonl", projects_dir / "sess1.jsonl")
            shutil.copy(FIXTURES / "full_session.jsonl", projects_dir / "sess2.jsonl")
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(main, ["summary"])
                assert result.exit_code == 0
                assert "Most Modified Files" in result.output
                # auth.py is edited in full_session, should appear with count >= 2
                assert "auth.py" in result.output
                assert "Most Common Prompts" in result.output

    def test_summary_with_project_filter(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(main, ["summary", "--project", "test-project"])
                assert result.exit_code == 0


class TestParseDate:
    def test_bad_date(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(main, ["list", "--since", "not-a-date"])
                assert result.exit_code != 0

    def test_datetime_format(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = _make_claude_dir(Path(tmp))
            with patch("claudephant.index.DEFAULT_CLAUDE_DIR", claude_dir):
                result = runner.invoke(main, ["list", "--since", "2026-02-20T10:00:00"])
                assert result.exit_code == 0
