from dataclasses import dataclass, asdict
from typing import List, Optional


@dataclass
class GradingResult:
    score: Optional[float] = None
    message: Optional[str] = None

    def get_schema(self) -> List[str]:
        return list(asdict(self).keys())

    def to_dict(self) -> dict:
        return asdict(self)
