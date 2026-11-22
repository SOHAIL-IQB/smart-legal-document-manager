"""Phase 3: soft delete, version metadata, single-version fetch and restore."""

import hashlib
from datetime import datetime


def add_version(client, account, document_id, content, **extra):
    return client.post(
        f"/api/documents/{document_id}/versions",
        json={"content": content, **extra},
        headers=account.headers,
    )


def history(client, account, document_id, **params):
    response = client.get(
        f"/api/documents/{document_id}/versions", params=params, headers=account.headers
    )
    assert response.status_code == 200
    return response.json()


# --- metadata ----------------------------------------------------------------


def test_versions_record_hash_word_count_editor_and_source(client, alice, make_document):
    content = "The tenant shall pay rent monthly."
    document_id = make_document(alice, content=content)

    [v1] = history(client, alice, document_id)

    assert v1["content_hash"] == hashlib.sha256(content.encode()).hexdigest()
    assert v1["word_count"] == 6
    assert v1["edited_by_name"] == "Alice"
    assert v1["source"] == "manual"
    assert v1["is_deleted"] is False
    assert v1["change_note"] is None


def test_change_note_is_saved_and_trimmed(client, alice, make_document):
    document_id = make_document(alice)
    add_version(client, alice, document_id, "Term: 2 years.", change_note="  Extended term  ")
    assert history(client, alice, document_id)[-1]["change_note"] == "Extended term"


def test_change_note_has_a_length_limit(client, alice, make_document):
    document_id = make_document(alice)
    response = add_version(client, alice, document_id, "Term: 2 years.", change_note="x" * 501)
    assert response.status_code == 422


def test_history_list_omits_content_but_single_version_has_it(client, alice, make_document):
    document_id = make_document(alice, content="Full clause text.")

    [summary] = history(client, alice, document_id)
    assert "content" not in summary

    single = client.get(f"/api/documents/{document_id}/versions/1", headers=alice.headers)
    assert single.status_code == 200
    assert single.json()["content"] == "Full clause text."


def test_unknown_single_version_is_404(client, alice, make_document):
    document_id = make_document(alice)
    response = client.get(f"/api/documents/{document_id}/versions/9", headers=alice.headers)
    assert response.status_code == 404


# --- soft delete -----------------------------------------------------------------


def test_deleted_version_is_hidden_but_kept_for_audit(client, alice, make_document):
    document_id = make_document(alice, content="v1")
    add_version(client, alice, document_id, "v2")
    client.delete(f"/api/documents/{document_id}/versions/1", headers=alice.headers)

    assert [v["version_number"] for v in history(client, alice, document_id)] == [2]

    everything = history(client, alice, document_id, include_deleted="true")
    deleted = everything[0]
    assert [v["version_number"] for v in everything] == [1, 2]
    assert deleted["is_deleted"] is True
    assert deleted["deleted_by"] == alice.id
    assert deleted["deleted_at"] is not None


def test_deleted_version_returns_410_for_fetch_compare_and_restore(client, alice, make_document):
    document_id = make_document(alice, content="v1")
    add_version(client, alice, document_id, "v2")
    client.delete(f"/api/documents/{document_id}/versions/1", headers=alice.headers)
    base = f"/api/documents/{document_id}"

    for response in (
        client.get(f"{base}/versions/1", headers=alice.headers),
        client.get(f"{base}/compare?v1=1&v2=2", headers=alice.headers),
        client.post(f"{base}/versions/1/restore", headers=alice.headers),
    ):
        assert response.status_code == 410, response.request.url
        assert response.json()["error"]["code"] == "gone"


def test_deleting_twice_is_410(client, alice, make_document):
    document_id = make_document(alice, content="v1")
    add_version(client, alice, document_id, "v2")
    url = f"/api/documents/{document_id}/versions/2"
    assert client.delete(url, headers=alice.headers).status_code == 200
    assert client.delete(url, headers=alice.headers).status_code == 410


def test_detail_counts_only_live_versions(client, alice, make_document):
    document_id = make_document(alice, content="v1")
    add_version(client, alice, document_id, "v2")
    add_version(client, alice, document_id, "v3")
    client.delete(f"/api/documents/{document_id}/versions/3", headers=alice.headers)

    detail = client.get(f"/api/documents/{document_id}", headers=alice.headers).json()

    assert detail["version_count"] == 2
    assert detail["latest_version"] == 2


def test_no_change_check_compares_against_latest_live_version(client, alice, make_document):
    document_id = make_document(alice, content="v1")
    add_version(client, alice, document_id, "v2")
    client.delete(f"/api/documents/{document_id}/versions/2", headers=alice.headers)

    # "v1" is the latest live content, so re-saving it changes nothing ...
    assert add_version(client, alice, document_id, "v1").status_code == 200
    # ... while re-saving the deleted content is a real new version (number 3).
    assert add_version(client, alice, document_id, "v2").json()["version"] == 3


