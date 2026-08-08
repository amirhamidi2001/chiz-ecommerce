from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class BlogPagination(PageNumberPagination):
    """
    Matches the response envelope of the existing shop StandardResultsPagination
    but adds total_pages and current_page for frontend convenience.
    """

    page_size = 6
    page_size_query_param = "page_size"
    max_page_size = 24

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "total_pages": self.page.paginator.num_pages,
                "current_page": self.page.number,
                "results": data,
            }
        )

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "required": ["count", "results"],
            "properties": {
                "count": {"type": "integer"},
                "next": {"type": "string", "nullable": True},
                "previous": {"type": "string", "nullable": True},
                "total_pages": {"type": "integer"},
                "current_page": {"type": "integer"},
                "results": schema,
            },
        }
