import pytest
from blog.tests.conftest import PostFactory
from rest_framework.test import APIClient


@pytest.fixture
def client():
    return APIClient()


URL = "/api/blog/posts/"


@pytest.mark.django_db
class TestBlogPagination:

    def test_response_envelope_has_all_required_keys(self, client):
        PostFactory()
        response = client.get(URL)
        assert response.status_code == 200
        keys = set(response.data.keys())
        assert {
            "count",
            "next",
            "previous",
            "total_pages",
            "current_page",
            "results",
        } <= keys

    def test_default_page_size_is_six(self, client):
        # Create 10 published posts; default page should return 6
        PostFactory.create_batch(10)
        response = client.get(URL)
        assert len(response.data["results"]) == 6

    def test_count_reflects_total_published(self, client):
        PostFactory.create_batch(4)
        response = client.get(URL)
        assert response.data["count"] == 4

    def test_total_pages_calculated_correctly(self, client):
        PostFactory.create_batch(13)  # ceil(13/6) = 3 pages
        response = client.get(URL)
        assert response.data["total_pages"] == 3

    def test_current_page_is_one_on_first_request(self, client):
        PostFactory.create_batch(3)
        response = client.get(URL)
        assert response.data["current_page"] == 1

    def test_current_page_advances_with_page_param(self, client):
        PostFactory.create_batch(8)
        response = client.get(URL + "?page=2")
        assert response.data["current_page"] == 2

    def test_next_link_present_when_more_pages_exist(self, client):
        PostFactory.create_batch(8)
        response = client.get(URL)
        assert response.data["next"] is not None

    def test_previous_link_null_on_first_page(self, client):
        PostFactory.create_batch(8)
        response = client.get(URL)
        assert response.data["previous"] is None

    def test_previous_link_present_on_second_page(self, client):
        PostFactory.create_batch(8)
        response = client.get(URL + "?page=2")
        assert response.data["previous"] is not None

    def test_next_link_null_on_last_page(self, client):
        PostFactory.create_batch(3)  # all fit on one page
        response = client.get(URL)
        assert response.data["next"] is None

    def test_page_size_query_param_overrides_default(self, client):
        PostFactory.create_batch(10)
        response = client.get(URL + "?page_size=3")
        assert len(response.data["results"]) == 3

    def test_page_size_capped_at_max_24(self, client):
        PostFactory.create_batch(30)
        response = client.get(URL + "?page_size=100")
        # Should be capped at 24, not 100
        assert len(response.data["results"]) == 24

    def test_empty_result_set_returns_correct_envelope(self, client):
        response = client.get(URL)
        assert response.status_code == 200
        assert response.data["count"] == 0
        assert response.data["results"] == []
        assert response.data["total_pages"] == 1
        assert response.data["current_page"] == 1
