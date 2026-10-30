"""Builds metrics.activity.svg: an ECG-style activity pulse from public GitHub events."""
import json, os, sys, urllib.request
from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape

USER = os.environ.get("PULSE_USER", "imagesent")
TZ_HOURS = float(os.environ.get("PULSE_TZ_HOURS", "8"))  # 8 = Philippines
DAYS = 30
OUT = os.environ.get("PULSE_OUT", "metrics.activity.svg")
TOKEN = os.environ.get("GH_TOKEN", "")


def fetch_events():
    events = []
    for page in (1, 2, 3):
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "pulse-script"}
        if TOKEN:
            headers["Authorization"] = f"Bearer {TOKEN}"
        url = f"https://api.github.com/users/{USER}/events/public?per_page=100&page={page}"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
                batch = json.load(r)
        except Exception as e:
            print("fetch failed:", e, file=sys.stderr)
            if page == 1:
                sys.exit(1)  # keep the old image instead of overwriting with nothing
            break
        if not batch:
            break
        events += batch
    return events


def compute(events, now=None):
    tz = timezone(timedelta(hours=TZ_HOURS))
    today = (now or datetime.now(timezone.utc)).astimezone(tz).date()
    days = [today - timedelta(days=DAYS - 1 - i) for i in range(DAYS)]
    counts = {d: 0 for d in days}
    prs = 0
    for e in events:
        d = datetime.fromisoformat(e["created_at"].replace("Z", "+00:00")).astimezone(tz).date()
        if d not in counts:
            continue
        p = e.get("payload", {})
        if e["type"] == "PushEvent":
            counts[d] += p.get("size") or len(p.get("commits", [])) or 1
        else:
            counts[d] += 1
            if e["type"] == "PullRequestEvent" and p.get("action") == "opened":
                prs += 1
    return days, counts, prs


def build_svg(days, counts, prs):
    vals = [counts[d] for d in days]
    total = sum(vals)
    avg = total / DAYS
    median = sorted(vals)[DAYS // 2]
    active = sum(1 for v in vals if v)
    mx = max(vals)
    peak_i = vals.index(mx) if mx else None
    wk = [0] * 7
    for d, v in zip(days, vals):
        wk[d.weekday()] += v
    names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    busiest = names[wk.index(max(wk))] if total else "—"

    W, H, base = 900, 280, 150
    x0, x1 = 50, 850
    step = (x1 - x0) / (DAYS - 1)
    pts = [f"M 30,{base}"]
    for i, v in enumerate(vals):
        x = x0 + i * step
        if v:
            h = 10 + 40 * v / mx
            pts += [f"L {x-10:.1f},{base}", f"L {x-8:.1f},{base-3}", f"L {x-6:.1f},{base}",
                    f"L {x-3:.1f},{base+4}", f"L {x:.1f},{base-h:.1f}",
                    f"L {x+3:.1f},{base+h*0.45:.1f}", f"L {x+6:.1f},{base}"]
    pts.append(f"L 870,{base}")
    path = " ".join(pts)

    dot = ""
    if peak_i is not None:
        px = x0 + peak_i * step
        py = base - (10 + 40)
        dot = (f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="#eafff1">'
               f'<animate attributeName="r" values="4;6;4" dur="2s" repeatCount="indefinite"/></circle>')

    if peak_i is not None:
        pd = days[peak_i]
        peak_val = f"{mx} events"
        peak_sub = f"{pd.strftime('%b').lower()} {pd.day} · {pd.strftime('%A').lower()}"
    else:
        peak_val, peak_sub = "0 events", "no activity yet"

    stats = [
        ("PEAK DAY", peak_val, peak_sub),
        ("AVG / DAY", f"{avg:.1f}", f"{total} events total"),
        ("PULL REQUESTS", str(prs), "opened, last 30 days"),
        ("BUSIEST DAY", busiest, "most active weekday"),
        ("ACTIVE DAYS", f"{active} / {DAYS}", "days with activity"),
    ]
    cols = ""
    for i, (lab, val, sub) in enumerate(stats):
        x = 50 + i * 170
        cols += (f'<text x="{x}" y="222" font-size="10" letter-spacing="2" fill="#3a6b4a">{escape(lab)}</text>'
                 f'<text x="{x}" y="247" font-size="20" font-weight="bold" fill="#eafff1">{escape(val)}</text>'
                 f'<text x="{x}" y="264" font-size="10" fill="#2f5a3d">{escape(sub)}</text>')

    draw = ('<animate attributeName="stroke-dashoffset" from="1" to="0" dur="3s" fill="freeze"/>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Activity pulse for the last 30 days">
  <defs>
    <filter id="glow" x="-5%" y="-50%" width="110%" height="200%"><feGaussianBlur stdDeviation="3"/></filter>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0b150f"/><stop offset="1" stop-color="#08100b"/></linearGradient>
  </defs>
  <rect width="{W}" height="{H}" rx="14" fill="url(#bg)"/>
  <g font-family="'JetBrains Mono','SF Mono',Consolas,Menlo,monospace">
    <circle cx="52" cy="38" r="4" fill="#3ddc84"><animate attributeName="opacity" values="1;0.3;1" dur="1.6s" repeatCount="indefinite"/></circle>
    <text x="66" y="42" font-size="10" letter-spacing="3" fill="#3ddc84">VITALS · LIVE</text>
    <text x="850" y="42" font-size="10" letter-spacing="2" fill="#2f5a3d" text-anchor="end">LAST 30 DAYS · MEDIAN {median} / DAY</text>
    <text x="50" y="76" font-size="22" font-weight="bold" fill="#eafff1">Activity pulse</text>
    <rect x="50" y="84" width="84" height="2" fill="#3ddc84"/>
    <text x="50" y="102" font-size="10" fill="#2f5a3d">public GitHub activity · {escape(USER)}</text>
    <path d="{path}" fill="none" stroke="#3ddc84" stroke-width="4" stroke-linejoin="round" opacity="0.55" filter="url(#glow)" pathLength="1" stroke-dasharray="1">{draw}</path>
    <path d="{path}" fill="none" stroke="#5dffa0" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" pathLength="1" stroke-dasharray="1">{draw}</path>
    {dot}
    <line x1="50" y1="200" x2="850" y2="200" stroke="#14301f"/>
    {cols}
  </g>
</svg>
'''


def main():
    days, counts, prs = compute(fetch_events())
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(build_svg(days, counts, prs))
    print("wrote", OUT, "| events in window:", sum(counts.values()))


if __name__ == "__main__":
    main()
