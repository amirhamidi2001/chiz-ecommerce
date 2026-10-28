"""
Tests for search-query logging (SearchQueryLog, shop.tasks.log_search_query,
ProductListView._log_search, SearchQueryLogAdmin).

Conventions follow the rest of the project: view tests patch
`shop.views.log_search_query.delay` (no broker, no worker — see
test_signals.py / test_price_drop.py); the task itself is tested by calling
it directly as a plain function (see test_tasks.py). `run_log_tasks` is the
glue for the end-to-end cases: it makes the patched .delay execute the real
task body immediately, i.e. what a worker would do a moment later.
"""

from unittest.mock import patch

import pytest
from django.db import connection
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from shop.admin import SearchQueryLogAdmin, ZeroResultsFilter
from shop.models import SearchQueryLog
from shop.tasks import log_search_query
from shop.tests.factories import ProductFactory, UserFactory


def search(client, term=None, **params):
    if term is not None:
        params["search"] = term
    return client.get(reverse("product-list"), params)


@pytest.fixture
def run_log_tasks():
    """Patch .delay so it runs log_search_query synchronously."""
    with patch(
        "shop.views.log_search_query.delay",
        side_effect=lambda *a, **kw: log_search_query(*a, **kw),
    ) as mock_delay:
        yield mock_delay


@pytest.fixture
def mock_delay():
    """Patch .delay and do nothing — for asserting what WOULD be enqueued."""
    with patch("shop.views.log_search_query.delay") as m:
        yield m


@pytest.fixture
def rose_catalog(db):
    """3 products matching 'rose', 2 that don't."""
    for i in range(3):
        ProductFactory(name=f"Rose Item {i}")
    ProductFactory(name="Matte Lipstick")
    ProductFactory(name="Running Shoes")


# ═══════════════════════════════════════════════════════════════════════════════
# What gets logged
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestSearchIsLogged:

    def test_a_search_creates_exactly_one_log_row(
        self, api_client, rose_catalog, run_log_tasks
    ):
        res = search(api_client, "rose")

        assert res.status_code == status.HTTP_200_OK
        assert SearchQueryLog.objects.count() == 1
        row = SearchQueryLog.objects.get()
        assert row.query == "rose"
        assert row.result_count == 3
        assert row.user is None
        assert row.created_at is not None

    def test_the_task_is_enqueued_with_term_count_and_user_id(
        self, api_client, rose_catalog, mock_delay
    ):
        search(api_client, "rose")
        mock_delay.assert_called_once_with("rose", 3, None)

    @pytest.mark.parametrize(
        "params",
        [
            {},  # plain browsing
            {"search": ""},
            {"search": "   "},
            {"search": "\u200c\u200b\ufeff"},  # only zero-width characters
            {"category": "anything", "ordering": "price"},  # filters, no search
        ],
        ids=["absent", "empty", "whitespace", "zero-width-only", "other-filters-only"],
    )
    def test_no_log_without_a_real_search_term(
        self, api_client, rose_catalog, run_log_tasks, params
    ):
        api_client.get(reverse("product-list"), params)
        run_log_tasks.assert_not_called()
        assert SearchQueryLog.objects.count() == 0

    def test_suggest_endpoint_is_not_logged(self, api_client, rose_catalog, mock_delay):
        """Autocomplete fires per keystroke; those are not searches."""
        res = api_client.get(reverse("product-suggest"), {"q": "rose"})
        assert res.status_code == status.HTTP_200_OK
        mock_delay.assert_not_called()

    def test_a_search_with_no_matches_is_logged_with_zero(
        self, api_client, rose_catalog, run_log_tasks
    ):
        res = search(api_client, "zzzqqq")
        assert res.status_code == status.HTTP_200_OK
        row = SearchQueryLog.objects.get()
        assert (row.query, row.result_count) == ("zzzqqq", 0)

    def test_unsearchable_input_is_logged_without_error(
        self, api_client, rose_catalog, run_log_tasks
    ):
        res = search(api_client, "!!!")
        assert res.status_code == status.HTTP_200_OK
        assert SearchQueryLog.objects.get().result_count == 0


