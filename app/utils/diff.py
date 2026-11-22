import difflib


def build_unified_diff(old_text: str, new_text: str) -> list[str]:
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    return list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile="Before",
            tofile="After",
            lineterm="",
        )
    )


def normalize_for_meaningful_change(content: str) -> str:
    normalized_lines = [" ".join(line.split()) for line in content.splitlines()]
    return "\n".join(line for line in normalized_lines if line)


def has_meaningful_changes(old_text: str, new_text: str) -> bool:
    return normalize_for_meaningful_change(old_text) != normalize_for_meaningful_change(new_text)
