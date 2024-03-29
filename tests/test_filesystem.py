import tempfile
from pathlib import Path, PurePath

import git

from repo_parser.filesystem import Dir, File, scan
from repo_parser.processor import DEFAULT_PROCESSORS


def test_scan():
    # create a temporary test directory with a bunch of content
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        (tmpdir / "README.md").write_text("This is a test")
        (tmpdir / ".gitignore").write_text("ignored_dir\n")
        (tmpdir / "ignored_dir").mkdir()
        (tmpdir / "ignored_dir" / "README.md").write_text("This file should be ignored")
        (tmpdir / "service-example").mkdir()
        (tmpdir / "service-example" / "README.md").write_text(
            "---\ntype: service\nlanguage: python\n---\nThis is a service"
        )
        (tmpdir / "service-example" / "service.py").write_text("print('hello world')")
        repo = git.Repo.init(tmpdir)
        repo.index.add(["."])
        repo.index.commit("initial commit")

        # scan the directory
        assert scan(tmpdir, DEFAULT_PROCESSORS) == Dir(
            path=PurePath(tmpdir),
            files=[
                File(
                    name="README.md",
                    src_path=(PurePath(tmpdir) / "README.md"),
                    content="This is a test",
                ),
            ],
            dirs=[
                Dir(
                    path=PurePath(tmpdir) / "service-example",
                    files=[
                        File(
                            name="README.md",
                            src_path=(
                                PurePath(tmpdir) / "service-example" / "README.md"
                            ),
                            content="---\ntype: service\nlanguage: python\n---\nThis is a service",
                        ),
                    ],
                    dirs=[],
                )
            ],
        )
