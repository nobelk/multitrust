from __future__ import annotations

from enum import Enum
from typing import NewType

AgentId = NewType("AgentId", str)
AuthorityId = NewType("AuthorityId", str)


class TrustLevel(float, Enum):
    UNTRUSTED = 0.2
    LOW = 0.4
    MODERATE = 0.6
    HIGH = 0.85
    FULLY_TRUSTED = 0.95