# ═══════════════════════════════════════════════════════════════════════════════
# result_count accuracy
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestResultCount:

    def test_counts_the_matching_products_not_the_whole_catalog(
        self, api_client, rose_catalog, run_log_tasks
    ):
        search(api_client, "rose")
        assert SearchQueryLog.objects.get().result_count == 3  # 5 products exist

    def test_counts_all_matches_not_just_the_current_page(
        self, api_client, db, run_log_tasks
    ):
        for i in range(5):
            ProductFactory(name=f"Rose Item {i}")
        res = search(api_client, "rose", page_size=2)
        assert len(res.data["results"]) == 2
        assert SearchQueryLog.objects.get().result_count == 5

    def test_matches_the_count_returned_to_the_customer(
        self, api_client, rose_catalog, run_log_tasks
    ):
        res = search(api_client, "rose")
        assert SearchQueryLog.objects.get().result_count == res.data["count"]

    def test_reflects_other_filters_applied_to_the_search(
        self, api_client, db, run_log_tasks
    ):
        ProductFactory(name="Rose Cheap", price=50_000)
        ProductFactory(name="Rose Dear", price=5_000_000)
        search(api_client, "rose", min_price=1_000_000)
        assert SearchQueryLog.objects.get().result_count == 1


# ═══════════════════════════════════════════════════════════════════════════════
# User attribution
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestUserAttribution:

    def test_authenticated_search_records_the_user(
        self, auth_client, user, rose_catalog, run_log_tasks
    ):
        search(auth_client, "rose")
        assert SearchQueryLog.objects.get().user == user

    def test_authenticated_search_enqueues_the_user_id(
        self, auth_client, user, rose_catalog, mock_delay
    ):
        search(auth_client, "rose")
        mock_delay.assert_called_once_with("rose", 3, user.id)

    def test_anonymous_search_records_no_user(
        self, api_client, rose_catalog, run_log_tasks
    ):
        search(api_client, "rose")
        assert SearchQueryLog.objects.get().user is None


# ═══════════════════════════════════════════════════════════════════════════════
# No added latency: no extra database work on the search request
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestNoRedundantQueries:

    def test_search_does_not_run_the_product_matching_query_twice(
        self, api_client, rose_catalog, mock_delay
    ):
        """
        The match count is taken from the paginator's already-computed
        `count`, so logging must not add its own .count(). Locks that in: a
        search is exactly ONE COUNT query (DRF's pagination) plus ONE page
        query. A future refactor that calls queryset.count() for logging
        would make this 2 COUNTs / 3 matching queries.
        """
        with CaptureQueriesContext(connection) as ctx:
            res = search(api_client, "rose")
        assert res.status_code == status.HTTP_200_OK

        sql = [q["sql"] for q in ctx.captured_queries]
        matching = [q for q in sql if "@@" in q]  # the tsvector match
        counts = [q for q in matching if "COUNT(" in q.upper()]
        assert len(counts) == 1, "search ran more than one COUNT query"
        assert len(matching) == 2, "matching query ran more than count + page"

    def test_logging_itself_adds_no_database_queries(
        self, api_client, rose_catalog, mock_delay
    ):
        with CaptureQueriesContext(connection) as with_search:
            search(api_client, "rose")
        # Same request shape with logging switched off entirely.
        with patch("shop.views.ProductListView._log_search"):
            api_client.handler  # noqa: B018 (keep client warm; cache cleared next)
            from django.core.cache import cache

            cache.clear()
            with CaptureQueriesContext(connection) as without_logging:
                search(api_client, "rose")
        assert len(with_search) == len(without_logging)

    def test_the_log_write_is_deferred_not_done_in_the_request(
        self, api_client, rose_catalog, mock_delay
    ):
        search(api_client, "rose")
        # Enqueued, but nothing written until the task actually runs.
        mock_delay.assert_called_once()
        assert SearchQueryLog.objects.count() == 0

    def test_cached_search_runs_no_product_queries_but_is_still_logged(
        self, api_client, rose_catalog, mock_delay
    ):
        search(api_client, "rose")  # warms the 60s response cache
        with CaptureQueriesContext(connection) as ctx:
            res = search(api_client, "rose")

        assert res.status_code == status.HTTP_200_OK
        assert len(ctx) == 0  # served from cache; count came from cached data
        assert mock_delay.call_count == 2  # ...and both searches were logged
        assert mock_delay.call_args_list[1].args == ("rose", 3, None)


