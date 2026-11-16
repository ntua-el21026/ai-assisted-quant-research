#!/usr/bin/env python3
"""Check tracked Markdown local paths and Markdown/HTML fragments without network access.

Supports inline/image/reference links, HTML href/src attributes, ATX/setext GFM
heading slugs (including duplicates), and explicit HTML id/name anchors. Code
blocks, inline code and HTML comments are excluded. Fragments in non-Markdown,
non-HTML files are provider-specific and are reported as unchecked; their paths
are still checked. Historical documents receive exactly the same checks.
"""

from __future__ import annotations

import argparse
import html
import re
import subprocess
import sys
import unicodedata
from collections.abc import Iterator
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


def _blank(text: str) -> str:
    return "".join("\n" if character == "\n" else " " for character in text)


def _prose(text: str, *, inline_code: bool = True) -> str:
    """Mask non-prose while retaining source line numbers and character offsets."""
    lines: list[str] = []
    fence: str | None = None
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence is not None:
            lines.append(_blank(line))
            if re.match(rf"^ {{0,3}}{re.escape(fence[0])}{{{len(fence)},}}\s*$", line):
                fence = None
        elif marker:
            fence = marker.group(1)
            lines.append(_blank(line))
        elif re.match(r"^(?: {4}|\t)", line):
            lines.append(_blank(line))
        else:
            lines.append(line)
    prose = re.sub(r"<!--[\s\S]*?(?:-->|\Z)", lambda match: _blank(match[0]), "".join(lines))
    if inline_code:
        prose = re.sub(
            r"(?<!`)(`+)(?!`)([\s\S]*?)(?<!`)\1(?!`)",
            lambda match: _blank(match[0]),
            prose,
        )
    return prose


def _escaped(text: str, position: int) -> bool:
    start = position
    while start > 0 and text[start - 1] == "\\":
        start -= 1
    return (position - start) % 2 == 1


def _unescape(text: str) -> str:
    return html.unescape(re.sub(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\]\\^_`{|}~])", r"\1", text))


def _destination(text: str, start: int) -> tuple[str, int] | None:
    start += len(text[start:]) - len(text[start:].lstrip())
    if start >= len(text):
        return None
    if text[start] == "<":
        end = start + 1
        while end < len(text):
            if text[end] == ">" and not _escaped(text, end):
                return _unescape(text[start + 1 : end]), end + 1
            if text[end] == "\n":
                return None
            end += 1
        return None
    depth = 0
    end = start
    while end < len(text):
        character = text[end]
        if not _escaped(text, end):
            if character.isspace() or (character == ")" and depth == 0):
                break
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
        end += 1
    if depth:
        return None
    return _unescape(text[start:end]), end


def _reference_key(label: str) -> str:
    return " ".join(_unescape(label).split()).casefold()


def _markdown_links(text: str) -> Iterator[tuple[int, str]]:
    prose = _prose(text)
    references: dict[str, str] = {}
    definition = re.compile(r"^ {0,3}\[([^\]\n]+)\]:[ \t]*(?:\n[ \t]*)?", re.MULTILINE)
    masked = list(prose)
    for match in definition.finditer(prose):
        destination = _destination(prose, match.end())
        if destination is None:
            continue
        reference_target, end = destination
        references.setdefault(_reference_key(match[1]), reference_target)
        end = prose.find("\n", end)
        if end < 0:
            end = len(prose)
        masked[match.start() : end] = _blank(prose[match.start() : end])
    prose = "".join(masked)
    cursor = 0
    while cursor < len(prose):
        start = prose.find("[", cursor)
        if start < 0:
            break
        cursor = start + 1
        if _escaped(prose, start):
            continue
        depth = 1
        end = start + 1
        while end < len(prose) and depth:
            if not _escaped(prose, end):
                if prose[end] == "[":
                    depth += 1
                elif prose[end] == "]":
                    depth -= 1
            end += 1
        if depth:
            continue
        label = prose[start + 1 : end - 1]
        target: str | None = None
        if end < len(prose) and prose[end] == "(":
            destination = _destination(prose, end + 1)
            if destination is not None:
                candidate, destination_end = destination
                closing = re.match(
                    r"""\s*(?:(?:"[^"\n]*"|'[^'\n]*'|\([^\n]*?\))\s*)?\)""",
                    prose[destination_end:],
                )
                if closing:
                    target = candidate
                    end = destination_end + closing.end()
        elif end < len(prose) and prose[end] == "[":
            reference_end = prose.find("]", end + 1)
            if reference_end >= 0:
                key = prose[end + 1 : reference_end] or label
                target = references.get(_reference_key(key))
                end = reference_end + 1
        else:
            target = references.get(_reference_key(label))
        if target is not None:
            yield prose.count("\n", 0, start) + 1, target
            cursor = end


class _HTMLTargets(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: set[str] = set()
        self.links: list[tuple[int, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if value is None:
                continue
            if name == "id" or (tag == "a" and name == "name"):
                self.anchors.add(value)
            if (tag == "a" and name == "href") or (tag == "img" and name == "src"):
                self.links.append((self.getpos()[0], value))


def _html_targets(text: str) -> _HTMLTargets:
    parser = _HTMLTargets()
    parser.feed(text)
    return parser


def _heading_slug(heading: str) -> str:
    code_spans: list[str] = []

    def preserve_code(match: re.Match[str]) -> str:
        code_spans.append(match[2])
        return f"\x00{len(code_spans) - 1}\x00"

    heading = re.sub(r"(`+)(.*?)\1", preserve_code, heading)
    heading = re.sub(r"<[^>]+>", "", heading)
    heading = re.sub(r"!?\[([^\]]+)\]\([^)]*\)", r"\1", heading)
    heading = re.sub(r"(?<!\w)_{1,3}(.+?)_{1,3}(?!\w)", r"\1", heading)
    for index, code in enumerate(code_spans):
        heading = heading.replace(f"\x00{index}\x00", code)
    heading = html.unescape(heading).lower()
    return "".join(
        character
        for character in heading
        if character in " -_" or unicodedata.category(character)[0] in "LMN"
    ).replace(" ", "-")