def test_new_version_bumps_document_updated_at(client, alice, make_document):
    document_id = make_document(alice)
    before = client.get(f"/api/documents/{document_id}", headers=alice.headers).json()
    add_version(client, alice, document_id, "changed")
    after = client.get(f"/api/documents/{document_id}", headers=alice.headers).json()
    # Parse: ISO strings don't compare correctly (".5Z" vs "Z" when microseconds are 0).
    assert datetime.fromisoformat(after["updated_at"]) >= datetime.fromisoformat(
        before["updated_at"]
    )


# --- restore -------------------------------------------------------------------------


def test_restore_creates_a_new_version_with_old_content(client, alice, make_document):
    document_id = make_document(alice, content="Original wording.")
    add_version(client, alice, document_id, "Bad edit.")

    response = client.post(
        f"/api/documents/{document_id}/versions/1/restore", headers=alice.headers
    )

    assert response.status_code == 201
    assert response.json()["version"] == 3
    restored = client.get(f"/api/documents/{document_id}/versions/3", headers=alice.headers).json()
    assert restored["content"] == "Original wording."
    assert restored["source"] == "restore"
    assert restored["restored_from"] == 1
    assert restored["change_note"] == "Restored from version 1"
    # History is not rewritten: the bad edit is still there.
    assert [v["version_number"] for v in history(client, alice, document_id)] == [1, 2, 3]


def test_restore_accepts_a_custom_note(client, alice, make_document):
    document_id = make_document(alice, content="A")
    add_version(client, alice, document_id, "B")
    client.post(
        f"/api/documents/{document_id}/versions/1/restore",
        json={"change_note": "Client rejected the change"},
        headers=alice.headers,
    )
    assert history(client, alice, document_id)[-1]["change_note"] == "Client rejected the change"


def test_restoring_the_current_content_changes_nothing(client, alice, make_document):
    document_id = make_document(alice, content="A")
    response = client.post(
        f"/api/documents/{document_id}/versions/1/restore", headers=alice.headers
    )
    assert response.status_code == 200
    assert response.json()["message"] == "No changes detected"


# --- structured comparison (Phase 4) -----------------------------------------------------------


def test_compare_returns_side_by_side_rows_stats_and_version_meta(client, alice, make_document):
    document_id = make_document(alice, content="Parties: A and B.\nTerm: 1 year.")
    add_version(client, alice, document_id, "Parties: A and B.\nTerm: 2 years.\nGoverning law: NY.")

    body = client.get(
        f"/api/documents/{document_id}/compare?v1=1&v2=2", headers=alice.headers
    ).json()

    assert [row["type"] for row in body["rows"]] == ["equal", "replace", "insert"]
    replace = body["rows"][1]
    assert [s["text"] for s in replace["new_segments"] if s["op"] == "insert"] == ["2 years"]
    assert body["stats"] == {
        "lines_added": 1,
        "lines_removed": 0,
        "lines_changed": 1,
        "words_added": 5,  # 2, years, Governing, law, NY
        "words_removed": 2,  # 1, year
    }
    assert body["version_1_meta"]["version_number"] == 1
    assert body["version_2_meta"]["edited_by_name"] == "Alice"
    assert "content" not in body["version_1_meta"]


def test_compare_context_collapses_unchanged_lines(client, alice, make_document):
    lines = [f"Clause {i}." for i in range(1, 31)]
    document_id = make_document(alice, content="\n".join(lines))
    lines[14] = "Clause 15, amended."
    add_version(client, alice, document_id, "\n".join(lines))

    body = client.get(
        f"/api/documents/{document_id}/compare?v1=1&v2=2&context=3", headers=alice.headers
    ).json()

    types = [row["type"] for row in body["rows"]]
    assert types.count("skip") == 2
    assert types.count("equal") == 6
    assert sum(row["skipped"] for row in body["rows"] if row["type"] == "skip") == 23


def test_compare_context_is_bounded(client, alice, make_document):
    document_id = make_document(alice)
    response = client.get(
        f"/api/documents/{document_id}/compare?v1=1&v2=1&context=51", headers=alice.headers
    )
    assert response.status_code == 422


def test_compare_can_go_backwards(client, alice, make_document):
    document_id = make_document(alice, content="A")
    add_version(client, alice, document_id, "B")
    body = client.get(
        f"/api/documents/{document_id}/compare?v1=2&v2=1", headers=alice.headers
    ).json()
    assert (body["before"], body["after"]) == ("B", "A")
