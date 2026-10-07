"""
Discrepancy Detector - Core monitoring logic
Detects 213 vs 214 type discrepancies between sources
Own the Outcome - verify line by line, no hallucinations
"""
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
try:
    from .models import DiscrepancyAlert, LiveGameSnapshot
    from .nba_api_client import MultiSourceFetcher
except ImportError:
    from models import DiscrepancyAlert, LiveGameSnapshot
    from nba_api_client import MultiSourceFetcher

class DiscrepancyDetector:
    """
    Continuously monitors NBA games for scoring discrepancies
    Workflow: detection -> investigation -> correction -> resolution
    """
    
    def __init__(self, data_dir: str = "data", alert_file: str = "data/live_alerts.json"):
        self.data_dir = data_dir
        self.alert_file = alert_file
        self.fetcher = MultiSourceFetcher()
        self.alerts: List[DiscrepancyAlert] = []
        self.load_alerts()
    
    def load_alerts(self):
        """Load existing alerts"""
        if os.path.exists(self.alert_file):
            try:
                with open(self.alert_file, 'r') as f:
                    data = json.load(f)
                    # Convert dicts to alerts if needed
                    print(f"[Detector] Loaded {len(data)} existing alerts")
            except Exception as e:
                print(f"[Detector] Failed to load alerts: {e}")
    
    def save_alerts(self):
        """Save alerts to file"""
        os.makedirs(os.path.dirname(self.alert_file), exist_ok=True)
        try:
            with open(self.alert_file, 'w') as f:
                json.dump([a.__dict__ if hasattr(a, '__dict__') else a for a in self.alerts], f, indent=2, default=str)
        except Exception as e:
            print(f"[Detector] Failed to save alerts: {e}")
    
    def detect_from_snapshots(self, snapshots: List[LiveGameSnapshot]) -> List[DiscrepancyAlert]:
        """
        Core detection logic: compare snapshots from different sources for same game
        If totals differ, create alert
        """
        alerts = []
        # Group by game_id
        by_game: Dict[str, List[LiveGameSnapshot]] = {}
        for snap in snapshots:
            if snap.game_id not in by_game:
                by_game[snap.game_id] = []
            by_game[snap.game_id].append(snap)
        
        for game_id, snaps in by_game.items():
            if len(snaps) < 2:
                continue  # Need at least 2 sources to compare
            
            # Compare each pair
            for i in range(len(snaps)):
                for j in range(i+1, len(snaps)):
                    a = snaps[i]
                    b = snaps[j]
                    if a.total != b.total:
                        alert_id = f"ALERT-{game_id}-{a.source}-vs-{b.source}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        alert = DiscrepancyAlert(
                            id=alert_id,
                            game_id=game_id,
                            detected_at=datetime.now(),
                            source_a=a.source,
                            source_b=b.source,
                            score_a=f"{a.away_score}-{a.home_score}",
                            score_b=f"{b.away_score}-{b.home_score}",
                            total_a=a.total,
                            total_b=b.total,
                            difference=abs(a.total - b.total),
                            status="detected",
                            investigation_notes=f"Auto-detected: {a.source} shows total {a.total}, {b.source} shows {b.total}. Difference {abs(a.total - b.total)}. Period {a.period} clock {a.clock}. Check if FT or 3pt misclassification."
                        )
                        alerts.append(alert)
                        print(f"[Detector] DISCREPANCY DETECTED: Game {game_id} {a.source}={a.total} vs {b.source}={b.total} diff={abs(a.total-b.total)}")
                        
                        # Special handling for 213 vs 214 case (1-point total difference)
                        if alert.is_one_point_discrepancy():
                            print(f"[Detector] *** 1-POINT DISCREPANCY (213/214 pattern) *** Game {game_id}")
        
        return alerts
    
    def create_investigation_record(self, alert: DiscrepancyAlert) -> Dict[str, Any]:
        """
        Create investigation record from alert
        This preserves original observation and tracks through resolution
        """
        record = {
            "id": alert.id.replace("ALERT-", "INV-"),
            "alert_id": alert.id,
            "game_id": alert.game_id,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "detection": {
                "detected_at": alert.detected_at.isoformat(),
                "source_a": alert.source_a,
                "source_b": alert.source_b,
                "score_a": alert.score_a,
                "total_a": alert.total_a,
                "score_b": alert.score_b,
                "total_b": alert.total_b,
                "difference": alert.difference
            },
            "investigation_status": "detected",
            "investigation_steps": [
                {
                    "step": 1,
                    "action": "Detected discrepancy between sources",
                    "timestamp": datetime.now().isoformat(),
                    "result": f"{alert.source_a} total {alert.total_a} vs {alert.source_b} total {alert.total_b}"
                }
            ],
            "potential_causes": [
                "free_throw_not_counted",
                "three_pointer_misclassified",
                "scoreboard_data_feed_error",
                "secondary_source_delay"
            ],
            "next_steps": [
                "Fetch play-by-play from both sources",
                "Check official NBA.com box score",
                "Check ESPN box score",
                "Check Basketball-Reference",
                "Look for official NBA correction statement",
                "Determine if NBA official record incorrect or only secondary source"
            ],
            "requires_manual_review": True,
            "is_213_214_pattern": alert.is_one_point_discrepancy()
        }
        return record
    
    def monitor_once(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        """Run one monitoring cycle"""
        print(f"[Detector] Monitoring cycle started for date {date_str or 'today'}")
        fetched = self.fetcher.fetch_all(date_str)
        
        # Convert fetched data to snapshots for detection
        snapshots = []
        for source_name, source_data in fetched.items():
            for game in source_data.get("games", []):
                try:
                    snap = LiveGameSnapshot(
                        game_id=game.get("id", f"{game.get('away_team')}-{game.get('home_team')}-{date_str}"),
                        timestamp=datetime.now(),
                        source=source_name,
                        home_score=game.get("home_score", 0),
                        away_score=game.get("away_score", 0),
                        total=game.get("home_score", 0) + game.get("away_score", 0),
                        period=str(game.get("period", "")),
                        clock=str(game.get("clock", "")),
                        raw_data=game
                    )
                    snapshots.append(snap)
                except Exception as e:
                    print(f"[Detector] Failed to create snapshot: {e}")
                    continue
        
        alerts = self.detect_from_snapshots(snapshots)
        self.alerts.extend(alerts)
        self.save_alerts()
        
        # Create investigation records for new alerts
        investigations = [self.create_investigation_record(a) for a in alerts]
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "date": date_str or datetime.now().strftime("%Y-%m-%d"),
            "snapshots_collected": len(snapshots),
            "sources": list(fetched.keys()),
            "alerts_generated": len(alerts),
            "alerts": [a.__dict__ for a in alerts],
            "investigations": investigations,
            "fetched_data_summary": {k: len(v.get("games", [])) for k, v in fetched.items()}
        }
        
        return result
    
    def get_statistics(self, historical_data_path: str = "data/discrepancies.json") -> Dict[str, Any]:
        """Calculate historical statistics for website"""
        try:
            with open(historical_data_path, 'r') as f:
                cases = json.load(f)
        except Exception as e:
            print(f"[Detector] Failed to load historical data: {e}")
            cases = []
        
        if not cases:
            return {"error": "no data"}
        
        total_cases = len(cases)
        by_type = {}
        by_verification = {}
        official_incorrect = 0
        secondary_error = 0
        total_impact = 0
        points_impact = []
        protest_upheld = 0
        
        for case in cases:
            t = case.get("incident_type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1
            
            v = case.get("verification_status", "unknown")
            by_verification[v] = by_verification.get(v, 0) + 1
            
            if case.get("nba_official_record_incorrect"):
                official_incorrect += 1
            if case.get("secondary_source_error"):
                secondary_error += 1
            if case.get("impact_on_final_total"):
                total_impact += 1
            if case.get("impact_points") is not None:
                points_impact.append(abs(case.get("impact_points", 0)))
            if case.get("protest_upheld"):
                protest_upheld += 1
        
        # Calculate rarity of 1-point discrepancies (213/214 pattern)
        one_point_cases = sum(1 for c in cases if abs(c.get("impact_points", 0)) == 1)
        
        stats = {
            "total_cases": total_cases,
            "by_type": by_type,
            "by_verification": by_verification,
            "official_record_incorrect_count": official_incorrect,
            "secondary_source_error_count": secondary_error,
            "impact_on_final_total_count": total_impact,
            "impact_on_final_total_percent": round(total_impact / total_cases * 100, 1) if total_cases else 0,
            "official_incorrect_percent": round(official_incorrect / total_cases * 100, 1) if total_cases else 0,
            "protest_upheld_count": protest_upheld,
            "one_point_discrepancies": one_point_cases,
            "one_point_percent": round(one_point_cases / total_cases * 100, 1) if total_cases else 0,
            "avg_points_impact": round(sum(points_impact) / len(points_impact), 2) if points_impact else 0,
            "max_points_impact": max(points_impact) if points_impact else 0,
            "rarity_note": f"1-point total discrepancies (like 213 vs 214) represent {round(one_point_cases / total_cases * 100, 1) if total_cases else 0}% of all verified cases. In our dataset of {total_cases} cases, {one_point_cases} are 1-point differences."
        }
        
        return stats

if __name__ == "__main__":
    detector = DiscrepancyDetector()
    result = detector.monitor_once()
    print(json.dumps(result, indent=2))
    stats = detector.get_statistics()
    print("\n=== STATISTICS ===")
    print(json.dumps(stats, indent=2))
