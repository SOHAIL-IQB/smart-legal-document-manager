from app.utils.diff_utils import build_unified_diff, has_meaningful_changes


def compare_versions(old_text: str, new_text: str) -> dict[str, object]:
    return {
        "before": old_text,
        "after": new_text,
        "changes": build_unified_diff(old_text, new_text),
        "has_meaningful_changes": has_meaningful_changes(old_text, new_text),
    }
