"""Optional MongoDB extension for flexible amenity/configuration documents.

Set MONGO_URI in the environment and install requirements to enable it.
The relational SQLite database remains the source of truth for employees,
resources, reservations, constraints and transactions.
"""
import os
from datetime import datetime, timezone


def get_collection():
    uri = os.environ.get('MONGO_URI')
    if not uri:
        raise RuntimeError('Set MONGO_URI to enable the optional MongoDB extension.')
    from pymongo import MongoClient
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    db = client[os.environ.get('MONGO_DB', 'smart_office')]
    return client, db['resource_metadata']


def save_resource_metadata(resource_type, resource_id, amenities=None, configuration=None):
    client, collection = get_collection()
    try:
        doc = {'resource_type': resource_type, 'resource_id': int(resource_id),
               'amenities': amenities or [], 'configuration': configuration or {},
               'updated_at': datetime.now(timezone.utc)}
        collection.update_one({'resource_type': resource_type, 'resource_id': int(resource_id)},
                              {'$set': doc}, upsert=True)
        return doc
    finally:
        client.close()


def aggregate_amenity_usage():
    client, collection = get_collection()
    try:
        pipeline = [{'$unwind': '$amenities'}, {'$group': {'_id': '$amenities', 'resources': {'$sum': 1}}},
                    {'$sort': {'resources': -1}}]
        return list(collection.aggregate(pipeline))
    finally:
        client.close()
