"""
LCU (League Client Update) connector.

Finds the running League client, reads its port + auth token from process
args, and polls /lol-champ-select/v1/session every 500 ms.  Translates the
raw LCU payload into a simple dict that the web app can forward to the
browser via SSE.

LCU auth: Basic base64("riot:{remoting-auth-token}")
LCU SSL:  self-signed cert — we disable verification.
"""

import base64
import re
import time
import threading
import logging
import queue
from typing import Optional

import psutil
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger(__name__)

# LCU position string → our Role string
_POS = {
    'top':     'top',
    'jungle':  'jungle',
    'middle':  'middle',
    'bottom':  'bottom',
    'utility': 'utility',
    'support': 'utility',
    '':        None,
}

_PROC_NAMES = {'LeagueClientUx', 'LeagueClientUx.exe'}


class LCUConnector:
    """Synchronous LCU REST client (runs in a background thread)."""

    def __init__(self, champion_key_map: dict):
        """
        champion_key_map: {numeric_key_int: champion_id_str}
        e.g. {103: 'ahri', 1: 'annie', ...}
        """
        self._key_map = champion_key_map
        self.port: Optional[int] = None
        self.token: Optional[str] = None
        self._session: Optional[requests.Session] = None

    # ── discovery ──────────────────────────────────────────────

    def find_client(self) -> bool:
        """Scan running processes for LeagueClientUx and extract credentials."""
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                name = proc.info.get('name', '') or ''
                if name not in _PROC_NAMES and 'LeagueClientUx' not in name:
                    continue
                cmdline = ' '.join(proc.info.get('cmdline') or [])
                port_m  = re.search(r'--app-port=(\d+)', cmdline)
                token_m = re.search(r'--remoting-auth-token=([^\s"]+)', cmdline)
                if port_m and token_m:
                    self.port  = int(port_m.group(1))
                    self.token = token_m.group(1)
                    self._session = self._make_session()
                    log.info('LCU found on port %s', self.port)
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def _make_session(self) -> requests.Session:
        s = requests.Session()
        creds = base64.b64encode(f'riot:{self.token}'.encode()).decode()
        s.headers.update({'Authorization': f'Basic {creds}'})
        s.verify = False
        return s

    def reset(self):
        self.port = None
        self.token = None
        self._session = None

    # ── polling ────────────────────────────────────────────────

    def get_champ_select(self) -> Optional[dict]:
        """Return parsed champion select state, or None if not in champ select."""
        if not self._session:
            return None
        try:
            r = self._session.get(
                f'https://127.0.0.1:{self.port}/lol-champ-select/v1/session',
                timeout=2,
            )
            if r.status_code == 200:
                return self._parse(r.json())
            if r.status_code == 404:
                return None   # not in champ select
        except requests.RequestException:
            self.reset()
        return None

    # ── parsing ────────────────────────────────────────────────

    def _cid(self, numeric_id: int) -> Optional[str]:
        """Convert numeric champion ID to our string ID (e.g. 103 → 'ahri')."""
        if not numeric_id:
            return None
        return self._key_map.get(int(numeric_id))

    def _parse(self, data: dict) -> dict:
        local_cell = data.get('localPlayerCellId', -1)
        my_team    = data.get('myTeam', [])
        their_team = data.get('theirTeam', [])
        timer      = data.get('timer', {})
        phase      = timer.get('phase', 'PLANNING')

        # Determine the local player's assigned role
        my_role = None
        for p in my_team:
            if p.get('cellId') == local_cell:
                my_role = _POS.get(p.get('assignedPosition', '').lower())
                break

        # Ally picks — keyed by role
        allies: dict = {}
        for p in my_team:
            role = _POS.get(p.get('assignedPosition', '').lower())
            if role:
                champ = self._cid(p.get('championId', 0))
                # During pick phase, championPickIntent shows hover before lock
                if not champ:
                    champ = self._cid(p.get('championPickIntent', 0))
                allies[role] = champ   # None until picked/hovered

        # Enemy picks — keyed by role
        enemies: dict = {}
        for p in their_team:
            role = _POS.get(p.get('assignedPosition', '').lower())
            if role:
                champ = self._cid(p.get('championId', 0))
                enemies[role] = champ

        # Bans
        bans_raw = data.get('bans', {})
        ally_bans  = [self._cid(c) for c in bans_raw.get('myTeamBans',    []) if c]
        enemy_bans = [self._cid(c) for c in bans_raw.get('theirTeamBans', []) if c]

        return {
            'active':      True,
            'phase':       phase,
            'my_role':     my_role,
            'allies':      allies,
            'enemies':     enemies,
            'ally_bans':   ally_bans,
            'enemy_bans':  enemy_bans,
        }


# ── background service ─────────────────────────────────────────────────────

class LCUService:
    """
    Runs a polling loop in a daemon thread.  Callers subscribe by calling
    subscribe() which returns a queue.Queue; each state change pushes a dict
    (or None when champ select ends) onto every subscribed queue.
    """

    POLL_INTERVAL = 0.5   # seconds
    FIND_INTERVAL = 3.0   # seconds between process-scan retries

    def __init__(self, champion_key_map: dict):
        self._connector = LCUConnector(champion_key_map)
        self._subscribers: list[queue.Queue] = []
        self._lock = threading.Lock()
        self._last_state: Optional[dict] = None
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self._thread.start()
        log.info('LCU service started')

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=20)
        with self._lock:
            self._subscribers.append(q)
            # Send current state immediately to new subscriber
            if self._last_state is not None:
                try:
                    q.put_nowait(self._last_state)
                except queue.Full:
                    pass
        return q

    def unsubscribe(self, q: queue.Queue):
        with self._lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    def current(self) -> Optional[dict]:
        return self._last_state

    def _broadcast(self, state: Optional[dict]):
        with self._lock:
            self._last_state = state
            for q in self._subscribers:
                try:
                    q.put_nowait(state)
                except queue.Full:
                    pass

    def _loop(self):
        connector = self._connector
        last_find_attempt = 0.0

        while True:
            try:
                if connector.port is None:
                    now = time.monotonic()
                    if now - last_find_attempt >= self.FIND_INTERVAL:
                        connector.find_client()
                        last_find_attempt = now
                    if connector.port is None:
                        time.sleep(self.POLL_INTERVAL)
                        continue

                state = connector.get_champ_select()

                if state != self._last_state:
                    self._broadcast(state)

            except Exception as exc:
                log.debug('LCU loop error: %s', exc)
                connector.reset()

            time.sleep(self.POLL_INTERVAL)
