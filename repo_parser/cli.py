"""
Command-line interface for repo-parser.
"""

import pathlib
from datetime import datetime, timezone
from importlib import resources

import git
import jinja2
import typer
from slugify import slugify

app = typer.Typer(help="repo-parser CLI tools")
idr_app = typer.Typer(help="IDR (Implementation Decision Record) commands")
app.add_typer(idr_app, name="idr")


def _get_git_author() -> str:
    """
    Get the author name from git config.
    
    Returns:
        Author name from git config user.name, or "Unknown" if not set.
    """
    try:
        # Read from global git config (doesn't require being in a repo)
        config = git.GitConfigParser([git.config.get_config_path("global")], read_only=True)
        return config.get_value("user", "name")
    except (KeyError, ValueError, OSError, git.GitCommandNotFound):
        # Config file doesn't exist, user.name not set, or git not installed
        typer.echo(
            "Warning: Could not read git config user.name, using 'Unknown' as author",
            err=True,
        )
        return "Unknown"


def _get_repo_root() -> pathlib.Path:
    """
    Get the root directory of the git repository.
    
    Returns:
        Path to repository root.
        
    Raises:
        typer.Exit: If not in a git repository.
    """
    try:
        repo = git.Repo(search_parent_directories=True)
        return pathlib.Path(repo.working_dir)
    except git.InvalidGitRepositoryError as e:
        typer.echo("Error: Not in a git repository", err=True)
        raise typer.Exit(1) from e


def _load_template() -> str:
    """
    Load the IDR template from package resources.
    
    Returns:
        Template content as string.
    """
    # Python 3.11+ uses importlib.resources.files
    template_path = resources.files("repo_parser").joinpath("templates/idr.md")
    return template_path.read_text()


@idr_app.command("new")
def idr_new(title: str):
    """
    Create a new IDR (Implementation Decision Record).
    
    Creates a new IDR file in the idrs/ directory with a timestamp and slugified title.
    Example: rp idr new "Add last modified metadata"
    """
    repo_root = _get_repo_root()
    
    # Create idrs directory if it doesn't exist
    idrs_dir = repo_root / "idrs"
    idrs_dir.mkdir(exist_ok=True)
    
    # Generate timestamp in UTC
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    
    # Slugify the title
    slug = slugify(title)
    
    # Create filename
    filename = f"{timestamp}-{slug}.md"
    filepath = idrs_dir / filename
    
    # Check if file already exists (realistically should not happen)
    if filepath.exists():
        typer.echo(f"Error: File already exists: {filepath}", err=True)
        raise typer.Exit(1)
    
    # Get author from git config
    author = _get_git_author()
    
    # Load and render template
    template_content = _load_template()
    template = jinja2.Template(template_content)
    rendered = template.render(title=title, author=author)
    
    # Write file
    filepath.write_text(rendered)
    
    typer.echo(f"Created IDR: {filepath}")


if __name__ == "__main__":
    app()
