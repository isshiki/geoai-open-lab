"""Offline audit of explicit foot-access rules; not a routing engine.

No class default is silently interpreted as permission. Unknown time/status
conditions retain all possible decisions; later matching rules override earlier
ones, as specified by Overture. Outputs contain aggregate counts only.
"""
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys

import pyarrow.parquet as pq

from station_access_aging_road_body import digest, save_json
from station_access_aging_road_footers import CACHE, RELEASE

FIELDS = {'during', 'heading', 'using', 'recognized', 'mode', 'vehicle'}
NON_FOOT_MODES = {'vehicle', 'motor_vehicle', 'bicycle', 'car', 'motorcycle',
                  'hgv', 'bus', 'hov', 'emergency', 'taxi'}


def clean_when(rule):
    return {k: v for k, v in (rule.get('when') or {}).items() if v is not None}


def foot_scope(rule, heading):
    """Return True, False, or None (unknown) for an ordinary through pedestrian.

Time and status are not guessed. A false known conjunct makes the entire scope
false, even if another conjunct cannot be evaluated. Geometry handled separately.
"""
    w = clean_when(rule)
    mode = w.get('mode')
    uncertain = bool(set(w) - FIELDS)
    if mode is not None:
        if not mode:
            uncertain = True
        elif 'foot' not in mode:
            if set(mode) <= NON_FOOT_MODES:
                return False
            uncertain = True
    if w.get('heading') in {'forward', 'backward'}:
        if w['heading'] != heading:
            return False
    elif 'heading' in w:
        uncertain = True
    # Vehicle constraints do not match a person travelling on foot.
    if w.get('vehicle'):
        return False
    if any(k in w for k in ('during', 'using', 'recognized')):
        uncertain = True
    return None if uncertain else True


def interval(rule):
    a, b = rule.get('between') or (0.0, 1.0)
    if not all(math.isfinite(x) for x in (a, b)) or not 0 <= a < b <= 1:
        raise ValueError('Invalid rule interval')
    return a, b


def decisions(rules, position, heading):
    """Possible explicit decisions at an interior point; no implied class default."""
    values = {'default_required'}
    for rule in rules or []:
        a, b = interval(rule)
        if not a <= position <= b:
            continue
        match = foot_scope(rule, heading)
        if match is False:
            continue
        value = rule.get('access_type')
        if value not in {'allowed', 'denied', 'designated'}:
            value = 'unsupported_access_type'
        if value == 'designated':
            value = 'allowed'
        if match is True:
            values = {value}
        else:
            values.add(value)
    return next(iter(values)) if len(values) == 1 else 'conditional_unresolved'


def audit(rows):
    counts = Counter()
    direction_intervals = Counter()
    mode_free_heading_classes = Counter()
    condition_keys = Counter()
    transition_modes = Counter()
    classes_default = Counter()
    for row in rows:
        counts['segments'] += 1
        rules = row.get('access_restrictions') or []
        counts['segments_with_access_rules'] += bool(rules)
        endpoints = {0.0, 1.0}
        for r in rules:
            endpoints.update(interval(r))
            condition_keys.update(clean_when(r).keys())
        mode_free = any(clean_when(r).get('heading') is not None and
                        clean_when(r).get('mode') is None for r in rules)
        if mode_free:
            counts['segments_with_mode_free_heading_rule'] += 1
            mode_free_heading_classes[row['class']] += 1
        points = sorted(endpoints)
        statuses = set()
        for a, b in zip(points, points[1:]):
            for heading in ('forward', 'backward'):
                status = decisions(rules, (a+b)/2, heading)
                direction_intervals[status] += 1
                statuses.add(status)
        for status in statuses:
            counts['segments_any_' + status] += 1
        if 'default_required' in statuses:
            classes_default[row['class']] += 1
        transitions = row.get('prohibited_transitions') or []
        counts['segments_with_transitions'] += bool(transitions)
        for t in transitions:
            scopes = [foot_scope(t, h) for h in ('forward', 'backward')]
            category = ('not_foot' if all(s is False for s in scopes) else
                        'conditional_unresolved' if any(s is None for s in scopes)
                        else 'potentially_applies_to_foot')
            transition_modes[category] += 1
            counts['transition_rules'] += 1
            counts['transition_rules_multi_step'] += len(t.get('sequence') or []) > 1
    return {name: dict(sorted(value.items())) for name, value in {
        'counts': counts, 'direction_intervals': direction_intervals,
        'mode_free_heading_classes': mode_free_heading_classes,
        'condition_key_rule_counts': condition_keys,
        'transition_scope_counts': transition_modes,
        'classes_needing_default': classes_default}.items()}


def main():
    source = CACHE / 'road-body' / 'segments.parquet'
    source_hash = digest(source)
    rows = pq.read_table(source, columns=['class', 'access_restrictions',
                                          'prohibited_transitions']).to_pylist()
    result = audit(rows)
    if digest(source) != source_hash:
        raise ValueError('Input changed during audit')
    result.update(audited_utc=datetime.now(timezone.utc).isoformat(),
                  release=RELEASE, source_sha256=source_hash,
                  script_sha256=digest(__file__), python=sys.version.split()[0],
                  semantics='Explicit rule audit only; no walkability or routing claim')
    out = CACHE / 'walking-rules'
    out.mkdir(exist_ok=True)
    save_json(out / 'audit.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
