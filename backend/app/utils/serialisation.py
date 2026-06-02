"""MongoDB document serialisation utilities."""

from __future__ import annotations


def serialise_doc(doc: dict) -> dict:
    """Convert a MongoDB document's ObjectId _id field to a plain string in-place."""
    doc["_id"] = str(doc["_id"])
    return doc
