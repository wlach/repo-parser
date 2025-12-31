"""
Tests for the CLI module.
"""

from datetime import datetime
from unittest.mock import patch

import git
import pytest
from typer.testing import CliRunner

from repo_parser.cli import (
    _get_git_author,
    _get_repo_root,
    _load_template,
    _strip_html_comments,
    app,
)

runner = CliRunner()


class TestGetGitAuthor:
    """Tests for _get_git_author function."""

    def test_get_git_author_success(self):
        """Test getting author from git config."""
        with patch("repo_parser.cli.git.GitConfigParser") as mock_parser:
            mock_instance = mock_parser.return_value
            mock_instance.get_value.side_effect = lambda _section, key: {
                "name": "Test Author",
                "email": "test@example.com",
            }[key]

            author = _get_git_author()
            assert author == "Test Author <test@example.com>"

    def test_get_git_author_no_config(self):
        """Test fallback when git config is not available."""
        with patch("repo_parser.cli.git.GitConfigParser") as mock_parser:
            mock_instance = mock_parser.return_value
            mock_instance.get_value.side_effect = KeyError

            author = _get_git_author()
            assert author == "Unknown"


class TestGetRepoRoot:
    """Tests for _get_repo_root function."""

    def test_get_repo_root_success(self, tmp_path):
        """Test getting repository root."""
        git.Repo.init(tmp_path)

        with patch("repo_parser.cli.git.Repo") as mock_repo:
            mock_instance = mock_repo.return_value
            mock_instance.working_dir = str(tmp_path)

            root = _get_repo_root()
            assert root == tmp_path

    def test_get_repo_root_not_in_repo(self):
        """Test error when not in a git repository."""
        with patch("repo_parser.cli.git.Repo") as mock_repo:
            mock_repo.side_effect = git.InvalidGitRepositoryError

            # typer.Exit is different from SystemExit
            from click.exceptions import Exit

            with pytest.raises(Exit):
                _get_repo_root()


class TestLoadTemplate:
    """Tests for _load_template function."""

    def test_load_template_success(self):
        """Test loading the IDR template."""
        template = _load_template()

        assert "{{ title }}" in template
        assert "{{ author }}" in template
        assert "## Implementation (ephemeral)" in template


class TestStripHtmlComments:
    """Tests for _strip_html_comments function."""

    def test_strip_single_line_comment(self):
        """Test stripping a single-line HTML comment."""
        text = "Before\n<!-- This is a comment -->\nAfter"
        result = _strip_html_comments(text)
        assert "<!--" not in result
        assert "This is a comment" not in result
        assert "Before" in result
        assert "After" in result

    def test_strip_multiline_comment(self):
        """Test stripping a multiline HTML comment."""
        text = """Before
<!--
This is a
multiline comment
-->
After"""
        result = _strip_html_comments(text)
        assert "<!--" not in result
        assert "multiline comment" not in result
        assert "Before" in result
        assert "After" in result

    def test_strip_multiple_comments(self):
        """Test stripping multiple HTML comments."""
        text = "<!-- Comment 1 -->\nText\n<!-- Comment 2 -->"
        result = _strip_html_comments(text)
        assert "<!--" not in result
        assert "Comment 1" not in result
        assert "Comment 2" not in result
        assert "Text" in result

    def test_clean_up_blank_lines(self):
        """Test that excessive blank lines are cleaned up."""
        text = "Line 1\n\n\n\n\nLine 2"
        result = _strip_html_comments(text)
        assert result == "Line 1\n\nLine 2"

    def test_strip_comment_on_own_line(self):
        """Test that removing a comment on its own line doesn't leave extra blank lines."""
        text = """Line 1

<!-- Comment on its own line -->

Line 2"""
        result = _strip_html_comments(text)
        # Should have at most one blank line between Line 1 and Line 2
        assert result == "Line 1\n\nLine 2"

    def test_strip_whitespace_only_lines(self):
        """Test that whitespace-only lines are normalized."""
        text = "Line 1\n  \n\t\nLine 2"
        result = _strip_html_comments(text)
        assert result == "Line 1\n\nLine 2"

    def test_strip_leading_trailing_whitespace(self):
        """Test that leading and trailing whitespace is removed."""
        text = "\n\n  Content  \n\n"
        result = _strip_html_comments(text)
        assert result == "Content"


