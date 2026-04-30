/* Drafted — Draft Advisor */

const ROLES = ['top', 'jungle', 'mid', 'bottom', 'support'];
const ROLE_NAMES = {
    top: 'Top Lane', jungle: 'Jungle', mid: 'Mid Lane', bottom: 'Bot Lane', support: 'Support',
};
const ROLE_ICONS = {
    top:     `<path d="M3 13L13 3M3 3h10v10" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/>`,
    jungle:  `<path d="M8 2c-1 2.5-3.5 4-3.5 7 0 2 1.5 4 3.5 4s3.5-2 3.5-4c0-3-2.5-4.5-3.5-7z" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linejoin="round"/>`,
    mid:     `<path d="M3 13L13 3M6 3h7v7" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/>`,
    bottom:  `<path d="M3 3l10 10M3 13h10V3" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/>`,
    support: `<path d="M8 13s-5-3-5-7a3 3 0 0 1 5-2 3 3 0 0 1 5 2c0 4-5 7-5 7z" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linejoin="round"/>`,
};

function roleSvg(role, size = 12) {
    return `<svg width="${size}" height="${size}" viewBox="0 0 16 16">${ROLE_ICONS[role] || ''}</svg>`;
}

class DraftAdvisor {
    constructor() {
        this.role       = 'mid';
        this.champions  = {};
        this.ddVersion  = '14.24.1';
        this.draft = {
            allies:    { top: null, jungle: null, mid: null, bottom: null, support: null },
            enemies:   { top: null, jungle: null, mid: null, bottom: null, support: null },
            allyBans:  [null, null, null, null, null],
            enemyBans: [null, null, null, null, null],
        };
        this.pool        = [];
        this.filter      = 'best';
        this.currentSlot = null;
        this.lastRecs    = null;
        this.timerSecs   = 0;
        this._timerInterval = null;
        this.init();
    }

    async init() {
        await Promise.all([this.loadDDragonVersion(), this.loadChampions()]);
        this.buildLayout();
        this.bindEvents();
        this.updateHeaderRole();
        this.updatePicksProgress();
        this.startTimer();
        this.fetchRecs();
        this.connectLCU();
    }

    // ── Data loading ─────────────────────────────────────────

    async loadDDragonVersion() {
        try {
            const v = await (await fetch('https://ddragon.leagueoflegends.com/api/versions.json')).json();
            if (v && v[0]) {
                this.ddVersion = v[0];
                const p = v[0].split('.');
                document.getElementById('patch-chip').textContent = `${p[0]}.${p[1]}`;
            }
        } catch (_) {}
    }

    async loadChampions() {
        try {
            this.champions = await (await fetch('/api/champions')).json();
        } catch (e) { console.error(e); }
    }

    // ── DDragon helpers ───────────────────────────────────────

    getDDragonId(champId) {
        const ex = {
            cho_gath:'Chogath', jarvan_iv:'JarvanIV', kai_sa:'Kaisa', kha_zix:'Khazix',
            vel_koz:'Velkoz', renata_glasc:'Renata', wukong:'MonkeyKing', k_sante:'KSante',
            lee_sin:'LeeSin', master_yi:'MasterYi', miss_fortune:'MissFortune',
            twisted_fate:'TwistedFate', kog_maw:'KogMaw', xin_zhao:'XinZhao',
            dr_mundo:'DrMundo', tahm_kench:'TahmKench', nunu:'Nunu',
        };
        if (ex[champId]) return ex[champId];
        // New champs stored as original DDragon PascalCase — pass through directly
        if (champId && champId[0] === champId[0].toUpperCase()) return champId;
        return champId.split('_').map(p => p[0].toUpperCase() + p.slice(1)).join('');
    }

    champImg(champId) {
        return `https://ddragon.leagueoflegends.com/cdn/${this.ddVersion}/img/champion/${this.getDDragonId(champId)}.png`;
    }

    itemImg(itemId) {
        return `https://ddragon.leagueoflegends.com/cdn/${this.ddVersion}/img/item/${itemId}.png`;
    }

    runeImg(runeId) {
        // DDragon doesn't host rune images by ID directly, but via path e.g. perk-images/...
        // Use CommunityDragon as fallback
        return `https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/perk-images/styles/${runeId}.png`;
    }

    // ── Portrait rendering ────────────────────────────────────
    // Portrait div: img has z-index:1 so it covers the initials span.
    // When img fails to load (onerror), it hides itself, initials show through.

    portraitBg(champId) {
        const s = champId.split('').reduce((a, c) => a + c.charCodeAt(0), 0);
        const h = (s * 47) % 360;
        return `linear-gradient(135deg,hsl(${h},45%,32%),hsl(${(h+60)%360},50%,18%))`;
    }

    portrait(champId, size, { ring = '', you = false } = {}) {
        const name = this.champions[champId]?.name || champId;
        const init = name.slice(0, 2);
        const url  = this.champImg(champId);
        const ringSt = you
            ? 'box-shadow:0 0 0 2px var(--accent),0 0 14px rgba(155,124,245,0.35);'
            : ring ? `box-shadow:0 0 0 2px ${ring};` : '';
        const r = Math.round(size * 0.083);
        return `<div style="width:${size}px;height:${size}px;border-radius:${r}px;overflow:hidden;position:relative;flex-shrink:0;display:flex;align-items:center;justify-content:center;background:${this.portraitBg(champId)};${ringSt}">
            <img src="${url}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-index:1" onerror="this.style.display='none'" alt="">
            <span style="font-size:${Math.round(size*0.33)}px;font-weight:700;color:rgba(255,255,255,0.9);font-family:'Space Grotesk'">${init}</span>
        </div>`;
    }

    // ── Layout building ───────────────────────────────────────

    buildLayout() {
        this.buildRoleDropdown();
        this.buildBanRow('ally-bans', 'ally');
        this.buildBanRow('enemy-bans', 'enemy');
        this.buildRoster('ally-roster', 'ally');
        this.buildRoster('enemy-roster', 'enemy');
    }

