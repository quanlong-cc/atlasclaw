"""

YAML frontmatter parser

implement, Py-YAML.support SKILL.md in``---``YAML metadata.

support``key:value``for mat(``:``split),
support /,, BOM and Windows.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FrontmatterResult:
    """

Frontmatter parse

    Attributes:
        metadata:parse
        body:Frontmatter after content
    
"""

    metadata: dict[str, str] = field(default_factory=dict)
    body: str = ""


def parse_frontmatter(content: str) -> FrontmatterResult:
    """

parse Markdown YAML Frontmatter.

    Rules:
    1.``---``start with(BOM and), to``---``Frontmatter.
    2.``:``split; in contains.
    3. support``'...'``and``"..."``(parse).
    4.(``#...``)and.
    5.``---``or for mat, return metadata andraw content.

    Args:
        content:raw text

    Returns:
        FrontmatterResult
    
"""
    # handle:BOM,
    content = content.lstrip("\ufeff")
    content = content.replace("\r\n", "\n")

    lines = content.split("\n")

    # check --- start with
    if not lines or lines[0].strip() != "---":
        return FrontmatterResult(metadata={}, body=content)

    # ---
    close_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            close_idx = i
            break

    if close_idx == -1:
        # :return metadata + raw content
        return FrontmatterResult(metadata={}, body=content)

    # parse Frontmatter
    metadata: dict[str, str] = {}
    for line in lines[1:close_idx]:
        stripped = line.strip()

        # and
        if not stripped or stripped.startswith("#"):
            continue

        # :split
        colon_pos = stripped.find(":")
        if colon_pos == -1:
            continue

        key = stripped[:colon_pos].strip()
        value = stripped[colon_pos + 1 :].strip()

        # 
        if len(value) >= 2:
            if (value[0] == "'" and value[-1] == "'") or (
                value[0] == '"' and value[-1] == '"'
            ):
                value = value[1:-1]

        if key:
            metadata[key] = value

    # body --- aftercontent
    body_lines = lines[close_idx + 1 :]
    body = "\n".join(body_lines)

    return FrontmatterResult(metadata=metadata, body=body)
