"""Book requests and upvotes (Sprint 07, ADR-0009)."""
from __future__ import annotations

import re
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import requests as reqs
from app import storage
from app.main import app
from tests.test_auth import PHONE, login
from tests.test_catalogue import add_book, no_cover_rendering  # noqa: F401 (autouse fixture)
from tests.test_stars import user_id

# A requester whose id and number are distinctive enough to search every response for.
SECRET_ID = 987654
SECRET_PHONE = "+99365432198"
SECRET_SHOWN = ["987654", "65432198", "65 432198", "65 43 21 98"]


def make_user(db, phone, uid=None) -> int:
    if uid is None:
        return user_id(db, phone)
    db.execute("INSERT INTO users (id, phone) VALUES (?, ?)", (uid, phone))
    db.commit()
    return uid


def ask(db, uid, title, author="", note="") -> int:
    return reqs.post_request(db, uid, title, author, note)


def votes(db, request_id) -> int:
    return db.execute(
        "SELECT COUNT(*) FROM request_upvotes WHERE request_id = ?", (request_id,)
    ).fetchone()[0]


def voters(db, request_id) -> set[int]:
    return {
        row[0]
        for row in db.execute("SELECT user_id FROM request_upvotes WHERE request_id = ?", (request_id,))
    }


def listed_titles(html: str) -> list[str]:
    return re.findall(
        r'<a class="request-text" href="/requests/\d+">\s*<span class="request-name">\s*<strong>([^<]*)</strong>', html
    )


def post(client, **form):
    return client.post("/requests/new", data=form, follow_redirects=False)


def new_client(phone) -> TestClient:
    other = TestClient(app, base_url="https://testserver")
    login(other, phone)
    return other


@pytest.fixture()
def reader(client, db):
    login(client)
    return user_id(db)


@pytest.fixture()
def admin(client, db):
    login(client)
    db.execute("UPDATE users SET is_admin = 1 WHERE phone = ?", (PHONE,))
    db.commit()
    return client


# --- Schema ----------------------------------------------------------------------------------


def test_the_database_rejects_a_second_upvote(db):
    uid = make_user(db, "+99365000001")
    rid = ask(db, uid, "Görogly")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO request_upvotes (request_id, user_id) VALUES (?, ?)", (rid, uid))
    db.rollback()
    assert votes(db, rid) == 1


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE requests SET status = 'merged'",  # merged without a target
        "UPDATE requests SET status = 'rejected', resolved_at = '2026-01-01 00:00:00'",  # no reason
        "UPDATE requests SET status = 'bogus'",
        "UPDATE requests SET merged_into_id = id, status = 'merged', resolved_at = '2026-01-01 00:00:00'",
        "UPDATE requests SET fulfilled_book_id = 1",  # open, yet linked to a book
    ],
)
def test_the_database_refuses_inconsistent_states(db, sql):
    ask(db, make_user(db, "+99365000001"), "Görogly")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(sql)
    db.rollback()


def test_deleting_the_book_of_a_fulfilled_request_still_works(admin, db):
    book_id = add_book(db, "Görogly")
    rid = ask(db, make_user(db, "+99365000001"), "Görogly")
    reqs.fulfil(db, rid, book_id)
    storage.delete_book(db, book_id)
    row = db.execute("SELECT status, fulfilled_book_id FROM requests WHERE id = ?", (rid,)).fetchone()
    assert (row["status"], row["fulfilled_book_id"]) == ("fulfilled", None)
    assert "häzir elýeterli däl" in admin.get(f"/requests/{rid}").text


# --- Posting ---------------------------------------------------------------------------------


