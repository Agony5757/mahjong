/**
 * AI Battle client — drives a 4-AI hansou via SSE and renders the new layout
 * with a sidepanel scoreboard + hansou progress stepper.
 */
(function () {
    const WIND_NAMES = ['东', '南', '西', '北'];
    const WIND_KEY = { East: 0, South: 1, West: 2, North: 3 };

    function actionLabel(idx) {
        if (idx >= 0 && idx < 34) {
            return `弃 ${tileLabel(idx)}`;
        }
        if (idx >= 34 && idx <= 36) return `弃 红5${'mps'[idx - 34]}`;
        const map = {
            37: '吃左', 38: '吃中', 39: '吃右',
            40: '吃赤左', 41: '吃赤中', 42: '吃赤右',
            43: '碰', 44: '碰赤',
            45: '暗杠', 46: '大明杠', 47: '加杠',
            48: '立直', 49: '荣和', 50: '自摸',
            51: '九种', 52: '取消立直', 53: '通过',
        };
        return map[idx] || `动作${idx}`;
    }

    function tileLabel(bt) {
        if (bt < 9) return `${bt + 1}m`;
        if (bt < 18) return `${bt - 9 + 1}p`;
        if (bt < 27) return `${bt - 18 + 1}s`;
        return ['1z', '2z', '3z', '4z', '5z', '6z', '7z'][bt - 27];
    }

    class AIBattleClient {
        constructor(canvasId) {
            this.canvas = document.getElementById(canvasId);
            this.ctx = this.canvas.getContext('2d');
            this.sessionId = null;
            this.state = null;
            this.followPlayer = -1;
            this.eventSource = null;
            this.maxRound = 1;
            this.kyokuLog = [];
            this.startScores = [25000, 25000, 25000, 25000];
            this.lastDelta = [0, 0, 0, 0];
            if (window.MahjongRenderer?.setInvalidateHandler) {
                window.MahjongRenderer.setInvalidateHandler(() => this._render());
            }
        }

        resize() {
            window.MahjongRenderer?.resizeCanvasToContainer(this.canvas, {
                maxWidth: 2200, maxHeightRatio: 1.10,
            });
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

        async startGame({ seed = null, maxRound = 1, aiModels = null } = {}) {
            this.maxRound = maxRound;
            const body = { mode: '4ai', ai_model: null, seed, max_round: maxRound };
            if (aiModels) body.ai_models = aiModels;
            const resp = await this._fetch('/api/game/new', {
                method: 'POST',
                body,
            });
            this.sessionId = resp.session_id;
            this.state = resp.state;
            this.kyokuLog = [];
            this.logUrl = resp.log_url || null;
            if (this.logUrl) {
                console.info('[mahjong] verbose log →', this.logUrl, '(server path:', resp.log_path, ')');
                let el = document.getElementById('verboseLogLink');
                if (!el) {
                    el = document.createElement('a');
                    el.id = 'verboseLogLink';
                    el.textContent = '⬇ 下载本局日志';
                    el.style.cssText = 'position:fixed;right:14px;bottom:12px;z-index:30;background:#1a2638;color:#cfd8e7;padding:6px 12px;border-radius:6px;font-size:12px;text-decoration:none;border:1px solid #3a4a66;';
                    document.body.appendChild(el);
                }
                el.href = this.logUrl;
                el.download = '';
            }
            this._render();
            this._renderHansouStepper();
            this._startSSE();
        }

        async setSpeed(delayMs) {
            if (!this.sessionId) return;
            try {
                await this._fetch(`/api/game/${this.sessionId}/speed`, {
                    method: 'POST',
                    body: { delay_ms: delayMs },
                });
            } catch (_) { /* ignore */ }
        }

        _startSSE() {
            if (this.eventSource) this.eventSource.close();
            this.eventSource = new EventSource(`/api/game/${this.sessionId}/events`);
            this.eventSource.addEventListener('message', (e) => {
                let data;
                try { data = JSON.parse(e.data); } catch { return; }
                this._onEvent(data);
            });
            this.eventSource.addEventListener('error', () => {});
        }

        _onEvent(data) {
            switch (data.type) {
                case 'snapshot':
                case 'ai_action':
                    if (data.state) this.state = data.state;
                    if (data.type === 'ai_action') {
                        this._appendLog(`P${data.player}: ${actionLabel(data.action)}`);
                    }
                    this._render();
                    break;
                case 'kyoku_start':
                    if (data.state) this.state = data.state;
                    this._appendLog(`=== ${data.kyoku?.round_label || ''} 开始 (${data.kyoku?.honba ?? 0}本场) ===`);
                    this._render();
                    break;
                case 'kyoku_end': {
                    if (data.state) this.state = data.state;
                    const r = data.record;
                    if (r) {
                        this.kyokuLog.push(r);
                        const delta = r.scores_out.map((s, i) => s - (r.scores_in[i] || 0));
                        this.lastDelta = delta;
                        const w = r.winner?.length ? `胜: ${r.winner.map(x => 'P' + x).join(',')}` : '';
                        this._appendLog(`◆ 局结束 (${r.result_type}) ${w} delta=${delta.join('/')}`);
                    }
                    this._render();
                    break;
                }
                case 'hansou_end':
                    if (data.state) this.state = data.state;
                    this._appendLog('=== 半庄结束 ===');
                    this._render();
                    this._showHansouSummary(data.final_scores || []);
                    break;
                case 'error':
                    this._appendLog(`⚠ ${data.message || ''}`);
                    break;
            }
        }

        _render() {
            if (!this.state) return;
            const { renderGame } = window.MahjongRenderer;
            let renderState = this.state;
            if (this.followPlayer >= 0) {
                renderState = JSON.parse(JSON.stringify(this.state));
                for (let i = 0; i < 4; i++) {
                    if (i !== this.followPlayer) {
                        renderState.players[i].hand = [{ count: this.state.players[i].hand?.length || 0 }];
                    }
                }
            }
            renderGame(this.ctx, this.canvas.width, this.canvas.height, renderState);
            this._renderTopBar();
            this._renderScoreboard();
            this._renderHansouStepper();
        }

        _renderTopBar() {
            const s = this.state;
            const winds = WIND_NAMES;
            const setText = (sel, txt) => {
                const el = document.querySelector(sel);
                if (el) el.textContent = txt;
            };
            const wind = winds[WIND_KEY[s.game_wind] ?? 0];
            // Round label uses hansou snapshot when available (more accurate over multi-kyoku).
            const round = s.hansou?.round_label || `${wind}${(s.oya ?? 0) + 1}局`;
            setText('.round-info', round);
            setText('.honba', `本场 ${s.honba}`);
            setText('.riichibo', `供托 ${s.kyoutaku || 0}`);
            setText('.tiles-left', `牌山 ${s.tiles_left ?? '?'}`);
            const doraBar = document.querySelector('.dora-tiles');
            if (doraBar) {
                doraBar.innerHTML = (s.dora || []).map(d => `<span class="mini-dora">${d}</span>`).join('');
            }
        }

        _renderScoreboard() {
            const board = document.getElementById('scoreboard');
            if (!board) return;
            const s = this.state;
            board.innerHTML = s.players.map((p, i) => {
                const cls = ['score-cell'];
                if (p.is_oya) cls.push('oya');
                if (i === s.turn) cls.push('active');
                if (p.riichi) cls.push('riichi');
                const w = WIND_NAMES[WIND_KEY[p.wind] ?? 0];
                const delta = this.lastDelta[i] || 0;
                const deltaStr = delta === 0 ? '' :
                    (delta > 0 ? `+${delta}` : `${delta}`);
                return `<div class="${cls.join(' ')}">
                    <span class="label">P${i} · ${w}${p.is_oya ? '(亲)' : ''}</span>
                    <span class="pts">${p.score}</span>
                    <span class="delta">${deltaStr}</span>
                </div>`;
            }).join('');
        }

        _renderHansouStepper() {
            const stepper = document.getElementById('hansouStepper');
            if (!stepper) return;
            const max = this.maxRound === 0 ? 4 : this.maxRound === 2 ? 16 : 8;
            const currIdx = this.state?.hansou?.kyoku_index ?? 0;
            const log = this.state?.hansou?.log || this.kyokuLog;
            const html = [];
            for (let i = 0; i < max; i++) {
                const wind = WIND_NAMES[Math.floor(i / 4)];
                const k = (i % 4) + 1;
                let cls = 'step';
                if (i < log.length) cls += ' done';
                else if (i === currIdx) cls += ' current';
                html.push(`<div class="${cls}">${wind}${k}</div>`);
            }
            stepper.innerHTML = html.join('');
        }

        _appendLog(msg) {
            const log = document.getElementById('logContent');
            if (!log) return;
            const entry = document.createElement('div');
            entry.className = 'log-entry';
            entry.textContent = msg;
            log.appendChild(entry);
            log.scrollTop = log.scrollHeight;
        }

        _showHansouSummary(finalScores) {
            if (document.getElementById('hansouModal')) return;
            const overlay = document.createElement('div');
            overlay.className = 'modal-overlay';
            overlay.id = 'hansouModal';
            overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
            const ranked = finalScores.map((s, i) => ({ pid: i, score: s }))
                .sort((a, b) => b.score - a.score);
            const rows = ranked.map((r, idx) => `
                <div class="result-row ${idx === 0 ? 'winner' : ''}">
                    <span>第${idx + 1}名 · P${r.pid}</span>
                    <span>${r.score}</span>
                </div>`).join('');
            const kyokuRows = this.kyokuLog.map(k => `
                <div class="result-row" style="font-size:12px">
                    <span>${k.index !== undefined ? '局' + (k.index + 1) : ''} (${k.result_type})</span>
                    <span>${k.scores_out.join(' / ')}</span>
                </div>`).join('');
            overlay.innerHTML = `
                <div class="modal">
                    <h2>半庄结束</h2>
                    <div class="result-scores">${rows}</div>
                    <details class="mt-16">
                        <summary>逐局回顾</summary>
                        <div class="result-scores mt-8">${kyokuRows}</div>
                    </details>
                    <button class="action-btn btn-confirm mt-16"
                        onclick="document.getElementById('hansouModal').remove()">确定</button>
                </div>`;
            document.body.appendChild(overlay);
        }

        follow(playerId) {
            this.followPlayer = playerId;
            this._render();
        }

        destroy() {
            if (this.eventSource) this.eventSource.close();
        }
    }

    window.AIBattleClient = AIBattleClient;
})();