    buildRoleDropdown() {
        document.getElementById('role-dropdown').innerHTML = ROLES.map(r =>
            `<div class="d2-role-opt${r === this.role ? ' active' : ''}" data-role="${r}">
                ${roleSvg(r, 12)}<span>${ROLE_NAMES[r]}</span>
            </div>`
        ).join('');
    }

    buildBanRow(id, side) {
        const el = document.getElementById(id);
        el.innerHTML = '';
        for (let i = 0; i < 5; i++) {
            const d = document.createElement('div');
            d.className = 'd2-ban-slot';
            d.dataset.side  = side;
            d.dataset.index = i;
            d.innerHTML = `<span style="color:rgba(255,255,255,0.18);font-size:14px;font-weight:300">×</span>`;
            el.appendChild(d);
        }
    }

    buildRoster(containerId, side) {
        const el = document.getElementById(containerId);
        el.innerHTML = '';
        ROLES.forEach(role => {
            const row = document.createElement('div');
            row.className = `d2-rrow${side === 'enemy' ? ' right' : ''}`;
            row.dataset.side = side;
            row.dataset.role = role;
            el.appendChild(row);
            this.refreshRosterRow(row, side, role, null);
        });
    }

    refreshRosterRow(el, side, role, champId) {
        const isRight  = side === 'enemy';
        const isYou    = side === 'ally' && role === this.role;
        const hasChamp = Boolean(champId);

        el.classList.toggle('is-you', isYou && !hasChamp);

        let portraitHtml;
        if (hasChamp) {
            portraitHtml = this.portrait(champId, 48, { you: isYou });
        } else {
            const cls = isYou ? 'empty-you' : (side === 'ally' ? 'empty-ally' : 'empty-enemy');
            const ic  = isYou ? 'var(--accent)' : (side === 'ally' ? 'rgba(78,163,255,0.5)' : 'rgba(255,91,120,0.5)');
            portraitHtml = `<div class="d2-portrait ${cls}" style="width:48px;height:48px">
                <svg width="20" height="20" viewBox="0 0 16 16" style="color:${ic}">${ROLE_ICONS[role]}</svg>
            </div>`;
        }

        const nameText = hasChamp
            ? (this.champions[champId]?.name || champId)
            : (isYou ? 'YOU' : '—');
        const nameCls = hasChamp ? '' : (isYou ? ' accent' : ' muted');
        const removeBtn = hasChamp
            ? `<button onclick="event.stopPropagation();app.removeFromRoster('${side}','${role}')" style="position:absolute;${isRight?'left':'right'}:2px;top:2px;background:rgba(0,0,0,0.65);border:none;color:rgba(255,255,255,0.55);font-size:12px;cursor:pointer;border-radius:3px;width:16px;height:16px;display:flex;align-items:center;justify-content:center;z-index:10">×</button>`
            : '';

        const meta = `<div class="d2-rrow-meta${isRight?' right':''}">
            <div class="d2-rrow-name${nameCls}">${nameText}</div>
            <div class="d2-rrow-role${isRight?' right':''}">
                ${isRight?'':roleSvg(role,9)}<span>${role.toUpperCase()}</span>${isRight?roleSvg(role,9):''}
            </div>
        </div>`;

        el.style.position = 'relative';
        el.innerHTML = (isRight ? meta + portraitHtml : portraitHtml + meta) + removeBtn;
    }

    // ── Events ────────────────────────────────────────────────