def _anchors(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".html", ".htm"}:
        return _html_targets(text).anchors
    prose = _prose(text, inline_code=False)
    anchors = _html_targets(_prose(text)).anchors
    lines = prose.splitlines()
    used: set[str] = set()
    for index, line in enumerate(lines):
        atx = re.match(r"^ {0,3}#{1,6}(?:\s+|$)(.*)$", line)
        if atx:
            heading = re.sub(r"\s+#+\s*$", "", atx[1]).strip()
        elif (
            index + 1 < len(lines)
            and line.strip()
            and re.fullmatch(r" {0,3}(?:=+|-+)\s*", lines[index + 1])
        ):
            start = index
            while start and lines[start - 1].strip():
                previous = lines[start - 1]
                if re.match(r"^ {0,3}(?:#{1,6}\s|>|[-+*] |\d+[.)] |(?:=+|-+)\s*$)", previous):
                    break
                start -= 1
            heading = "\n".join(lines[start : index + 1]).strip()
        else:
            continue
        base = _heading_slug(heading)
        slug = base
        suffix = 0
        while slug in used:
            suffix += 1
            slug = f"{base}-{suffix}"
        used.add(slug)
        anchors.add(slug)
    return anchors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    root = parser.parse_args(argv).root.resolve()
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"Cannot enumerate tracked Markdown: {type(exc).__name__}", file=sys.stderr)
        return 2
    paths = sorted(
        Path(name.decode("utf-8"))
        for name in result.stdout.split(b"\0")
        if name and Path(name.decode("utf-8")).suffix.lower() == ".md"
    )
    checked = 0
    failures = 0
    unchecked = 0
    anchor_cache: dict[Path, set[str]] = {}
    for relative in paths:
        path = root / relative
        try:
            text = path.read_text(encoding="utf-8")
            links = sorted([*_markdown_links(text), *_html_targets(_prose(text)).links])
            for line, target in links:
                url = urlsplit(target)
                if url.scheme or url.netloc:
                    continue
                checked += 1
                local_path = unquote(url.path)
                destination = (
                    root / local_path.lstrip("/")
                    if local_path.startswith("/")
                    else path.parent / local_path
                    if local_path
                    else path
                ).resolve()
                reason = ""
                if not destination.exists():
                    reason = "missing target"
                elif url.fragment and destination.is_file():
                    if destination.suffix.lower() in {".md", ".html", ".htm"}:
                        if destination not in anchor_cache:
                            anchor_cache[destination] = _anchors(destination)
                        if unquote(url.fragment) not in anchor_cache[destination]:
                            reason = "missing fragment"
                    else:
                        unchecked += 1
                        print(f"{relative}:{line}: unchecked non-document fragment: {target}")
                if reason:
                    failures += 1
                    print(f"{relative}:{line}: {reason}: {target}")
        except (OSError, UnicodeError, ValueError) as exc:
            failures += 1
            print(f"{relative}: cannot check document: {type(exc).__name__}")
    print(
        f"Checked {len(paths)} Markdown files, {checked} local links: "
        f"{failures} failures, {unchecked} unchecked non-document fragments."
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
