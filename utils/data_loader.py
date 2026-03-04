"""Data loading utilities for memory comparison tool."""

import json
from typing import Any, Dict, List, Tuple


def load_json_file(file_path: str) -> Dict:
    """Load JSON data from file.

    Args:
        file_path: Path to JSON file

    Returns:
        Parsed JSON data
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def parse_memory_records(data: List[Dict]) -> List[Dict]:
    """Parse memory records from data.

    Args:
        data: Raw data list

    Returns:
        Parsed memory records
    """
    return data


def validate_data_format(data: Any) -> Tuple[bool, str]:
    """Validate that data has the correct format.

    Supports two formats:
    1. Standard format: {uid, text, meta/...}
    2. Phase1 Events format: {event_id, date, location, participants, activity}

    Args:
        data: Data to validate

    Returns:
        Tuple of (is_valid, message)
    """
    if not isinstance(data, list):
        return False, "Data must be a list of records"

    if len(data) == 0:
        return False, "Data is empty"

    # Check first record structure
    first_record = data[0]
    if not isinstance(first_record, dict):
        return False, "Each record must be a dictionary"

    # Check for standard format (uid + text)
    has_uid = "uid" in first_record
    has_text = "text" in first_record

    # Check for phase1 events format
    has_event_id = "event_id" in first_record
    has_activity = "activity" in first_record
    has_location = "location" in first_record

    if has_uid and has_text:
        return True, "Valid standard format"
    elif has_event_id and has_activity and has_location:
        return True, "Valid Phase1 Events format (will be converted)"
    elif has_event_id or has_activity:
        # Partial phase1 format
        return True, "Partial Phase1 Events format (will be converted)"
    else:
        return False, "Unrecognized format. Need either (uid + text) or (event_id + activity + location)"


def get_unique_users(data: List[Dict]) -> List[str]:
    """Get list of unique user IDs from data.

    Handles both standard format (with uid field) and phase1_events format
    (which defaults to "ouyang_bingjie").

    Args:
        data: List of memory records

    Returns:
        Sorted list of unique user IDs
    """
    uids = set()

    # Check if data is phase1_events format
    if data and isinstance(data[0], dict):
        first_record = data[0]
        if "event_id" in first_record and "activity" in first_record:
            # Phase1 events format - use default user
            return ["ouyang_bingjie"]

    # Standard format - extract uid from each record
    for record in data:
        uid = record.get("uid")
        if uid:
            uids.add(uid)

    return sorted(list(uids)) if uids else ["default_user"]


def get_categories(data: List[Dict]) -> List[str]:
    """Get list of unique categories from data.

    Args:
        data: List of memory records

    Returns:
        Sorted list of unique categories
    """
    categories = set()
    for record in data:
        category = record.get("meta", {}).get("category")
        if category:
            categories.add(category)
    return sorted(list(categories))
