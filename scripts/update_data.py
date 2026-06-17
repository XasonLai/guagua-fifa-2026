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
SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/summary"
TAIPEI = ZoneInfo("Asia/Taipei")


def fetch_json(url: str) -> dict:
    req = Request(url, headers={"User-Agent": "guagua-fifa-2026/1.0"})
    with urlopen(req, timeout=30) as res:
        return json.load(res)


def fetch(day: date) -> dict:
    return fetch_json(f"{SOURCE}?dates={day:%Y%m%d}")


def fetch_summary(event_id: str) -> dict:
    return fetch_json(f"{SUMMARY}?event={event_id}")


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


def goal_scorers(summary: dict, match: dict) -> list[dict]:
    goals = []
    for event in summary.get("keyEvents", []):
        if not event.get("scoringPlay") or event.get("type", {}).get("type") != "goal" or event.get("shootout"):
            continue
        participants = event.get("participants") or []
        if not participants:
            continue
        athlete = participants[0].get("athlete", {})
        if not athlete.get("id"):
            continue
        goals.append({
            "id": athlete["id"],
            "name": athlete.get("displayName", ""),
            "teamId": event.get("team", {}).get("id", ""),
            "team": event.get("team", {}).get("displayName", ""),
            "matchId": match["id"],
            "minute": event.get("clock", {}).get("displayValue", ""),
        })
    return goals


def scorer_table(goals: list[dict]) -> list[dict]:
    scorers = {}
    for goal in goals:
        row = scorers.setdefault(goal["id"], {
            "id": goal["id"],
            "name": goal["name"],
            "teamId": goal["teamId"],
            "team": goal["team"],
            "goals": 0,
            "matches": [],
        })
        row["goals"] += 1
        row["matches"].append({"matchId": goal["matchId"], "minute": goal["minute"]})
    return sorted(scorers.values(), key=lambda r: (-r["goals"], r["name"]))[:10]


def stat(player: dict, name: str) -> int:
    for item in player.get("stats", []):
        if item.get("name") == name:
            return int(item.get("value", 0))
    return 0


def goalkeepers(summary: dict) -> list[dict]:
    rows = []
    for side in summary.get("rosters", []):
        team = side.get("team", {})
        for player in side.get("roster", []):
            if player.get("position", {}).get("name") != "Goalkeeper" or not player.get("active"):
                continue
            athlete = player.get("athlete", {})
            rows.append({
                "id": athlete.get("id", ""),
                "name": athlete.get("displayName", ""),
                "teamId": team.get("id", ""),
                "team": team.get("displayName", ""),
                "saves": stat(player, "saves"),
                "goalsConceded": stat(player, "goalsConceded"),
                "appearances": stat(player, "appearances"),
            })
    return rows


def goalkeeper_table(rows: list[dict]) -> list[dict]:
    keepers = {}
    for item in rows:
        if not item["id"]:
            continue
        row = keepers.setdefault(item["id"], {
            "id": item["id"],
            "name": item["name"],
            "teamId": item["teamId"],
            "team": item["team"],
            "saves": 0,
            "goalsConceded": 0,
            "appearances": 0,
        })
        row["saves"] += item["saves"]
        row["goalsConceded"] += item["goalsConceded"]
        row["appearances"] += item["appearances"]
    return sorted(keepers.values(), key=lambda r: (-r["saves"], r["goalsConceded"], r["name"]))[:10]


def update(start: date, end: date) -> None:
    DATA.mkdir(exist_ok=True)
    matches, teams, goals, keepers = [], {}, [], []

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
    for match in matches:
        if match["completed"]:
            summary = fetch_summary(match["id"])
            goals.extend(goal_scorers(summary, match))
            keepers.extend(goalkeepers(summary))

    write_json(DATA / "matches.json", matches)
    write_json(DATA / "teams.json", sorted(teams.values(), key=lambda t: t["name"]))
    write_json(DATA / "scorers.json", scorer_table(goals))
    write_json(DATA / "goalkeepers.json", goalkeeper_table(keepers))
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
    summary = {"keyEvents": [
        {"type": {"type": "goal"}, "scoringPlay": True, "shootout": False, "team": {"id": "1", "displayName": "Home"}, "participants": [{"athlete": {"id": "9", "displayName": "Nine"}}], "clock": {"displayValue": "9'"}},
        {"type": {"type": "goal"}, "scoringPlay": True, "shootout": True, "participants": [{"athlete": {"id": "10", "displayName": "Ten"}}]},
    ]}
    assert scorer_table(goal_scorers(summary, out))[0]["goals"] == 1
    roster = {"rosters": [{"team": {"id": "1", "displayName": "Home"}, "roster": [{
        "active": True,
        "position": {"name": "Goalkeeper"},
        "athlete": {"id": "1", "displayName": "Keeper"},
        "stats": [{"name": "saves", "value": 2}, {"name": "goalsConceded", "value": 1}, {"name": "appearances", "value": 1}],
    }]}]}
    assert goalkeeper_table(goalkeepers(roster))[0]["saves"] == 2


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
