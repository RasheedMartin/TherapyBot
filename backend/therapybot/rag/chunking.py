"""Split documents into retrievable chunks."""

import re

_HEADER_RE = re.compile(r"^(#+)\s(.*)")


def parse_front_matter(text: str) -> tuple[dict, str]:
    """Split a `---`-delimited `key: value` header from a Markdown body."""
    if not text.startswith("---"):
        return {}, text
    header, _, body = text[3:].partition("\n---")
    meta = {}
    for line in header.strip().splitlines():
        key, sep, value = line.partition(":")
        if sep and value.strip():
            meta[key.strip()] = value.strip()
    return meta, body.lstrip("\n")


def split_markdown(text: str) -> list[tuple[str, str]]:
    """
    One chunk per Markdown section, each starting with its own heading line, paired with the path of
    its parent headings ("/" at the top level, "/Parent/" below one). Headings inside fenced code blocks
    are ignored; text before the first heading becomes its own chunk.
    """
    chunks: list[tuple[str, str]] = []
    stack: list[tuple[int, str]] = []  # (level, heading text) of the current section and its parents
    current, in_code = "", False

    def path() -> str:
        parents = [title for _, title in stack[:-1]]
        return "/" + "/".join(parents) + "/" if parents else "/"

    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_code = not in_code
        elif not in_code and (match := _HEADER_RE.match(line)):
            if current.strip():
                chunks.append((current.strip(), path()))
            level = len(match.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, match.group(2)))
            current = ""
        current += line + "\n"
    if current.strip():
        chunks.append((current.strip(), path()))
    return chunks


def embedding_text(text: str, metadata: dict) -> str:
    """Metadata lines, a blank line, then the text. Words in titles and URLs help retrieval match topics."""
    metadata_str = "\n".join(f"{key}: {value}" for key, value in metadata.items())
    return f"{metadata_str}\n\n{text}".strip() if metadata_str else text
