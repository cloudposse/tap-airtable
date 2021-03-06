from services.fields_mapping import FieldsMapping
from utils.json_utils import JsonUtils, Relations
import requests
import json
import singer


class Airtable(object):
    with open('./config.json', 'r') as f:
        config = json.load(f)
        metadata_url = config["metadata_url"]
        records_url = config["records_url"]
        token = config["token"]

    @classmethod
    def run_discovery(cls, base_id):
        headers = {'Authorization': 'Bearer {}'.format(cls.token)}
        response = requests.get(url=cls.metadata_url + base_id, headers=headers)
        schemas = []

        for table in response.json()["tables"]:

            columns = {}
            schema = {"name": table["name"],
                      "properties": columns}

            columns["id"] = {"type": ["null", "string"], 'key': True}

            for field in table["fields"]:
                if not field["name"] == "Id":
                    columns[field["name"]] = {"type": ["null", FieldsMapping.map_field(field["config"])]}

            schemas.append(schema)

        with open('./services/{}_schemas.json'.format(base_id), 'w') as outfile:
            json.dump(schemas, outfile)

    @classmethod
    def run_tap(cls, base_id):

        with open('./services/{}_schemas.json'.format(base_id), 'r') as f:
            schemas = json.load(f)

        for schema in schemas:
            table = schema["name"].replace('/', '')
            table = table.replace(' ', '')

            if table != 'relations':
                response = Airtable.get_response(base_id, schema["name"])
                if response.json().get('records'):
                    records = JsonUtils.match_record_with_keys(schema,
                                                               response.json().get('records'))

                singer.write_schema(table, schema, 'id')
                singer.write_records(table, records)

                offset = response.json().get("offset")

                while offset:
                    response = Airtable.get_response(base_id, schema["name"], offset)
                    if response.json().get('records'):
                        records = JsonUtils.match_record_with_keys(schema,
                                                                   response.json().get('records'))

                    singer.write_records(table, records)
                    offset = response.json().get("offset")

        relations_table = {"name": "relations",
                           "properties": {"id": {"type": ["null", "string"]},
                                          "relation1": {"type": ["null", "string"]},
                                          "relation2": {"type": ["null", "string"]}}}

        singer.write_schema('relations', relations_table, 'id')
        singer.write_records('relations', Relations.get_records())

    @classmethod
    def get_response(cls, base_id, table, offset=None):

        headers = {'Authorization': 'Bearer {}'.format(cls.token)}
        table = table.replace('/', '%2F')

        if offset:
            request = cls.records_url + base_id + '/' + table + '?offset={}'.format(offset)
        else:
            request = cls.records_url + base_id + '/' + table

        return requests.get(url=request, headers=headers)
