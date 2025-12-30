"""
Tests for the CLI module.
"""

from datetime import datetime
from unittest.mock import patch

import git
import pytest
from typer.testing import CliRunner

from repo_parser.cli import _get_git_author, _get_repo_root, _load_template, app

runner = CliRunner()


class TestGetGitAuthor:
    """Tests for _get_git_author function."""

    def test_get_git_author_success(self):
        """Test getting author from git config."""
        with patch("repo_parser.cli.git.GitConfigParser") as mock_parser:
            mock_instance = mock_parser.return_value
            mock_instance.get_value.return_value = "Test Author"
            
            author = _get_git_author()
            assert author == "Test Author"

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


class TestIdrNew:
    """Tests for idr new command."""

    def test_idr_new_creates_file_with_correct_content(self, tmp_path):
        """Test that idr new creates a properly formatted file."""
        git.Repo.init(tmp_path)
        
        with patch("repo_parser.cli._get_repo_root") as mock_root, \
             patch("repo_parser.cli._get_git_author") as mock_author:
            mock_root.return_value = tmp_path
            mock_author.return_value = "Test Author"
            
            result = runner.invoke(app, ["idr", "new", "Add Cool Feature"])
            
            assert result.exit_code == 0
            assert "Created IDR:" in result.stdout
            
            # Check file was created with slugified name
            idrs_dir = tmp_path / "idrs"
            assert idrs_dir.exists()
            idr_files = list(idrs_dir.glob("*-add-cool-feature.md"))
            assert len(idr_files) == 1
            
            # Check content is correctly rendered
            content = idr_files[0].read_text()
            assert "# Add Cool Feature" in content
            assert "Author: Test Author" in content
            assert "## Implementation (ephemeral)" in content

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
        
        with patch("repo_parser.cli._get_repo_root") as mock_root, \
             patch("repo_parser.cli.datetime") as mock_datetime:
            mock_root.return_value = tmp_path
            fixed_time = datetime(2025, 12, 30, 16, 0, 0)
            mock_datetime.now.return_value = fixed_time
            mock_datetime.strftime = datetime.strftime
            
            result = runner.invoke(app, ["idr", "new", "Test"])
            assert result.exit_code == 1
