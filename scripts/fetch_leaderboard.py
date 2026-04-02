import json
import os
import sys
from datetime import datetime, timezone
import urllib.request
import urllib.parse

# ── Config ────────────────────────────────────────────────────────────────────
STEAM_API_KEY      = os.environ["STEAM_API_KEY"]
APP_ID             = os.environ["STEAM_APP_ID"]

LEADERBOARD_NAME_DEAD  = "Stew_Dead"
LEADERBOARD_NAME_ALIVE = "Stew_Alive"

OUTPUT_PATH = "docs/leaderboard.json"

PARTNER_API = "https://partner.steam-api.com"
PUBLIC_API  = "https://api.steampowered.com"

# ── Helpers ───────────────────────────────────────────────────────────────────

def steam_get(base, interface, method, version, params):
    params["key"] = STEAM_API_KEY
    url = f"{base}/{interface}/{method}/{version}/?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read().decode())

_leaderboard_cache = {}

def find_leaderboard(name):
    global _leaderboard_cache

    if not _leaderboard_cache:
        data = steam_get(
            PARTNER_API,
            "ISteamLeaderboards",
            "GetLeaderboardsForGame",
            "v1",
            {"appid": APP_ID}
        )
        boards = data.get("leaderBoards", {})
        for key, val in boards.items():
            if isinstance(val, dict) and "leaderBoardID" in val:
                _leaderboard_cache[key] = val["leaderBoardID"]
        print(f"[INFO] Found {len(_leaderboard_cache)} leaderboards: {list(_leaderboard_cache.keys())}")

    lb_id = _leaderboard_cache.get(name)
    if not lb_id:
        print(f"[ERROR] Leaderboard '{name}' not found. Available: {list(_leaderboard_cache.keys())}")
        sys.exit(1)

    print(f"[INFO] Resolved '{name}' → leaderboard ID {lb_id}")
    return lb_id



def get_entries(leaderboard_id, data_request=3, start=1, end=100):
    data = steam_get(
        PARTNER_API,
        "ISteamLeaderboards",
        "GetLeaderboardEntries",
        "v1",
        {
            "appid":         APP_ID,
            "leaderboardid": leaderboard_id,
            "dataRequest":   data_request,
            "rangeStart":    start,
            "rangeEnd":      end,
        }
    )
    print(f"[DEBUG] GetLeaderboardEntries response: {json.dumps(data, indent=2)}")
    return data.get("leaderboardEntryInformation", {}).get("entries", [])

def resolve_names(steam_ids):
    """Batch-resolve Steam IDs to persona names."""
    if not steam_ids:
        return {}
    ids_str = ",".join(str(sid) for sid in steam_ids)
    data = steam_get(
        PUBLIC_API,
        "ISteamUser",
        "GetPlayerSummaries",
        "v2",
        {"steamids": ids_str}
    )
    players = data.get("response", {}).get("players", [])
    return {int(p["steamid"]): p["personaname"] for p in players}

def format_time(total_seconds):
    """Mirror StewTime.Format() from C#."""
    s = int(total_seconds)
    years   = s // (365 * 24 * 3600); s %= (365 * 24 * 3600)
    days    = s // (24 * 3600);       s %= (24 * 3600)
    hours   = s // 3600;              s %= 3600
    minutes = s // 60

    if years  > 0: return f"{years}y {days}d"
    if days   > 0: return f"{days}d {hours}h"
    if hours  > 0: return f"{hours}h {minutes}m"
    return f"{minutes}m"

# ── Main ──────────────────────────────────────────────────────────────────────

def build_entry_list(entries, names):
    result = []
    for e in entries:
        sid   = int(e.get("steamID", 0))
        score = e.get("score", 0)
        result.append({
            "rank":     e.get("globalRank", 0),
            "name":     names.get(sid, str(sid)),
            "score":    score,
            "duration": format_time(score),
        })
    return result

def main():
    # Resolve leaderboard names → numeric IDs
    dead_id  = find_leaderboard(LEADERBOARD_NAME_DEAD)
    alive_id = find_leaderboard(LEADERBOARD_NAME_ALIVE)

    # Fetch entries
    dead_entries  = get_entries(dead_id,  start=1, end=100)
    alive_entries = get_entries(alive_id, start=1, end=100)

    # Filter currently alive: score == 0 means still running
    alive_entries = [e for e in alive_entries if e.get("score", -1) == 0]

    # Resolve all Steam IDs to names in two batch calls
    dead_ids  = [int(e["steamID"]) for e in dead_entries  if "steamID" in e]
    alive_ids = [int(e["steamID"]) for e in alive_entries if "steamID" in e]
    all_ids   = list(set(dead_ids + alive_ids))
    names     = resolve_names(all_ids)

    output = {
        "updated":        datetime.now(timezone.utc).isoformat(),
        "allTime":        build_entry_list(dead_entries,  names),
        "currentlyAlive": build_entry_list(alive_entries, names),
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"[OK] Wrote {len(output['allTime'])} all-time and "
          f"{len(output['currentlyAlive'])} alive entries → {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
