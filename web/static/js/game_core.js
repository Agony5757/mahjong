/**
 * Mahjong Game Core — API client, state management, and event handling.
 */

class MahjongGame {
    constructor(canvasId, opts = {}) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.opts = opts;

        this.sessionId = null;
        this.state = null;
        this.mode = 'human_ai';  // 'human_ai' or '4ai'
        this.isMyTurn = false;
        this.selectedTileIdx = null;
        this.pendingRiichi = false;
        this.eventSource = null;
        this.aiSpeed = 1000;  // ms between AI actions
        this._animFrame = null;

        if (window.MahjongRenderer?.setInvalidateHandler) {
            window.MahjongRenderer.setInvalidateHandler(() => this._render());
        }
    }

    // ─── Canvas Sizing ────────────────────────────────────────────────────

    resize() {
        if (window.MahjongRenderer?.resizeCanvasToContainer) {
            window.MahjongRenderer.resizeCanvasToContainer(this.canvas, { maxWidth: 1700, maxHeightRatio: 0.78 });
        }
    }

    // ─── API Calls ─────────────────────────────────────────────────────────

    async _fetch(url, options = {}) {
        const resp = await fetch(url, {
            headers: { 'Content-Type': 'application/json', ...options.headers },
            ...options,
            body: options.body ? JSON.stringify(options.body) : undefined,
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(err.detail || `HTTP ${resp.status}`);
        }
        if (resp.headers.get('content-type')?.includes('application/json')) {
            return resp.json();
        }
        return resp.text();
    }

    async newGame(mode = 'human_ai', aiModel = null, seed = null, maxRound = 1) {
        this.mode = mode;
        const resp = await this._fetch('/api/game/new', {
            method: 'POST',
            body: { mode, ai_model: aiModel, seed, max_round: maxRound }
        });
        this.sessionId = resp.session_id;
        this.state = resp.state;
        this._startSSE();
        this._render();

        // Auto AI turn if not human's turn
        this._scheduleAI();

        return resp;
    }

    async getState() {
        if (!this.sessionId) return null;
        try {
            const state = await this._fetch(`/api/game/${this.sessionId}/state?for_player=0`);
            this.state = state;
            this._render();
            return state;
        } catch (e) {
            console.error('getState failed:', e);
            return null;
        }
    }

    async submitAction(actionIdx) {
        if (!this.sessionId) return;
        try {
            const resp = await this._fetch(`/api/game/${this.sessionId}/action`, {
                method: 'POST',
                body: { player_id: 0, action_idx: actionIdx }
            });
            this.state = resp.state;
            this.selectedTileIdx = null;
            this.pendingRiichi = false;
            this._render();
            this._scheduleAI();
            return resp;
        } catch (e) {
            console.error('submitAction failed:', e);
        }
    }

    // ─── SSE ───────────────────────────────────────────────────────────────

    _startSSE() {
        if (this.eventSource) {
            this.eventSource.close();
        }
        this.eventSource = new EventSource(`/api/game/${this.sessionId}/events`);

        this.eventSource.addEventListener('message', (e) => {
            try {
                const data = JSON.parse(e.data);
                switch (data.type) {
                    case 'snapshot':
                    case 'ai_action':
                    case 'kyoku_start':
                        this.state = data.state;
                        this._render();
                        if (data.type === 'ai_action') {
                            this._showAIMove(data.player, data.action);
                        }
                        break;
                    case 'kyoku_end':
                        this.state = data.state;
                        this._render();
                        this._showKyokuEndToast(data);
                        break;
                    case 'hansou_end':
                        this.state = data.state;
                        this._render();
                        this._onGameOver(data.state, data);
                        break;
                    case 'error':
                        console.error('server error event:', data);
                        break;
                }
            } catch (err) {
                console.error('SSE parse error:', err);
            }
        });

        this.eventSource.onerror = () => {
            console.warn('SSE connection lost, will retry...');
        };
    }

    _stopSSE() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }

    // ─── AI Scheduling ─────────────────────────────────────────────────────

    _scheduleAI() {
        if (this.mode === '4ai') return;  // Server handles AI in 4ai mode
        if (!this.state || this.state.is_over) return;
        const curr = this.state.turn;
        const isHuman = (curr === 0);
        if (!isHuman) {
            // AI turn — wait a bit then the SSE will deliver the result
        }
    }

    // ─── Tile Click Handling ───────────────────────────────────────────────

    _onCanvasClick(e) {
        if (!this.state || this.state.is_over) return;
        if (this.state.turn !== 0) return;  // Not our turn

        const rect = this.canvas.getBoundingClientRect();
        const scaleX = this.canvas.width / rect.width;
        const scaleY = this.canvas.height / rect.height;
        const mx = (e.clientX - rect.left) * scaleX;
        const my = (e.clientY - rect.top) * scaleY;

        const hitBoxes = window.MahjongRenderer.getHandHitBoxes(this.canvas.width, this.canvas.height, this.state);
        for (const hit of hitBoxes) {
            if (mx >= hit.x && mx <= hit.x + hit.w && my >= hit.y && my <= hit.y + hit.h) {
                this._selectTile(hit.index, hit.tile);
                return;
            }
        }
    }

    _selectTile(idx, tileData) {
        if (this.pendingRiichi) {
            // Second click — confirm riichi (submit RIICHI action = index 48)
            this.pendingRiichi = false;
            this.submitAction(48);
            return;
        }

        // Normal discard or riichi step 1
        const actionIdx = this._findDiscardAction(tileData);
        if (actionIdx === null) return;

        // Check if this tile can start riichi
        const validMask = this.state.valid_actions_mask;
        const isRiichi = validMask && validMask[48] === true;
        const isValidDiscard = validMask && validMask[actionIdx] === true;

        if (isRiichi && isValidDiscard) {
            // Submit riichi step 1: same as discard, server detects riichi tile
            this._submitRiichiStep1(actionIdx, tileData, idx);
        } else if (isValidDiscard) {
            this.submitAction(actionIdx);
        }
    }

    _submitRiichiStep1(discardIdx, tileData, tileDisplayIdx) {
        // Riichi is a two-step process:
        // Step 1: Player clicks a riichi-eligible tile → submit discard (same as normal)
        //   The server's MahjongEnvWrapper detects riichi_stage2=True
        // Step 2: Player confirms → submit action 48 (RIICHI)
        //
        // For Step 1, we just submit the discard normally:
        this.pendingRiichi = true;
        this._riichiDiscardIdx = discardIdx;
        this._riichiDisplayIdx = tileDisplayIdx;

        // Visual: highlight selected tile
        this.state.players[0].hand.forEach((t, i) => {
            if (typeof t === 'object') t.selected = (i === tileDisplayIdx);
        });
        this._render();

        // Submit discard (server will detect riichi and enter stage 2)
        this.submitAction(discardIdx);
    }

    _showRiichiConfirm() {
        // This is now handled by click detection (pendingRiichi flag)
        // Kept for the button-based fallback
        const panel = document.getElementById('actionPanel');
        if (!panel) return;
        panel.innerHTML = '';
        panel.className = 'action-panel';

        const confirmBtn = this._makeBtn('确认立直', 'btn-riichi', () => {
            this.pendingRiichi = false;
            this.submitAction(48);
        });
        const cancelBtn = this._makeBtn('取消立直', 'btn-pass', () => {
            this.pendingRiichi = false;
            this.submitAction(this._riichiDiscardIdx);
        });
        panel.appendChild(confirmBtn);
        panel.appendChild(cancelBtn);
    }

    _findDiscardAction(tileData) {
        // Map clicked tile to action index
        // Tiles 0-36 map to basetiles (handling red 5)
        const tileStr = typeof tileData === 'string' ? tileData : (tileData.str || '');
        const isRed = tileData.red_dora || false;

        if (isRed) {
            if (tileStr.startsWith('5m') || tileStr === '5m') return 37;  // red 5m
            if (tileStr.startsWith('5p') || tileStr === '5p') return 38;  // red 5p
            if (tileStr.startsWith('5s') || tileStr === '5s') return 39;  // red 5s
        }

        const basetile = this._strToBasetile(tileStr);
        if (basetile === null) return null;
        return basetile;  // 0-36 for basetiles 0-33
    }

    _strToBasetile(s) {
        s = String(s);
        const ch = s.charAt(s.length - 1);
        const num = parseInt(s);
        if (ch === 'm') return num - 1;
        if (ch === 'p') return num - 1 + 9;
        if (ch === 's') return num - 1 + 18;
        if (ch === 'z') return num - 1 + 27;
        return null;
    }

    // ─── Response Actions ───────────────────────────────────────────────────

    _showResponseActions() {
        const panel = document.getElementById('actionPanel');
        if (!panel || !this.state) return;
        panel.innerHTML = '';

        const validMask = this.state.valid_actions_mask || [];
        const canRon = validMask[49] === true;
        const canPon = validMask[43] === true || validMask[44] === true;
        const canKan = validMask[46] === true;  // Minkan
        const canChi = validMask[37] || validMask[38] || validMask[39] ||
                       validMask[40] || validMask[41] || validMask[42];

        if (canRon) {
            panel.appendChild(this._makeBtn('荣和', 'btn-ron', () => this.submitAction(49)));
        }
        if (canPon) {
            panel.appendChild(this._makeBtn('碰', 'btn-pon', () => this.submitAction(43)));
        }
        if (canKan) {
            panel.appendChild(this._makeBtn('杠', 'btn-kan', () => this.submitAction(46)));
        }
        if (canChi) {
            panel.appendChild(this._makeBtn('吃', 'btn-chi', () => this.submitAction(37)));
        }
        panel.appendChild(this._makeBtn('跳过', 'btn-pass', () => this.submitAction(53)));

        this._updateStatus(`P${this.state.turn} 打出了 ${this._getLastDiscardStr() || '?'}`);
    }

    _getLastDiscardStr() {
        // Find the last discarded tile by the previous player
        const prev = (this.state.turn + 3) % 4;
        const river = this.state.players[prev]?.river || [];
        if (river.length > 0) {
            const last = river[river.length - 1];
            return last.tile?.str || last.str || '?';
        }
        return null;
    }

    // ─── Render Loop ───────────────────────────────────────────────────────

    _render() {
        if (!this.state) return;
        const { renderGame } = window.MahjongRenderer;
        renderGame(this.ctx, this.canvas.width, this.canvas.height, this.state, this.opts);
        this._updateUI();
    }

    _updateUI() {
        this._updateTopBar();
        this._updateActionPanel();

        const statusEl = document.getElementById('statusMsg');
        if (statusEl) {
            if (this.state.is_over) {
                statusEl.textContent = '对局结束';
            } else if (this.state.turn === 0) {
                statusEl.textContent = '你的回合 — 请打出或回应';
            } else {
                statusEl.textContent = `P${this.state.turn} 思考中...`;
            }
        }

        if (this.state.is_over) {
            // Kyoku/hansou end is handled by SSE event handlers (toast + modal).
        }
    }

    _updateTopBar() {
        if (!this.state) return;
        const s = this.state;

        // Round info
        const windNames = ['东', '南', '西', '北'];
        const windKey = (w) => w === 'East' ? 0 : w === 'South' ? 1 : w === 'West' ? 2 : 3;
        document.querySelectorAll('.round-info').forEach(el => {
            el.textContent = `${windNames[windKey(s.game_wind)]}${(s.oya ?? 0) + 1}局`;
        });
        document.querySelectorAll('.honba').forEach(el => {
            el.textContent = `本场 ${s.honba || 0}`;
        });
        document.querySelectorAll('.riichibo').forEach(el => {
            el.textContent = `供托 ${s.kyoutaku || 0}`;
        });
        document.querySelectorAll('.tiles-left').forEach(el => {
            el.textContent = `牌山 ${s.tiles_left ?? '?'}`;
        });

        // Side-panel scoreboard
        const board = document.getElementById('scoreboard');
        if (board) {
            board.innerHTML = s.players.map((p, i) => {
                const cls = ['score-cell'];
                if (p.is_oya) cls.push('oya');
                if (i === s.turn) cls.push('active');
                if (p.riichi) cls.push('riichi');
                if (i === 0) cls.push('human');
                const w = windNames[windKey(p.wind)];
                return `<div class="${cls.join(' ')}">
                    <span class="label">${i === 0 ? '你' : 'P' + i} · ${w}${p.is_oya ? '(亲)' : ''}</span>
                    <span class="pts">${p.score}</span>
                </div>`;
            }).join('');
        }

        // Hansou stepper
        const stepper = document.getElementById('hansouStepper');
        if (stepper && s.hansou) {
            const total = (s.hansou.max_kyoku_index ?? 7) + 1;
            const curr = s.hansou.kyoku_index ?? 0;
            stepper.innerHTML = Array.from({ length: total }, (_, i) => {
                let cls = 'step';
                if (i < curr) cls += ' done';
                else if (i === curr) cls += ' current';
                const wind = windNames[Math.floor(i / 4)];
                const ki = (i % 4) + 1;
                return `<div class="${cls}">${wind}${ki}</div>`;
            }).join('');
        }

        // Legacy score chips (if any present)
        const chips = document.querySelectorAll('.score-chip');
        s.players.forEach((p, i) => {
            if (chips[i]) {
                chips[i].querySelector('.pid').textContent = `${i === 0 ? '你' : 'P' + i} · ${windNames[windKey(p.wind)]}`;
                chips[i].querySelector('.pts').textContent = p.score;
                chips[i].classList.toggle('oya', !!p.is_oya);
                chips[i].classList.toggle('human', i === 0);
                chips[i].classList.toggle('active', i === s.turn);
                chips[i].classList.toggle('riichi', !!p.riichi);
            }
        });

        // Dora
        const doraBar = document.querySelector('.dora-tiles');
        if (doraBar) {
            doraBar.innerHTML = (s.dora || []).map(d =>
                `<span class="mini-dora">${d}</span>`
            ).join('');
        }
    }

    _updateActionPanel() {
        if (!this.state || this.state.is_over || this.state.turn !== 0) return;

        const panel = document.getElementById('actionPanel');
        if (!panel) return;
        panel.innerHTML = '';

        // Riichi stage 2 — waiting for confirm
        if (this.state.riichi_stage2 || this.pendingRiichi) {
            const tileData = this.state.players[0]?.hand?.[this._riichiDisplayIdx ?? 0];
            panel.appendChild(this._makeBtn('确认立直', 'btn-riichi', () => {
                this.pendingRiichi = false;
                this.submitAction(48);
            }));
            panel.appendChild(this._makeBtn('取消立直', 'btn-pass', () => {
                this.pendingRiichi = false;
                if (this._riichiDiscardIdx !== null) {
                    this.submitAction(this._riichiDiscardIdx);
                }
            }));
            this._updateStatus('请确认是否立直');
            return;
        }

        // Self-action phase
        const validMask = this.state.valid_actions_mask || [];
        if (validMask[50]) {
            panel.appendChild(this._makeBtn('自摸', 'btn-tsumo', () => this.submitAction(50)));
        }
        // Discard tiles are handled by canvas click
    }

    _makeBtn(label, cls, onClick) {
        const btn = document.createElement('button');
        btn.className = `action-btn ${cls}`;
        btn.textContent = label;
        btn.onclick = onClick;
        return btn;
    }

    _updateStatus(msg) {
        const el = document.getElementById('statusMsg');
        if (el) el.textContent = msg;
    }

    _showAIMove(player, actionIdx) {
        const actionNames = [
            '摸牌', '摸牌', '摸牌', '摸牌', '摸牌', '摸牌', '摸牌', '摸牌', '摸牌', '摸牌',
            '摸牌', '摸牌', '摸牌', '摸牌', '摸牌', '摸牌', '摸牌', '摸牌', '摸牌', '摸牌',
            '摸牌', '摸牌', '摸牌', '摸牌', '摸牌', '摸牌', '摸牌', '摸牌', '摸牌', '摸牌',
            '摸牌', '摸牌', '摸牌', '摸牌', '摸牌', '摸牌', '摸牌',
            '吃(左)', '吃(中)', '吃(右)',
            '吃+赤(左)', '吃+赤(中)', '吃+赤(右)',
            '碰', '碰+赤', '暗杠', '大明杠', '加杠', '立直', '荣和', '自摸', '通过', '确认立直', '跳过'
        ];
        const name = actionNames[actionIdx] || `动作${actionIdx}`;
        const el = document.getElementById('statusMsg');
        if (el) el.textContent = `P${player} 执行: ${name}`;
    }

    _showResultModal() {
        if (document.getElementById('resultModal')) return;
        const r = this.state.result;
        if (!r) return;

        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.id = 'resultModal';
        overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

        const modal = document.createElement('div');
        modal.className = 'modal';
        const typeNames = {
            'RonAgari': '荣和',
            'TsumoAgari': '自摸',
            'Ryukyouku_9Hai': '九种九牌',
            'Ryukyouku_4Wind': '四风连打',
            'Ryukyouku_4Riichi': '四立直',
            'Ryukyouku_4Kan': '四杠子',
            'Ryukyouku_Notile': '流局',
        };
        const losers = Array.isArray(r.loser) ? r.loser : (r.loser != null ? [r.loser] : []);
        modal.innerHTML = `
            <h2>${typeNames[r.type] || r.type || '对局结束'}</h2>
            <div class="result-scores">
                ${(r.scores || []).map((s, i) => `
                    <div class="result-row ${(r.winner || []).includes(i) ? 'winner' : ''}">
                        <span>P${i}${losers.includes(i) ? ' (放铳)' : ''}</span>
                        <span>${s}点</span>
                    </div>
                `).join('')}
            </div>
            ${r.winner?.length ? `<p>胜利: P${r.winner.join(', P')}</p>` : ''}
            <button class="action-btn btn-confirm mt-16" onclick="document.getElementById('resultModal').remove()">确定</button>
        `;
        overlay.appendChild(modal);
        document.body.appendChild(overlay);
    }

    _showKyokuEndToast(data) {
        const r = data.result || {};
        const typeNames = {
            'RonAgari': '荣和', 'TsumoAgari': '自摸',
            'Ryukyouku_Notile': '流局', 'Ryukyouku_9Hai': '九种九牌',
            'Ryukyouku_4Wind': '四风连打', 'Ryukyouku_4Riichi': '四立直',
            'Ryukyouku_4Kan': '四杠子',
        };
        const t = typeNames[r.type] || r.type || '局结束';
        const winners = (r.winner || []).map(i => `P${i}`).join(',');
        const msg = `${data.round_label || ''} ${t}${winners ? ' 胜者:' + winners : ''}`;
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.textContent = msg;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3500);
    }

    _onGameOver(state, data) {
        if (document.getElementById('resultModal')) return;
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.id = 'resultModal';
        overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
        const modal = document.createElement('div');
        modal.className = 'modal';
        const finalScores = (data && data.final_scores) || (state.players || []).map(p => p.score);
        const ranked = finalScores.map((s, i) => ({ i, s })).sort((a, b) => b.s - a.s);
        modal.innerHTML = `
            <h2>半庄结束</h2>
            <div class="result-scores">
                ${ranked.map((r, rank) => `
                    <div class="result-row ${rank === 0 ? 'winner' : ''}">
                        <span>${rank + 1}位 · P${r.i}${r.i === 0 ? '(你)' : ''}</span>
                        <span>${r.s}点</span>
                    </div>
                `).join('')}
            </div>
            <button class="action-btn btn-confirm mt-16" onclick="document.getElementById('resultModal').remove()">关闭</button>
        `;
        overlay.appendChild(modal);
        document.body.appendChild(overlay);
    }

    // ─── Lifecycle ─────────────────────────────────────────────────────────

    destroy() {
        this._stopSSE();
        if (this._animFrame) cancelAnimationFrame(this._animFrame);
    }
}

// ─── Export ─────────────────────────────────────────────────────────────────

window.MahjongGame = MahjongGame;
