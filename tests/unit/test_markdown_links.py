from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_markdown_links.py"


def _check(root: Path, files: dict[str, str]) -> subprocess.CompletedProcess[str]:
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "--", *files], check=True)
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_checks_relative_root_encoded_image_and_balanced_targets(tmp_path: Path) -> None:
    result = _check(
        tmp_path,
        {
            "docs/README.md": (
                "[Space](../with%20space.md)\n"
                "[Angle](<../with space.md>)\n"
                "[Parens](../notes(one).md)\n"
                "[Escaped](../notes\\(one\\).md)\n"
                "![Image](/assets/figure%23one.svg)\n"
                "[Directory](../assets/)\n"
            ),
            "with space.md": "# Notes\n",
            "notes(one).md": "# Notes\n",
            "assets/figure#one.svg": "<svg/>\n",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "6 local links" in result.stdout


def test_reports_historical_missing_targets_with_source_line(tmp_path: Path) -> None:
    result = _check(
        tmp_path,
        {"docs/history/README.md": "# History\n\n[Original](missing.md)\n"},
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "docs/history/README.md:3:" in result.stdout
    assert "missing.md" in result.stdout
    assert "missing target" in result.stdout


def test_validates_gfm_unicode_duplicate_setext_and_explicit_anchors(tmp_path: Path) -> None:
    result = _check(
        tmp_path,
        {
            "README.md": (
                "[Unicode](guide.md#caf%C3%A9--costs)\n"
                "[Duplicate](guide.md#repeat-1)\n"
                "[Collision](guide.md#repeat-1-1)\n"
                "[Setext](guide.md#appendix-a)\n"
                "[Markup](guide.md#use-code-and-links)\n"
                "[Explicit](guide.md#custom.section)\n"
            ),
            "guide.md": (
                "# Café & Costs\n# Repeat\n# Repeat\n# Repeat-1\n\n"
                "Appendix <em>A</em>\n-------------------\n\n"
                "## Use `code` and [links](https://example.com) ##\n"
                '<a id="custom.section"></a>\n'
            ),
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "6 local links" in result.stdout


def test_reports_missing_fragment_even_when_file_exists(tmp_path: Path) -> None:
    result = _check(
        tmp_path,
        {"README.md": "[Section](guide.md#absent)\n", "guide.md": "# Present\n"},
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "README.md:1:" in result.stdout
    assert "missing fragment" in result.stdout


def test_ignores_code_comments_escaped_links_and_external_schemes(tmp_path: Path) -> None:
    result = _check(
        tmp_path,
        {
            "README.md": (
                "````md\n[Missing](missing.md)\n```\n[Still code](missing.md)\n````\n"
                "~~~\n[Missing](missing.md)\n~~~\n"
                "    [Indented](missing.md)\n"
                "`[Inline](missing.md)` and ``[Other](missing.md)``\n"
                "<!-- [Comment](missing.md) -->\n"
                "\\[Escaped](missing.md)\n"
                "[External](https://example.com/missing.md)\n"
                "[Email](mailto:research@example.com)\n"
                "[Protocol](//example.com/missing.md)\n"
                "[Present](present.txt)\n"
            ),
            "present.txt": "exists\n",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 local links" in result.stdout


def test_checks_full_collapsed_shortcut_and_multiline_reference_links(tmp_path: Path) -> None:
    result = _check(
        tmp_path,
        {
            "README.md": (
                "[First][KEY] [key][] [key]\n"
                "[second]\n\n"
                '[key]: guide.md#heading "Title"\n'
                "[second]:\n  <guide.md#heading>\n"
            ),
            "guide.md": "# Heading\n",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "4 local links" in result.stdout


def test_checks_html_links_and_local_html_fragments(tmp_path: Path) -> None:
    result = _check(
        tmp_path,
        {
            "README.md": '<a href="page.html#details">Details</a>\n<img src="figure.svg">\n',
            "page.html": '<h2 id="details">Details</h2>\n',
            "figure.svg": "<svg/>\n",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 local links" in result.stdout


def test_does_not_invent_heading_anchors_inside_code(tmp_path: Path) -> None:
    result = _check(
        tmp_path,
        {"README.md": "[Missing](#fake)\n\n```md\n# Fake\n```\n"},
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "missing fragment" in result.stdout


def test_heading_anchors_remove_emphasis_and_join_setext_lines(tmp_path: Path) -> None:
    result = _check(
        tmp_path,
        {
            "README.md": (
                "[Emphasis](guide.md#emphasized-and-literal_under_score)\n"
                "[Multiline](guide.md#first-linesecond-line)\n"
            ),
            "guide.md": (
                "# _Emphasized_ and literal_under_score\n\nFirst line\nsecond line\n===========\n"
            ),
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_non_document_fragments_are_reported_without_claiming_validation(tmp_path: Path) -> None:
    result = _check(
        tmp_path,
        {"README.md": "[Source](source.py#L1)\n", "source.py": "pass\n"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "unchecked non-document fragment: source.py#L1" in result.stdout
    assert "1 unchecked non-document fragments" in result.stdout


def test_only_discovers_tracked_markdown_files(tmp_path: Path) -> None:
    (tmp_path / "untracked.md").write_text("[Broken](absent.md)\n", encoding="utf-8")
    result = _check(tmp_path, {"README.md": "# Tracked\n"})
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 Markdown files" in result.stdout


def test_refuses_to_claim_success_outside_git_repository(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "Cannot enumerate tracked Markdown" in result.stderr
