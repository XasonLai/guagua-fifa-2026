#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCE = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
TAIPEI = ZoneInfo("Asia/Taipei")


def fetch(day: date) -> dict:
    url = f"{SOURCE}?dates={day:%Y%m%d}"
    req = Request(url, headers={"User-Agent": "guagua-fifa-2026/1.0"})
    with urlopen(req, timeout=30) as res:
        return json.load(res)


def tw_time(iso: str) -> str:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TAIPEI).isoformat()


def normalize_event(event: dict) -> dict:
    comp = event["competitions"][0]
    teams = sorted(comp["competitors"], key=lambda c: c.get("homeAway") != "home")
    status = comp["status"]["type"]
    return {
        "id": event["id"],
        "stage": event.get("season", {}).get("slug", ""),
        "group": comp.get("altGameNote", "").replace("FIFA World Cup, ", ""),
        "kickoffUtc": event["date"],
        "kickoffTaiwan": tw_time(event["date"]),
        "venue": comp.get("venue", {}).get("fullName") or comp.get("venue", {}).get("displayName", ""),
        "city": comp.get("venue", {}).get("address", {}).get("city", ""),
        "status": status["description"],
        "completed": bool(status["completed"]),
        "home": team(teams[0]),
        "away": team(teams[1]),
    }


def team(item: dict) -> dict:
    data = item["team"]
    return {
        "id": data["id"],
        "name": data["displayName"],
        "shortName": data.get("shortDisplayName", data["displayName"]),
        "abbr": data.get("abbreviation", ""),
        "logo": data.get("logo", ""),
        "score": item.get("score"),
        "winner": item.get("winner"),
    }


def daterange(start: date, end: date):
    while start <= end:
        yield start
        start += timedelta(days=1)


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update(start: date, end: date) -> None:
    DATA.mkdir(exist_ok=True)
    matches, teams = [], {}

    for day in daterange(start, end):
        day_matches = [normalize_event(e) for e in fetch(day).get("events", [])]
        write_json(DATA / f"{day}.json", day_matches)
        matches.extend(day_matches)
        for match in day_matches:
            if match["stage"] != "group-stage":
                continue
            for side in ("home", "away"):
                t = match[side]
                teams[t["id"]] = {k: t[k] for k in ("id", "name", "shortName", "abbr", "logo")}

    matches.sort(key=lambda m: m["kickoffUtc"])
    write_json(DATA / "matches.json", matches)
    write_json(DATA / "teams.json", sorted(teams.values(), key=lambda t: t["name"]))
    write_json(DATA / "meta.json", {
        "source": SOURCE,
        "updatedAt": datetime.now(UTC).isoformat(),
        "timezone": "Asia/Taipei",
        "start": start.isoformat(),
        "end": end.isoformat(),
    })


def self_check() -> None:
    sample = {
        "id": "1",
        "date": "2026-06-17T17:00Z",
        "season": {"slug": "group-stage"},
        "competitions": [{
            "altGameNote": "FIFA World Cup, Group K",
            "venue": {"fullName": "NRG Stadium", "address": {"city": "Houston"}},
            "status": {"type": {"description": "Scheduled", "completed": False}},
            "competitors": [
                {"homeAway": "away", "score": "0", "winner": False, "team": {"id": "2", "displayName": "Away", "abbreviation": "AWY"}},
                {"homeAway": "home", "score": "1", "winner": True, "team": {"id": "1", "displayName": "Home", "abbreviation": "HME"}},
            ],
        }],
    }
    out = normalize_event(sample)
    assert out["kickoffTaiwan"] == "2026-06-18T01:00:00+08:00"
    assert out["home"]["name"] == "Home"
    assert out["group"] == "Group K"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="2026-06-11")
    p.add_argument("--end", default="2026-07-19")
    p.add_argument("--check", action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.check:
        self_check()
        sys.exit(0)
    update(date.fromisoformat(args.start), date.fromisoformat(args.end))
