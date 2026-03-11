"""

web_fetch tool

content.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from app.atlasclaw.tools.base import ToolResult
from app.atlasclaw.tools.truncation import truncate_output, TruncationConfig

if TYPE_CHECKING:
    from pydantic_ai import RunContext
    from app.atlasclaw.core.deps import SkillDeps


async def web_fetch_tool(
    ctx: "RunContext[SkillDeps]",
    url: str,
    extract_mode: str = "text",
) -> dict:
    """

content

    Args:
        ctx:PydanticAI RunContext dependency injection
        url:URL
        extract_mode:mode(text / markdown / html)

    Returns:
        Serialized `ToolResult` dictionary
    
"""
    try:
        import httpx
    except ImportError:
        return ToolResult.error("httpx is not installed").to_dict()

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text
    except Exception as e:
        return ToolResult.error(
            f"Invalid URL or connection error: {e}",
            details={"url": url},
        ).to_dict()

    # mode
    if extract_mode == "html":
        content = html
    elif extract_mode == "markdown":
        content = _html_to_markdown(html)
    else:
        content = _html_to_text(html)

    # truncate
    original_len = len(content)
    content = truncate_output(content, TruncationConfig())
    truncated = len(content) < original_len

    return ToolResult.text(
        content,
        details={
            "url": url,
            "extract_mode": extract_mode,
            "truncated": truncated,
            "status_code": response.status_code,
        },
    ).to_dict()


def _html_to_text(html: str) -> str:
    """HTML"""
    import re
    # script and style
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # 
    text = re.sub(r"<[^>]+>", " ", text)
    # 
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _html_to_markdown(html: str) -> str:
    """HTML Markdown"""
    import re
    text = html
    # h1-h6
    for i in range(1, 7):
        text = re.sub(
            rf"<h{i}[^>]*>(.*?)</h{i}>",
            lambda m, level=i: f"\n{'#' * level} {m.group(1).strip()}\n",
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )
    # p -> paragraph
    text = re.sub(r"<p[^>]*>(.*?)</p>", r"\n\1\n", text, flags=re.DOTALL | re.IGNORECASE)
    # 
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text
