"""
Data models for NBA Scoring Discrepancy Research
Own the Outcome - Maximize P(Win)
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class IncidentType(Enum):
    FREE_THROW_NOT_COUNTED = "free_throw_not_counted"
    THREE_POINTER_MISCLASSIFIED = "three_pointer_misclassified"
    SCOREBOOK_FOUL_MISCOUNT = "scorebook_foul_miscount"
    ILLEGAL_SUBSTITUTION = "illegal_substitution"
    BUZZER_BEATER_DISPUTED = "buzzer_beater_disputed"
    THROW_IN_LOCATION_ERROR = "throw_in_location_error"
    TECHNICAL_FOUL_MISCOUNT = "technical_foul_miscount"
    LANE_VIOLATION_MISAPPLICATION = "lane_violation_misapplication"
    SCOREBOARD_DATA_FEED_ERROR = "scoreboard_data_feed_error"
    SCOREBUG_TIMEOUT_ERROR = "scorebug_timeout_error"
    OTHER = "other"

class VerificationStatus(Enum):
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    UNVERIFIED = "unverified"
    DISPUTED = "disputed"
    REQUIRES_INVESTIGATION = "requires_investigation"

class InvestigationStatus(Enum):
    DETECTED = "detected"
    INVESTIGATING = "investigating"
    CORRECTED = "corrected"
    RESOLVED = "resolved"
    CLOSED = "closed"

@dataclass
class Source:
    url: str
    title: str
    publisher: str
    type: str  # official_nba, espn, news, etc
    access_date: str
    archived_url: Optional[str] = None

@dataclass
class DiscrepancyRecord:
    id: str
    game_id: str
    date: str
    teams: Dict[str, str]
    incident_type: str
    description: str = ""
    original_final_score: str = ""
    corrected_final_score: str = ""
    original_total: Optional[int] = None
    corrected_total: Optional[int] = None
    nba_official_incorrect: bool = False
    secondary_error: bool = False
    impact_on_total: bool = False
    impact_points: int = 0
    sources: List[Source] = field(default_factory=list)
    verification_status: str = "unverified"
    investigation_status: str = "detected"
    cause: str = ""
    cause_confidence: str = "suspected"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "game_id": self.game_id,
            "date": self.date,
            "teams": self.teams,
            "incident_type": self.incident_type,
            "original_final_score": self.original_final_score,
            "corrected_final_score": self.corrected_final_score,
            "original_total": self.original_total,
            "corrected_total": self.corrected_total,
            "nba_official_incorrect": self.nba_official_incorrect,
            "secondary_error": self.secondary_error,
            "impact_on_total": self.impact_on_total,
            "impact_points": self.impact_points,
            "verification_status": self.verification_status,
            "investigation_status": self.investigation_status,
            "cause": self.cause
        }

@dataclass
class LiveGameSnapshot:
    """For monitoring system - captures score from multiple sources at a point in time"""
    game_id: str
    timestamp: datetime
    source: str  # nba_official, espn, br, etc
    home_score: int
    away_score: int
    total: int
    period: str
    clock: str
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    def total_points(self) -> int:
        return self.home_score + self.away_score

@dataclass
class DiscrepancyAlert:
    """Alert generated when discrepancy detected between sources"""
    id: str
    game_id: str
    detected_at: datetime
    source_a: str
    source_b: str
    score_a: str
    score_b: str
    total_a: int
    total_b: int
    difference: int
    status: str = "detected"
    investigation_notes: str = ""
    
    def is_total_mismatch(self) -> bool:
        return self.total_a != self.total_b
    
    def is_one_point_discrepancy(self) -> bool:
        """213 vs 214 case"""
        return abs(self.total_a - self.total_b) == 1
