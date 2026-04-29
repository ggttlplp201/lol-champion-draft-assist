class DraftAdvisor {
    constructor() {
        this.champions = {};
        this.role = 'mid';
        this.tab = 'overall';
        this.draft = { allies: [], enemies: [], banned: [], pool: [] };
        this.currentSlot = null;
        this.lastData = null;
        this.ddVersion = '14.24.1';

        this.init();
    }

    async init() {
        await this.loadDDragonVersion();
        await this.loadChampions();
        this.bindEvents();
        this.fetchRecs();
    }

    async loadDDragonVersion() {
        try {
            const r = await fetch('https://ddragon.leagueoflegends.com/api/versions.json');
            const versions = await r.json();
            if (versions && versions[0]) this.ddVersion = versions[0];
        } catch(e) { /* keep fallback */ }
    }

    async loadChampions() {
        try {
            const r = await fetch('/api/champions');
            this.champions = await r.json();
        } catch (e) { console.error(e); }
    }

    // ── DDragon icons ─────────────────────────────────────────

    getDDragonId(champId) {
        const exceptions = {
            'cho_gath':    'Chogath',
            'jarvan_iv':   'JarvanIV',
            'kai_sa':      'Kaisa',
            'kha_zix':     'Khazix',
            'vel_koz':     'Velkoz',
            'renata_glasc':'Renata',
            'wukong':      'MonkeyKing',
        };
        return exceptions[champId] ||
            champId.split('_').map(p => p[0].toUpperCase() + p.slice(1)).join('');
    }

    iconHtml(champId, name) {
        const url = `https://ddragon.leagueoflegends.com/cdn/${this.ddVersion}/img/champion/${this.getDDragonId(champId)}.png`;
        return `<img src="${url}" alt="${name}" class="champ-icon" loading="lazy" onerror="this.style.display='none'">`;
    }

    bindEvents() {
        // Role tabs
        document.querySelectorAll('.role-tab').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.role-tab').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.role = btn.dataset.role;
                this.fetchRecs();
            });
        });

        // View tabs
        document.querySelectorAll('.view-tab').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.view-tab').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.tab = btn.dataset.tab;
                if (this.lastData) this.renderRecs(this.lastData);
            });
        });

        // Champion slots
        document.querySelectorAll('.champ-slot').forEach(slot => {
            slot.addEventListener('click', () => {
                if (slot.classList.contains('empty')) this.openModal(slot);
            });
        });

        // Pool input
        document.getElementById('pool-input').addEventListener('keydown', e => {
            if (e.key === 'Enter') {
                this.addToPool(e.target.value.trim());
                e.target.value = '';
            }
        });

        // Modal
        document.getElementById('modal-close').addEventListener('click', () => this.closeModal());
        document.getElementById('modal').addEventListener('click', e => {
            if (e.target.id === 'modal') this.closeModal();
        });
        document.getElementById('modal-search').addEventListener('input', e => {
            this.filterModal(e.target.value);
        });

        // Rec row click
        document.getElementById('recommendations').addEventListener('click', e => {
            const row = e.target.closest('.rec-row');
            if (row) this.selectRow(row);
        });
    }

    // ── Recommendations ───────────────────────────────────────

    async fetchRecs() {
        const el = document.getElementById('recommendations');
        el.innerHTML = '<div class="state-box"><div class="spinner"></div><p>Analyzing draft...</p></div>';

        try {
            const body = {
                role: this.role,
                allies: this.draft.allies.filter(Boolean),
                enemies: this.draft.enemies.filter(Boolean),
                banned: this.draft.banned.filter(Boolean),
                championPool: this.draft.pool,
                patch: '14.3',
            };
            const r = await fetch('/api/recommendations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const data = await r.json();
            if (data.error) throw new Error(data.error);
            this.lastData = data;
            this.renderRecs(data);
        } catch (e) {
            el.innerHTML = `<div class="state-box"><h3>Error</h3><p>${e.message}</p></div>`;
        }
    }

    renderRecs(data) {
        const list = this.tab === 'pool' ? data.championPoolRecommendations : data.overallRecommendations;
        const el = document.getElementById('recommendations');

        if (!list || list.length === 0) {
            const msg = this.tab === 'pool'
                ? 'Add champions to your pool to see personalized picks.'
                : 'Add ally and enemy picks to refine recommendations.';
            el.innerHTML = `<div class="state-box"><h3>No picks yet</h3><p>${msg}</p></div>`;
            return;
        }

        el.innerHTML = '';
        list.forEach((rec, i) => {
            const tier = this.getTier(rec.score);
            const row = document.createElement('div');
            row.className = 'rec-row';
            row.dataset.rec = JSON.stringify(rec);
            row.innerHTML = `
                <span class="rec-rank">${i + 1}</span>
                <div class="rec-champ-cell">
                    <div class="rec-icon">${this.iconHtml(rec.championId, rec.championName)}</div>
                    <span class="rec-name">${rec.championName}</span>
                </div>
                <div style="text-align:center">
                    <span class="tier-badge tier-${tier.cls}">${tier.label}</span>
                </div>
                <span class="rec-score-val" style="color:${tier.color}">${rec.score}</span>
                <span class="rec-stat rec-wr">${rec.winRate}%</span>
                <span class="rec-stat">${rec.pickRate}%</span>
                <span class="rec-stat">${rec.banRate}%</span>
            `;
            el.appendChild(row);
        });

        const first = el.querySelector('.rec-row');
        if (first) this.selectRow(first);
    }

    selectRow(row) {
        document.querySelectorAll('.rec-row').forEach(r => r.classList.remove('selected'));
        row.classList.add('selected');
        this.updateDetail(JSON.parse(row.dataset.rec));
    }

    updateDetail(rec) {
        const tier = this.getTier(rec.score);
        document.getElementById('detail-avatar').innerHTML = this.iconHtml(rec.championId, rec.championName);
        document.getElementById('detail-name').textContent = rec.championName;

        const tb = document.getElementById('detail-tier');
        tb.textContent = tier.label;
        tb.className = `detail-tier-badge tier-${tier.cls}`;

        const sv = document.getElementById('detail-score');
        sv.textContent = rec.score;
        sv.style.color = tier.color;

        document.getElementById('dstat-wr').textContent = rec.winRate + '%';
        document.getElementById('dstat-pr').textContent = rec.pickRate + '%';
        document.getElementById('dstat-br').textContent = rec.banRate + '%';

        const sb = rec.scoreBreakdown;
        this.setBar('meta',    sb.metaScore);
        this.setBar('synergy', sb.synergyScore);
        this.setBar('counter', sb.counterScore);

        const poolRow = document.getElementById('pool-bar-row');
        if (sb.confidenceBonus > 0) {
            poolRow.style.display = 'flex';
            this.setBar('pool', Math.min(100, sb.confidenceBonus * 5));
        } else {
            poolRow.style.display = 'none';
        }

        const ul = document.getElementById('reasons-list');
        ul.innerHTML = '';
        (rec.explanations || []).forEach(txt => {
            const li = document.createElement('li');
            li.textContent = txt;
            ul.appendChild(li);
        });
    }

    setBar(id, val) {
        const v = Math.round(val);
        document.getElementById(`bar-${id}`).style.width = `${Math.min(100, Math.max(0, val))}%`;
        document.getElementById(`val-${id}`).textContent = v;
    }

    getTier(score) {
        if (score >= 68) return { label: 'S+', cls: 'sp', color: 'var(--sp-c)' };
        if (score >= 60) return { label: 'S',  cls: 's',  color: 'var(--s-c)'  };
        if (score >= 55) return { label: 'A',  cls: 'a',  color: 'var(--a-c)'  };
        if (score >= 50) return { label: 'B',  cls: 'b',  color: 'var(--b-c)'  };
        if (score >= 45) return { label: 'C',  cls: 'c',  color: 'var(--c-c)'  };
        return                   { label: 'D',  cls: 'd',  color: 'var(--d-c)'  };
    }

    // ── Draft slots ───────────────────────────────────────────

    openModal(slot) {
        this.currentSlot = slot;
        const used = new Set([
            ...this.draft.allies.filter(Boolean),
            ...this.draft.enemies.filter(Boolean),
            ...this.draft.banned.filter(Boolean),
        ]);
        const grid = document.getElementById('champ-grid');
        grid.innerHTML = '';
        Object.entries(this.champions).forEach(([id, c]) => {
            const div = document.createElement('div');
            div.className = 'champ-opt' + (used.has(id) ? ' used' : '');
            div.dataset.id = id;
            div.innerHTML = `
                <div class="champ-opt-icon">${this.iconHtml(id, c.name)}</div>
                <div class="champ-opt-name">${c.name}</div>
            `;
            if (!used.has(id)) {
                div.addEventListener('click', () => this.pickChampion(id));
            }
            grid.appendChild(div);
        });
        document.getElementById('modal-search').value = '';
        document.getElementById('modal').style.display = 'flex';
        document.getElementById('modal-search').focus();
    }

    closeModal() {
        document.getElementById('modal').style.display = 'none';
        this.currentSlot = null;
    }

    filterModal(q) {
        const term = q.toLowerCase();
        document.querySelectorAll('.champ-opt').forEach(opt => {
            const name = opt.querySelector('.champ-opt-name').textContent.toLowerCase();
            opt.style.display = name.includes(term) ? '' : 'none';
        });
    }

    pickChampion(id) {
        if (!this.currentSlot) return;
        const type  = this.currentSlot.dataset.type;
        const index = parseInt(this.currentSlot.dataset.index);

        if (type === 'ally')   this.draft.allies[index]  = id;
        if (type === 'enemy')  this.draft.enemies[index] = id;
        if (type === 'ban')    this.draft.banned[index]  = id;

        this.fillSlot(this.currentSlot, id, type);
        this.closeModal();
        this.fetchRecs();
    }

    fillSlot(slot, id, type) {
        const name = this.champions[id]?.name || id;
        slot.classList.remove('empty');
        slot.classList.add('filled');
        slot.innerHTML = `
            <div class="slot-icon-box ${type}">${this.iconHtml(id, name)}</div>
            <div class="slot-name">${name}</div>
            <button class="slot-remove" onclick="app.removeSlot(this)">&times;</button>
        `;
    }

    removeSlot(btn) {
        const slot  = btn.closest('.champ-slot');
        const type  = slot.dataset.type;
        const index = parseInt(slot.dataset.index);

        if (type === 'ally')  this.draft.allies[index]  = null;
        if (type === 'enemy') this.draft.enemies[index] = null;
        if (type === 'ban')   this.draft.banned[index]  = null;

        slot.classList.remove('filled');
        slot.classList.add('empty');
        slot.innerHTML = '<span class="slot-plus">+</span>';
        this.fetchRecs();
    }

    // ── Champion pool ─────────────────────────────────────────

    addToPool(name) {
        if (!name) return;
        const id = Object.keys(this.champions).find(
            k => this.champions[k].name.toLowerCase() === name.toLowerCase()
        );
        if (id && !this.draft.pool.includes(id)) {
            this.draft.pool.push(id);
            this.renderPool();
            this.fetchRecs();
        }
    }

    removeFromPool(id) {
        this.draft.pool = this.draft.pool.filter(x => x !== id);
        this.renderPool();
        this.fetchRecs();
    }

    renderPool() {
        const el = document.getElementById('pool-tags');
        el.innerHTML = '';
        this.draft.pool.forEach(id => {
            const name = this.champions[id]?.name || id;
            const tag = document.createElement('div');
            tag.className = 'pool-tag';
            tag.innerHTML = `${name}<span class="pool-tag-remove" onclick="app.removeFromPool('${id}')">&times;</span>`;
            el.appendChild(tag);
        });
    }
}

const app = new DraftAdvisor();
