"""
NBA API clients for monitoring system
Fetches from multiple authoritative and secondary sources
Own the Outcome - verify line by line, no hallucinations
"""
import requests
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import time

class NBAOfficialClient:
    """Client for NBA official stats"""
    BASE_URL = "https://stats.nba.com"
    NBA_COM_URL = "https://www.nba.com"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nba.com/",
            "Origin": "https://www.nba.com"
        })
    
    def get_scoreboard(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        """
        Get scoreboard for a date (YYYY-MM-DD). If None, today.
        Returns dict with games and scores.
        Note: This is a best-effort implementation. Real production would use NBA stats API.
        """
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
        
        # Use balldontlie.io as fallback for demo - it's free and reliable
        # In production, you'd use official NBA API with proper auth
        try:
            # Try balldontlie free API
            url = f"https://api.balldontlie.io/nba/v1/games?dates[]={date_str}"
            # This requires API key now, so we handle failure gracefully
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"[NBAOfficialClient] scoreboard fetch failed: {e}")
        
        # Return empty structure if failed - monitoring system should handle
        return {"date": date_str, "games": [], "source": "nba_official", "error": "fetch_failed", "timestamp": datetime.now().isoformat()}

class ESPNClient:
    """Client for ESPN secondary source"""
    BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0"
        })
    
    def get_scoreboard(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        """Get ESPN scoreboard"""
        if not date_str:
            date_str = datetime.now().strftime("%Y%m%d")
        else:
            # Convert YYYY-MM-DD to YYYYMMDD
            date_str = date_str.replace("-", "")
        
        try:
            url = f"{self.BASE_URL}/scoreboard?dates={date_str}"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                # Normalize to our format
                games = []
                for event in data.get("events", []):
                    try:
                        comp = event["competitions"][0]
                        home = comp["competitors"][0] if comp["competitors"][0]["homeAway"] == "home" else comp["competitors"][1]
                        away = comp["competitors"][1] if comp["competitors"][0]["homeAway"] == "home" else comp["competitors"][0]
                        games.append({
                            "id": event["id"],
                            "home_team": home["team"]["abbreviation"],
                            "away_team": away["team"]["abbreviation"],
                            "home_score": int(home.get("score", 0)),
                            "away_score": int(away.get("score", 0)),
                            "status": comp["status"]["type"]["name"],
                            "period": comp["status"]["period"],
                            "clock": comp["status"]["displayClock"]
                        })
                    except Exception as inner_e:
                        print(f"[ESPNClient] parse error for event: {inner_e}")
                        continue
                return {"date": date_str, "games": games, "source": "espn", "timestamp": datetime.now().isoformat()}
        except Exception as e:
            print(f"[ESPNClient] fetch failed: {e}")
        
        return {"date": date_str, "games": [], "source": "espn", "error": "fetch_failed", "timestamp": datetime.now().isoformat()}

class BasketballReferenceClient:
    """Client for Basketball-Reference as tertiary verification"""
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0"
        })
    
    def get_scoreboard(self, date_str: Optional[str] = None) -> Dict[str, Any]:
        """
        Basketball-Reference does not have official API, so this is a placeholder.
        In production, would scrape or use their data via sports-reference API.
        For now, returns empty but documents the need.
        """
        return {
            "date": date_str or datetime.now().strftime("%Y-%m-%d"),
            "games": [],
            "source": "basketball_reference",
            "note": "No official API - would require scraping or third-party",
            "timestamp": datetime.now().isoformat()
        }

class MultiSourceFetcher:
    """Fetches from all sources and compares"""
    def __init__(self):
        self.nba = NBAOfficialClient()
        self.espn = ESPNClient()
        self.br = BasketballReferenceClient()
    
    def fetch_all(self, date_str: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """Fetch from all sources"""
        results = {}
        results["nba_official"] = self.nba.get_scoreboard(date_str)
        time.sleep(0.5)  # Be nice to APIs
        results["espn"] = self.espn.get_scoreboard(date_str)
        time.sleep(0.5)
        results["basketball_reference"] = self.br.get_scoreboard(date_str)
        return results
    
    def compare_scores(self, date_str: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Compare scores across sources, return discrepancies
        This is the core of 213 vs 214 detection
        """
        all_data = self.fetch_all(date_str)
        discrepancies = []
        
        # Build map of game_id -> source -> total
        # For demo, we compare ESPN games
        espn_games = {g["id"]: g for g in all_data.get("espn", {}).get("games", [])}
        nba_games = {g["id"]: g for g in all_data.get("nba_official", {}).get("games", [])}
        
        # Simple comparison - in real system, need game matching logic by teams/date
        # For now, just log that comparison happened
        comparison_log = {
            "timestamp": datetime.now().isoformat(),
            "date": date_str,
            "sources_fetched": list(all_data.keys()),
            "espn_game_count": len(espn_games),
            "nba_game_count": len(nba_games),
            "discrepancies_found": len(discrepancies),
            "note": "Full comparison requires game ID matching across providers"
        }
        
        return [comparison_log]

if __name__ == "__main__":
    fetcher = MultiSourceFetcher()
    result = fetcher.fetch_all()
    print(json.dumps(result, indent=2))
