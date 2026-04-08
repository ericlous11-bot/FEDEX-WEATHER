"""
rebuild.py — Lou Malnati's FedEx Weather Alert Auto-Rebuild
Runs via GitHub Actions on a schedule.
Fetches live NOAA alerts and rewrites index.html with updated data.
"""

import json, re, urllib.request, urllib.error, datetime, sys, os

# ── Chicago-origin transit config — all 50 states + DC ──
TRANSIT = {
    "IL":{"chiGround":1,"chiExpress":1,"periRisk":"MODERATE"},
    "IN":{"chiGround":1,"chiExpress":1,"periRisk":"MODERATE"},
    "WI":{"chiGround":1,"chiExpress":1,"periRisk":"MODERATE"},
    "MI":{"chiGround":1,"chiExpress":1,"periRisk":"MODERATE"},
    "OH":{"chiGround":1,"chiExpress":1,"periRisk":"HIGH"},
    "MO":{"chiGround":1,"chiExpress":1,"periRisk":"MODERATE"},
    "IA":{"chiGround":1,"chiExpress":1,"periRisk":"MODERATE"},
    "MN":{"chiGround":2,"chiExpress":1,"periRisk":"MODERATE"},
    "KY":{"chiGround":1,"chiExpress":1,"periRisk":"MODERATE"},
    "KS":{"chiGround":2,"chiExpress":1,"periRisk":"CRITICAL"},
    "NE":{"chiGround":2,"chiExpress":1,"periRisk":"MODERATE"},
    "SD":{"chiGround":2,"chiExpress":1,"periRisk":"MODERATE"},
    "ND":{"chiGround":2,"chiExpress":1,"periRisk":"MODERATE"},
    "TN":{"chiGround":2,"chiExpress":1,"periRisk":"HIGH"},
    "WV":{"chiGround":2,"chiExpress":1,"periRisk":"MODERATE"},
    "VA":{"chiGround":2,"chiExpress":1,"periRisk":"HIGH"},
    "PA":{"chiGround":2,"chiExpress":1,"periRisk":"HIGH"},
    "MD":{"chiGround":2,"chiExpress":1,"periRisk":"HIGH"},
    "DE":{"chiGround":2,"chiExpress":1,"periRisk":"HIGH"},
    "NJ":{"chiGround":2,"chiExpress":1,"periRisk":"HIGH"},
    "NY":{"chiGround":2,"chiExpress":1,"periRisk":"HIGH"},
    "CT":{"chiGround":2,"chiExpress":1,"periRisk":"HIGH"},
    "RI":{"chiGround":2,"chiExpress":1,"periRisk":"HIGH"},
    "MA":{"chiGround":2,"chiExpress":1,"periRisk":"HIGH"},
    "OK":{"chiGround":2,"chiExpress":2,"periRisk":"CRITICAL"},
    "AR":{"chiGround":2,"chiExpress":1,"periRisk":"MODERATE"},
    "MS":{"chiGround":2,"chiExpress":1,"periRisk":"MODERATE"},
    "AL":{"chiGround":2,"chiExpress":1,"periRisk":"MODERATE"},
    "GA":{"chiGround":2,"chiExpress":1,"periRisk":"HIGH"},
    "SC":{"chiGround":2,"chiExpress":1,"periRisk":"HIGH"},
    "NC":{"chiGround":2,"chiExpress":1,"periRisk":"HIGH"},
    "DC":{"chiGround":2,"chiExpress":1,"periRisk":"HIGH"},
    "TX":{"chiGround":3,"chiExpress":2,"periRisk":"CRITICAL"},
    "LA":{"chiGround":2,"chiExpress":2,"periRisk":"MODERATE"},
    "FL":{"chiGround":3,"chiExpress":2,"periRisk":"HIGH"},
    "CO":{"chiGround":2,"chiExpress":2,"periRisk":"MODERATE"},
    "WY":{"chiGround":2,"chiExpress":2,"periRisk":"MODERATE"},
    "MT":{"chiGround":3,"chiExpress":2,"periRisk":"MODERATE"},
    "ID":{"chiGround":3,"chiExpress":2,"periRisk":"MODERATE"},
    "UT":{"chiGround":3,"chiExpress":2,"periRisk":"MODERATE"},
    "NV":{"chiGround":3,"chiExpress":2,"periRisk":"MODERATE"},
    "AZ":{"chiGround":3,"chiExpress":2,"periRisk":"HIGH"},
    "NM":{"chiGround":3,"chiExpress":2,"periRisk":"MODERATE"},
    "WA":{"chiGround":4,"chiExpress":2,"periRisk":"MODERATE"},
    "OR":{"chiGround":4,"chiExpress":2,"periRisk":"MODERATE"},
    "CA":{"chiGround":4,"chiExpress":2,"periRisk":"HIGH"},
    "NH":{"chiGround":3,"chiExpress":1,"periRisk":"MODERATE"},
    "VT":{"chiGround":3,"chiExpress":1,"periRisk":"MODERATE"},
    "ME":{"chiGround":3,"chiExpress":2,"periRisk":"MODERATE"},
    "AK":{"chiGround":7,"chiExpress":3,"periRisk":"MODERATE"},
    "HI":{"chiGround":7,"chiExpress":3,"periRisk":"MODERATE"},
}

