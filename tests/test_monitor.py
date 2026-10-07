import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from monitor import compare, nba_games, espn_games


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.nba = nba_games({'scoreboard': {'games': [{'gameId': '1', 'gameTimeUTC': '2026-10-07T01:00:00Z', 'gameStatus': 3, 'gameStatusText': 'Final', 'homeTeam': {'teamTricode': 'BOS', 'score': 110}, 'awayTeam': {'teamTricode': 'NYK', 'score': 104}}]}})[0]
        self.espn = espn_games({'events': [{'id': '2', 'date': '2026-10-07T01:00:00Z', 'status': {'type': {'completed': True}}, 'competitions': [{'competitors': [{'homeAway': 'home', 'team': {'abbreviation': 'BOS'}, 'score': '110'}, {'homeAway': 'away', 'team': {'abbreviation': 'NYK'}, 'score': '105'}]}]}]}, 'https://site.api.espn.com/test')[0]

    def test_final_difference(self):
        self.assertEqual(len(list(compare([self.nba], [self.espn]))), 1)

    def test_not_final(self):
        self.espn['final'] = False
        self.assertEqual(list(compare([self.nba], [self.espn])), [])

    def test_duplicate_match_not_trusted(self):
        self.assertEqual(list(compare([self.nba], [self.espn, self.espn])), [])

    def test_same_score(self):
        self.espn['away_score'] = 104
        self.assertEqual(list(compare([self.nba], [self.espn])), [])


if __name__ == '__main__':
    unittest.main()
