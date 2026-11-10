"""Django fixture JSON with full microsecond precision for instance transfers."""
import datetime
from django.core.serializers.json import DjangoJSONEncoder, Serializer as JSONSerializer, Deserializer


class PreciseEncoder(DjangoJSONEncoder):
    def default(self, value):
        if isinstance(value, (datetime.datetime, datetime.time)):
            return value.isoformat()
        return super().default(value)


class Serializer(JSONSerializer):
    def _init_options(self):
        super()._init_options()
        self.json_kwargs["cls"] = PreciseEncoder