STATE_NAMES = {
    "AL":"Alabama","AK":"Alaska","AZ":"Arizona","AR":"Arkansas","CA":"California",
    "CO":"Colorado","CT":"Connecticut","DC":"District of Columbia","DE":"Delaware",
    "FL":"Florida","GA":"Georgia","HI":"Hawaii","ID":"Idaho","IL":"Illinois",
    "IN":"Indiana","IA":"Iowa","KS":"Kansas","KY":"Kentucky","LA":"Louisiana",
    "ME":"Maine","MD":"Maryland","MA":"Massachusetts","MI":"Michigan","MN":"Minnesota",
    "MS":"Mississippi","MO":"Missouri","MT":"Montana","NE":"Nebraska","NV":"Nevada",
    "NH":"New Hampshire","NJ":"New Jersey","NM":"New Mexico","NY":"New York",
    "NC":"North Carolina","ND":"North Dakota","OH":"Ohio","OK":"Oklahoma","OR":"Oregon",
    "PA":"Pennsylvania","RI":"Rhode Island","SC":"South Carolina","SD":"South Dakota",
    "TN":"Tennessee","TX":"Texas","UT":"Utah","VT":"Vermont","VA":"Virginia",
    "WA":"Washington","WV":"West Virginia","WI":"Wisconsin","WY":"Wyoming",
}

# Interruption probability by NWS event type and severity
EVENT_IMPACT = {
    # Tornado-related
    "Tornado Warning":        ("HIGH", 82, "DELAYED", "DELAYED"),
    "Tornado Watch":          ("HIGH", 72, "DELAYED", "DELAYED"),
    # Severe thunderstorm
    "Severe Thunderstorm Warning": ("HIGH", 70, "DELAYED", "DELAYED"),
    "Severe Thunderstorm Watch":   ("MODERATE-HIGH", 58, "POSS. IMPACT", "POSS. IMPACT"),
    # Winter
    "Blizzard Warning":       ("HIGH", 80, "DELAYED", "DELAYED"),
    "Winter Storm Warning":   ("HIGH", 74, "DELAYED", "DELAYED"),
    "Winter Storm Watch":     ("MODERATE-HIGH", 60, "POSS. IMPACT", "POSS. IMPACT"),
    "Ice Storm Warning":      ("HIGH", 78, "DELAYED", "DELAYED"),
    "Winter Weather Advisory":("MODERATE-HIGH", 50, "POSS. IMPACT", "POSS. IMPACT"),
    # Wind
    "High Wind Warning":      ("HIGH", 70, "DELAYED", "DELAYED"),
    "High Wind Watch":        ("MODERATE-HIGH", 55, "POSS. IMPACT", "POSS. IMPACT"),
    "Wind Advisory":          ("MODERATE-HIGH", 48, "POSS. IMPACT", "POSS. IMPACT"),
    # Flood
    "Flash Flood Warning":    ("MODERATE-HIGH", 60, "POSS. IMPACT", "POSS. IMPACT"),
    "Flood Warning":          ("MODERATE-HIGH", 52, "POSS. IMPACT", "POSS. IMPACT"),
    # Hurricane/tropical
    "Hurricane Warning":      ("HIGH", 82, "DELAYED", "DELAYED"),
    "Tropical Storm Warning": ("HIGH", 72, "DELAYED", "DELAYED"),
    # Extreme heat/cold
    "Excessive Heat Warning": ("MODERATE-HIGH", 48, "POSS. IMPACT", "POSS. IMPACT"),
    "Extreme Cold Warning":   ("HIGH", 68, "DELAYED", "DELAYED"),
}

DEFAULT_SEVERE  = ("HIGH",          70, "DELAYED",      "DELAYED")
DEFAULT_MODHI   = ("MODERATE-HIGH", 52, "POSS. IMPACT", "POSS. IMPACT")


