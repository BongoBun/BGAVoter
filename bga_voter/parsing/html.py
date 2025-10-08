"""HTML / embedded JSON extraction helpers."""

import json
import re
from typing import List

_DOWNVOTE_RE = re.compile(r'"red_thumbs_given"\s*:\s*({[^}]*})')
_FRIENDS_RE = re.compile(r'"friends"\s*:\s*({[^}]*})')


def _extract_ids(regex: re.Pattern[str], html: str) -> list[int]:
    m = regex.search(html)
    if not m:
        return []
    try:
        obj = json.loads(m.group(1))
        return [int(k) for k in obj.keys()]
    except (json.JSONDecodeError, ValueError):
        return []


def parse_downvoted_ids(html: str) -> List[int]:
    return _extract_ids(_DOWNVOTE_RE, html)


def parse_friend_ids(html: str) -> List[int]:
    return _extract_ids(_FRIENDS_RE, html)
