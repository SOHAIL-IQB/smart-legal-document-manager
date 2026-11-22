"""Phase 4: document list search, filters, sorting and pagination (B6)."""

import pytest


def listing(client, account, **params):
    response = client.get("/api/documents", params=params, headers=account.headers)
    assert response.status_code == 200, response.text
    return response.json()


def titles(body):
    return [item["title"] for item in body["items"]]


def add_version(client, account, document_id, content):
    response = client.post(
        f"/api/documents/{document_id}/versions", json={"content": content}, headers=account.headers
    )
    assert response.status_code == 201
    return response


# --- item shape ------------------------------------------------------------------


def test_items_carry_owner_name_role_and_live_version_stats(client, alice, make_document):
    document_id = make_document(alice, title="Lease", content="Rent is due monthly.")
    add_version(client, alice, document_id, "Rent is due on the first day.")
    add_version(client, alice, document_id, "Rent is due on the first business day.")
    client.delete(f"/api/documents/{document_id}/versions/3", headers=alice.headers)

    [item] = listing(client, alice)["items"]

    assert item["created_by_name"] == "Alice"
    assert item["my_role"] == "owner"
    assert item["latest_version"] == 2
    assert item["version_count"] == 2
    assert item["word_count"] == 7  # "Rent is due on the first day."


def test_detail_has_the_same_shape_as_list_items(client, alice, make_document):
    document_id = make_document(alice)
    [item] = listing(client, alice)["items"]
    detail = client.get(f"/api/documents/{document_id}", headers=alice.headers).json()
    assert detail == item


# --- search ------------------------------------------------------------------------


def test_search_matches_title_case_insensitively(client, alice, make_document):
    make_document(alice, title="Master Services Agreement")
    make_document(alice, title="Office Lease")
    assert titles(listing(client, alice, q="services")) == ["Master Services Agreement"]


def test_search_matches_latest_content(client, alice, make_document):
    make_document(alice, title="NDA", content="Confidential information includes source code.")
    make_document(alice, title="Lease", content="Rent is due monthly.")
    assert titles(listing(client, alice, q="SOURCE CODE")) == ["NDA"]


def test_search_ignores_content_that_only_exists_in_older_versions(client, alice, make_document):
    document_id = make_document(alice, title="NDA", content="Term: perpetual.")
    add_version(client, alice, document_id, "Term: five years.")
    assert listing(client, alice, q="perpetual")["total"] == 0
    assert listing(client, alice, q="five years")["total"] == 1


def test_search_ignores_content_of_a_deleted_latest_version(client, alice, make_document):
    document_id = make_document(alice, title="NDA", content="Term: five years.")
    add_version(client, alice, document_id, "Term: secret draft wording.")
    client.delete(f"/api/documents/{document_id}/versions/2", headers=alice.headers)
    assert listing(client, alice, q="secret draft")["total"] == 0
    assert listing(client, alice, q="five years")["total"] == 1


@pytest.mark.parametrize(("term", "expected"), [("100%", ["Fee 100%"]), ("a_b", ["Clause a_b"])])
def test_search_treats_like_wildcards_literally(client, alice, make_document, term, expected):
    make_document(alice, title="Fee 100%")
    make_document(alice, title="Fee 1000")
    make_document(alice, title="Clause a_b")
    make_document(alice, title="Clause axb")
    assert titles(listing(client, alice, q=term)) == expected


def test_search_never_returns_other_users_documents(client, alice, signup, make_document):
    bob = signup("Bob", "bob@example.com")
    make_document(bob, title="Bob's secret merger", content="Acquire Acme.")
    assert listing(client, alice, q="merger")["total"] == 0
    assert listing(client, alice, q="Acme")["total"] == 0


def test_blank_search_returns_everything(client, alice, make_document):
    make_document(alice, title="One")
    make_document(alice, title="Two")
    assert listing(client, alice, q="   ")["total"] == 2


def test_search_term_length_is_limited(client, alice):
    response = client.get("/api/documents", params={"q": "x" * 201}, headers=alice.headers)
    assert response.status_code == 422


# --- role filter ------------------------------------------------------------------------


def test_role_filter(client, alice, signup, make_document):
    bob = signup("Bob", "bob@example.com")
    make_document(alice, title="Mine")
    shared = make_document(bob, title="Shared with me")
    client.post(
        f"/api/documents/{shared}/members",
        json={"email": alice.email, "role": "editor"},
        headers=bob.headers,
    )
    assert titles(listing(client, alice, role="owner")) == ["Mine"]
    assert titles(listing(client, alice, role="editor")) == ["Shared with me"]
    assert listing(client, alice, role="viewer")["total"] == 0


# --- sorting ------------------------------------------------------------------------------


def test_default_sort_is_most_recently_updated_first(client, alice, make_document):
    first = make_document(alice, title="First")
    make_document(alice, title="Second")
    add_version(client, alice, first, "First, edited later.")
    assert titles(listing(client, alice)) == ["First", "Second"]


def test_sort_by_title_is_case_insensitive(client, alice, make_document):
    # Byte order would give Apple, Delta, banana, cherry.
    for title in ["banana", "Delta", "Apple", "cherry"]:
        make_document(alice, title=title)
    ascending = ["Apple", "banana", "cherry", "Delta"]
    assert titles(listing(client, alice, sort="title", order="asc")) == ascending
    assert titles(listing(client, alice, sort="title", order="desc")) == ascending[::-1]


def test_sort_by_created_at(client, alice, make_document):
    for title in ["A", "B", "C"]:
        make_document(alice, title=title)
    assert titles(listing(client, alice, sort="created_at", order="asc")) == ["A", "B", "C"]


def test_invalid_sort_is_rejected(client, alice):
    response = client.get("/api/documents", params={"sort": "content"}, headers=alice.headers)
    assert response.status_code == 422


# --- pagination ---------------------------------------------------------------------------


def test_pagination_pages_through_all_documents_without_overlap(client, alice, make_document):
    for i in range(7):
        make_document(alice, title=f"Doc {i}")

    pages = [listing(client, alice, limit=3, offset=offset) for offset in (0, 3, 6)]

    assert [len(page["items"]) for page in pages] == [3, 3, 1]
    assert {page["total"] for page in pages} == {7}
    ids = [item["id"] for page in pages for item in page["items"]]
    assert len(ids) == len(set(ids)) == 7


def test_total_reflects_the_filter_not_the_page(client, alice, make_document):
    for i in range(5):
        make_document(alice, title=f"Lease {i}")
    make_document(alice, title="NDA")
    body = listing(client, alice, q="lease", limit=2)
    assert (len(body["items"]), body["total"], body["limit"]) == (2, 5, 2)


def test_offset_past_the_end_returns_empty_page(client, alice, make_document):
    make_document(alice)
    body = listing(client, alice, offset=50)
    assert body["items"] == [] and body["total"] == 1


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
def test_pagination_bounds(client, alice, params):
    assert client.get("/api/documents", params=params, headers=alice.headers).status_code == 422
