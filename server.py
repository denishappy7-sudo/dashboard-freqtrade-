#!/usr/bin/env python3
"""Freqtrade Dashboard: a small read-only web dashboard for a Freqtrade bot (stdlib only).

It reads data from the Freqtrade REST API (api_server) and shows open/closed trades,
orders and re-entries, candlestick charts, daily profit, totals and host health.
It never sends commands to the bot.
"""
import base64, hmac, json, os, re, shutil, subprocess, time, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
HOST = os.environ.get('DASH_HOST', '127.0.0.1')
PORT = int(os.environ.get('DASH_PORT', '8090'))
# Freqtrade API: either FT_API_URL/FT_API_USER/FT_API_PASS, or read api_server from FT_CONFIG
FT_CONFIG = os.environ.get('FT_CONFIG', os.path.expanduser('~/freqtrade/user_data/config.json'))
FT_API_URL = os.environ.get('FT_API_URL')
FT_API_USER = os.environ.get('FT_API_USER')
FT_API_PASS = os.environ.get('FT_API_PASS')
FT_SERVICE = os.environ.get('FT_SERVICE', 'freqtrade')  # systemd unit name (optional)
# Optional HTTP Basic auth for the dashboard itself
DASH_USER = os.environ.get('DASH_USER', 'admin')
DASH_PASS = os.environ.get('DASH_PASS', '')
BINANCE_FUTURES = os.environ.get('DASH_BINANCE_FUTURES', 'https://fapi.binance.com')
BINANCE_SPOT = os.environ.get('DASH_BINANCE_SPOT', 'https://api.binance.com')
CACHE = {'t': 0, 'v': b'{}'}
CND = {}


def api(path):
    url, user, pw = FT_API_URL, FT_API_USER, FT_API_PASS
    if not url or user is None:
        a = json.load(open(FT_CONFIG)).get('api_server', {})
        host = a.get('listen_ip_address') or '127.0.0.1'
        if host == '0.0.0.0':
            host = '127.0.0.1'
        url = 'http://%s:%s' % (host, a.get('listen_port', 8080))
        user, pw = a.get('username', ''), a.get('password', '')
    req = urllib.request.Request('%s/api/v1/%s' % (url.rstrip('/'), path))
    req.add_header('Authorization', 'Basic ' + base64.b64encode(('%s:%s' % (user, pw)).encode()).decode())
    return json.load(urllib.request.urlopen(req, timeout=10))


def sysinfo():
    m = {}
    for line in open('/proc/meminfo'):
        k, v = line.split(':')
        m[k] = int(v.split()[0]) // 1024
    o = {'mem_total': m.get('MemTotal'), 'mem_avail': m.get('MemAvailable'),
         'swap_total': m.get('SwapTotal'), 'swap_used': m.get('SwapTotal', 0) - m.get('SwapFree', 0)}
    o['uptime_h'] = round(float(open('/proc/uptime').read().split()[0]) / 3600, 1)
    o['load'] = open('/proc/loadavg').read().split()[0]
    try:
        o['temp'] = int(open('/sys/class/thermal/thermal_zone0/temp').read()) / 1000
    except Exception:
        o['temp'] = None
    du = shutil.disk_usage('/')
    o['disk_pct'] = round(du.used / du.total * 100)
    try:
        s = subprocess.run(['systemctl', 'show', FT_SERVICE, '-p', 'NRestarts', '-p', 'ActiveState'],
                           capture_output=True, text=True, timeout=5).stdout
        d = dict(x.split('=', 1) for x in s.strip().splitlines() if '=' in x)
        o['restarts'], o['state'] = d.get('NRestarts'), d.get('ActiveState')
    except Exception:
        pass
    return o


def orders_of(t):
    """Compact list of filled (and pending) orders of a trade: entries, re-entries, partial exits, final exit."""
    out = []
    short = bool(t.get('is_short'))
    for o in t.get('orders') or []:
        try:
            ts = o.get('order_filled_timestamp') or (o.get('order_timestamp') if o.get('status') in ('closed', 'filled') else None)
            filled = o.get('filled')
            if filled is None:
                filled = o.get('amount') if ts else 0
            filled = float(filled or 0)
            e = o.get('ft_is_entry')
            if e is None:
                e = (o.get('ft_order_side') == ('sell' if short else 'buy'))
            if filled > 0 and ts:
                out.append({'t': ts, 'e': 1 if e else 0, 'p': o.get('safe_price') or o.get('price'), 'q': filled,
                            'tag': o.get('ft_order_tag')})
            elif o.get('is_open') and o.get('order_timestamp'):
                out.append({'t': o.get('order_timestamp'), 'e': 1 if e else 0, 'p': o.get('price'),
                            'q': float(o.get('amount') or 0), 'tag': o.get('ft_order_tag'), 'w': 1})
        except Exception:
            pass
    out.sort(key=lambda x: x['t'] or 0)
    return out


