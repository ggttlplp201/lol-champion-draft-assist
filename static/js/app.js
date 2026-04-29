class DraftAdvisor {
    constructor() {
        this.champions = {};
        this.draftState = {
            allies: [],
            enemies: [],
            banned: [],
            championPool: []
        };
        this.currentTab = 'overall';
        this.currentSlot = null;
        this.lastRecommendationData = null;

        this.init();
    }

    async init() {
        await this.loadChampions();
        this.setupEventListeners();
        this.updateRecommendations();
    }

    async loadChampions() {
        try {
            const response = await fetch('/api/champions');
            this.champions = await response.json();
        } catch (error) {
            console.error('Failed to load champions:', error);
        }
    }

    setupEventListeners() {
        document.querySelectorAll('.tab-button').forEach(button => {
            button.addEventListener('click', (e) => {
                this.switchTab(e.target.dataset.tab);
            });
        });

        document.querySelectorAll('.champion-slot').forEach(slot => {
            slot.addEventListener('click', () => {
                if (slot.classList.contains('empty')) {
                    this.openChampionModal(slot);
                }
            });
        });

        const poolInput = document.querySelector('.champion-pool-input');
        poolInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.addToChampionPool(e.target.value.trim());
                e.target.value = '';
            }
        });

        document.getElementById('close-modal').addEventListener('click', () => {
            this.closeChampionModal();
        });

        document.getElementById('champion-modal').addEventListener('click', (e) => {
            if (e.target.id === 'champion-modal') {
                this.closeChampionModal();
            }
        });

        document.getElementById('champion-search').addEventListener('input', (e) => {
            this.filterChampions(e.target.value);
        });

        document.addEventListener('click', (e) => {
            const card = e.target.closest('.recommendation-card');
            if (card) this.selectRecommendation(card);
        });
    }

    switchTab(tab) {
        this.currentTab = tab;
        document.querySelectorAll('.tab-button').forEach(button => {
            button.classList.toggle('active', button.dataset.tab === tab);
        });
        if (this.lastRecommendationData) {
            this.displayRecommendations(this.lastRecommendationData);
        } else {
            this.updateRecommendations();
        }
    }

    openChampionModal(slot) {
        this.currentSlot = slot;
        document.getElementById('champion-modal').style.display = 'flex';
        this.populateChampionGrid();
        const search = document.getElementById('champion-search');
        search.value = '';
        search.focus();
    }

    closeChampionModal() {
        document.getElementById('champion-modal').style.display = 'none';
        this.currentSlot = null;
    }

    populateChampionGrid() {
        const grid = document.getElementById('champion-grid');
        grid.innerHTML = '';

        const used = new Set([
            ...this.draftState.allies.filter(Boolean),
            ...this.draftState.enemies.filter(Boolean),
            ...this.draftState.banned.filter(Boolean),
        ]);

        Object.entries(this.champions).forEach(([id, champion]) => {
            const option = document.createElement('div');
            option.className = 'champion-option' + (used.has(id) ? ' disabled' : '');
            option.dataset.championId = id;
            option.innerHTML = `
                <div class="champ-icon">${champion.name.charAt(0)}</div>
                <span>${champion.name}</span>
            `;
            if (!used.has(id)) {
                option.addEventListener('click', () => this.selectChampion(id));
            }
            grid.appendChild(option);
        });
    }

    filterChampions(searchTerm) {
        const term = searchTerm.toLowerCase();
        document.querySelectorAll('.champion-option').forEach(option => {
            const name = option.querySelector('span').textContent.toLowerCase();
            option.style.display = name.includes(term) ? '' : 'none';
        });
    }

    selectChampion(championId) {
        if (!this.currentSlot) return;

        const slotType = this.currentSlot.dataset.type;
        const slotIndex = parseInt(this.currentSlot.dataset.index);

        if (slotType === 'ally') this.draftState.allies[slotIndex] = championId;
        else if (slotType === 'enemy') this.draftState.enemies[slotIndex] = championId;
        else if (slotType === 'ban') this.draftState.banned[slotIndex] = championId;

        this.updateChampionSlot(this.currentSlot, championId, slotType);
        this.closeChampionModal();
        this.updateRecommendations();
    }

    updateChampionSlot(slot, championId, slotType) {
        const champion = this.champions[championId];
        if (!champion) return;

        slot.classList.remove('empty');
        slot.classList.add('filled');
        slot.dataset.championId = championId;

        const colorClass = slotType === 'ally' ? 'ally' : slotType === 'enemy' ? 'enemy' : 'ban';
        slot.innerHTML = `
            <div class="slot-icon ${colorClass}">${champion.name.charAt(0)}</div>
            <div class="slot-label">${champion.name}</div>
            <button class="remove-champion" onclick="draftAdvisor.removeChampion(this)">&times;</button>
        `;
    }

    removeChampion(button) {
        const slot = button.closest('.champion-slot');
        const slotType = slot.dataset.type;
        const slotIndex = parseInt(slot.dataset.index);

        if (slotType === 'ally') this.draftState.allies[slotIndex] = null;
        else if (slotType === 'enemy') this.draftState.enemies[slotIndex] = null;
        else if (slotType === 'ban') this.draftState.banned[slotIndex] = null;

        slot.classList.remove('filled');
        slot.classList.add('empty');
        slot.innerHTML = '<span class="plus-icon">+</span>';
        delete slot.dataset.championId;

        this.updateRecommendations();
    }

    addToChampionPool(championName) {
        if (!championName) return;
        const championId = Object.keys(this.champions).find(id =>
            this.champions[id].name.toLowerCase() === championName.toLowerCase()
        );
        if (championId && !this.draftState.championPool.includes(championId)) {
            this.draftState.championPool.push(championId);
            this.updateChampionPoolDisplay();
            this.updateRecommendations();
        }
    }

    updateChampionPoolDisplay() {
        const container = document.getElementById('champion-pool');
        container.innerHTML = '';
        this.draftState.championPool.forEach(championId => {
            const champion = this.champions[championId];
            if (!champion) return;
            const tag = document.createElement('div');
            tag.className = 'pool-champion';
            tag.innerHTML = `
                ${champion.name}
                <span class="remove" onclick="draftAdvisor.removeFromChampionPool('${championId}')">&times;</span>
            `;
            container.appendChild(tag);
        });
    }

    removeFromChampionPool(championId) {
        this.draftState.championPool = this.draftState.championPool.filter(id => id !== championId);
        this.updateChampionPoolDisplay();
        this.updateRecommendations();
    }

    async updateRecommendations() {
        const container = document.getElementById('recommendations');
        container.innerHTML = '<div class="loading"><div class="spinner"></div><span>Analyzing draft...</span></div>';

        try {
            const cleanDraftState = {
                allies: this.draftState.allies.filter(Boolean),
                enemies: this.draftState.enemies.filter(Boolean),
                banned: this.draftState.banned.filter(Boolean),
                championPool: this.draftState.championPool,
                patch: '14.3'
            };

            const response = await fetch('/api/recommendations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(cleanDraftState)
            });

            const data = await response.json();
            if (data.error) throw new Error(data.error);

            this.lastRecommendationData = data;
            this.displayRecommendations(data);
        } catch (error) {
            console.error('Failed to get recommendations:', error);
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">!</div>
                    <h3>Error loading recommendations</h3>
                    <p>Please try again.</p>
                </div>
            `;
        }
    }

    displayRecommendations(data) {
        const container = document.getElementById('recommendations');
        const recommendations = this.currentTab === 'pool'
            ? data.championPoolRecommendations
            : data.overallRecommendations;

        if (!recommendations || recommendations.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">?</div>
                    <h3>${this.currentTab === 'pool' ? 'No Pool Picks' : 'Ready to Draft'}</h3>
                    <p>${this.currentTab === 'pool'
                        ? 'Add champions to your pool below.'
                        : 'Add ally and enemy picks to get personalized recommendations.'}</p>
                </div>
            `;
            return;
        }

        container.innerHTML = '';
        recommendations.forEach((rec, index) => {
            const card = document.createElement('div');
            card.className = 'recommendation-card';
            card.dataset.championId = rec.championId;
            card.dataset.recIndex = index;
            card.dataset.recData = JSON.stringify(rec);

            const scoreColor = this.getScoreColor(rec.score);
            const meta = rec.scoreBreakdown.metaScore;
            const synergy = rec.scoreBreakdown.synergyScore;
            const counter = rec.scoreBreakdown.counterScore;

            card.innerHTML = `
                <div class="rec-rank">${index + 1}</div>
                <div class="rec-avatar">${rec.championName.charAt(0)}</div>
                <div class="rec-body">
                    <div class="rec-header">
                        <span class="rec-name">${rec.championName}</span>
                        <span class="rec-score" style="color:${scoreColor}">${rec.score}</span>
                    </div>
                    <div class="rec-mini-bars">
                        <div class="mini-bar-row">
                            <span class="mini-label">Meta</span>
                            <div class="mini-bar"><div class="mini-fill meta" style="width:${meta}%"></div></div>
                        </div>
                        <div class="mini-bar-row">
                            <span class="mini-label">Syn</span>
                            <div class="mini-bar"><div class="mini-fill synergy" style="width:${synergy}%"></div></div>
                        </div>
                        <div class="mini-bar-row">
                            <span class="mini-label">Ctr</span>
                            <div class="mini-bar"><div class="mini-fill counter" style="width:${counter}%"></div></div>
                        </div>
                    </div>
                </div>
            `;

            container.appendChild(card);
        });

        const firstCard = container.querySelector('.recommendation-card');
        if (firstCard) this.selectRecommendation(firstCard);
    }

    selectRecommendation(card) {
        document.querySelectorAll('.recommendation-card').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');

        const rec = JSON.parse(card.dataset.recData);
        this.updateChampionDetail(rec);
    }

    updateChampionDetail(rec) {
        const champion = this.champions[rec.championId];
        const name = champion ? champion.name : rec.championName;

        document.getElementById('detail-champion-name').textContent = name;
        const detailScore = document.getElementById('detail-total-score');
        if (detailScore) {
            detailScore.textContent = rec.score;
            detailScore.style.color = this.getScoreColor(rec.score);
        }

        const avatar = document.getElementById('detail-champion-avatar');
        avatar.textContent = name.charAt(0);

        const sb = rec.scoreBreakdown;
        this.updateScoreBar('meta', sb.metaScore);
        this.updateScoreBar('synergy', sb.synergyScore);
        this.updateScoreBar('counter', sb.counterScore);

        const masteryBar = document.getElementById('mastery-bar');
        if (sb.confidenceBonus > 0) {
            masteryBar.style.display = 'block';
            this.updateScoreBar('mastery', Math.min(100, sb.confidenceBonus * 5));
        } else {
            masteryBar.style.display = 'none';
        }

        // Use actual explanations from the API
        const explanationsList = document.getElementById('positive-explanations');
        explanationsList.innerHTML = '';
        (rec.explanations || []).forEach(text => {
            const li = document.createElement('li');
            li.textContent = text;
            explanationsList.appendChild(li);
        });
    }

    updateScoreBar(type, score) {
        const scoreEl = document.getElementById(`${type}-score`);
        const fillEl = document.getElementById(`${type}-progress`);
        if (scoreEl && fillEl) {
            scoreEl.textContent = Math.round(score);
            fillEl.style.width = `${Math.min(100, Math.max(0, score))}%`;
        }
    }

    getScoreColor(score) {
        if (score >= 70) return '#22c55e';
        if (score >= 55) return '#f59e0b';
        return '#ef4444';
    }
}

let draftAdvisor;
document.addEventListener('DOMContentLoaded', () => {
    draftAdvisor = new DraftAdvisor();
});