    bindEvents() {
        const pickerBtn = document.getElementById('role-picker-btn');
        const dropdown  = document.getElementById('role-dropdown');
        pickerBtn.addEventListener('click', e => {
            e.stopPropagation();
            pickerBtn.classList.toggle('open');
            dropdown.classList.toggle('open');
        });
        document.addEventListener('click', () => {
            pickerBtn.classList.remove('open');
            dropdown.classList.remove('open');
        });
        dropdown.addEventListener('click', e => {
            const opt = e.target.closest('.d2-role-opt');
            if (!opt) return;
            this._roleOverridden = true;  // user manually chose — don't auto-override from LCU
            this.setRole(opt.dataset.role);
            pickerBtn.classList.remove('open');
            dropdown.classList.remove('open');
        });

        document.getElementById('filter-tabs').addEventListener('click', e => {
            const btn = e.target.closest('.d2-ftab');
            if (!btn) return;
            document.querySelectorAll('.d2-ftab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            this.filter = btn.dataset.filter;
            document.getElementById('pool-bar').style.display = this.filter === 'pool' ? 'flex' : 'none';
            if (this.lastRecs) this.renderCenter(this.lastRecs);
        });

        document.getElementById('ally-roster').addEventListener('click', e => {
            const row = e.target.closest('.d2-rrow');
            if (!row || e.target.closest('button')) return;
            if (row.dataset.role === this.role) return;  // user's own slot — not manually pickable
            if (!this.draft.allies[row.dataset.role]) this.openPicker({ side: 'ally', role: row.dataset.role });
        });
        document.getElementById('enemy-roster').addEventListener('click', e => {
            const row = e.target.closest('.d2-rrow');
            if (!row || e.target.closest('button')) return;
            if (!this.draft.enemies[row.dataset.role]) this.openPicker({ side: 'enemy', role: row.dataset.role });
        });

        document.getElementById('ally-bans').addEventListener('click', e => {
            const slot = e.target.closest('.d2-ban-slot');
            if (slot) this.openPicker({ side: 'ban', banSide: 'ally', index: +slot.dataset.index });
        });
        document.getElementById('enemy-bans').addEventListener('click', e => {
            const slot = e.target.closest('.d2-ban-slot');
            if (slot) this.openPicker({ side: 'ban', banSide: 'enemy', index: +slot.dataset.index });
        });

        document.getElementById('modal-close').addEventListener('click', () => this.closeModal());
        document.getElementById('modal').addEventListener('click', e => {
            if (e.target.id === 'modal') this.closeModal();
        });
        document.getElementById('modal-search').addEventListener('input', e => this.filterModal(e.target.value));

        document.getElementById('rec-content').addEventListener('click', e => {
            const row = e.target.closest('.d2-alt-row');
            if (!row || !this.lastRecs) return;
            const list = this.getRecList(this.lastRecs);
            const idx  = parseInt(row.dataset.idx);
            if (list && list[idx]) this.showDetailFor(list[idx], idx);
        });

        document.getElementById('pool-input').addEventListener('keydown', e => {
            if (e.key === 'Enter') { this.addToPool(e.target.value.trim()); e.target.value = ''; }
        });
    }

    setRole(role) {
        this.role = role;
        this.updateHeaderRole();
        this.buildRoleDropdown();
        document.querySelectorAll('#ally-roster .d2-rrow').forEach(row =>
            this.refreshRosterRow(row, 'ally', row.dataset.role, this.draft.allies[row.dataset.role])
        );
        this.fetchRecs();
    }

    updateHeaderRole() {
        document.getElementById('header-role-name').textContent = ROLE_NAMES[this.role];
        const svg = document.getElementById('header-role-svg');
        svg.innerHTML = ROLE_ICONS[this.role];
        svg.setAttribute('viewBox', '0 0 16 16');
    }

    // ── Draft management ──────────────────────────────────────

    removeFromRoster(side, role) {
        const map = side === 'ally' ? 'allies' : 'enemies';
        this.draft[map][role] = null;
        const id = side === 'ally' ? 'ally-roster' : 'enemy-roster';
        const row = document.querySelector(`#${id} [data-role="${role}"]`);
        if (row) this.refreshRosterRow(row, side, role, null);
        this.updatePicksProgress();
        this.fetchRecs();
    }

    updatePicksProgress() {
        const a = Object.values(this.draft.allies).filter(Boolean).length;
        const e = Object.values(this.draft.enemies).filter(Boolean).length;
        const t = a + e;
        document.getElementById('picks-count').textContent = t;
        document.getElementById('picks-fill').style.width  = `${(t / 10) * 100}%`;
        document.getElementById('ally-lock-count').textContent   = `${a} / 5 LOCKED`;
        document.getElementById('enemy-lock-count').textContent  = `${e} / 5 LOCKED`;
    }

    // ── Modal ─────────────────────────────────────────────────

    openPicker(ctx) {
        this.currentSlot = ctx;
        const used = new Set([
            ...Object.values(this.draft.allies).filter(Boolean),
            ...Object.values(this.draft.enemies).filter(Boolean),
            ...this.draft.allyBans.filter(Boolean),
            ...this.draft.enemyBans.filter(Boolean),
        ]);
        const grid = document.getElementById('champ-grid');
        grid.innerHTML = '';
        Object.entries(this.champions).forEach(([id, c]) => {
            const d = document.createElement('div');
            d.className = 'd2-champ-opt' + (used.has(id) ? ' used' : '');
            d.dataset.id = id;
            const init = c.name.slice(0, 2);
            const url  = this.champImg(id);
            d.innerHTML = `
                <div class="d2-champ-opt-icon" style="position:relative;background:${this.portraitBg(id)}">
                    <img src="${url}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-index:1" onerror="this.style.display='none'" alt="">
                    <span style="font-size:13px;font-weight:700;color:rgba(255,255,255,0.9)">${init}</span>
                </div>
                <div class="d2-champ-opt-name">${c.name}</div>`;
            if (!used.has(id)) d.addEventListener('click', () => this.pickChampion(id));
            grid.appendChild(d);
        });
        document.getElementById('modal-search').value = '';
        document.getElementById('modal').classList.add('open');
        setTimeout(() => document.getElementById('modal-search').focus(), 40);
    }

    closeModal() {
        document.getElementById('modal').classList.remove('open');
        this.currentSlot = null;
    }

    filterModal(q) {
        const t = q.toLowerCase();
        document.querySelectorAll('.d2-champ-opt').forEach(o => {
            o.style.display = o.querySelector('.d2-champ-opt-name').textContent.toLowerCase().includes(t) ? '' : 'none';
        });
    }

    pickChampion(champId) {
        const ctx = this.currentSlot;
        this.closeModal();
        if (!ctx) return;

        if (ctx.side === 'ban') {
            const arr = ctx.banSide === 'ally' ? this.draft.allyBans : this.draft.enemyBans;
            arr[ctx.index] = champId;
            this.updateBanSlot(ctx.banSide, ctx.index, champId);
        } else {
            const map = ctx.side === 'ally' ? this.draft.allies : this.draft.enemies;
            map[ctx.role] = champId;
            const id = ctx.side === 'ally' ? 'ally-roster' : 'enemy-roster';
            const row = document.querySelector(`#${id} [data-role="${ctx.role}"]`);
            if (row) this.refreshRosterRow(row, ctx.side, ctx.role, champId);
            this.updatePicksProgress();
        }
        this.fetchRecs();
    }

    updateBanSlot(side, index, champId) {
        const slots = document.querySelectorAll(`#${side === 'ally' ? 'ally' : 'enemy'}-bans .d2-ban-slot`);
        const slot  = slots[index];
        if (!slot) return;
        const name  = this.champions[champId]?.name || champId;
        const url   = this.champImg(champId);
        const line  = side === 'ally' ? 'var(--ally)' : 'var(--enemy)';
        const init  = name.slice(0, 2);
        slot.classList.add('filled');
        slot.innerHTML = `
            <div style="width:100%;height:100%;position:relative;background:${this.portraitBg(champId)}">
                <img src="${url}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-index:1" onerror="this.style.display='none'" alt="">
                <span style="font-size:11px;font-weight:700;color:rgba(255,255,255,0.9)">${init}</span>
            </div>
            <div class="d2-ban-slash">
                <svg width="20" height="20" viewBox="0 0 20 20">
                    <line x1="3" y1="3" x2="17" y2="17" stroke="${line}" stroke-width="2" stroke-linecap="round"/>
                </svg>
            </div>`;
        slot.title   = `${name} — click to remove`;
        slot.onclick = () => this.removeBan(side, index);
    }

    removeBan(side, index) {
        const arr = side === 'ally' ? this.draft.allyBans : this.draft.enemyBans;
        arr[index] = null;
        const slots = document.querySelectorAll(`#${side}-bans .d2-ban-slot`);
        const slot  = slots[index];
        if (!slot) return;
        slot.classList.remove('filled');
        slot.innerHTML = `<span style="color:rgba(255,255,255,0.18);font-size:14px;font-weight:300">×</span>`;
        slot.title = '';
        slot.onclick = null;
        this.fetchRecs();
    }

    // ── LCU live overlay ─────────────────────────────────────

    connectLCU() {
        if (this._lcuEs) return;
        const es = new EventSource('/api/lcu/stream');
        this._lcuEs = es;

        es.onmessage = (e) => {
            try {
                const state = JSON.parse(e.data);
                this.applyLCUState(state);
            } catch (_) {}
        };

        es.onerror = () => {
            // SSE auto-reconnects; update the indicator to show disconnected
            this._setLCUIndicator(false);
        };
    }

    applyLCUState(state) {
        if (!state || !state.active) {
            this._setLCUIndicator(false);
            return;
        }
        this._setLCUIndicator(true);

        let changed = false;

        // Auto-set role from LCU if the user hasn't manually changed it
        if (state.my_role && state.my_role !== this.role && !this._roleOverridden) {
            this.setRole(state.my_role);
            return;  // setRole calls fetchRecs; state will re-apply on next message
        }

        // Apply ally picks (including the user's own slot so their pick shows)
        for (const [role, champId] of Object.entries(state.allies || {})) {
            const current = this.draft.allies[role];
            if (champId && current !== champId) {
                this.draft.allies[role] = champId;
                const row = document.querySelector(`#ally-roster .d2-rrow[data-role="${role}"]`);
                if (row) this.refreshRosterRow(row, 'ally', role, champId);
                this.updateLockCount('ally');
                changed = true;
            } else if (!champId && current) {
                this.draft.allies[role] = null;
                const row = document.querySelector(`#ally-roster .d2-rrow[data-role="${role}"]`);
                if (row) this.refreshRosterRow(row, 'ally', role, null);
                this.updateLockCount('ally');
                changed = true;
            }
        }

        // Apply enemy picks
        const applyEnemies = (enemies) => {
            for (const [role, champId] of Object.entries(enemies || {})) {
                const current = this.draft.enemies[role];
                if (champId && current !== champId) {
                    this.draft.enemies[role] = champId;
                    const row = document.querySelector(`#enemy-roster .d2-rrow[data-role="${role}"]`);
                    if (row) this.refreshRosterRow(row, 'enemy', role, champId);
                    this.updateLockCount('enemy');
                    changed = true;
                } else if (!champId && current) {
                    this.draft.enemies[role] = null;
                    const row = document.querySelector(`#enemy-roster .d2-rrow[data-role="${role}"]`);
                    if (row) this.refreshRosterRow(row, 'enemy', role, null);
                    this.updateLockCount('enemy');
                    changed = true;
                }
            }
        };

        const enemyChamps = Object.values(state.enemies || {}).filter(Boolean);
        if (!state.enemy_roles_real && enemyChamps.length > 0) {
            // Enemy positions unknown — infer from Lolalytics primary lane data
            fetch('/api/infer_roles', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ champions: enemyChamps }),
            })
            .then(r => r.json())
            .then(inferred => {
                // Rebuild enemies dict with inferred roles
                const reKeyed = {};
                for (const [role, champId] of Object.entries(state.enemies || {})) {
                    if (!champId) continue;
                    const betterRole = inferred[champId] || role;
                    reKeyed[betterRole] = champId;
                }
                applyEnemies(reKeyed);
                if (changed) this.fetchRecs();
            })
            .catch(() => applyEnemies(state.enemies));
        } else {
            applyEnemies(state.enemies);
        }

        // Apply bans
        const applyBans = (incoming, side) => {
            const el = document.getElementById(`${side}-bans`);
            if (!el) return;
            const slots = el.querySelectorAll('.d2-ban-slot');
            incoming.forEach((champId, i) => {
                if (!slots[i]) return;
                const current = slots[i].dataset.champId;
                if (champId && current !== champId) {
                    slots[i].dataset.champId = champId;
                    const name = this.champions[champId]?.name || champId;
                    slots[i].classList.add('filled');
                    slots[i].title = name;
                    slots[i].innerHTML = `<img src="${this.champImg(champId)}"
                        style="width:100%;height:100%;object-fit:cover;border-radius:3px;opacity:0.6"
                        onerror="this.style.display='none'" alt="${name}">`;
                    changed = true;
                }
            });
        };
        applyBans(state.ally_bans  || [], 'ally');
        applyBans(state.enemy_bans || [], 'enemy');

        // If infer_roles is in flight it will call fetchRecs itself; otherwise call here
        const inferInFlight = !state.enemy_roles_real && enemyChamps.length > 0;
        if (changed && !inferInFlight) this.fetchRecs();
    }

    _setLCUIndicator(connected) {
        const dot  = document.querySelector('.d2-live-dot');
        const label = document.querySelector('.d2-live-label');
        if (!dot || !label) return;
        if (connected) {
            dot.style.background  = 'var(--green)';
            label.textContent = 'LIVE';
            label.style.color = 'var(--green)';
        } else {
            dot.style.background  = '#4a5168';
            label.textContent = 'OFFLINE';
            label.style.color = '#4a5168';
        }
    }

    // ── Recommendations ───────────────────────────────────────

    async fetchRecs() {
        // Cancel any in-flight request so a stale role/state can't overwrite newer results
        if (this._fetchRecsAbort) this._fetchRecsAbort.abort();
        this._fetchRecsAbort = new AbortController();
        const { signal } = this._fetchRecsAbort;

        this.showState('loading');
        try {
            const body = {
                role:          this.role,
                allies:        Object.values(this.draft.allies).filter(Boolean),
                enemies:       Object.values(this.draft.enemies).filter(Boolean),
                banned:        [...this.draft.allyBans, ...this.draft.enemyBans].filter(Boolean),
                championPool:  this.pool,
            };
            const data = await (await fetch('/api/recommendations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
                signal,
            })).json();
            if (data.error) throw new Error(data.error);
            this.lastRecs = data;
            this.renderCenter(data);
        } catch (e) {
            if (e.name === 'AbortError') return;  // superseded by a newer request
            this.showState('empty');
            console.error(e);
        }
    }

    getRecList(data) {
        return this.filter === 'pool'
            ? data.championPoolRecommendations
            : data.overallRecommendations;
    }

    renderCenter(data) {
        const list = this.getRecList(data);
        if (!list || list.length === 0) { this.showState('empty'); return; }
        this.showState('content');
        this.showDetailFor(list[0], 0);
    }

    showDetailFor(rec, activeIdx) {
        this.renderHeroCard(rec);
        this.renderWhy(rec);

        // Fetch detail from backend (power spike + counters + build/runes)
        const allies  = Object.values(this.draft.allies).filter(Boolean);
        const enemies = Object.values(this.draft.enemies).filter(Boolean);
        fetch('/api/champion_detail', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ champion_id: rec.championId, role: this.role, allies, enemies }),
        })
        .then(r => r.json())
        .then(detail => {
            this.renderPowerSpike(rec, detail.power_curve);
            this.renderCounters(rec, detail.counters || []);
            this.renderBuildRunes(rec, detail.build || [], detail.runes || {});
        })
        .catch(() => {
            this.renderPowerSpike(rec, null);
            this.renderCounters(rec, []);
            this.renderBuildRunes(rec, [], {});
        });

        const list = this.lastRecs ? this.getRecList(this.lastRecs) : null;
        if (list && list.length > 1) this.renderAlternatives(list, activeIdx);
    }

    showState(s) {
        document.getElementById('state-loading').style.display = s === 'loading' ? 'flex' : 'none';
        document.getElementById('state-empty').style.display   = s === 'empty'   ? 'flex' : 'none';
        const rc = document.getElementById('rec-content');
        if (s === 'content') {
            rc.style.display        = 'flex';
            rc.style.flexDirection  = 'column';
            rc.style.gap            = '12px';
        } else {
            rc.style.display = 'none';
        }
    }

    // ── Tier ─────────────────────────────────────────────────

    getTier(score) {
        if (score >= 72) return { label: 'S+', cls: 'Sp' };
        if (score >= 62) return { label: 'S',  cls: 'S'  };
        if (score >= 55) return { label: 'A',  cls: 'A'  };
        if (score >= 48) return { label: 'B',  cls: 'B'  };
        if (score >= 42) return { label: 'C',  cls: 'C'  };
        return                  { label: 'D',  cls: 'D'  };
    }

    tierColor(cls) {
        return { Sp: 'var(--gold)', S: 'var(--gold)', A: 'var(--yellow)', B: 'var(--green)', C: 'var(--text-dim)', D: 'var(--text-mute)' }[cls] || 'var(--text-mute)';
    }

    blurb(rec) {
        const sb = rec.scoreBreakdown;
        const p  = [];
        if (sb.counterScore > 65) p.push('strong counter');
        if (sb.synergyScore > 65) p.push('great synergy');
        if (sb.metaScore > 65)    p.push('meta pick');
        if (rec.winRate > 53)     p.push(`${rec.winRate}% WR`);
        return p.length ? p.join(' · ') : `${rec.pickRate}% pick rate`;
    }

    // ── Hero card ─────────────────────────────────────────────

    renderHeroCard(rec) {
        const el   = document.getElementById('hero-card');
        const tier = this.getTier(rec.score);
        const sb   = rec.scoreBreakdown;
        const lolUrl = `https://lolalytics.com/lol/${rec.championId}/build/`;

        el.className = 'd2-hero-card';
        el.innerHTML = `
            <div class="d2-hero-portrait-wrap">
                <div class="d2-hero-portrait-img" style="background:${this.portraitBg(rec.championId)}">
                    <img src="${this.champImg(rec.championId)}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-index:1" onerror="this.style.display='none'" alt="">
                    <span class="d2-portrait-init" style="font-size:28px">${rec.championName.slice(0,2)}</span>
                </div>
                <div class="d2-tier-badge tier-${tier.cls}">${tier.label} TIER</div>
            </div>
            <div class="d2-hero-info">
                <div class="d2-hero-eyebrow">★ TOP RECOMMENDATION</div>
                <div class="d2-hero-name">${rec.championName}</div>
                <div class="d2-hero-blurb">${this.blurb(rec)}</div>
                <div class="d2-hero-stats">
                    <div><div class="d2-hstat-label">SCORE</div>   <div class="d2-hstat-val" style="color:var(--gold)">${rec.score}</div></div>
                    <div><div class="d2-hstat-label">WIN</div>     <div class="d2-hstat-val" style="color:var(--green)">${rec.winRate}%</div></div>
                    <div><div class="d2-hstat-label">SYNERGY</div> <div class="d2-hstat-val" style="color:var(--ally)">${Math.round(sb.synergyScore)}</div></div>
                    <div><div class="d2-hstat-label">COUNTER</div> <div class="d2-hstat-val" style="color:var(--green)">${Math.round(sb.counterScore)}</div></div>
                </div>
            </div>
            <div class="d2-hero-actions">
                <a class="d2-btn-primary" href="${lolUrl}" target="_blank" rel="noopener" style="text-decoration:none;text-align:center">Lolalytics ↗</a>
                <button class="d2-btn-secondary" onclick="app.scrollToBuildRunes()">Build &amp; Runes ↓</button>
            </div>`;
    }

    scrollToBuildRunes() {
        document.getElementById('build-runes-panel').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    // ── Power spike timeline ──────────────────────────────────

    renderPowerSpike(rec, powerCurve) {
        const el = document.getElementById('power-spike-panel');
        const ally  = powerCurve?.ally  || [50, 62, 72, 70, 65];
        const enemy = powerCurve?.enemy || [55, 65, 66, 64, 60];
        const stages = ['Lane', 'Lvl 6', 'Mid', 'Late', 'Full'];
        const lvls   = ['<20m', '~22m', '~28m', '~37m', '45m+'];

        // Find peak advantage stage
        const advantage = ally.map((v, i) => v - enemy[i]);
        const peak = advantage.indexOf(Math.max(...advantage));
        const peakAdv = Math.round(Math.max(...advantage) * 10) / 10;
        const stageLabels = ['FORCE EARLY', 'FIGHT AT LVL 6', 'FORCE FIGHTS AT LVL 11', 'TAKE LATE FIGHTS', 'SCALE TO FULL BUILD'];
        const calloutLabel = stageLabels[peak];

        // Auto-scale Y-axis to the actual win rate range
        const all = [...ally, ...enemy];
        const rawMin = Math.min(...all), rawMax = Math.max(...all);
        const pad = Math.max(1.5, (rawMax - rawMin) * 0.2);
        const minV = rawMin - pad, maxV = rawMax + pad;
        const range = maxV - minV;

        // SVG dimensions
        const W = 680, H = 150, PX = 44, PY = 24;
        const x = t => PX + t * (W - PX - 18) / 4;
        const y = v => H - PY - ((v - minV) / range) * (H - PY * 2);

        const bezier = (arr) => {
            const pts = arr.map((v, i) => [x(i), y(v)]);
            let d = `M ${pts[0].join(' ')}`;
            for (let i = 1; i < pts.length; i++) {
                const [px1, py1] = pts[i - 1];
                const [cx2, cy2] = pts[i];
                const mx = px1 + (cx2 - px1) / 2;
                d += ` C ${mx} ${py1}, ${mx} ${cy2}, ${cx2} ${cy2}`;
            }
            return d;
        };

        const area = (arr) => {
            const pts = arr.map((v, i) => [x(i), y(v)]);
            let d = `M ${pts[0][0]} ${H - PY}`;
            pts.forEach(([px, py], i) => {
                if (i === 0) { d += ` L ${px} ${py}`; return; }
                const [ppx, ppy] = pts[i - 1];
                const mx = ppx + (px - ppx) / 2;
                d += ` C ${mx} ${ppy}, ${mx} ${py}, ${px} ${py}`;
            });
            d += ` L ${pts[pts.length - 1][0]} ${H - PY} Z`;
            return d;
        };

        // Grid lines at sensible intervals
        const gridStep = range < 5 ? 1 : range < 10 ? 2 : 5;
        const gridStart = Math.ceil(minV / gridStep) * gridStep;
        const gridLines = [];
        for (let g = gridStart; g <= maxV; g += gridStep) gridLines.push(g);

        const px = x(peak);

        // Data source label
        const isRealData = powerCurve?.ally && Math.abs(ally[0] - 50) < 20 && ally.some(v => v !== ally[0]);
        const sourceLabel = isRealData ? 'Win rate by game length · Lolalytics · Emerald+' : 'Estimated curve by archetype';

        el.innerHTML = `<div class="d2-power-spike">
            <div class="d2-spike-head">
                <div>
                    <span class="d2-spike-title">WIN RATE BY GAME LENGTH</span>
                    <span class="d2-spike-sub">· ${rec.championName}</span>
                </div>
                <div class="d2-spike-legend">
                    <div class="d2-spike-legend-item">
                        <div style="width:14px;height:2px;background:var(--ally);border-radius:1px"></div>Your pick
                    </div>
                    <div class="d2-spike-legend-item">
                        <div style="width:14px;height:2px;border-top:2px dashed var(--enemy)"></div>Baseline
                    </div>
                </div>
            </div>
            <svg viewBox="0 0 ${W} ${H}" style="display:block;width:100%;height:auto" preserveAspectRatio="none">
                <defs>
                    <linearGradient id="allyFill" x1="0" x2="0" y1="0" y2="1">
                        <stop offset="0%" stop-color="#4ea3ff" stop-opacity="0.3"/>
                        <stop offset="100%" stop-color="#4ea3ff" stop-opacity="0"/>
                    </linearGradient>
                    <linearGradient id="winGrad" x1="0" x2="0" y1="0" y2="1">
                        <stop offset="0%" stop-color="#3ed694" stop-opacity="0.15"/>
                        <stop offset="100%" stop-color="#3ed694" stop-opacity="0"/>
                    </linearGradient>
                </defs>
                ${gridLines.map(g =>
                    `<line x1="${PX}" x2="${W-18}" y1="${y(g)}" y2="${y(g)}" stroke="#262b3a" stroke-dasharray="2 4" opacity="0.6"/>
                     <text x="${PX-4}" y="${y(g)+3.5}" text-anchor="end" font-size="8.5" fill="#4a5168" font-family="JetBrains Mono">${g}%</text>`
                ).join('')}
                <rect x="${px-52}" y="${PY-4}" width="104" height="${H-PY*2+4}" fill="url(#winGrad)" rx="6"/>
                <line x1="${px}" x2="${px}" y1="${PY}" y2="${H-PY}" stroke="#3ed694" stroke-dasharray="3 3" opacity="0.5"/>
                <path d="${area(ally)}" fill="url(#allyFill)"/>
                <path d="${bezier(enemy)}" stroke="#ff5b78" stroke-width="1.5" fill="none" stroke-dasharray="4 3" opacity="0.7"/>
                <path d="${bezier(ally)}"  stroke="#4ea3ff" stroke-width="2.5" fill="none"/>
                ${ally.map((v, i) => `
                    <circle cx="${x(i)}" cy="${y(v)}" r="4" fill="#0b0e15" stroke="#4ea3ff" stroke-width="2"/>
                    <text cx="${x(i)}" x="${x(i)}" y="${y(v)-7}" text-anchor="middle" font-size="9" fill="#4ea3ff" font-family="JetBrains Mono" font-weight="600">${v}%</text>
                `).join('')}
                <rect x="${px-58}" y="4" width="116" height="18" rx="9" fill="#3ed69428"/>
                <text x="${px}" y="17" text-anchor="middle" font-size="10" font-weight="700" fill="#3ed694" font-family="Space Grotesk" letter-spacing="0.5">⚔ WIN WINDOW</text>
                ${stages.map((s, i) => `
                    <text x="${x(i)}" y="${H-8}" text-anchor="middle" font-size="10" font-weight="600" fill="#9ba3b8" font-family="Space Grotesk">${s}</text>
                    <text x="${x(i)}" y="${H+1}" text-anchor="middle" font-size="8.5" fill="#4a5168" font-family="JetBrains Mono">${lvls[i]}</text>
                `).join('')}
            </svg>
            <div class="d2-spike-callout">
                <span class="d2-spike-callout-title">${calloutLabel}</span>
                <div style="width:1px;height:12px;background:rgba(62,214,148,0.3);flex-shrink:0"></div>
                <span class="d2-spike-callout-body">Peak win rate ${ally[peak]}% at this stage${peakAdv > 0 ? ` (+${peakAdv}% vs baseline)` : ''}.</span>
            </div>
        </div>`;
    }

    // ── Why panel ─────────────────────────────────────────────

    renderWhy(rec) {
        const el  = document.getElementById('why-panel');
        const exs = rec.explanations || [];

        const items = (exs.length ? exs.slice(0, 4) : ['Strong meta pick recommended for the current draft.']).map(txt => {
            const lower = txt.toLowerCase();
            let type = 'comp', badge = 'COMP';
            if (lower.includes('counter') || lower.includes('beats') || lower.includes('vs ') || lower.includes('advantage'))
                { type = 'counter'; badge = 'COUNTERS'; }
            else if (lower.includes('synergy') || lower.includes('combo') || lower.includes('pair') || lower.includes('with '))
                { type = 'synergy'; badge = 'SYNERGY'; }
            else if (lower.includes('meta') || lower.includes('patch') || lower.includes('tier') || lower.includes('win rate'))
                { type = 'meta'; badge = 'META'; }
            // Split at first sentence-ending punctuation after 25 chars
            const split = txt.search(/[.,:—]/);
            let main = txt, sub = '';
            if (split > 25 && split < txt.length - 4) {
                main = txt.slice(0, split);
                sub  = txt.slice(split + 1).trim();
            }
            return `<div class="d2-why-item">
                <div class="d2-why-badge badge-${type}">${badge}</div>
                <div class="d2-why-body">
                    <div class="d2-why-main">${main}</div>
                    ${sub ? `<div class="d2-why-sub">${sub}</div>` : ''}
                </div>
            </div>`;
        });

        el.innerHTML = `<div class="d2-why-panel">
            <div class="d2-panel-heading">WHY ${rec.championName.toUpperCase()}</div>
            <div class="d2-why-list">${items.join('')}</div>
        </div>`;
    }

    // ── Counters panel ────────────────────────────────────────

    renderCounters(rec, counters) {
        const el = document.getElementById('counters-panel');
        if (!counters.length) {
            el.innerHTML = `<div class="d2-breakdown-panel">
                <div class="d2-panel-heading">SCORE BREAKDOWN</div>
                ${this.barHtml('Meta',    rec.scoreBreakdown.metaScore,    'meta')}
                ${this.barHtml('Synergy', rec.scoreBreakdown.synergyScore, 'synergy')}
                ${this.barHtml('Counter', rec.scoreBreakdown.counterScore, 'counter')}
                ${this.barHtml('Stats',   Math.min(100, ((rec.winRate-45)/15)*100), 'meta')}
            </div>`;
            return;
        }
        const rows = counters.map(c => {
            const pct  = c.risk === 'high' ? 78 : 50;
            const col  = c.risk === 'high' ? 'var(--enemy)' : 'var(--yellow)';
            return `<div class="d2-counter-row">
                ${this.portrait(c.champion_id, 32)}
                <div>
                    <div class="d2-counter-name">${c.champion_name}</div>
                    <div class="d2-counter-note">${c.win_rate}% WR against you</div>
                </div>
                <div class="d2-risk-bar">
                    <div class="d2-risk-track"><div class="d2-risk-fill" style="width:${pct}%;background:${col}"></div></div>
                    <div class="d2-risk-label">${c.risk.toUpperCase()} RISK</div>
                </div>
            </div>`;
        }).join('');

        el.innerHTML = `<div class="d2-counters-panel">
            <div class="d2-counters-head">
                <svg width="13" height="13" viewBox="0 0 16 16">
                    <path d="M8 1L15 14H1L8 1z" fill="var(--enemy)"/>
                    <path d="M8 6v4M8 12v0.5" stroke="#0b0e15" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
                <span class="d2-counters-title">STILL CAN COUNTER YOU</span>
                <span class="d2-counters-sub">${counters.length} threat${counters.length !== 1 ? 's' : ''} from data</span>
            </div>
            ${rows}
        </div>`;
    }

    barHtml(label, val, cls) {
        const v = Math.min(100, Math.max(0, Math.round(val)));
        return `<div class="d2-bar-row">
            <span class="d2-bar-lbl">${label}</span>
            <div class="d2-bar-track"><div class="d2-bar-fill bar-${cls}" style="width:${v}%"></div></div>
            <span class="d2-bar-num">${v}</span>
        </div>`;
    }

    // ── Build & Runes ─────────────────────────────────────────

    renderBuildRunes(rec, build, runes) {
        const el = document.getElementById('build-runes-panel');
        const hasBuild = Array.isArray(build) && build.length > 0;
        const hasRunes = runes && Array.isArray(runes.pri) && runes.pri.length > 0;

        if (!hasBuild && !hasRunes) {
            el.innerHTML = '';
            return;
        }

        const cdnImg = (id) => `https://cdn5.lolalytics.com/item64/${id}.webp`;
        const runeImg = (id) => `https://cdn5.lolalytics.com/rune68/${id}.webp`;

        const itemsHtml = hasBuild ? build.map(item => {
            const abbr = item.name.length > 12 ? item.name.slice(0, 10) + '…' : item.name;
            return `<div class="d2-item" title="${item.name}${item.wr ? ' · ' + item.wr + '% WR' : ''}">
                <div class="d2-item-img">
                    <img src="${cdnImg(item.id)}" onerror="this.src=''" alt="">
                </div>
                <div class="d2-item-name">${abbr}</div>
            </div>`;
        }).join('') : '';

        // Render rune icons: keystone first, then primary, then secondary, then shards
        let runesHtml = '';
        if (hasRunes) {
            const allRunes = [
                ...runes.pri.map((r, i) => ({...r, slot: i === 0 ? 'Keystone' : `Primary ${i}`})),
                ...runes.sec.map((r, i) => ({...r, slot: `Secondary ${i+1}`})),
            ];
            runesHtml = `<div class="d2-rune-page">
                <div class="d2-rune-row">
                    ${allRunes.map(r => `<div class="d2-rune-chip" title="${r.name || r.id}">
                        <img src="${runeImg(r.id)}" onerror="this.style.opacity='0.2'" alt="">
                        <span class="d2-rune-chip-name">${r.name || r.id}</span>
                    </div>`).join('')}
                </div>
                ${runes.mod && runes.mod.length > 0 ? `<div class="d2-rune-shards">
                    ${runes.mod.map(r => `<div class="d2-shard-chip" title="${r.name || r.id}">
                        <img src="https://cdn5.lolalytics.com/statmod32/${r.id}.webp" onerror="this.style.opacity='0.2'" alt="">
                    </div>`).join('')}
                </div>` : ''}
                ${runes.wr ? `<div class="d2-rune-wr-line">${runes.wr}% WR · ${runes.n?.toLocaleString()} games (most-picked page)</div>` : ''}
            </div>`;
        }

        el.innerHTML = `<div class="d2-build-runes">
            <div class="d2-br-head">
                <span class="d2-br-title">BUILD &amp; RUNES</span>
                <span class="d2-br-source">via Lolalytics · Emerald+</span>
            </div>
            <div class="d2-br-row2">
                ${hasBuild ? `<div>
                    <div class="d2-br-section-title">CORE BUILD</div>
                    <div class="d2-items-row">${itemsHtml}</div>
                </div>` : ''}
                ${hasRunes ? `<div>
                    <div class="d2-br-section-title">RUNES (MOST PICKED)</div>
                    ${runesHtml}
                </div>` : ''}
            </div>
        </div>`;
    }

    // ── Alternatives ──────────────────────────────────────────

    renderAlternatives(list, activeIdx) {
        const el  = document.getElementById('alts-panel');
        const alt = list.slice(1, 9);
        if (!alt.length) { el.innerHTML = ''; return; }

        const rows = alt.map((rec, i) => {
            const idx  = i + 1;
            const tier = this.getTier(rec.score);
            const sel  = activeIdx === idx ? ' selected' : '';
            return `<div class="d2-alt-row${sel}" data-idx="${idx}">
                ${this.portrait(rec.championId, 32)}
                <div style="min-width:0">
                    <div class="d2-alt-name">${rec.championName}</div>
                    <div class="d2-alt-blurb">${this.blurb(rec)}</div>
                </div>
                <div class="d2-alt-tier" style="color:${this.tierColor(tier.cls)}">${tier.label}</div>
                <div class="d2-alt-score">${rec.score}</div>
                <div class="d2-alt-wr">${rec.winRate}%</div>
            </div>`;
        }).join('');

        el.innerHTML = `<div class="d2-alts-panel">
            <div class="d2-alts-head">
                <span class="d2-alts-title">ALTERNATIVES</span>
                <span class="d2-alts-sub">${alt.length} more strong picks</span>
            </div>
            <div class="d2-alts-grid">${rows}</div>
        </div>`;
    }

    // ── Pool ─────────────────────────────────────────────────

    addToPool(name) {
        if (!name) return;
        const id = Object.keys(this.champions).find(
            k => this.champions[k].name.toLowerCase() === name.toLowerCase()
        );
        if (id && !this.pool.includes(id)) {
            this.pool.push(id);
            this.renderPoolTags();
            if (this.filter === 'pool') this.fetchRecs();
        }
    }

    removeFromPool(id) {
        this.pool = this.pool.filter(x => x !== id);
        this.renderPoolTags();
        if (this.filter === 'pool') this.fetchRecs();
    }

    renderPoolTags() {
        document.getElementById('pool-tags').innerHTML = this.pool.map(id => {
            const name = this.champions[id]?.name || id;
            return `<div class="d2-pool-tag">${name}<span class="d2-pool-x" onclick="app.removeFromPool('${id}')">×</span></div>`;
        }).join('');
    }

    // ── Timer ─────────────────────────────────────────────────

    startTimer() {
        clearInterval(this._timerInterval);
        this._timerInterval = setInterval(() => {
            this.timerSecs++;
            const m = Math.floor(this.timerSecs / 60);
            const s = this.timerSecs % 60;
            document.getElementById('live-timer').textContent = `${m}:${s.toString().padStart(2,'0')}`;
        }, 1000);
    }
}

const app = new DraftAdvisor();
