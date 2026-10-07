"""Compare NBA CDN and ESPN scoreboard snapshots. No unverified case is confirmed automatically."""
import argparse
import datetime as dt
import hashlib
import gzip
import json
import os
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
NBA = 'https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json'
ESPN = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date}'


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'ScoringDiscrepNBA/0.1 (research monitor)', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=25) as response:
        raw = response.read(5_000_001)
        if len(raw) > 5_000_000:
            raise ValueError('response exceeds size limit')
    return json.loads(raw), hashlib.sha256(raw).hexdigest(), raw


def nba_games(payload):
    result = []
    for game in payload['scoreboard']['games']:
        result.append({'source': 'NBA CDN scoreboard', 'source_url': NBA,
                       'source_id': str(game['gameId']), 'date': game['gameTimeUTC'][:10],
                       'home': game['homeTeam']['teamTricode'], 'away': game['awayTeam']['teamTricode'],
                       'home_score': int(game['homeTeam']['score']), 'away_score': int(game['awayTeam']['score']),
                       'final': int(game['gameStatus']) == 3, 'status': str(game.get('gameStatusText', ''))})
    return result


def espn_games(payload, url):
    result = []
    for event in payload['events']:
        competition = event['competitions'][0]
        sides = {c['homeAway']: c for c in competition['competitors']}
        home, away = sides['home'], sides['away']
        result.append({'source': 'ESPN scoreboard', 'source_url': url,
                       'source_id': str(event['id']), 'date': event['date'][:10],
                       'home': home['team']['abbreviation'], 'away': away['team']['abbreviation'],
                       'home_score': int(home['score']), 'away_score': int(away['score']),
                       'final': bool(event['status']['type']['completed']),
                       'status': str(event['status']['type'].get('description', ''))})
    return result


def key(game):
    return (game['date'], game['home'], game['away'])


def append(path, record):
    with path.open('a', encoding='utf-8') as file:
        file.write(json.dumps(record, sort_keys=True, separators=(',', ':')) + '\n')


def read_lines(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def compare(nba, espn):
    """Only uniquely matched final games can trigger final-score candidate alerts."""
    left, right = {}, {}
    for game in nba:
        left.setdefault(key(game), []).append(game)
    for game in espn:
        right.setdefault(key(game), []).append(game)
    for match, games in left.items():
        others = right.get(match, [])
        if len(games) != 1 or len(others) != 1:
            continue
        a, b = games[0], others[0]
        if not a['final'] or not b['final']:
            continue
        if (a['home_score'], a['away_score']) != (b['home_score'], b['away_score']):
            yield a, b


def run(now=None):
    DATA.mkdir(exist_ok=True)
    now = now or dt.datetime.now(dt.timezone.utc)
    stamp = now.isoformat()
    date = now.strftime('%Y%m%d')
    dates = [(now.date() + dt.timedelta(days=delta)).strftime('%Y%m%d') for delta in (-1, 0, 1)]
    results = {}
    errors = {}
    requests = [('nba', NBA, nba_games)] + [
        (f'espn_{day}', ESPN.format(date=day), lambda p, u=ESPN.format(date=day): espn_games(p, u))
        for day in dates
    ]
    for name, address, parser in requests:
        try:
            payload, digest, raw = fetch(address)
            games = parser(payload)
            for game in games:
                game['response_sha256'] = digest
            results[name] = (games, digest)
            archive = DATA / 'raw' / f'{digest}.json.gz'
            if not archive.exists():
                archive.parent.mkdir(exist_ok=True)
                with archive.open('wb') as output:
                    with gzip.GzipFile(fileobj=output, mode='wb', mtime=0) as zipped:
                        zipped.write(raw)
        except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
            errors[name] = f'{type(exc).__name__}: {exc}'
    append(DATA / 'runs.jsonl', {'fetched_at': stamp, 'errors': errors,
                                   'sources_ok': list(results), 'dates_queried': dates})
    history = read_lines(DATA / 'observations.jsonl')
    latest = {(r['source'], r['source_id']): r for r in history}
    for games, digest in results.values():
        for game in games:
            observation = {**game, 'fetched_at': stamp, 'response_sha256': digest}
            previous = latest.get((game['source'], game['source_id']))
            fields = ('home_score', 'away_score', 'final', 'status')
            if previous is None or any(previous.get(field) != game[field] for field in fields):
                append(DATA / 'observations.jsonl', observation)
                latest[(game['source'], game['source_id'])] = observation
    if 'nba' in results and any(name.startswith('espn_') for name in results):
        alerts = read_lines(DATA / 'investigations.jsonl')
        active = {r['id']: r for r in alerts}
        espn = [game for name, (games, _) in results.items() if name.startswith('espn_') for game in games]
        # Duplicate appearances across queried dates are the same ESPN event.
        espn = list({game['source_id']: game for game in espn}.values())
        for a, b in compare(results['nba'][0], espn):
            identity = f"{a['date']}:{a['home']}:{a['away']}"
            candidate = {'id': identity, 'observed_at': stamp, 'status': 'candidate — requires investigation',
                         'nba': {k: a[k] for k in ('source_id', 'source_url', 'home_score', 'away_score', 'response_sha256')},
                         'espn': {k: b[k] for k in ('source_id', 'source_url', 'home_score', 'away_score', 'response_sha256')},
                         'note': 'Snapshot disagreement; neither cause nor official scorer record verified.'}
            previous = active.get(identity)
            if previous is None or previous['nba'] != candidate['nba'] or previous['espn'] != candidate['espn']:
                append(DATA / 'investigations.jsonl', candidate)
    return errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-only', action='store_true')
    args = parser.parse_args()
    if not args.build_only:
        problems = run()
        if problems:
            print('Source failures:', problems)
    from build import build
    build()
