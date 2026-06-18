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
TEAM_ZH = {
    "ALG": "阿爾及利亞", "ARG": "阿根廷", "AUS": "澳洲", "AUT": "奧地利", "BEL": "比利時",
    "BIH": "波士尼亞與赫塞哥維納", "BRA": "巴西", "CAN": "加拿大", "CPV": "維德角", "COL": "哥倫比亞",
    "COD": "剛果民主共和國", "CRO": "克羅埃西亞", "CUW": "庫拉索", "CZE": "捷克", "ECU": "厄瓜多",
    "EGY": "埃及", "ENG": "英格蘭", "FRA": "法國", "GER": "德國", "GHA": "迦納",
    "HAI": "海地", "IRN": "伊朗", "IRQ": "伊拉克", "CIV": "象牙海岸", "JPN": "日本",
    "JOR": "約旦", "MEX": "墨西哥", "MAR": "摩洛哥", "NED": "荷蘭", "NZL": "紐西蘭",
    "NOR": "挪威", "PAN": "巴拿馬", "PAR": "巴拉圭", "POR": "葡萄牙", "QAT": "卡達",
    "KSA": "沙烏地阿拉伯", "SCO": "蘇格蘭", "SEN": "塞內加爾", "RSA": "南非", "KOR": "南韓",
    "ESP": "西班牙", "SWE": "瑞典", "SUI": "瑞士", "TUN": "突尼西亞", "TUR": "土耳其",
    "USA": "美國", "URU": "烏拉圭", "UZB": "烏茲別克",
}
TEAM_ZH_BY_NAME = {
    "Bosnia-Herzegovina": "波士尼亞與赫塞哥維納", "Cape Verde": "維德角", "Congo DR": "剛果民主共和國",
    "Curaçao": "庫拉索", "Czechia": "捷克", "Ivory Coast": "象牙海岸", "New Zealand": "紐西蘭",
    "Saudi Arabia": "沙烏地阿拉伯", "South Africa": "南非", "South Korea": "南韓", "United States": "美國",
}


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
        "probabilities": probabilities(comp),
    }


def team(item: dict) -> dict:
    data = item["team"]
    abbr = data.get("abbreviation", "")
    name = data["displayName"]
    return {
        "id": data["id"],
        "name": name,
        "zhName": zh_name(name, abbr),
        "shortName": data.get("shortDisplayName", name),
        "abbr": abbr,
        "logo": data.get("logo", ""),
        "homeAway": item.get("homeAway", ""),
        "score": item.get("score"),
        "winner": item.get("winner"),
    }


def daterange(start: date, end: date):
    while start <= end:
        yield start
        start += timedelta(days=1)


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def zh_name(name: str, abbr: str = "") -> str:
    return TEAM_ZH.get(abbr) or TEAM_ZH_BY_NAME.get(name) or name


def american_probability(value) -> float | None:
    try:
        odds = int(value)
    except (TypeError, ValueError):
        return None
    return 100 / (odds + 100) if odds > 0 else abs(odds) / (abs(odds) + 100)


def probabilities(comp: dict) -> dict | None:
    odds = comp.get("odds") or []
    odd = odds[0] or {} if odds else {}
    moneyline = odd.get("moneyline", {})
    raw = {
        "home": american_probability(moneyline.get("home", {}).get("close", {}).get("odds")),
        "draw": american_probability(moneyline.get("draw", {}).get("close", {}).get("odds")),
        "away": american_probability(moneyline.get("away", {}).get("close", {}).get("odds")),
    }
    if not all(raw.values()):
        return None
    total = sum(raw.values())
    return {
        "source": odd.get("provider", {}).get("displayName", "ESPN odds"),
        "note": "由 ESPN 賠率換算並標準化，僅供市場參考，非官方預測。",
        "home": round(raw["home"] / total * 100),
        "draw": round(raw["draw"] / total * 100),
        "away": round(raw["away"] / total * 100),
    }


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
            "teamZh": zh_name(event.get("team", {}).get("displayName", "")),
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
            "teamZh": goal["teamZh"],
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
        team_name = team.get("displayName", "")
        for player in side.get("roster", []):
            if player.get("position", {}).get("name") != "Goalkeeper" or not player.get("active"):
                continue
            athlete = player.get("athlete", {})
            rows.append({
                "id": athlete.get("id", ""),
                "name": athlete.get("displayName", ""),
                "teamId": team.get("id", ""),
                "team": team_name,
                "teamZh": zh_name(team_name, team.get("abbreviation", "")),
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
            "teamZh": item["teamZh"],
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
                teams[t["id"]] = {k: t[k] for k in ("id", "name", "zhName", "shortName", "abbr", "logo")}

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
    assert zh_name("Portugal", "POR") == "葡萄牙"
    assert american_probability("-150") == 0.6
    assert american_probability("300") == 0.25
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
