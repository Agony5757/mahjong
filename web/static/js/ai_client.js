/**
 * AI Battle client — watches a 4-AI game with speed controls and multi-view.
 */
class AIBattleClient {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.sessionId = null;
        this.state = null;
        this.speed = 1.0;  // 0.5x, 1x, 2x
        this.isPaused = false;
        this.followPlayer = -1;  // -1 = all visible, 0-3 = follow specific player
        this.eventSource = null;
    }

    resize() {
        const W = Math.min(this.canvas.parentElement.clientWidth - 16, 900);
        const H = Math.min(W * 0.65, 600);
        this.canvas.width = W;
        this.canvas.height = H;
    }

    async _fetch(url, options = {}) {
        const resp = await fetch(url, {
            headers: { 'Content-Type': 'application/json', ...options.headers },
            ...options,
            body: options.body ? JSON.stringify(options.body) : undefined,
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
        return resp.json();
    }

    async startGame(seed = null) {
        const resp = await this._fetch('/api/game/new', {
            method: 'POST',
            body: { mode: '4ai', ai_model: null, seed }
        });
        this.sessionId = resp.session_id;
        this.state = resp.state;
        this._render();
        this._startSSE();
    }

    _startSSE() {
        if (this.eventSource) this.eventSource.close();
        this.eventSource = new EventSource(`/api/game/${this.sessionId}/events`);

        this.eventSource.addEventListener('message', (e) => {
            try {
                const data = JSON.parse(e.data);
                if (data.type === 'ai_action') {
                    this.state = data.state;
                    this._render();
                    this._appendLog(`P${data.player}: ${this._actionName(data.action)}`);
                } else if (data.type === 'game_over') {
                    this.state = data.state;
                    this._render();
                    this._appendLog('=== 对局结束 ===');
                    this._showResult();
                }
            } catch (err) {
                console.error('SSE error:', err);
            }
        });
    }

    async getState() {
        const s = await this._fetch(`/api/game/${this.sessionId}/state`);
        this.state = s;
        this._render();
        return s;
    }

    _render() {
        if (!this.state) return;
        const { renderGame } = window.MahjongRenderer;

        if (this.followPlayer >= 0) {
            // Render from followed player's perspective (hide others' hands)
            const state = JSON.parse(JSON.stringify(this.state));
            for (let i = 0; i < 4; i++) {
                if (i !== this.followPlayer) {
                    state.players[i].hand = [{ count: state.players[i].hand?.length || 0 }];
                }
            }
            renderGame(this.ctx, this.canvas.width, this.canvas.height, state);
        } else {
            renderGame(this.ctx, this.canvas.width, this.canvas.height, this.state);
        }

        this._updateTopBar();
    }

    _updateTopBar() {
        if (!this.state) return;
        const s = this.state;
        const windNames = ['东', '南', '西', '北'];
        document.querySelectorAll('.round-info').forEach(el => {
            el.textContent = `${windNames[0]}一局`;
        });
        document.querySelectorAll('.honba').forEach(el => {
            el.textContent = `本场${s.honba}`;
        });
        const chips = document.querySelectorAll('.score-chip');
        s.players.forEach((p, i) => {
            if (chips[i]) {
                chips[i].querySelector('.pts').textContent = p.score;
                chips[i].classList.toggle('oya', !!p.is_oya);
            }
        });
    }

    _appendLog(msg) {
        const log = document.getElementById('logContent');
        if (!log) return;
        const entry = document.createElement('div');
        entry.className = 'log-entry';
        const now = new Date();
        entry.innerHTML = `<span class="text-dim">${now.toLocaleTimeString()}</span> ${msg}`;
        log.appendChild(entry);
        log.scrollTop = log.scrollHeight;
    }

    _actionName(idx) {
        const names = [
            '摸牌', null, null, null, null, null, null, null, null, null,
            null, null, null, null, null, null, null, null, null, null,
            null, null, null, null, null, null, null, null, null, null,
            null, null, null, null, null, null,
            '吃左', '吃中', '吃右',
            '吃赤左', '吃赤中', '吃赤右',
            '碰', '碰赤', '暗杠', '大明杠', '加杠', '立直', '荣和', '自摸', '通过', '确认立直', '跳过'
        ];
        return names[idx] || `动作${idx}`;
    }

    _showResult() {
        if (document.getElementById('resultModal')) return;
        const r = this.state.result;
        if (!r) return;
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.id = 'resultModal';
        overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
        overlay.innerHTML = `
            <div class="modal">
                <h2>对局结束</h2>
                <div class="result-scores">
                    ${r.scores.map((s, i) => `
                        <div class="result-row ${r.winner?.includes(i) ? 'winner' : ''}">
                            <span>AI-${i}${i === r.loser ? ' ⚠️' : ''}</span>
                            <span>${s}点</span>
                        </div>
                    `).join('')}
                </div>
                ${r.winner?.length ? `<p>胜: ${r.winner.map(w => 'AI-' + w).join(', ')}</p>` : ''}
                <button class="action-btn btn-confirm mt-16" onclick="document.getElementById('resultModal').remove()">确定</button>
            </div>
        `;
        document.body.appendChild(overlay);
    }

    setSpeed(speed) {
        this.speed = speed;
    }

    togglePause() {
        this.isPaused = !this.isPaused;
    }

    follow(playerId) {
        this.followPlayer = playerId;
        this._render();
    }

    showAll() {
        this.followPlayer = -1;
        this._render();
    }

    destroy() {
        if (this.eventSource) this.eventSource.close();
    }
}

// Export
window.AIBattleClient = AIBattleClient;
