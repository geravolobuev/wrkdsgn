import re


HEADLINE_RE = re.compile(r"^[^\n/]{2,140}\s*/\s*[^/\n]{2,140}$")


def split_jobs_from_post(raw_text: str) -> list[str]:
    text = (raw_text or "").strip()
    if not text:
        return []

    lines = [line.strip() for line in text.splitlines()]

    headline_indexes: list[int] = []
    for idx, line in enumerate(lines):
        if not line:
            continue
        if HEADLINE_RE.match(line):
            headline_indexes.append(idx)

    # Keep single-item behavior for standard posts.
    if len(headline_indexes) < 2:
        return [text]

    chunks: list[str] = []
    for i, start_idx in enumerate(headline_indexes):
        end_idx = headline_indexes[i + 1] if i + 1 < len(headline_indexes) else len(lines)
        part_lines = [ln for ln in lines[start_idx:end_idx] if ln]
        if not part_lines:
            continue
        part_text = "\n".join(part_lines).strip()
        if len(part_text) < 8:
            continue
        chunks.append(part_text)

    return chunks if chunks else [text]