def fetch_noaa_alerts():
    """Pull active Extreme + Severe alerts from NOAA NWS API."""
    url = (
        "https://api.weather.gov/alerts/active"
        "?status=actual&message_type=alert"
        "&urgency=Immediate,Expected"
        "&severity=Extreme,Severe"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "LouMalnatis-FedExAlert/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"NOAA fetch error: {e}", file=sys.stderr)
        return None


# State FIPS (2-digit) to abbreviation — for SAME geocode county extraction
FIPS_TO_ABBR = {
    "01":"AL","02":"AK","04":"AZ","05":"AR","06":"CA","08":"CO","09":"CT",
    "10":"DE","11":"DC","12":"FL","13":"GA","15":"HI","16":"ID","17":"IL",
    "18":"IN","19":"IA","20":"KS","21":"KY","22":"LA","23":"ME","24":"MD",
    "25":"MA","26":"MI","27":"MN","28":"MS","29":"MO","30":"MT","31":"NE",
    "32":"NV","33":"NH","34":"NJ","35":"NM","36":"NY","37":"NC","38":"ND",
    "39":"OH","40":"OK","41":"OR","42":"PA","44":"RI","45":"SC","46":"SD",
    "47":"TN","48":"TX","49":"UT","50":"VT","51":"VA","53":"WA","54":"WV",
    "55":"WI","56":"WY"
}

def states_from_alert(feat):
    """Extract state abbreviations and county codes from an alert feature.
    Returns (states: set, counties: dict[abbr -> set of 3-digit county codes]).
    County extraction uses both /zones/county/ URLs and SAME geocodes so that
    fire-weather zone alerts (GAZ###) are handled correctly."""
    props = feat.get("properties", {})
    states = set()
    counties = {}  # abbr -> set of 3-digit county FIPS codes
    geocode = props.get("geocode", {})
    # UGC codes: "GAZ132" -> state abbr "GA" (first 2 chars)
    for code in geocode.get("UGC", []):
        if len(code) >= 2:
            states.add(code[:2])
    # SAME codes: "013069" = 0 + state-FIPS "13" (GA) + county "069"
    for code in geocode.get("SAME", []):
        if len(code) == 6:
            abbr = FIPS_TO_ABBR.get(code[1:3])
            if abbr:
                states.add(abbr)
                counties.setdefault(abbr, set()).add(code[3:])
    # County zone URLs: /zones/county/INC097 -> IN, 097
    for zone_url in props.get("affectedZones", []):
        m = re.search(r'/([A-Z]{2})C(\d{3})$', zone_url)
        if m:
            abbr, county = m.group(1), m.group(2)
            states.add(abbr)
            counties.setdefault(abbr, set()).add(county)
        else:
            m2 = re.search(r'/([A-Z]{2})[A-Z]\d{3}$', zone_url)
            if m2:
                states.add(m2.group(1))
    return states, counties

def build_state_data(alerts_geojson):
    """Map live NOAA alerts to Chicago-route states, returning state rows."""
    now_utc = datetime.datetime.utcnow()
    affected = {}

    if alerts_geojson:
        for feat in alerts_geojson.get("features", []):
            props = feat.get("properties", {})
            event = props.get("event", "")
            severity = props.get("severity", "")
            headline = props.get("headline", event)
            onset = props.get("onset", "")
            ends  = props.get("ends", props.get("expires", ""))

            # Determine impact level
            if event in EVENT_IMPACT:
                level, pct, ground, express = EVENT_IMPACT[event]
            elif severity == "Extreme":
                level, pct, ground, express = DEFAULT_SEVERE
            else:
                level, pct, ground, express = DEFAULT_MODHI

            # Only keep HIGH + MODERATE-HIGH
            if level not in ("HIGH", "MODERATE-HIGH"):
                continue

            alert_states, alert_counties = states_from_alert(feat)
            for abbr in alert_states:
                if abbr not in TRANSIT:
                    continue
                # Keep highest-impact alert per state; always merge county codes
                existing = affected.get(abbr)
                state_counties = alert_counties.get(abbr, set())
                if existing is None or pct > existing["pct"]:
                    affected[abbr] = {
                        "abbr": abbr,
                        "state": STATE_NAMES.get(abbr, abbr),
                        "level": level,
                        "pct": pct,
                        "ground": ground,
                        "express": express,
                        "weather": headline,
                        "onset": onset,
                        "ends": ends,
                        "noaa": "ACTIVE",
                        "counties": set(state_counties),
                    }
                else:
                    existing["counties"].update(state_counties)

    # Build sorted state rows (HIGH first, then MODERATE-HIGH, by pct desc)
    rows = sorted(affected.values(), key=lambda x: (-{"HIGH":1,"MODERATE-HIGH":0}.get(x["level"],0), -x["pct"]))

    # Format dates for display
    for r in rows:
        for key in ("onset", "ends"):
            raw = r[key]
            if raw:
                try:
                    dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    offset = datetime.timedelta(hours=-5)
                    dt_local = dt + offset
                    r[key + "_fmt"] = dt_local.strftime("%a %b %-d  %-I:%M %p CDT")
                except Exception:
                    r[key + "_fmt"] = raw[:16]
            else:
                r[key + "_fmt"] = "—"

    return rows, now_utc


def fmt_js_state_data(rows):
    """Emit the STATE_DATA JS array."""
    lines = []
    for r in rows:
        t = TRANSIT[r["abbr"]]
        counties_js = json.dumps(sorted(r.get("counties", [])))
        lines.append(
            f'  {{state:"{r["state"]}",abbr:"{r["abbr"]}",'
            f'impact:{r["pct"]},level:"{r["level"]}",'
            f'weather:"{r["weather"].replace(chr(34), chr(39))}",'
            f'noaa:"{r["noaa"]}",'
            f'ground:"{r["ground"]}",express:"{r["express"]}",'
            f'start:"{r.get("onset_fmt","—")}",end:"{r.get("ends_fmt","—")}",ends_iso:"{r.get("ends") or ""}",'
            f'pct:{r["pct"]},'
            f'counties:{counties_js},'
            f'note:"Live NOAA alert — verify at fedex.com/service-alerts"}}'
        )
    return "[\n" + ",\n".join(lines) + "\n]"


def update_html(html, rows, now_utc, alert_count):
    """Patch the STATE_DATA and ZIP_DATA arrays and update timestamps in the HTML."""
    state_js = fmt_js_state_data(rows)
    html = re.sub(
        r'const STATE_DATA\s*=\s*\[[\s\S]*?\];',
        f'const STATE_DATA = {state_js};',
        html
    )

    ts = now_utc.strftime("%b %-d, %Y  %I:%M %p UTC")
    html = re.sub(
        r'(7-Day Outlook — Chicago Route Impact \(Confirmed NOAA Data,\s*)[^)]+\)',
        rf'\g<1>{ts})',
        html
    )
    html = re.sub(
        r'(Mar 31 2026)',
        ts,
        html
    )

    high_count = sum(1 for r in rows if r["level"] == "HIGH")
    modhi_count = sum(1 for r in rows if r["level"] == "MODERATE-HIGH")
    state_count = len(rows)

    html = re.sub(r"(id='kpi-high'[^>]*>)[^<]*", rf"\g<1>{high_count}", html)
    html = re.sub(r"(id='kpi-modhi'[^>]*>)[^<]*", rf"\g<1>{modhi_count}", html)
    html = re.sub(r"(id='kpi-states'[^>]*>)[^<]*", rf"\g<1>{state_count}", html)

    html = re.sub(
        r'(⚠ Sources:)',
        f'\U0001f504 Auto-updated: {ts} · \g<1>',
        html,
        count=1
    )

    return html


def generate_zips_json(base_dir):
    """Download full US ZIP database and save as zips.json next to index.html."""
    csv_url = "https://raw.githubusercontent.com/scpike/us-state-county-zip/master/geo-data.csv"
    print("  Fetching US ZIP database...")
    req = urllib.request.Request(csv_url, headers={"User-Agent": "LouMalnatis-FedExAlert/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            csv_text = r.read().decode("utf-8")
    except Exception as e:
        print(f"  ZIP database fetch failed: {e} — skipping zips.json update", file=sys.stderr)
        return

    seen = set()
    zips = []
    for line in csv_text.split("\n")[1:]:
        parts = line.split(",")
        if len(parts) < 6:
            continue
        zipcode = parts[3].strip().zfill(5)
        city    = parts[5].strip()
        state   = parts[1].strip()
        abbr    = parts[2].strip()
        if not zipcode or not abbr or zipcode in seen:
            continue
        seen.add(zipcode)
        county = parts[4].strip().zfill(3) if len(parts) > 4 else ''
        zips.append([zipcode, city, state, abbr, county])

    out_path = os.path.join(base_dir, "zips.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(zips, f, separators=(",", ":"))
    print(f"  zips.json saved — {len(zips)} ZIP codes")


def main():
    print("Fetching NOAA alerts...")
    alerts = fetch_noaa_alerts()
    alert_count = len(alerts.get("features", [])) if alerts else 0
    print(f"  Got {alert_count} active alerts")

    rows, now_utc = build_state_data(alerts)
    print(f"  {len(rows)} Chicago-route states affected: {[r['abbr'] for r in rows]}")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(base_dir, "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    html = update_html(html, rows, now_utc, alert_count)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  index.html updated — {len(rows)} states, rebuilt at {now_utc.strftime('%Y-%m-%d %H:%M UTC')}")

    generate_zips_json(base_dir)


if __name__ == "__main__":
    main()
