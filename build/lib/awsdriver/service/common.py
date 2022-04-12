import uuid
from datetime import datetime
from ignition.utils.propvaluemap import PropValueMap


CREATE_REQUEST_PREFIX = 'Create'
DELETE_REQUEST_PREFIX = 'Delete'

REQUEST_ID_SEPARATOR = '::'

def build_request_id(request_type, stack_id):
    request_id = request_type
    request_id += REQUEST_ID_SEPARATOR
    request_id += stack_id
    request_id += REQUEST_ID_SEPARATOR
    request_id += str(uuid.uuid4())
    return request_id


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        serial = obj.isoformat()
        return serial
    raise TypeError('Type not serializable')


class PropertiesMerger:

    def merge(self, properties, system_properties):
        new_props = {k:v for k,v in properties.items_with_types()}
        for k, v in system_properties.items_with_types():
            new_key = 'system_{0}'.format(k)
            new_props[new_key] = v
        return PropValueMap(new_props)