# ═══════════════════════════════════════════════════════════════════════════════
# Term handling
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestLoggedTerm:

    def test_term_is_lowercased_trimmed_and_whitespace_collapsed(
        self, api_client, rose_catalog, mock_delay
    ):
        search(api_client, "  ROSE   Cream ")
        assert mock_delay.call_args.args[0] == "rose cream"

    def test_persian_character_variants_are_logged_in_canonical_form(
        self, api_client, db, mock_delay
    ):
        search(api_client, "كرم آرايشي")  # Arabic kaf / yeh
        assert mock_delay.call_args.args[0] == "کرم آرایشی"  # Persian forms

    def test_zwnj_is_stripped_from_the_logged_term(self, api_client, db, mock_delay):
        search(api_client, "ضد\u200cآفتاب")
        assert mock_delay.call_args.args[0] == "ضدآفتاب"

    def test_overlong_term_is_truncated_and_the_row_still_saves(
        self, api_client, db, run_log_tasks
    ):
        res = search(api_client, "x" * 5000)
        assert res.status_code == status.HTTP_200_OK
        assert len(SearchQueryLog.objects.get().query) == 255

    def test_only_the_first_page_of_a_search_is_logged(
        self, api_client, db, mock_delay
    ):
        for i in range(5):
            ProductFactory(name=f"Rose Item {i}")
        search(api_client, "rose", page_size=2)  # page 1 (implicit)
        search(api_client, "rose", page_size=2, page=1)
        search(api_client, "rose", page_size=2, page=2)
        search(api_client, "rose", page_size=2, page=3)
        assert mock_delay.call_count == 2

    def test_failed_requests_are_not_logged(self, api_client, db, mock_delay):
        ProductFactory(name="Rose Item")
        res = search(api_client, "rose", page=999)  # past the last page -> 404
        assert res.status_code == status.HTTP_404_NOT_FOUND
        mock_delay.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# Logging must never break search
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestLoggingFailureIsHarmless:

    def test_search_still_succeeds_when_the_broker_is_down(
        self, api_client, rose_catalog, mock_delay
    ):
        mock_delay.side_effect = ConnectionError("broker unreachable")
        res = search(api_client, "rose")
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] == 3

    def test_failure_is_logged_as_a_warning(
        self, api_client, rose_catalog, mock_delay, caplog
    ):
        mock_delay.side_effect = ConnectionError("broker unreachable")
        with caplog.at_level("WARNING", logger="shop.views"):
            search(api_client, "rose")
        assert "Could not enqueue search-query log" in caplog.text


# ═══════════════════════════════════════════════════════════════════════════════
# The task and the model
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestLogSearchQueryTask:

    def test_creates_a_row(self):
        log_search_query("rose", 4, None)
        row = SearchQueryLog.objects.get()
        assert (row.query, row.result_count, row.user_id) == ("rose", 4, None)

    def test_records_the_user(self):
        user = UserFactory()
        log_search_query("rose", 4, user.id)
        assert SearchQueryLog.objects.get().user == user

    @pytest.mark.django_db(transaction=True)
    def test_a_since_deleted_user_does_not_lose_the_search(self):
        # transaction=True: Postgres defers FK checks to COMMIT, so the
        # violation (and the task's fallback) only happens with a real
        # commit — inside pytest's wrapping transaction it never would.
        log_search_query("rose", 4, 987654321)  # no such user
        row = SearchQueryLog.objects.get()
        assert row.query == "rose" and row.user_id is None

    def test_result_is_not_stored(self):
        assert log_search_query.ignore_result is True


