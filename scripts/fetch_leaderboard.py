import os, json, requests
from datetime import datetime, timezone

def format_time(total_minutes):
    """Mirror StewTime.Format — years/days/hours/minutes, omitting zeroes."""
    years    = total_minutes // 525960
    rem      = total_minutes  % 525960
    days     = rem // 1440;  rem = rem % 1440
    hours    = rem // 60;    minutes = rem % 60
    parts = []
    if years:             parts.append(f"{years}y")
    if days:              parts.append(f"{days}d")
    if hours:             parts.append(f"{hours}h")
    if minutes or not parts: parts.append(f"{minutes}m")
    return " ".join(parts)

def fetch_entries(api_key, app_id, leaderboard_id, count=100):
    r = requests.get(
        "https://partner.steam-api.com/ISteamLeaderboards/GetLeaderboardEntries/v1/",
        params={
            "key":          api_key,
            "appid":        app_id,
            "leaderboardid": leaderboard_id,
            "rangestart":   0,
            "rangeend":     count - 1,
            "datarequest":  1,  # global ranking
        },
        timeout=10,
    )
    r.raise_for_status()
    raw = r.json().get("leaderboard", {}).get("entries", {}).get("entry", [])
    # Steam returns a dict (not list) when there's only one entry
    return raw if isinstance(raw, list) else [raw]

def fetch_names(api_key, steam_ids):
    """Resolve Steam IDs to persona names in one batch call (max 100)."""
    if not steam_ids:
        return {}
    r = requests.get(
        "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
        params={"key": api_key, "steamids": ",".join(steam_ids)},
        timeout=10,
    )
    r.raise_for_status()
    players = r.json().get("response", {}).get("players", [])
    return {p["steamid"]: p["personaname"] for p in players}

api_key    = os.environ["STEAM_API_KEY"]
app_id     = os.environ["STEAM_APP_ID"]
dead_id    = os.environ["LEADERBOARD_ID_DEAD"]
alive_id   = os.environ["LEADERBOARD_ID_ALIVE"]

output = {
    "updated":       datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "allTime":       [],
    "currentlyAlive": [],
}

def process(leaderboard_id, key, filter_zero=False):
    try:
        entries = fetch_entries(api_key, app_id, leaderboard_id)
        if filter_zero:
            entries = [e for e in entries if int(e.get("score", 0)) > 0]
        ids = [e["steamid"] for e in entries]
        names = fetch_names(api_key, ids)
        for e in entries:
            sid = e["steamid"]
            output[key].append({
                "rank":    int(e["rank"]),
                "name":    names.get(sid, sid),
                "score":   int(e["score"]),
                "display": format_time(int(e["score"])),
            })
        print(f"{key}: {len(output[key])} entries")
    except Exception as ex:
        print(f"Error fetching {key}: {ex}")

process(dead_id,  "allTime")
process(alive_id, "currentlyAlive", filter_zero=True)

os.makedirs("docs", exist_ok=True)
with open("docs/leaderboard.json", "w") as f:
    json.dump(output, f, indent=2)
