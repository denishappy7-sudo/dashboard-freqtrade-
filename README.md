# Freqtrade Dashboard

[Русская версия: README.ru.md](README.ru.md)

A small **read-only** web dashboard for a [Freqtrade](https://www.freqtrade.io) bot, made for checking the bot from a phone.
One Python file (standard library only) plus one HTML page. No pip packages, no build step, about 10 MB of RAM.
Built for small boxes (TV boxes, Raspberry Pi, old phones), works anywhere Python 3.8+ runs.

It never sends commands to the bot: it only reads data from the Freqtrade REST API.

<p>
<img src="screenshot-overview.png" width="260" alt="Overview">
<img src="screenshot-open-trade.png" width="260" alt="Open trade with candles and re-entries">
<img src="screenshot-closed-trade.png" width="260" alt="Closed trades with re-entries">
</p>

*Screenshots use generated demo data.*

## What it shows

- Balance, total profit, open slots, win rate.
- **Open trades**: profit in % and USDT, average entry price, current price, the list of entry prices
  (`entries: 1.19 → 1.24 → 1.16`), distance to liquidation (futures), number of re-entries and partial sells, age, entry tag.
- **Tap an open trade** for details: first entry, invested margin, position size with leverage, worst and best price since entry
  (and what that means in % on your stake), realized profit from partial sells, and a **candlestick chart** (OHLC) with:
  - the average entry price line and the liquidation price line,
  - numbered markers for every entry and re-entry (1, 2, 3 …), a red minus for each partial sell, a grey dot for a pending order,
  - the list of all orders: time, order tag, price, size in USDT and the % distance from the first entry price.
  - **Chart controls**: switch the candle size between Auto, 15 min and 1 hour, and press **◀ +7d** to load another week of history before the trade (press it again for more, ↺ resets).
- **Closed trades**: collapsible list of up to 300 trades with filters **All / Week / Month**, a summary line (wins, losses, total USDT),
  badges with the number of re-entries and partial sells. Tap a trade to see the same details, candle chart and order list
  (with a check mark at the final exit).
- Daily profit chart (last 14 days) and totals.
- Host health: bot service state, restarts, free memory, swap, CPU load, temperature, disk usage, uptime.

Works with futures and spot. Candles come from Binance public klines (no API key needed); the chart step adapts
to the trade age (5 min, 15 min, 30 min, 1 h … 1 d). Light and dark themes follow the system setting. Made for phone screens.

## Requirements

- A running Freqtrade bot with the REST API enabled.
- Python 3.8+ on the machine that runs the dashboard (usually the same machine as the bot).
- Any OS for the dashboard itself (Linux, Windows, macOS; see section 5). Linux is needed only for the host health block, elsewhere it shows dashes.

## 1. Enable the Freqtrade API

In your Freqtrade `config.json` (see the Freqtrade docs, "REST API"):

```json
"api_server": {
    "enabled": true,
    "listen_ip_address": "127.0.0.1",
    "listen_port": 8080,
    "username": "your_user",
    "password": "a_long_random_password",
    "jwt_secret_key": "something_random",
    "CORS_origins": []
}
```

Restart the bot after changing the config. Keep `listen_ip_address` on `127.0.0.1` if the dashboard runs on the same machine.

## 2. Install and run

```bash
mkdir -p ~/freqtrade-dashboard && cd ~/freqtrade-dashboard
# put server.py and index.html here
python3 server.py
```

Open `http://127.0.0.1:8090` on that machine. By default the dashboard reads the API address and
credentials from `~/freqtrade/user_data/config.json`. If your config is elsewhere, or you do not want
the dashboard to read a file that contains exchange keys, pass the API settings as environment variables instead:

```bash
FT_API_URL=http://127.0.0.1:8080 FT_API_USER=your_user FT_API_PASS='a_long_random_password' python3 server.py
```

## 3. See it from your phone (home network)

By default the dashboard listens only on `127.0.0.1`. To open it from another device on your home network:

```bash
DASH_HOST=0.0.0.0 DASH_PASS='choose-a-password' python3 server.py
```

Then open `http://<box-ip>:8090` and log in (user `admin`, or set `DASH_USER`).

### Security, please read

- The page shows your balance and positions. **Do not expose it to the internet** (no port forwarding).
- Use it only on your home network, or reach it through a VPN such as Tailscale/WireGuard, or an SSH tunnel:
  `ssh -L 8090:127.0.0.1:8090 user@box`, then open `http://127.0.0.1:8090`.
- Always set `DASH_PASS` when you use `DASH_HOST=0.0.0.0`. Basic auth over plain HTTP is only fine on a trusted network.
- The dashboard has no buttons and cannot trade, stop or restart the bot.
- The chart endpoint only answers for pairs that appear in your own open or closed trades.

## 4. Run it as a service (systemd)

Create `/etc/systemd/system/freqtrade-dashboard.service` (change the user and paths):

```ini
[Unit]
Description=Freqtrade Dashboard
After=network-online.target

[Service]
User=YOUR_USER
WorkingDirectory=/home/YOUR_USER/freqtrade-dashboard
Environment=DASH_HOST=0.0.0.0
Environment=DASH_PASS=choose-a-password
Environment=FT_CONFIG=/home/YOUR_USER/freqtrade/user_data/config.json
ExecStart=/usr/bin/python3 /home/YOUR_USER/freqtrade-dashboard/server.py
Restart=always
MemoryMax=80M

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now freqtrade-dashboard
sudo systemctl status freqtrade-dashboard
```

If your bot service has another name, set `Environment=FT_SERVICE=name` so the "Bot service" and "Restarts" fields work.

## 5. Windows, macOS and Docker

The dashboard itself (trades, orders, candles, history, daily profit) runs on any system with Python 3.8+.
Only the "Bot and host" block reads Linux files (`/proc`, `/sys`, `systemctl`); on Windows and macOS it simply shows dashes.
On these systems pass the API settings as environment variables (the default config path is a Linux path).

### Windows

1. Install Python 3 from [python.org](https://www.python.org/downloads/) (tick **Add python.exe to PATH**).
2. Put `server.py` and `index.html` in a folder, for example `C:\freqtrade-dashboard`.
3. Open PowerShell in that folder and run:

```powershell
$env:FT_API_URL="http://127.0.0.1:8080"
$env:FT_API_USER="your_user"
$env:FT_API_PASS="a_long_random_password"
python server.py
```

Open `http://127.0.0.1:8090`. To open it from your phone on the same network add `$env:DASH_HOST="0.0.0.0"` and
`$env:DASH_PASS="choose-a-password"` before `python server.py`, and allow Python in the Windows Firewall for **private** networks only.

To start it automatically, save this as `start.bat` in the same folder and add it to Task Scheduler ("At log on"):

```bat
@echo off
cd /d %~dp0
set FT_API_URL=http://127.0.0.1:8080
set FT_API_USER=your_user
set FT_API_PASS=a_long_random_password
python server.py
```

### macOS

Python 3 is included with the Xcode command line tools (`python3 --version`), or install it with `brew install python`.

```bash
cd ~/freqtrade-dashboard
FT_API_URL=http://127.0.0.1:8080 FT_API_USER=your_user FT_API_PASS='a_long_random_password' python3 server.py
```

To start it at login, create `~/Library/LaunchAgents/com.freqtrade.dashboard.plist` (use the path from `which python3` and your own paths):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.freqtrade.dashboard</string>
  <key>ProgramArguments</key><array>
    <string>/usr/bin/python3</string>
    <string>/Users/YOU/freqtrade-dashboard/server.py</string>
  </array>
  <key>EnvironmentVariables</key><dict>
    <key>FT_API_URL</key><string>http://127.0.0.1:8080</string>
    <key>FT_API_USER</key><string>your_user</string>
    <key>FT_API_PASS</key><string>a_long_random_password</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict></plist>
```

Then run `launchctl load ~/Library/LaunchAgents/com.freqtrade.dashboard.plist`.

### Freqtrade in Docker

Inside the container the API must listen on all interfaces, but publish the port only to the host's loopback so it is not reachable from outside.
In the Freqtrade `config.json` use `"listen_ip_address": "0.0.0.0"`, and in `docker-compose.yml`:

```yaml
    ports:
      - "127.0.0.1:8080:8080"
```

Then run the dashboard on the host with `FT_API_URL=http://127.0.0.1:8080` and your API user and password (see above).
If you run the dashboard as another container in the same compose network, use `FT_API_URL=http://freqtrade:8080` (your service name).
The host block then shows the machine where the dashboard runs, not the bot container.

*The Windows, macOS and Docker steps are written from the standard behaviour of these systems; the dashboard code itself was tested on Linux, and without Linux files (no `/proc`, `/sys`, `systemctl`) in a simulated environment.*

## Settings (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `DASH_HOST` | `127.0.0.1` | Address to listen on (`0.0.0.0` = all interfaces) |
| `DASH_PORT` | `8090` | Port |
| `DASH_USER` / `DASH_PASS` | `admin` / empty | HTTP Basic auth for the dashboard itself (off when `DASH_PASS` is empty) |
| `FT_CONFIG` | `~/freqtrade/user_data/config.json` | Freqtrade config with the `api_server` section |
| `FT_API_URL`, `FT_API_USER`, `FT_API_PASS` | empty | Use these instead of reading the config file |
| `FT_SERVICE` | `freqtrade` | systemd unit name of the bot (for state and restart count) |
| `DASH_BINANCE_FUTURES`, `DASH_BINANCE_SPOT` | Binance public URLs | Source of price candles |

## How re-entries and partial sells are shown

The dashboard reads the `orders` list that the Freqtrade API returns for every trade.
The first filled entry order is "First entry", the next entry orders are "Re-entry 1, 2, 3 …" (position adjustments / grinding / DCA),
exit orders before the final one are "Partial sell", and the last exit order of a closed trade is "Closed".
Order tags (for example `grind_1_entry` in NostalgiaForInfinity) are shown as the bot reports them.
The percent next to each order is the price change versus the first entry price, not your profit.
"On stake" percentages are price moves multiplied by the leverage, measured from the average entry price.
Worst and best price come from the min/max rate that Freqtrade tracks while the trade is open, so they are as accurate as the bot's loop interval.

## Update / remove

Update: replace `server.py` and `index.html`, then `sudo systemctl restart freqtrade-dashboard`.
Remove: `sudo systemctl disable --now freqtrade-dashboard`, delete the unit file and the folder.

## Troubleshooting

- **"bot API unreachable"**: the dashboard cannot reach the Freqtrade API. Check that `api_server` is enabled, the port is right,
  and the username and password match. Test: `curl -u your_user:password http://127.0.0.1:8080/api/v1/ping`.
- **No chart on a trade**: charts need internet access to Binance public klines; pairs must be `XXX/USDT` or `XXX/USDT:USDT`.
  If your trades are on another exchange, the order list still works, only the candle chart will be missing or wrong.
- **No orders on a trade**: very old trades imported from other sources may have no order history in the Freqtrade database.
- **Memory / temperature fields are empty**: the host block reads `/proc` and `/sys`, so it needs Linux.

## Notes

- Unofficial community tool, not affiliated with Freqtrade or NostalgiaForInfinity. It only reads data from your bot's API and does not modify your bot.
- Tested with Freqtrade 2026.10-dev on Armbian (Python 3) with a NostalgiaForInfinityX8 bot on Binance USDⓈ-M futures. Provided as is, without warranty. Not financial advice.
- License: MIT (see `LICENSE`). Issues and pull requests are welcome.