@pytest.mark.django_db
class TestSearchQueryLogModel:

    def test_str(self):
        assert str(SearchQueryLog(query="rose", result_count=3)) == "'rose' (3 results)"

    def test_newest_first(self):
        first = SearchQueryLog.objects.create(query="a", result_count=1)
        second = SearchQueryLog.objects.create(query="b", result_count=1)
        assert list(SearchQueryLog.objects.all()) == [second, first]

    def test_deleting_a_user_keeps_their_search_history_anonymously(self):
        user = UserFactory()
        log = SearchQueryLog.objects.create(query="a", result_count=1, user=user)
        user.delete()
        log.refresh_from_db()
        assert log.user is None


# ═══════════════════════════════════════════════════════════════════════════════
# Admin
# ═══════════════════════════════════════════════════════════════════════════════
def _filter_request(results=None):
    path = "/admin/shop/searchquerylog/"
    if results is not None:
        path += f"?results={results}"
    return RequestFactory().get(path)


def _apply_filter(results):
    request = _filter_request(results)
    f = ZeroResultsFilter(request, dict(request.GET.lists()), SearchQueryLog, None)
    return f.queryset(request, SearchQueryLog.objects.all())


@pytest.fixture
def mixed_logs(db):
    SearchQueryLog.objects.create(query="found it", result_count=7)
    SearchQueryLog.objects.create(query="nothing", result_count=0)
    SearchQueryLog.objects.create(query="nothing", result_count=0)


@pytest.mark.django_db
class TestZeroResultsFilter:

    def test_zero_shows_only_zero_result_searches(self, mixed_logs):
        qs = _apply_filter("zero")
        assert qs.count() == 2
        assert set(qs.values_list("query", flat=True)) == {"nothing"}

    def test_some_shows_only_searches_with_results(self, mixed_logs):
        assert list(_apply_filter("some").values_list("query", flat=True)) == [
            "found it"
        ]

    def test_no_selection_shows_everything(self, mixed_logs):
        assert _apply_filter(None).count() == 3


@pytest.mark.django_db
class TestSearchQueryLogAdmin:

    @pytest.fixture
    def admin_client(self, db):
        staff = UserFactory(is_staff=True, is_superuser=True)
        # UserFactory sets the password hash in memory but skips the
        # post-generation save, so persist it — otherwise the session auth
        # hash won't match the DB row and Django discards the login.
        staff.save()
        client = Client()
        client.force_login(staff)
        return client

    def test_is_read_only(self, admin_client):
        from django.contrib.admin.sites import site

        model_admin = site._registry[SearchQueryLog]
        assert isinstance(model_admin, SearchQueryLogAdmin)
        request = RequestFactory().get("/")
        assert model_admin.has_add_permission(request) is False
        assert model_admin.has_change_permission(request) is False
        assert set(model_admin.readonly_fields) == {
            f.name for f in SearchQueryLog._meta.fields
        }

    def test_changelist_renders_and_the_zero_filter_works(
        self, admin_client, mixed_logs
    ):
        url = reverse("admin:shop_searchquerylog_changelist")
        assert admin_client.get(url).status_code == 200

        res = admin_client.get(url, {"results": "zero"})
        assert res.status_code == 200
        shown = list(res.context["cl"].queryset)
        assert len(shown) == 2 and all(r.result_count == 0 for r in shown)

    def test_add_page_is_forbidden(self, admin_client):
        res = admin_client.get(reverse("admin:shop_searchquerylog_add"))
        assert res.status_code == 403
