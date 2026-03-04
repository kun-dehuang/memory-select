"""Data processing utilities for memory comparison tool.

Supports two data formats:
1. Standard format: {uid, text, timestamp, category, metadata}
2. Phase1 Events format: {event_id, batch, date, time_of_day, location, participants, activity}
"""

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

# Import MemoryRecord model for type compatibility
from models import MemoryRecord


# City extraction mapping for common locations
# Format: keyword -> (country, city)
COUNTRY_CITY_MAP = {
    # Spain
    "巴塞罗那": ("西班牙", "巴塞罗那"),
    "西班牙": ("西班牙", "巴塞罗那"),
    # Italy
    "佛罗伦萨": ("意大利", "佛罗伦萨"),
    "意大利": ("意大利", "佛罗伦萨"),
    "老桥": ("意大利", "佛罗伦萨"),
    "阿诺河": ("意大利", "佛罗伦萨"),
    # China - Beijing
    "北京": ("中国", "北京"),
    "中国尊": ("中国", "北京"),
    "央视大楼": ("中国", "北京"),
    "北海公园": ("中国", "北京"),
    "鲁迅博物馆": ("中国", "北京"),
    "地坛公园": ("中国", "北京"),
    "五道营": ("中国", "北京"),
    "什刹海": ("中国", "北京"),
    "南锣鼓巷": ("中国", "北京"),
    "新鼎大厦": ("中国", "北京"),
    "红枫景区": ("中国", "北京"),
    "银杏林": ("中国", "北京"),
    "GEORGIA": ("中国", "北京"),
    "珍宝海鲜": ("中国", "新加坡"),  # JUMBO SEAFOOD is Singaporean
    "JIMBO": ("中国", "新加坡"),  # JIMBO SEAFOOD
    # Other China cities
    "兴义": ("中国", "兴义"),
    "厦门": ("中国", "厦门"),
    "湖边": ("中国", "北京"),  # Default to Beijing
    "红枫景区": ("中国", "北京"),
    # Indonesia
    "巴厘岛": ("印度尼西亚", "巴厘岛"),
    # Home default
    "家中": ("中国", "北京"),
}

# Patterns that should NOT be extracted as cities
SKIP_CITY_PATTERNS = [
    "某", "餐厅", "酒吧", "咖啡", "风格", "装饰", "主题",
    "YYY", "FUSION", "JONCAKE", "CASINO", "W Hotel",
    "Sagrada", "Familia", "CARRE", "SAN", "PERE",
    "PANTHECELL", "SHAKSHUKA", "SERENDIPITY",
    "同一", "室内", "室外", "周边", "附近", "广场", "街道",
]


