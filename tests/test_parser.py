"""Tests for the JSONL parser."""

from pathlib import Path

from claudephant.parser import (
    _extract_tool_results,
    _extract_user_text,
    _is_meta_message,
    _is_tool_result_only,
    _parse_timestamp,
    parse_session,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestParseTimestamp:
    def test_with_z_suffix(self):
        dt = _parse_timestamp("2026-02-20T10:00:00.000Z")
        assert dt.year == 2026
        assert dt.month == 2
        assert dt.day == 20
        assert dt.hour == 10
        assert dt.tzinfo is not None

    def test_with_offset(self):
        dt = _parse_timestamp("2026-02-20T10:00:00+00:00")
        assert dt.tzinfo is not None

    def test_naive_gets_utc(self):
        dt = _parse_timestamp("2026-02-20T10:00:00")
        assert dt.tzinfo is not None


class TestIsMetaMessage:
    def test_local_command_caveat(self):
        assert _is_meta_message("<local-command-caveat>test</local-command-caveat>")

    def test_command_name(self):
        assert _is_meta_message("<command-name>/exit</command-name>")

    def test_local_command_stdout(self):
        assert _is_meta_message("<local-command-stdout>output</local-command-stdout>")

    def test_normal_message(self):
        assert not _is_meta_message("Fix the bug in auth.py")

    def test_whitespace(self):
        assert _is_meta_message("  <local-command-caveat>test</local-command-caveat>")


class TestIsToolResultOnly:
    def test_pure_tool_results(self):
        content = [
            {"type": "tool_result", "tool_use_id": "t1", "content": "ok"},
        ]
        assert _is_tool_result_only(content)

    def test_mixed_content(self):
        content = [
            {"type": "text", "text": "hello"},
            {"type": "tool_result", "tool_use_id": "t1", "content": "ok"},
        ]
        assert not _is_tool_result_only(content)

    def test_string_content(self):
        assert not _is_tool_result_only("hello")

    def test_empty_list(self):
        assert _is_tool_result_only([])


class TestExtractToolResults:
    def test_simple_result(self):
        content = [
            {
                "type": "tool_result",
                "tool_use_id": "t1",
                "content": "output",
                "is_error": False,
            },
        ]
        results = _extract_tool_results(content)
        assert len(results) == 1
        assert results[0].tool_use_id == "t1"
        assert results[0].content == "output"
        assert results[0].is_error is False

    def test_error_result(self):
        content = [
            {
                "type": "tool_result",
                "tool_use_id": "t1",
                "content": "FAILED",
                "is_error": True,
            },
        ]
        results = _extract_tool_results(content)
        assert results[0].is_error is True

    def test_list_content(self):
        content = [
            {
                "type": "tool_result",
                "tool_use_id": "t1",
                "content": [
                    {"type": "text", "text": "line1"},
                    {"type": "text", "text": "line2"},
                ],
            },
        ]
        results = _extract_tool_results(content)
        assert "line1" in results[0].content
        assert "line2" in results[0].content


class TestExtractUserText:
    def test_string_content(self):
        assert _extract_user_text("Fix the bug") == "Fix the bug"

    def test_meta_message_returns_none(self):
        assert (
            _extract_user_text("<local-command-caveat>test</local-command-caveat>")
            is None
        )

    def test_empty_string(self):
        assert _extract_user_text("") is None

    def test_list_with_text_blocks(self):
        content = [{"type": "text", "text": "hello"}]
        assert _extract_user_text(content) == "hello"

    def test_list_with_tool_results_skipped(self):
        content = [
            {"type": "text", "text": "context"},
            {"type": "tool_result", "tool_use_id": "t1", "content": "result"},
        ]
        assert _extract_user_text(content) == "context"

    def test_list_with_only_tool_results(self):
        content = [{"type": "tool_result", "tool_use_id": "t1", "content": "result"}]
        assert _extract_user_text(content) is None

    def test_list_with_string_items(self):
        content = ["hello", "world"]
        assert _extract_user_text(content) == "hello\nworld"

    def test_none_content(self):
        assert _extract_user_text(None) is None

    def test_integer_content(self):
        assert _extract_user_text(42) is None


class TestParseSession:
    def test_full_session(self):
        session = parse_session(FIXTURES / "full_session.jsonl")
        assert session.session_id == "full_session"
        assert session.cwd == "/home/user/project"
        assert session.git_branch == "main"
        assert session.start_time.year == 2026

        # Should have real turns with user prompts
        real_turns = [t for t in session.turns if t.user_prompt]
        assert len(real_turns) >= 2
        assert real_turns[0].user_prompt == "Fix the login bug in auth.py"

        # Check tool calls were parsed
        all_tool_calls = []
        for t in session.turns:
            all_tool_calls.extend(t.tool_calls)
        tool_names = {tc.name for tc in all_tool_calls}
        assert "Read" in tool_names
        assert "Edit" in tool_names
        assert "Bash" in tool_names
        assert "Write" in tool_names
        assert "Glob" in tool_names
        assert "Grep" in tool_names

    def test_with_compaction(self):
        session = parse_session(FIXTURES / "with_compaction.jsonl")
        # Should have compact boundary markers
        boundary_turns = [t for t in session.turns if t.compact_boundary]
        assert len(boundary_turns) == 1

        # Real turns should be on both sides
        real_turns = [
            t for t in session.turns if not t.compact_boundary and t.user_prompt
        ]
        assert len(real_turns) == 2
        assert real_turns[0].user_prompt == "Explain the config module"
        assert real_turns[1].user_prompt == "Now add logging"

    def test_noise_only_session(self):
        session = parse_session(FIXTURES / "noise_only.jsonl")
        assert len(session.turns) == 0

    def test_meta_messages_filtered(self):
        session = parse_session(FIXTURES / "meta_messages.jsonl")
        prompts = [t.user_prompt for t in session.turns if t.user_prompt]
        assert "A real user prompt after meta messages" in prompts
        # Meta messages should not appear as prompts
        for p in prompts:
            assert not p.startswith("<local-command-")
            assert not p.startswith("<command-name>")

    def test_mixed_content(self):
        session = parse_session(FIXTURES / "mixed_content.jsonl")
        # The user message has both text and tool_result
        turn = session.turns[0]
        assert turn.user_prompt == "Here is some context"
        assert len(turn.tool_results) >= 1

    def test_error_results(self):
        session = parse_session(FIXTURES / "error_result.jsonl")
        # Find the turn with the error result
        error_results = []
        for t in session.turns:
            for tr in t.tool_results:
                if tr.is_error:
                    error_results.append(tr)
        assert len(error_results) == 1
        assert "FAILED" in error_results[0].content

    def test_turn_duration_system_message(self):
        session = parse_session(FIXTURES / "turn_duration.jsonl")
        # turn_duration system messages should not create turns
        assert all(not t.compact_boundary for t in session.turns)

    def test_assistant_text_merging(self):
        session = parse_session(FIXTURES / "full_session.jsonl")
        # First turn should have merged assistant text from thinking + text blocks
        first_turn_with_assistant = None
        for t in session.turns:
            if t.assistant_text:
                first_turn_with_assistant = t
                break
        assert first_turn_with_assistant is not None
        assert "fix" in first_turn_with_assistant.assistant_text.lower()

    def test_session_project_from_dirname(self):
        session = parse_session(FIXTURES / "full_session.jsonl")
        assert session.project == "fixtures"

    def test_nonexistent_file_raises(self):
        import pytest

        with pytest.raises(FileNotFoundError):
            parse_session(FIXTURES / "does_not_exist.jsonl")

    def test_empty_file(self):
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("")
            tmp_path = Path(f.name)
        try:
            session = parse_session(tmp_path)
            assert len(session.turns) == 0
        finally:
            tmp_path.unlink()

    def test_malformed_json_lines_skipped(self):
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("not valid json\n")
            f.write(
                '{"type": "user", "cwd": "/tmp", "sessionId": "test", "message": {"role": "user", "content": "hello"}, "uuid": "u1", "timestamp": "2026-02-20T10:00:00.000Z"}\n'
            )
            tmp_path = Path(f.name)
        try:
            session = parse_session(tmp_path)
            prompts = [t.user_prompt for t in session.turns if t.user_prompt]
            assert "hello" in prompts
        finally:
            tmp_path.unlink()

    def test_assistant_before_any_user_message(self):
        """Assistant messages arriving before any user message should create their own turn."""
        session = parse_session(FIXTURES / "assistant_first.jsonl")
        # Should handle assistant-first gracefully without crashing
        assert session.session_id == "assistant_first"
        # The assistant text should be captured even without a preceding user message
        assistant_texts = [t.assistant_text for t in session.turns if t.assistant_text]
        assert any("Starting up" in t for t in assistant_texts)

    def test_non_list_assistant_content_skipped(self):
        """Assistant content that isn't a list (string instead) should be skipped gracefully."""
        session = parse_session(FIXTURES / "assistant_first.jsonl")
        # The second record has content="not a list" — shouldn't crash
        assert session is not None

    def test_non_dict_block_in_assistant_content(self):
        """Non-dict items in assistant content list (e.g. integers) should be skipped."""
        session = parse_session(FIXTURES / "assistant_first.jsonl")
        # The first record has a 42 integer in the content list — shouldn't crash
        assert session is not None

    def test_unknown_tool_in_tool_calls(self):
        """Tool calls with unknown tool names should be captured."""
        session = parse_session(FIXTURES / "assistant_first.jsonl")
        all_tools = []
        for t in session.turns:
            all_tools.extend(tc.name for tc in t.tool_calls)
        assert "SomeUnknownTool" in all_tools

    def test_file_with_blank_lines(self):
        """Blank lines in JSONL files should be silently skipped."""
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("\n")
            f.write(
                '{"type": "user", "cwd": "/tmp", "sessionId": "test", "message": {"role": "user", "content": "after blank"}, "uuid": "u1", "timestamp": "2026-02-20T10:00:00.000Z"}\n'
            )
            f.write("\n")
            tmp_path = Path(f.name)
        try:
            session = parse_session(tmp_path)
            prompts = [t.user_prompt for t in session.turns if t.user_prompt]
            assert "after blank" in prompts
        finally:
            tmp_path.unlink()
