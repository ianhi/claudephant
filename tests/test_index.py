"""Tests for the index builder."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from claudephant.index import build_index, find_session, summarize_session
from claudephant.parser import parse_session

FIXTURES = Path(__file__).parent / "fixtures"


class TestSummarizeSession:
    def test_full_session_summary(self):
        session = parse_session(FIXTURES / "full_session.jsonl")
        summary = summarize_session(session)
        assert summary.session_id == "full_session"
        assert summary.project == "fixtures"
        assert summary.git_branch == "main"
        assert summary.num_turns > 0
        assert "Fix the login bug" in summary.first_prompt
        assert len(summary.user_prompts) >= 2
        assert "Edit" in summary.tools_used
        assert "Read" in summary.tools_used
        assert "Bash" in summary.tools_used
        assert "Write" in summary.tools_used
        assert "/home/user/project/auth.py" in summary.files_modified
        assert "/home/user/project/config.yaml" in summary.files_modified

    def test_compaction_session_excludes_boundary_turns(self):
        session = parse_session(FIXTURES / "with_compaction.jsonl")
        summary = summarize_session(session)
        # num_turns should not count compact boundary markers
        assert summary.num_turns == len(
            [t for t in session.turns if not t.compact_boundary]
        )

    def test_noise_only_session(self):
        session = parse_session(FIXTURES / "noise_only.jsonl")
        summary = summarize_session(session)
        assert summary.num_turns == 0
        assert summary.first_prompt == ""
        assert len(summary.user_prompts) == 0


class TestBuildIndex:
    def test_build_from_fixtures(self):
        # Set up a temp dir structure mimicking ~/.claude/projects/<project>/
        with tempfile.TemporaryDirectory() as tmp:
            projects_dir = Path(tmp) / "projects" / "test-project"
            projects_dir.mkdir(parents=True)

            # Copy a fixture file in
            import shutil

            shutil.copy(
                FIXTURES / "full_session.jsonl",
                projects_dir / "aaaa1111-2222-3333-4444-555566667777.jsonl",
            )

            summaries = build_index(claude_dir=Path(tmp))
            assert len(summaries) == 1
            assert summaries[0].session_id == "aaaa1111-2222-3333-4444-555566667777"
            assert summaries[0].project == "test-project"

    def test_project_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj_a = Path(tmp) / "projects" / "project-alpha"
            proj_b = Path(tmp) / "projects" / "project-beta"
            proj_a.mkdir(parents=True)
            proj_b.mkdir(parents=True)

            import shutil

            shutil.copy(
                FIXTURES / "full_session.jsonl",
                proj_a / "sess-a.jsonl",
            )
            shutil.copy(
                FIXTURES / "with_compaction.jsonl",
                proj_b / "sess-b.jsonl",
            )

            # Filter for alpha only
            summaries = build_index(claude_dir=Path(tmp), project_filter="alpha")
            assert len(summaries) == 1
            assert summaries[0].project == "project-alpha"

    def test_since_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            projects_dir = Path(tmp) / "projects" / "test-project"
            projects_dir.mkdir(parents=True)

            import shutil

            shutil.copy(
                FIXTURES / "full_session.jsonl",
                projects_dir / "test.jsonl",
            )

            # Session is from 2026-02-20, filter to after 2026-03-01
            future_dt = datetime(2026, 3, 1, tzinfo=timezone.utc)
            summaries = build_index(claude_dir=Path(tmp), since=future_dt)
            assert len(summaries) == 0

            # Filter to before the session
            past_dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
            summaries = build_index(claude_dir=Path(tmp), since=past_dt)
            assert len(summaries) == 1

    def test_nonexistent_dir(self):
        summaries = build_index(claude_dir=Path("/nonexistent/path"))
        assert summaries == []

    def test_sorted_by_start_time_descending(self):
        with tempfile.TemporaryDirectory() as tmp:
            projects_dir = Path(tmp) / "projects" / "test-project"
            projects_dir.mkdir(parents=True)

            import shutil

            # full_session is at 10:00, with_compaction is at 09:00
            shutil.copy(FIXTURES / "full_session.jsonl", projects_dir / "newer.jsonl")
            shutil.copy(
                FIXTURES / "with_compaction.jsonl", projects_dir / "older.jsonl"
            )

            summaries = build_index(claude_dir=Path(tmp))
            assert len(summaries) == 2
            assert summaries[0].start_time >= summaries[1].start_time


class TestFindSession:
    def test_find_by_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            projects_dir = Path(tmp) / "projects" / "test-project"
            projects_dir.mkdir(parents=True)

            import shutil

            shutil.copy(
                FIXTURES / "full_session.jsonl",
                projects_dir / "aaaa1111-2222-3333-4444-555566667777.jsonl",
            )

            session = find_session("aaaa1111", claude_dir=Path(tmp))
            assert session is not None
            assert session.session_id == "aaaa1111-2222-3333-4444-555566667777"

    def test_find_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            projects_dir = Path(tmp) / "projects" / "test-project"
            projects_dir.mkdir(parents=True)

            session = find_session("zzzzzzzz", claude_dir=Path(tmp))
            assert session is None

    def test_find_nonexistent_dir(self):
        session = find_session("anything", claude_dir=Path("/nonexistent/path"))
        assert session is None