def extract_city_from_location(location: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract country and city from location string.

    Args:
        location: Location description

    Returns:
        Tuple of (country, city)
    """
    if not location:
        return None, None

    # Check for known locations first
    for key, (country, city) in COUNTRY_CITY_MAP.items():
        if key in location:
            return country, city

    # Try to extract city pattern, but skip certain patterns
    city_match = re.search(r'([^（）\s]+)(?:市|城|广场|餐厅|咖啡馆|酒吧|公园|博物馆|街道|景区|附近|周边)', location)
    if city_match:
        potential_city = city_match.group(1)
        # Skip if it matches any skip pattern
        for skip_pattern in SKIP_CITY_PATTERNS:
            if skip_pattern in potential_city:
                return None, None
        # Only return if it's a proper city name (2-4 characters)
        if 2 <= len(potential_city) <= 4:
            return None, potential_city

    return None, None


def parse_date_range(date_str: str) -> Tuple[str, str]:
    """Parse date range string and return start_date and end_date.

    Args:
        date_str: Date string like "2025-10-06 ~ 2025-10-11" or "2025-11-02"

    Returns:
        Tuple of (start_date, end_date) in YYYY-MM-DD format
    """
    if not date_str:
        return "2025-01-01", "2025-01-01"

    # Remove time in parentheses like "2025-11-02（15:39~16:42）"
    date_str = re.sub(r'\([^)]*\)', '', date_str).strip()
    date_str = date_str.replace('（', '').replace('）', '').strip()

    # Handle range format "2025-10-06 ~ 2025-10-11"
    if '~' in date_str or '～' in date_str:
        parts = re.split(r'[~～]', date_str)
        start = parts[0].strip()
        end = parts[1].strip() if len(parts) > 1 else start
        return start, end

    # Single date like "2025-11-02"
    return date_str.strip(), date_str.strip()


def extract_season_from_date(date_str: str) -> Optional[str]:
    """Extract season from date string.

    Args:
        date_str: Date string

    Returns:
        Season like "深秋", "初冬", etc.
    """
    month_match = re.search(r'(\d{4})-(\d{2})', date_str)
    if month_match:
        month = int(month_match.group(2))
        if month in [9, 10]:
            return "秋季"
        elif month in [11]:
            return "深秋/初冬"
        elif month in [12, 1, 2]:
            return "冬季"
        elif month in [3, 4, 5]:
            return "春季"
        elif month in [6, 7, 8]:
            return "夏季"
    return None


def categorize_activity(activity: str, location: str) -> str:
    """Categorize activity based on content and location.

    Args:
        activity: Activity description
        location: Location description

    Returns:
        Category string
    """
    activity_lower = activity.lower()
    location_lower = location.lower()

    # Food & Drink
    if any(keyword in activity_lower for keyword in ['吃', '喝', '点', '外卖', '用餐', '聚餐', '海鲜', '餐厅', '咖啡', '酒吧', '菜', '沙拉']):
        return '餐饮'

    # Shopping
    if any(keyword in activity_lower for keyword in ['购买', '买', '挑选', '下单']):
        return '购物'

    # Health
    if any(keyword in activity_lower for keyword in ['生病', '治疗', '输液', '药', '医']):
        return '健康'

    # Work
    if any(keyword in activity_lower for keyword in ['工作', '办公', '入职', '合同', '报告', '分析']):
        return '工作'

    # Travel
    if any(keyword in location_lower + activity_lower for keyword in ['航班', '机场', '旅行', '巴厘岛', '巴塞罗那', '佛罗伦萨']):
        return '旅行'

    # Social
    if any(keyword in activity_lower for keyword in ['朋友', '聚会', '派对', '合影']):
        return '社交'

    # Culture/Interest
    if any(keyword in activity_lower + location_lower for keyword in ['博物馆', '教堂', '占卜', '运势', '古籍']):
        return '文化兴趣'

    # Home
    if '家中' in location_lower or '家' in location_lower:
        return '居家'

    # Commute
    if any(keyword in activity_lower for keyword in ['驾车', '开车', '通勤', '导航']):
        return '通勤'

    return '日常'


def generate_memory_text(event: Dict) -> str:
    """Generate memory text from event data for semantic search.

    This creates a rich, natural language description that includes:
    - Time context
    - Location
    - Participants
    - Activity details

    Args:
        event: Event dictionary with phase1 format

    Returns:
        Natural language memory text
    """
    date = event.get("date", "")
    time_of_day = event.get("time_of_day", "")
    location = event.get("location", "")
    participants = event.get("participants", [])
    activity = event.get("activity", "")

    # Build time context
    time_context = ""
    if date:
        # Clean date string
        clean_date = re.sub(r'\([^)]*\)', '', date).replace('（', '').replace('）', '').strip()
        time_context = clean_date
        if time_of_day:
            time_context += f"的{time_of_day}"

    # Build participants text
    participants_text = ""
    if participants:
        # Filter out generic terms and get main characters
        main_participants = [p for p in participants if p not in ["摊主", "店员", "四位中年男性同伴", "多名朋友"]]
        if main_participants:
            participants_text = main_participants[0] if len(main_participants) == 1 else "、".join(main_participants[:2])

    # Build full text
    text_parts = []

    if participants_text:
        text_parts.append(participants_text)

    if time_context:
        text_parts.append(f"在{time_context}")
    elif time_of_day:
        text_parts.append(f"在{time_of_day}")

    if location:
        text_parts.append(f"于{location}")

    if activity:
        text_parts.append(activity)

    memory_text = "，".join(text_parts) + "。"
    return memory_text


def convert_phase1_to_standard(event: Dict, user_id: str = "ouyang_bingjie") -> MemoryRecord:
    """Convert phase1 event format to standard memory format.

    Args:
        event: Event dictionary with phase1 format
        user_id: User ID for the memory

    Returns:
        MemoryRecord object
    """
    # Parse date
    date_str = event.get("date", "")
    start_date, end_date = parse_date_range(date_str)

    # Extract location info
    location = event.get("location", "")
    country, city = extract_city_from_location(location)
    season = extract_season_from_date(date_str)

    # Build metadata
    metadata = {
        "event_id": event.get("event_id"),
        "batch": event.get("batch"),
        "date_range": date_str,
        "end_date": end_date,
        "time_of_day": event.get("time_of_day"),
        "location": location,
        "city": city,
        "country": country,
        "participants": event.get("participants", []),
        "activity": event.get("activity"),
    }

    # Add season if available
    if season:
        metadata["season"] = season

    # Generate semantic text
    text = generate_memory_text(event)

    # Categorize
    category = categorize_activity(event.get("activity", ""), location)

    return MemoryRecord(
        uid=user_id,
        text=text,
        timestamp=start_date,
        category=category,
        metadata=metadata
    )


class DataProcessor:
    """Process JSON data files for memory comparison."""

    def __init__(self):
        self.processed_records: List[MemoryRecord] = []
        self.data_format = "unknown"  # "standard" or "phase1_events"

    @classmethod
    def from_data(cls, data: Any, user_id: str = "ouyang_bingjie") -> "DataProcessor":
        """Create a DataProcessor instance from data.

        Args:
            data: Raw JSON data (list of dicts)
            user_id: User ID for phase1 format conversion

        Returns:
            DataProcessor instance with processed records
        """
        processor = cls()
        processor.process_data(data, user_id=user_id)
        return processor

    def process(self) -> List[MemoryRecord]:
        """Process and return records (alias for compatibility).

        Returns:
            List of MemoryRecord objects
        """
        return self.processed_records

    def process_file(self, file_path: str, user_id: str = "default_user") -> List[MemoryRecord]:
        """Process a JSON file.

        Args:
            file_path: Path to JSON file
            user_id: User ID for phase1 format conversion

        Returns:
            List of processed records
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return self.process_data(data, user_id=user_id)

    def process_data(self, data: Any, user_id: str = "default_user") -> List[MemoryRecord]:
        """Process raw data.

        Args:
            data: Raw data (list of dicts)
            user_id: User ID for phase1 format conversion

        Returns:
            List of MemoryRecord objects
        """
        if not isinstance(data, list) or len(data) == 0:
            self.processed_records = []
            self.data_format = "unknown"
            return self.processed_records

        first_record = data[0]

        # Detect format
        if "event_id" in first_record and "activity" in first_record:
            # Phase1 events format
            self.data_format = "phase1_events"
            self.processed_records = [
                convert_phase1_to_standard(event, user_id=user_id)
                for event in data
            ]
        elif "uid" in first_record and "text" in first_record:
            # Standard format - convert to MemoryRecord
            self.data_format = "standard"
            self.processed_records = []
            for record in data:
                meta = record.get("meta", {})
                self.processed_records.append(MemoryRecord(
                    uid=record.get("uid", "unknown"),
                    text=record.get("text", ""),
                    timestamp=meta.get("timestamp") or record.get("timestamp", ""),
                    category=meta.get("category") or record.get("category", "unknown"),
                    metadata=meta
                ))
        else:
            # Unknown format, try to convert as phase1
            self.data_format = "phase1_events"
            self.processed_records = [
                convert_phase1_to_standard(event, user_id=user_id)
                for event in data
            ]

        return self.processed_records

    def summary(self) -> Dict[str, Any]:
        """Generate summary of processed records.

        Returns:
            Summary dictionary with stats
        """
        if not self.processed_records:
            return {
                "total_records": 0,
                "user_count": 0,
                "category_count": 0,
                "unique_users": [],
                "unique_categories": [],
                "timestamp_range": None
            }

        users = set()
        categories = set()
        timestamps = []

        for record in self.processed_records:
            users.add(record.uid)
            categories.add(record.category)
            if record.timestamp:
                timestamps.append(str(record.timestamp)[:10])

        summary = {
            "total_records": len(self.processed_records),
            "user_count": len(users),
            "category_count": len(categories),
            "unique_users": sorted(list(users)),
            "unique_categories": sorted(list(categories)),
            "timestamp_range": None
        }

        if timestamps:
            summary["timestamp_range"] = {
                "earliest": min(timestamps),
                "latest": max(timestamps)
            }

        return summary


def process_json_file(file_path: str, user_id: str = "default_user") -> List[Dict]:
    """Process a JSON file and return records.

    Args:
        file_path: Path to JSON file
        user_id: User ID for phase1 format conversion

    Returns:
        List of records in standard format
    """
    processor = DataProcessor()
    return processor.process_file(file_path, user_id=user_id)


def process_json_data(data: Any, user_id: str = "default_user") -> List[Dict]:
    """Process JSON data and return records.

    Args:
        data: Raw JSON data
        user_id: User ID for phase1 format conversion

    Returns:
        List of records in standard format
    """
    processor = DataProcessor()
    return processor.process_data(data, user_id=user_id)
