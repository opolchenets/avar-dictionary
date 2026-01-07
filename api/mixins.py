from typing import Callable, Mapping, Union
from django.db.models import QuerySet


FilterFunc = Callable[[QuerySet, str], QuerySet]


class QueryParamsFilterMixin:
    """Filter a queryset based on request query parameters."""

    query_params_map: Mapping[str, Union[str, FilterFunc]] = {}

    def filter_queryset_by_params(self, queryset: QuerySet) -> QuerySet:
        for param, lookup in self.query_params_map.items():
            value = self.request.query_params.get(param)
            if not value:
                continue
            if callable(lookup):
                queryset = lookup(queryset, value)
            else:
                queryset = queryset.filter(**{lookup: value})
        return queryset

    def get_queryset(self) -> QuerySet:
        """Return the base queryset filtered by mapped query params."""
        queryset = super().get_queryset()
        return self.filter_queryset_by_params(queryset)
