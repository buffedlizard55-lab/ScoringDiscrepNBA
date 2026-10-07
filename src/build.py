"""Export a static, non-interpretive view of accumulated evidence."""
import json
from pathlib import Path
from monitor import DATA, ROOT, read_lines


def build():
    observations = read_lines(DATA / 'observations.jsonl')
    investigations = read_lines(DATA / 'investigations.jsonl')
    latest = {}
    for item in investigations:
        latest[item['id']] = item
    output = {'observations': observations, 'investigations': list(latest.values()),
              'runs': read_lines(DATA / 'runs.jsonl')[-1:]}
    (ROOT / 'site').mkdir(exist_ok=True)
    (ROOT / 'site' / 'dataset.json').write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    build()
