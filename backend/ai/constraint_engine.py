import re
from enum import Enum


class ConstraintType(Enum):
    HARD = 'hard'
    SOFT = 'soft'


class Constraint:
    def __init__(self, category, value, constraint_type=ConstraintType.SOFT, raw_text=''):
        self.category = category
        self.value = value
        self.type = constraint_type
        self.raw_text = raw_text

    def __repr__(self):
        return f'Constraint({self.category}={self.value}, type={self.type.value})'


_HARD_CONSTRAINT_PATTERNS = [
    (r'\b(?:must|must have|require|requires|need|needs|need to have)\b', 'requirement'),
    (r'\bcuda\b', 'cuda'),
    (r'\blinux\b', 'os_linux'),
    (r'\bwindows\b', 'os_windows'),
    (r'\bmacos?\b', 'os_mac'),
    (r'\bunder \$?\s*(\d[\d,]*)\b', 'max_price'),
    (r'\bbelow \$?\s*(\d[\d,]*)\b', 'max_price'),
    (r'\bless than \$?\s*(\d[\d,]*)\b', 'max_price'),
    (r'\bmax\s+(?:price|cost)\s+\$?\s*(\d[\d,]*)\b', 'max_price'),
    (r'\bover \$?\s*(\d[\d,]*)\b', 'min_price'),
    (r'\babove \$?\s*(\d[\d,]*)\b', 'min_price'),
    (r'\bmore than \$?\s*(\d[\d,]*)\b', 'min_price'),
    (r'\b(?:at least|minimum)\s+\$?\s*(\d[\d,]*)\b', 'min_price'),
    (r'\b(\d+)\s*(?:gb|tb|mb)\b', 'storage'),
    (r'\b(\d+)\s*(?:gb|tb)\s*(?:ram|memory|ram)\b', 'ram'),
    (r'\b(\d+)\s*(?:inch|in|cm|mm)\b', 'screen_size'),
    (r'\b(\d+)\s*(?:hour|hr|h)\s*(?:battery|life)\b', 'battery'),
    (r'\b(\d+)\s*(?:hour|hr|h)\b', 'battery'),
    (r'\b(?:no more than|not more than|max)\s+(\d+)\s*(?:hour|hr|h)\b', 'max_battery'),
    (r'\b(?:at most|maximum)\s+(\d+)\s*(?:hour|hr|h)\b', 'max_battery'),
    (r'\bweight\s*(?:under|below|less than|max|maximum)\s*(\d+)\s*(?:kg|lb|g)\b', 'max_weight'),
    (r'\b(\d+)\s*(?:kg|lb)\b', 'weight'),
    (r'\b(?:exactly|precisely|specific)\s+(.+?)(?:\s+|$)\b', 'exact'),
]

_SOFT_CONSTRAINT_PATTERNS = [
    (r'\b(?:prefer|preferably|would like|ideally|nice to have|if possible)\b', 'preference'),
    (r'\b(?:good|best|great|excellent|high.?quality)\b', 'quality'),
    (r'\b(?:lightweight|light|portable|thin)\b', 'portability'),
    (r'\b(?:long.?lasting|endurance|durable|robust)\b', 'durability'),
    (r'\b(?:cheap|affordable|budget|inexpensive|value)\b', 'budget'),
    (r'\b(?:fast|speed|performance|powerful)\b', 'performance'),
    (r'\b(?:quiet|silent|noisy|noise)\b', 'noise'),
    (r'\b(?:color|colour)\b', 'color'),
    (r'\b(?:brand|manufacturer|maker)\b', 'brand'),
    (r'\b(?:review|rating|score|recommend|recommended)\b', 'review_based'),
    (r'\b(?:latest|newest|recent|202[56])\b', 'recency'),
    (r'\b(?:eco|friendly|sustainable|green)\b', 'eco_friendly'),
]

