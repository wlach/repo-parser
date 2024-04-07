import tempfile
from pathlib import Path, PurePath

import git
from pytest_unordered import unordered

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
        (tmpdir / "service-example1").mkdir()
        (tmpdir / "service-example1" / "README.md").write_text(
            "---\ntype: service\nlanguage: python\n---\nThis is service 1"
        )
        (tmpdir / "service-example1" / "service.py").write_text(
            "print('hello world 1')"
        )
        (tmpdir / "service-example2").mkdir()
        (tmpdir / "service-example2" / "README.md").write_text(
            "---\ntype: service\nlanguage: python\n---\nThis is service 2"
        )
        (tmpdir / "service-example2" / "service.py").write_text(
            "print('hello world 2')"
        )
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
            dirs=unordered(
                [
                    Dir(
                        path=PurePath(tmpdir) / subdir,
                        files=[
                            File(
                                name="README.md",
                                src_path=(PurePath(tmpdir) / subdir / "README.md"),
                                content=f"---\ntype: service\nlanguage: python\n---\n{readme_content}",
                            ),
                        ],
                        dirs=[],
                    )
                    for (subdir, readme_content) in [
                        ("service-example1", "This is service 1"),
                        ("service-example2", "This is service 2"),
                    ]
                ]
            ),
        )

        # Test only looking in one subdirectory
        assert scan(tmpdir, DEFAULT_PROCESSORS, subdirs=["service-example1"]) == Dir(
            path=PurePath(tmpdir),
            files=[],
            dirs=[
                Dir(
                    path=PurePath(tmpdir) / "service-example1",
                    files=[
                        File(
                            name="README.md",
                            src_path=(
                                PurePath(tmpdir) / "service-example1" / "README.md"
                            ),
                            content="---\ntype: service\nlanguage: python\n---\nThis is service 1",
                        ),
                    ],
                    dirs=[],
                )
            ],
        )