class TestIdrNew:
    """Tests for idr new command."""

    def test_idr_new_creates_file_with_correct_content(self, tmp_path):
        """Test that idr new creates a properly formatted file."""
        git.Repo.init(tmp_path)

        with (
            patch("repo_parser.cli._get_repo_root") as mock_root,
            patch("repo_parser.cli._get_git_author") as mock_author,
        ):
            mock_root.return_value = tmp_path
            mock_author.return_value = "Test Author <test@example.com>"

            result = runner.invoke(app, ["idr", "new", "Add Cool Feature"])

            assert result.exit_code == 0
            assert "Created IDR:" in result.stdout
            # Should not show tip in output anymore
            assert "Tip:" not in result.stdout

            # Check file was created with slugified name
            idrs_dir = tmp_path / "idrs"
            assert idrs_dir.exists()
            idr_files = list(idrs_dir.glob("*-add-cool-feature.md"))
            assert len(idr_files) == 1

            # Check content is correctly rendered
            content = idr_files[0].read_text()
            assert "# Add Cool Feature" in content
            assert "Owner: Test Author <test@example.com>" in content
            assert "## Implementation (ephemeral)" in content
            # Should have comments by default
            assert "<!--" in content

    def test_idr_new_with_no_comments_flag(self, tmp_path):
        """Test that --no-comments flag strips HTML comments."""
        git.Repo.init(tmp_path)

        with (
            patch("repo_parser.cli._get_repo_root") as mock_root,
            patch("repo_parser.cli._get_git_author") as mock_author,
        ):
            mock_root.return_value = tmp_path
            mock_author.return_value = "Test Author <test@example.com>"

            result = runner.invoke(
                app, ["idr", "new", "Clean Feature", "--no-comments"]
            )

            assert result.exit_code == 0
            assert "Created IDR:" in result.stdout
            # No tip message in any case
            assert "Tip:" not in result.stdout

            # Check file was created
            idrs_dir = tmp_path / "idrs"
            idr_files = list(idrs_dir.glob("*-clean-feature.md"))
            assert len(idr_files) == 1

            # Check content has no comments
            content = idr_files[0].read_text()
            assert "# Clean Feature" in content
            assert "Owner: Test Author <test@example.com>" in content
            assert "<!--" not in content
            assert "-->" not in content

    def test_idr_new_with_env_variable(self, tmp_path):
        """Test that RP_IDR_NO_COMMENTS environment variable works."""
        git.Repo.init(tmp_path)

        with (
            patch("repo_parser.cli._get_repo_root") as mock_root,
            patch("repo_parser.cli._get_git_author") as mock_author,
            patch.dict("os.environ", {"RP_IDR_NO_COMMENTS": "1"}),
        ):
            mock_root.return_value = tmp_path
            mock_author.return_value = "Test Author <test@example.com>"

            result = runner.invoke(app, ["idr", "new", "Env Feature"])

            assert result.exit_code == 0

            # Check content has no comments due to env var
            idrs_dir = tmp_path / "idrs"
            idr_files = list(idrs_dir.glob("*-env-feature.md"))
            assert len(idr_files) == 1

            content = idr_files[0].read_text()
            assert "<!--" not in content

    def test_idr_new_error_cases(self, tmp_path):
        """Test error handling for common cases."""
        # Test: not in a git repository
        with patch("repo_parser.cli._get_repo_root", side_effect=SystemExit(1)):
            result = runner.invoke(app, ["idr", "new", "Test"])
            assert result.exit_code == 1

        # Test: file already exists
        git.Repo.init(tmp_path)
        idrs_dir = tmp_path / "idrs"
        idrs_dir.mkdir()
        existing_file = idrs_dir / "202512301600-test.md"
        existing_file.write_text("existing")

        with (
            patch("repo_parser.cli._get_repo_root") as mock_root,
            patch("repo_parser.cli.datetime") as mock_datetime,
        ):
            mock_root.return_value = tmp_path
            fixed_time = datetime(2025, 12, 30, 16, 0, 0)
            mock_datetime.now.return_value = fixed_time
            mock_datetime.strftime = datetime.strftime

            result = runner.invoke(app, ["idr", "new", "Test"])
            assert result.exit_code == 1