_CATEGORY_MAP = {
    'cuda': 'gpu',
    'os_linux': 'os',
    'os_windows': 'os',
    'os_mac': 'os',
    'max_price': 'price',
    'min_price': 'price',
    'storage': 'storage',
    'ram': 'memory',
    'screen_size': 'display',
    'battery': 'battery',
    'max_battery': 'battery',
    'max_weight': 'weight',
    'weight': 'weight',
    'requirement': 'requirement',
    'preference': 'preference',
    'quality': 'quality',
    'portability': 'portability',
    'durability': 'durability',
    'budget': 'price',
    'performance': 'performance',
    'noise': 'noise',
    'color': 'color',
    'brand': 'brand',
    'review_based': 'quality',
    'recency': 'recency',
    'eco_friendly': 'eco_friendly',
    'exact': 'exact',
}


class ConstraintEngine:
    @staticmethod
    def extract(query):
        q = query.lower().strip()
        constraints = []

        for pattern, category in _HARD_CONSTRAINT_PATTERNS:
            match = re.search(pattern, q, re.IGNORECASE)
            if match:
                value = match.group(1) if match.lastindex else match.group(0)
                constraints.append(Constraint(
                    category=_CATEGORY_MAP.get(category, category),
                    value=value.strip(),
                    constraint_type=ConstraintType.HARD,
                    raw_text=match.group(0),
                ))

        for pattern, category in _SOFT_CONSTRAINT_PATTERNS:
            match = re.search(pattern, q, re.IGNORECASE)
            if match:
                value = match.group(1) if match.lastindex else match.group(0)
                constraints.append(Constraint(
                    category=_CATEGORY_MAP.get(category, category),
                    value=value.strip(),
                    constraint_type=ConstraintType.SOFT,
                    raw_text=match.group(0),
                ))

        return constraints

    @staticmethod
    def get_hard_constraints(constraints):
        return [c for c in constraints if c.type == ConstraintType.HARD]

    @staticmethod
    def get_soft_constraints(constraints):
        return [c for c in constraints if c.type == ConstraintType.SOFT]

    @staticmethod
    def violates_hard_constraint(item, constraints):
        hard = ConstraintEngine.get_hard_constraints(constraints)
        for c in hard:
            if c.category == 'gpu' and 'cuda' in c.value.lower():
                item_text = str(item).lower()
                if 'cuda' not in item_text and 'nvidia' not in item_text and 'gpu' not in item_text:
                    return True
            if c.category == 'os' and c.value == 'os_linux':
                item_text = str(item).lower()
                if 'linux' not in item_text and 'windows' in item_text:
                    return True
            if c.category == 'price':
                try:
                    max_price = float(c.value.replace(',', ''))
                    item_price = ConstraintEngine._extract_price(item)
                    if item_price and item_price > max_price:
                        return True
                except (ValueError, TypeError):
                    pass
        return False

    @staticmethod
    def _extract_price(item):
        if isinstance(item, dict):
            for key in ('price', 'cost', 'amount', 'value'):
                val = item.get(key)
                if val is not None:
                    try:
                        return float(str(val).replace(',', '').replace('$', ''))
                    except (ValueError, TypeError):
                        continue
        return None

    @staticmethod
    def score_item(item, constraints):
        score = 0.0
        hard = ConstraintEngine.get_hard_constraints(constraints)
        soft = ConstraintEngine.get_soft_constraints(constraints)

        for c in hard:
            if ConstraintEngine._matches_constraint(item, c):
                score += 3.0

        for c in soft:
            if ConstraintEngine._matches_constraint(item, c):
                score += 1.0

        return score

    @staticmethod
    def _matches_constraint(item, constraint):
        item_text = str(item).lower()
        if isinstance(item, dict):
            for val in item.values():
                item_text += ' ' + str(val).lower()

        category = constraint.category
        value = constraint.value.lower()

        if category == 'gpu' and 'cuda' in value:
            return 'cuda' in item_text or 'nvidia' in item_text or 'gpu' in item_text
        if category == 'os':
            return value.replace('os_', '') in item_text
        if category == 'price':
            item_price = ConstraintEngine._extract_price(item)
            if item_price is not None:
                try:
                    max_p = float(value.replace(',', ''))
                    return item_price <= max_p
                except (ValueError, TypeError):
                    pass
        if category == 'battery':
            return 'battery' in item_text and value in item_text
        if category == 'weight':
            return 'weight' in item_text or 'kg' in item_text or 'lb' in item_text

        return value in item_text