def test_visitors_are_sent_to_sign_in_and_brought_back_to_the_prefilled_form(client, db):
    response = client.get("/requests/new?title=Älem&author=X", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=%2Frequests%2Fnew%3Ftitle%3D%25C3%2584lem%26author%3DX"
    assert post(client, title="Älem").status_code == 303
    assert db.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == 0

    login(client)
    form = client.get("/requests/new?title=Älem&author=X").text
    assert 'name="title" type="text" value="Älem"' in form


def test_a_signed_in_reader_posts_and_is_the_first_upvote(client, db, reader):
    response = post(client, title="  Aýlar   we ýyllar ", author="Nurmyrat Saryhanow", note="1970-nji ýyl")
    assert response.status_code == 303
    rid = int(re.fullmatch(r"/requests/(\d+)\?posted=1", response.headers["location"]).group(1))
    row = db.execute("SELECT * FROM requests WHERE id = ?", (rid,)).fetchone()
    assert (row["title"], row["author"], row["note"], row["status"]) == (
        "Aýlar we ýyllar", "Nurmyrat Saryhanow", "1970-nji ýyl", "open",
    )
    assert row["user_id"] == reader
    assert voters(db, rid) == {reader}

    page = client.get(response.headers["location"]).text
    assert "Soragyňyz goşuldy" in page and "adsyz" in page
    assert "Aýlar we ýyllar" in page and "1 adam goldady" in page


@pytest.mark.parametrize(
    "form, error",
    [
        ({"title": ""}, "Kitabyň adyny ýazyň"),
        ({"title": "   "}, "Kitabyň adyny ýazyň"),
        ({"title": "?!…"}, "Kitabyň adyny ýazyň"),
        ({"title": "A" * 301}, "300 harpdan uzyn"),
        ({"title": "Kitap", "author": "B" * 301}, "300 harpdan uzyn"),
        ({"title": "Kitap", "note": "C" * 1001}, "1000 harpdan uzyn"),
    ],
)
def test_empty_and_oversized_requests_are_refused(client, db, reader, form, error):
    response = post(client, **form)
    assert response.status_code == 400
    assert error in response.text
    assert db.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == 0


def test_a_book_already_in_the_library_is_offered_first(client, db, reader):
    book_id = add_book(db, "Görogly", "Halk döredijiligi")
    response = post(client, title="gorogly")  # typed without Turkmen letters
    assert response.status_code == 200
    assert "Bu kitaplar eýýäm bar" in response.text
    assert f'href="/books/{book_id}"' in response.text
    assert db.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == 0

    # The reader says it is a different book: now it is posted.
    assert 'name="confirmed" value="1"' in response.text
    assert post(client, title="gorogly", confirmed="1").status_code == 303
    assert db.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == 1


def test_a_similar_open_request_is_offered_to_upvote_instead(client, db, reader):
    other = make_user(db, "+99365000001")
    rid = ask(db, other, "Magtymguly Pyragy: goşgular")
    response = post(client, title="magtymguly goşgulary")
    assert response.status_code == 200
    assert "Meňzeş soraglar" in response.text
    assert f'action="/requests/{rid}/upvote"' in response.text
    assert db.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == 1


def test_unpublished_books_are_not_offered(client, db, reader):
    add_book(db, "Gizlin kitap", published=False)
    assert post(client, title="Gizlin kitap").status_code == 303


def test_the_request_rate_limit_fires_per_reader(client, db, reader, test_settings):
    test_settings(request_limits=((2, 3600), (10, 86400)))
    assert post(client, title="Birinji kitap").status_code == 303
    assert post(client, title="Ikinji eser").status_code == 303
    response = post(client, title="Üçünji roman")
    assert response.status_code == 429
    assert "gaty köp sorag goşduňyz" in response.text and "minutdan soň" in response.text
    assert db.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == 2

    # Another reader is not affected.
    assert post(new_client("+99365000001"), title="Dördünji düzme").status_code == 303


def test_a_blocked_reader_cannot_post_but_keeps_everything_else(client, db, reader):
    from app import stars

    stars.grant(db, reader, 5, "Bonus")
    rid = ask(db, make_user(db, "+99365000001"), "Görogly")
    reqs.set_posting_blocked(db, reader, True)

    assert client.get("/requests/new").status_code == 403
    response = post(client, title="Täze kitap")
    assert response.status_code == 403 and "gadagan edildi" in response.text
    with pytest.raises(reqs.PostingBlocked):
        ask(db, reader, "Täze kitap")
    assert db.execute("SELECT COUNT(*) FROM requests WHERE user_id = ?", (reader,)).fetchone()[0] == 0

    # Still signed in, still has stars, can still upvote.
    assert client.get("/account").status_code == 200
    assert stars.balance(db, reader) == 5
    client.post(f"/requests/{rid}/upvote", follow_redirects=False)
    assert reader in voters(db, rid)


# --- Anonymity -------------------------------------------------------------------------------


def _public_responses(client, rid, fulfilled_rid):
    return {
        url: client.get(url)
        for url in [
            "/requests",
            "/requests?list=fulfilled",
            "/requests?list=mine",
            f"/requests/{rid}",
            f"/requests/{fulfilled_rid}",
            "/requests/new?title=Görogly",
            "/books?q=nothing-matches-this",
            "/",
            "/openapi.json",
        ]
    }


def test_no_public_page_or_endpoint_reveals_who_asked(client, db):
    requester = make_user(db, SECRET_PHONE, SECRET_ID)
    rid = ask(db, requester, "Görogly", "Halk döredijiligi", "Gyzyl neşiri")
    fulfilled_rid = ask(db, requester, "Älem")
    reqs.fulfil(db, fulfilled_rid, add_book(db, "Älem"))

    # A signed-out visitor, then another signed-in reader who upvotes it and posts a similar one.
    for signed_in in (False, True):
        if signed_in:
            login(client)
            client.post(f"/requests/{rid}/upvote")
            post(client, title="Görogly")  # the similar-requests step
        for url, response in _public_responses(client, rid, fulfilled_rid).items():
            assert response.status_code in (200, 303), url
            for secret in SECRET_SHOWN:
                assert secret not in response.text, f"{secret} leaked on {url}"


def test_public_queries_never_select_the_requester():
    """Anonymity by construction: the public column list has no user id in it."""
    assert "user_id" not in reqs._PUBLIC.replace("request_upvotes.user_id = :viewer", "")


def test_public_rows_carry_no_user_id(db):
    rid = ask(db, make_user(db, SECRET_PHONE, SECRET_ID), "Görogly")
    rows, _, _ = reqs.list_requests(db, "open", None, 1)
    for row in [*rows, reqs.get_request(db, rid, None), *reqs.similar_requests(db, "Görogly", None)]:
        assert "user_id" not in row.keys()
        assert SECRET_ID not in tuple(row)


def test_the_requester_is_shown_to_the_admin_only(admin, db):
    rid = ask(db, make_user(db, SECRET_PHONE, SECRET_ID), "Görogly")
    assert "+993 65 432198" in admin.get(f"/admin/requests/{rid}").text
    assert "+993 65 432198" in admin.get("/admin/requests").text


# --- The list --------------------------------------------------------------------------------


def test_anyone_can_read_the_list_ordered_by_upvotes_then_newest(client, db):
    a, b, c = (make_user(db, f"+9936500000{i}") for i in range(3))
    old_popular = ask(db, a, "Köne we meşhur")
    ask(db, b, "Köne we ýalňyz")
    new_quiet = ask(db, c, "Täze we ýalňyz")
    reqs.upvote(db, old_popular, b)
    reqs.upvote(db, old_popular, c)
    db.execute("UPDATE requests SET created_at = '2026-01-01 00:00:00' WHERE id < ?", (new_quiet,))
    db.commit()

    html = client.get("/requests").text
    assert listed_titles(html) == ["Köne we meşhur", "Täze we ýalňyz", "Köne we ýalňyz"]
    assert "Kitap sora" in html


def test_the_list_paginates(client, db):
    uid = make_user(db, "+99365000001")
    for i in range(reqs.PAGE_SIZE + 3):
        db.execute(
            "INSERT INTO requests (user_id, title, search_text) VALUES (?, ?, ?)", (uid, f"Kitap {i:02d}", "")
        )
    db.commit()
    first, second = client.get("/requests").text, client.get("/requests?page=2").text
    assert len(listed_titles(first)) == reqs.PAGE_SIZE and len(listed_titles(second)) == 3
    assert 'href="/requests?page=2" rel="next"' in first
    assert listed_titles(client.get("/requests?page=99").text) == listed_titles(second)
    assert client.get("/requests?page=abc&list=nonsense").status_code == 200


def test_mine_needs_signing_in_and_lists_what_i_upvoted(client, db):
    response = client.get("/requests?list=mine", follow_redirects=False)
    assert response.headers["location"] == "/login?next=%2Frequests%3Flist%3Dmine"

    login(client)
    me = user_id(db)
    other = make_user(db, "+99365000001")
    liked = ask(db, other, "Goldanan kitap")
    ask(db, other, "Başga kitap")
    rejected = ask(db, other, "Ret edilen kitap")
    reqs.upvote(db, liked, me)
    reqs.upvote(db, rejected, me)
    reqs.reject(db, rejected, "Bu kitap entek neşir edilmedi.")

    html = client.get("/requests?list=mine").text
    assert sorted(listed_titles(html)) == ["Goldanan kitap", "Ret edilen kitap"]
    assert "Ret edildi" in html


def test_a_request_page_is_404_when_unknown_or_malformed(client):
    for url in ["/requests/999", "/requests/0", "/requests/abc", "/requests/01"]:
        assert client.get(url).status_code == 404, url


# --- Upvoting --------------------------------------------------------------------------------


def test_upvote_once_and_take_it_back(client, db, reader):
    rid = ask(db, make_user(db, "+99365000001"), "Görogly")
    for _ in range(2):
        response = client.post(f"/requests/{rid}/upvote", follow_redirects=False)
        assert response.status_code == 303 and response.headers["location"] == f"/requests/{rid}"
    assert votes(db, rid) == 2 and reader in voters(db, rid)
    assert 'aria-pressed="true"' in client.get(f"/requests/{rid}").text

    client.post(f"/requests/{rid}/unvote")
    assert votes(db, rid) == 1 and reader not in voters(db, rid)
    client.post(f"/requests/{rid}/unvote")
    assert votes(db, rid) == 1
    assert 'aria-pressed="false"' in client.get(f"/requests/{rid}").text


def test_the_displayed_count_is_the_number_of_rows(client, db):
    rid = ask(db, make_user(db, "+99365000001"), "Görogly")
    for i in range(2, 6):
        reqs.upvote(db, rid, make_user(db, f"+9936500000{i}"))
    assert votes(db, rid) == 5
    assert "5 adam goldady" in client.get(f"/requests/{rid}").text


def test_visitors_cannot_upvote(client, db):
    rid = ask(db, make_user(db, "+99365000001"), "Görogly")
    response = client.post(f"/requests/{rid}/upvote", follow_redirects=False)
    assert response.headers["location"] == f"/login?next=%2Frequests%2F{rid}"
    assert votes(db, rid) == 1
    assert f'href="/login?next=/requests/{rid}"' in client.get("/requests").text


def test_upvoting_returns_to_the_list_but_never_to_another_site(client, db, reader):
    rid = ask(db, make_user(db, "+99365000001"), "Görogly")
    back = client.post(f"/requests/{rid}/upvote", data={"next": "/requests?page=2"}, follow_redirects=False)
    assert back.headers["location"] == "/requests?page=2"
    away = client.post(f"/requests/{rid}/unvote", data={"next": "//evil.example"}, follow_redirects=False)
    assert away.headers["location"] == f"/requests/{rid}"


def test_closed_requests_cannot_be_upvoted(client, db, reader):
    rid = ask(db, make_user(db, "+99365000001"), "Görogly")
    reqs.reject(db, rid, "Sebäp")
    client.post(f"/requests/{rid}/upvote")
    assert votes(db, rid) == 1
    assert "ýapyldy" in client.get(f"/requests/{rid}").text


def test_upvoting_an_unknown_request_is_404(client, reader):
    assert client.post("/requests/999/upvote").status_code == 404


# --- Fulfilment, rejection, merging (admin) --------------------------------------------------


ADMIN_REQUESTS = [
    ("get", "/admin/requests"),
    ("get", "/admin/requests/1"),
    ("post", "/admin/requests/1/fulfil"),
    ("post", "/admin/requests/1/reject"),
    ("post", "/admin/requests/1/merge"),
    ("post", "/admin/requests/1/reopen"),
    ("post", "/admin/requests/1/block"),
    ("post", "/admin/requests/1/unblock"),
]


@pytest.mark.parametrize("method, path", ADMIN_REQUESTS)
def test_request_admin_is_404_for_readers(client, db, method, path):
    ask(db, make_user(db, "+99365000001"), "Görogly")
    login(client)
    assert getattr(client, method)(path, follow_redirects=False).status_code == 404
    assert db.execute("SELECT status FROM requests").fetchone()[0] == "open"


def test_fulfilling_links_the_book_and_leaves_the_open_list(admin, db):
    rid = ask(db, make_user(db, "+99365000001"), "Görogly")
    book_id = add_book(db, "Görogly")
    page = admin.get(f"/admin/requests/{rid}").text
    assert f'name="book_id" value="{book_id}"' in page  # offered as a likely match

    response = admin.post(f"/admin/requests/{rid}/fulfil", data={"book_id": str(book_id)}, follow_redirects=False)
    assert response.headers["location"] == f"/admin/requests/{rid}?notice=fulfilled"
    public = admin.get(f"/requests/{rid}").text
    assert f'href="/books/{book_id}"' in public and "indi kitaphanada bar" in public
    assert "Görogly" not in listed_titles(admin.get("/requests").text)
    assert listed_titles(admin.get("/requests?list=fulfilled").text) == ["Görogly"]


def test_a_request_fulfilled_with_a_draft_shows_no_link_until_published(admin, db):
    rid = ask(db, make_user(db, "+99365000001"), "Görogly")
    book_id = add_book(db, "Görogly", published=False)
    admin.post(f"/admin/requests/{rid}/fulfil", data={"book_id": str(book_id)})
    assert f'href="/books/{book_id}"' not in admin.get(f"/requests/{rid}").text
    db.execute("UPDATE books SET is_published = 1 WHERE id = ?", (book_id,))
    db.commit()
    assert f'href="/books/{book_id}"' in admin.get(f"/requests/{rid}").text


@pytest.mark.parametrize("book_id", ["", "abc", "0", "999"])
def test_fulfilling_needs_a_real_book(admin, db, book_id):
    rid = ask(db, make_user(db, "+99365000001"), "Görogly")
    assert admin.post(f"/admin/requests/{rid}/fulfil", data={"book_id": book_id}).status_code == 400
    assert db.execute("SELECT status FROM requests").fetchone()[0] == "open"


def test_rejecting_shows_the_reason(admin, db):
    rid = ask(db, make_user(db, "+99365000001"), "Görogly")
    assert admin.post(f"/admin/requests/{rid}/reject", data={"reason": " "}).status_code == 400
    admin.post(f"/admin/requests/{rid}/reject", data={"reason": "Awtorlyk hukugy bilen goralýar."})
    public = admin.get(f"/requests/{rid}").text
    assert "Bu sorag ret edildi" in public and "Awtorlyk hukugy bilen goralýar." in public
    assert listed_titles(admin.get("/requests").text) == []


def test_nonsense_is_cleared_in_one_click(admin, db):
    rid = ask(db, make_user(db, "+99365000001"), "asdfgh")
    page = admin.get(f"/admin/requests/{rid}").text
    assert 'value="Boş ýa-da manysyz sorag."' in page
    admin.post(f"/admin/requests/{rid}/reject", data={"reason": "Boş ýa-da manysyz sorag."})
    assert db.execute("SELECT status FROM requests").fetchone()[0] == "rejected"


def test_reopening_undoes_a_mistake(admin, db):
    rid = ask(db, make_user(db, "+99365000001"), "Görogly")
    reqs.reject(db, rid, "Ýalňyşlyk")
    admin.post(f"/admin/requests/{rid}/reopen")
    row = db.execute("SELECT * FROM requests WHERE id = ?", (rid,)).fetchone()
    assert (row["status"], row["reject_reason"], row["resolved_at"]) == ("open", None, None)
    assert admin.post(f"/admin/requests/{rid}/reopen").status_code == 400  # already open


def test_merging_carries_upvotes_and_counts_each_reader_once(admin, db):
    u1, u2, u3 = (make_user(db, f"+9936500000{i}") for i in range(1, 4))
    source = ask(db, u1, "Gorogly")  # voters: u1, u2
    target = ask(db, u3, "Görogly")  # voters: u3, u2
    reqs.upvote(db, source, u2)
    reqs.upvote(db, target, u2)

    response = admin.post(f"/admin/requests/{source}/merge", data={"target_id": str(target)}, follow_redirects=False)
    assert response.headers["location"] == f"/admin/requests/{target}?notice=merged"
    assert voters(db, target) == {u1, u2, u3}
    assert votes(db, source) == 0
    row = db.execute("SELECT status, merged_into_id FROM requests WHERE id = ?", (source,)).fetchone()
    assert (row["status"], row["merged_into_id"]) == ("merged", target)

    # The merged request's page redirects to the one it was merged into.
    moved = admin.get(f"/requests/{source}", follow_redirects=False)
    assert moved.status_code == 303 and moved.headers["location"] == f"/requests/{target}"
    assert listed_titles(admin.get("/requests").text) == ["Görogly"]


def test_a_merge_chain_redirects_to_its_end(admin, db):
    uid = make_user(db, "+99365000001")
    a, b, c = ask(db, uid, "A kitap"), ask(db, uid, "B kitap"), ask(db, uid, "C kitap")
    reqs.merge(db, a, b)
    reqs.merge(db, b, c)
    assert admin.get(f"/requests/{a}", follow_redirects=False).headers["location"] == f"/requests/{c}"


@pytest.mark.parametrize("case", ["self", "closed-target", "closed-source", "unknown", "blank"])
def test_bad_merges_are_refused(admin, db, case):
    uid = make_user(db, "+99365000001")
    source, target = ask(db, uid, "Birinji"), ask(db, uid, "Ikinji")
    target_id = {"self": source, "unknown": 999}.get(case, target)
    if case == "closed-target":
        reqs.reject(db, target, "x")
    if case == "closed-source":
        reqs.reject(db, source, "x")
    form = {"target_id": "" if case == "blank" else str(target_id)}
    assert admin.post(f"/admin/requests/{source}/merge", data=form).status_code == 400
    assert votes(db, target) == 1
    assert db.execute("SELECT COUNT(*) FROM requests WHERE status = 'merged'").fetchone()[0] == 0


def test_admin_blocks_and_unblocks_a_requester(admin, db):
    requester = make_user(db, "+99365000001")
    rid = ask(db, requester, "Görogly")
    admin.post(f"/admin/requests/{rid}/block")
    assert db.execute("SELECT requests_blocked FROM users WHERE id = ?", (requester,)).fetchone()[0] == 1
    assert "Petigi aýyr" in admin.get(f"/admin/requests/{rid}").text
    admin.post(f"/admin/requests/{rid}/unblock")
    assert db.execute("SELECT requests_blocked FROM users WHERE id = ?", (requester,)).fetchone()[0] == 0


def test_admin_overview_lists_the_most_wanted(admin, db):
    uid = make_user(db, "+99365000001")
    popular = ask(db, uid, "Iň köp soralan")
    ask(db, uid, "Az soralan")
    reqs.upvote(db, popular, make_user(db, "+99365000002"))
    html = admin.get("/admin").text
    assert html.index("Iň köp soralan") < html.index("Az soralan")


def test_admin_list_filters_by_status(admin, db):
    uid = make_user(db, "+99365000001")
    ask(db, uid, "Açyk kitap")
    reqs.reject(db, ask(db, uid, "Ret kitap"), "x")
    assert "Açyk kitap" in admin.get("/admin/requests").text
    assert "Ret kitap" not in admin.get("/admin/requests").text
    assert "Ret kitap" in admin.get("/admin/requests?status=rejected").text
    both = admin.get("/admin/requests?status=all").text
    assert "Açyk kitap" in both and "Ret kitap" in both


# --- From a failed search --------------------------------------------------------------------


def test_a_fruitless_search_leads_to_a_prefilled_request_in_one_click(client, db, reader):
    add_book(db, "Görogly")
    html = client.get("/books?q=Aýlar we ýyllar").text
    link = re.search(r'<a class="button" href="(/requests/new\?[^"]+)"', html)
    assert link, "the no-results page should link to the request form"
    form = client.get(link.group(1).replace("&amp;", "&")).text
    assert 'name="title" type="text" value="Aýlar we ýyllar"' in form


# --- Picking the book or the duplicate (no numbers to type) ----------------------------------


def _choices(html: str, field: str) -> list[str]:
    return re.findall(rf'name="{field}" value="(\d+)"', html)


def test_the_newest_books_are_offered_even_when_the_titles_differ(admin, db):
    rid = ask(db, make_user(db, "+99365000001"), "Türkmen halk ertekileri")
    uploaded = add_book(db, "Ertekiler ýygyndysy", published=False)  # nothing in common with the title
    html = admin.get(f"/admin/requests/{rid}").text
    assert str(uploaded) in _choices(html, "book_id")
    assert "Meňzeş we soňky goşulan kitaplar" in html
    assert 'name="book_id" type="text"' not in html  # no number box to fill in


def test_the_admin_searches_for_the_book_to_fulfil_with(admin, db):
    rid = ask(db, make_user(db, "+99365000001"), "Garagum")
    wanted = add_book(db, "Çölüň aýdymy", "Berdi Kerbabaýew")
    for i in range(10):
        add_book(db, f"Başga kitap {i}")  # push it out of the newest few

    assert str(wanted) not in _choices(admin.get(f"/admin/requests/{rid}").text, "book_id")
    html = admin.get(f"/admin/requests/{rid}", params={"book_q": "kerbabayew"}).text
    assert _choices(html, "book_id") == [str(wanted)]
    assert "«kerbabayew» boýunça tapylan kitaplar" in html

    admin.post(f"/admin/requests/{rid}/fulfil", data={"book_id": str(wanted)})
    assert db.execute("SELECT fulfilled_book_id FROM requests WHERE id = ?", (rid,)).fetchone()[0] == wanted


def test_a_search_with_no_results_says_so(admin, db):
    rid = ask(db, make_user(db, "+99365000001"), "Garagum")
    add_book(db, "Görogly")
    html = admin.get(f"/admin/requests/{rid}", params={"book_q": "ýok-beýle-kitap", "req_q": "ýok"}).text
    assert "boýunça kitap tapylmady" in html and "boýunça açyk sorag tapylmady" in html


def test_the_admin_searches_for_the_duplicate_to_merge_into(admin, db):
    uid = make_user(db, "+99365000001")
    rid = ask(db, uid, "Garagum")
    other = ask(db, uid, "Kerbabaýewiň romany")  # a duplicate nobody would guess from the title
    closed = ask(db, uid, "Kerbabaýew: Aýgytly ädim")
    reqs.reject(db, closed, "x")

    assert str(other) not in _choices(admin.get(f"/admin/requests/{rid}").text, "target_id")
    html = admin.get(f"/admin/requests/{rid}", params={"req_q": "kerbabayew"}).text
    assert _choices(html, "target_id") == [str(other)]  # open ones only, never itself