def collect():
    d = {'ts': int(time.time()), 'api_ok': True}
    try:
        d['sys'] = sysinfo()
    except Exception as e:
        d['sys'] = {'err': str(e)}
    try:
        trades = []
        for t in api('status'):
            pct = t.get('profit_pct')
            if pct is None:
                pct = (t.get('profit_ratio') or 0) * 100
            cur, liq = t.get('current_rate'), t.get('liquidation_price')
            trades.append({
                'id': t.get('trade_id'), 'pair': t.get('pair'), 'pct': pct, 'abs': t.get('profit_abs'),
                'open_rate': t.get('open_rate'), 'cur': cur, 'stake': t.get('stake_amount'),
                'lev': t.get('leverage'), 'short': t.get('is_short'), 'opened': t.get('open_timestamp'),
                'tag': t.get('enter_tag'), 'entries': t.get('nr_of_successful_entries'),
                'exits': t.get('nr_of_successful_exits'), 'minr': t.get('min_rate'), 'maxr': t.get('max_rate'),
                'real': t.get('realized_profit'), 'orders': orders_of(t),
                'liq_dist': (abs(cur - liq) / cur * 100) if (liq and cur) else None})
        d['trades'] = trades
    except Exception as e:
        d['api_ok'], d['trades'], d['err'] = False, [], str(e)
    try:
        r = api('trades?limit=300&order_by_id=true')
        cl = []
        for t in (r.get('trades') if isinstance(r, dict) else r) or []:
            if not t.get('close_timestamp'):
                continue
            pct = t.get('close_profit_pct')
            if pct is None:
                pct = (t.get('close_profit') or 0) * 100
            cl.append({'id': t.get('trade_id'), 'pair': t.get('pair'), 'pct': pct, 'abs': t.get('close_profit_abs'),
                       'reason': t.get('exit_reason'), 'tag': t.get('enter_tag'), 'lev': t.get('leverage'),
                       'short': t.get('is_short'), 'opened': t.get('open_timestamp'),
                       'closed': t.get('close_timestamp'), 'dur': t.get('trade_duration'),
                       'open_rate': t.get('open_rate'), 'close_rate': t.get('close_rate'),
                       'minr': t.get('min_rate'), 'maxr': t.get('max_rate'), 'orders': orders_of(t)})
        cl.sort(key=lambda x: -x['closed'])
        d['closed'] = cl[:300]
    except Exception:
        d['closed'] = None
    for key, path in (('profit', 'profit'), ('balance', 'balance'), ('count', 'count'), ('daily', 'daily?timescale=14')):
        try:
            d[key] = api(path)
        except Exception:
            d[key] = None
    return d


IVS = [(300000, '5m'), (900000, '15m'), (1800000, '30m'), (3600000, '1h'), (7200000, '2h'),
       (14400000, '4h'), (28800000, '8h'), (86400000, '1d')]


def known_pairs():
    try:
        d = json.loads(CACHE['v'])
    except Exception:
        return set()
    s = {t.get('pair') for t in d.get('trades') or []}
    s |= {t.get('pair') for t in d.get('closed') or []}
    return s


def candles(pair, start=None, end=None):
    """OHLC candles (Binance public klines) for a pair that appears in your open/closed trades."""
    if pair not in known_pairs() or not re.match(r'^[A-Z0-9]{1,20}/USDT(:USDT)?$', pair):
        return {'err': 'pair is not in your trades'}
    now = int(time.time() * 1000)
    end = min(int(end), now) if end else now
    start = int(start) if start else end - 86400000
    start = max(start, end - 200 * 86400000)
    if end - start < 3600000:
        start = end - 3600000
    span = end - start
    iv, name = IVS[-1]
    for ms, nm in IVS:
        if span / ms <= 160:
            iv, name = ms, nm
            break
    start = start // iv * iv
    key = (pair, name, start, end // iv)
    c = CND.get(key)
    if c and time.time() - c[0] < (30 if end >= now - iv else 3600):
        return c[1]
    sym = pair.split('/')[0] + 'USDT'
    base, path = (BINANCE_FUTURES, 'fapi/v1') if ':USDT' in pair else (BINANCE_SPOT, 'api/v3')
    url = '%s/%s/klines?symbol=%s&interval=%s&startTime=%d&endTime=%d&limit=500' % (base, path, sym, name, start, end)
    raw = json.load(urllib.request.urlopen(url, timeout=10))
    out = {'pair': pair, 'iv': iv, 'c': [[k[0], float(k[1]), float(k[2]), float(k[3]), float(k[4])] for k in raw],
           'hi': max(float(k[2]) for k in raw), 'lo': min(float(k[3]) for k in raw)}
    if len(CND) >= 40:
        CND.pop(min(CND, key=lambda x: CND[x][0]), None)
    CND[key] = (time.time(), out)
    return out


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype, extra=None):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def authed(self):
        if not DASH_PASS:
            return True
        h = self.headers.get('Authorization', '')
        if h.startswith('Basic '):
            try:
                u, _, p = base64.b64decode(h[6:]).decode().partition(':')
                return hmac.compare_digest(u, DASH_USER) and hmac.compare_digest(p, DASH_PASS)
            except Exception:
                return False
        return False

    def do_GET(self):
        if not self.authed():
            self.send(401, b'authentication required', 'text/plain', {'WWW-Authenticate': 'Basic realm="dashboard"'})
            return
        p = self.path.split('?')[0]
        if p == '/data':
            if time.time() - CACHE['t'] > 8:
                CACHE['v'] = json.dumps(collect()).encode()
                CACHE['t'] = time.time()
            self.send(200, CACHE['v'], 'application/json; charset=utf-8')
        elif p == '/candles':
            q = urllib.parse.parse_qs(self.path.split('?', 1)[1]) if '?' in self.path else {}
            try:
                body = candles((q.get('pair') or [''])[0], (q.get('from') or [None])[0], (q.get('to') or [None])[0])
            except Exception as e:
                body = {'err': 'no data: %s' % e}
            self.send(200, json.dumps(body).encode(), 'application/json; charset=utf-8')
        elif p in ('/', '/index.html'):
            self.send(200, open(os.path.join(HERE, 'index.html'), 'rb').read(), 'text/html; charset=utf-8')
        else:
            self.send(404, b'not found', 'text/plain')


if __name__ == '__main__':
    print('Freqtrade Dashboard on http://%s:%s' % (HOST, PORT))
    ThreadingHTTPServer((HOST, PORT), H).serve_forever()
