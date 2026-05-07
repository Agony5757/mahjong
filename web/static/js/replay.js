/**
 * Paipu Replay Client — drives /api/replay/steps and renders snapshots.
 */
(function () {
    const WIND_NAMES = ['东', '南', '西', '北'];
    const WIND_KEY = { East: 0, South: 1, West: 2, North: 3 };

    const EVENT_LABELS = {
        init: '开局',
        draw: '摸牌',
        discard: '弃牌',
        call: '鸣牌',
        riichi: '立直',
        agari: '和了',
        ryuukyoku: '流局',
        kyoku_end: '局结束',
        hansou_end: '半庄结束',
        dora: '翻 DORA',
        bye: '掉线',
    };

    class ReplayClient {
        constructor(canvasId) {
            this.canvas = document.getElementById(canvasId);
            this.ctx = this.canvas.getContext('2d');
            this.steps = [];
            this.currentStep = -1;
            this.isPlaying = false;
            this.playInterval = null;
            this.speed = 600;
            this.kyokuIndices = [];
            if (window.MahjongRenderer?.setInvalidateHandler) {
                window.MahjongRenderer.setInvalidateHandler(() => this._renderStep());
            }
        }

        resize() {
            window.MahjongRenderer?.resizeCanvasToContainer(this.canvas, {
                maxWidth: 2200, maxHeightRatio: 1.10,
            });
        }

        async listBuiltinPaipu() {
            try {
                const r = await fetch('/api/replay/builtin').then(x => x.json());
                return r.paipu_files || [];
            } catch { return []; }
        }

        async loadBuiltinPaipu(filename) {
            const xml = await fetch(`/api/replay/builtin/${filename}`).then(r => r.text());
            return this.loadFromXML(xml);
        }

        async loadFromXML(xmlContent) {
            const resp = await fetch('/api/replay/steps', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ xml_content: xmlContent }),
            });
            if (!resp.ok) {
                throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
            }
            const data = await resp.json();
            this.steps = data.steps || [];
            this.kyokuIndices = data.kyoku_indices || [];
            this.currentStep = this.steps.length > 0 ? 0 : -1;
            this._renderStep();
            this._renderKyokuList();
            return this.steps.length;
        }

        stepForward() {
            if (this.currentStep >= this.steps.length - 1) return;
            this.currentStep++;
            this._renderStep();
        }

        stepBackward() {
            if (this.currentStep <= 0) return;
            this.currentStep--;
            this._renderStep();
        }

        seekTo(step) {
            this.currentStep = Math.max(0, Math.min(step, this.steps.length - 1));
            this._renderStep();
        }

        seekToKyoku(kyokuIndex) {
            const idx = this.steps.findIndex(s => s.kyoku_index === kyokuIndex && s.event_type === 'init');
            if (idx >= 0) this.seekTo(idx);
        }

        play() {
            if (this.isPlaying) { this.pause(); return; }
            this.isPlaying = true;
            const btn = document.getElementById('btnPlay');
            if (btn) btn.textContent = '⏸ 暂停';
            const tick = () => {
                if (!this.isPlaying) return;
                if (this.currentStep >= this.steps.length - 1) { this.pause(); return; }
                this.stepForward();
                this.playInterval = setTimeout(tick, this.speed);
            };
            tick();
        }

        pause() {
            this.isPlaying = false;
            if (this.playInterval) clearTimeout(this.playInterval);
            const btn = document.getElementById('btnPlay');
            if (btn) btn.textContent = '▶ 播放';
        }

        setSpeed(ms) {
            this.speed = ms;
            if (this.isPlaying) { this.pause(); this.play(); }
        }

        _renderStep() {
            if (this.currentStep < 0 || !this.steps.length) {
                window.MahjongRenderer?.renderSplash(
                    this.ctx, this.canvas.width, this.canvas.height,
                    '牌谱复现', '上传天凤 XML 牌谱或加载内置示例'
                );
                return;
            }
            const step = this.steps[this.currentStep];
            const state = step.state;
            window.MahjongRenderer.renderReplay(
                this.ctx, this.canvas.width, this.canvas.height, state
            );
            this._updateTimeline();
            this._updateInfoPanel(step);
            this._updateTopBar(state);
            this._renderScoreboard(state);
            this._renderKyokuList();
        }

        _updateTimeline() {
            const slider = document.getElementById('timelineSlider');
            const progress = document.getElementById('timelineProgress');
            if (slider) {
                slider.max = Math.max(1, this.steps.length - 1);
                slider.value = this.currentStep;
            }
            if (progress) {
                const pct = this.steps.length > 1
                    ? (this.currentStep / (this.steps.length - 1)) * 100 : 0;
                progress.style.width = pct + '%';
            }
            const counter = document.getElementById('stepCounter');
            if (counter) counter.textContent = `${this.currentStep + 1} / ${this.steps.length}`;
        }

        _updateInfoPanel(step) {
            const el = document.getElementById('stepInfo');
            if (!el) return;
            const label = EVENT_LABELS[step.event_type] || step.event_type;
            const player = step.player >= 0 ? `P${step.player}` : '';
            el.innerHTML = `
                <div><strong>事件 ${this.currentStep + 1}/${this.steps.length}</strong></div>
                <div class="text-dim" style="font-size:12px; margin-top:4px">${label}</div>
                <div style="margin-top:6px">${player} ${step.description || ''}</div>
            `;
        }

        _updateTopBar(state) {
            if (!state) return;
            const setText = (sel, t) => {
                const el = document.querySelector(sel);
                if (el) el.textContent = t;
            };
            const wind = WIND_NAMES[WIND_KEY[state.game_wind] ?? 0];
            setText('.round-info', `${wind}${(state.oya ?? 0) + 1}局`);
            setText('.honba', `本场 ${state.honba || 0}`);
            setText('.riichibo', `供托 ${state.kyoutaku || 0}`);
            setText('.tiles-left', `牌山 ${state.tiles_left ?? '?'}`);
            const doraBar = document.querySelector('.dora-tiles');
            if (doraBar) {
                doraBar.innerHTML = (state.dora || []).map(d =>
                    `<span class="mini-dora">${d}</span>`).join('');
            }
        }

        _renderScoreboard(state) {
            const board = document.getElementById('scoreboard');
            if (!board || !state) return;
            board.innerHTML = state.players.map((p, i) => {
                const cls = ['score-cell'];
                if (p.is_oya) cls.push('oya');
                if (i === state.turn) cls.push('active');
                if (p.riichi) cls.push('riichi');
                const w = WIND_NAMES[WIND_KEY[p.wind] ?? 0];
                return `<div class="${cls.join(' ')}">
                    <span class="label">P${i} · ${w}${p.is_oya ? '(亲)' : ''}</span>
                    <span class="pts">${p.score}</span>
                </div>`;
            }).join('');
        }

        _renderKyokuList() {
            const list = document.getElementById('kyokuList');
            if (!list || !this.kyokuIndices.length) return;
            const curr = this.currentStep >= 0 ? this.steps[this.currentStep]?.kyoku_index : -1;
            list.innerHTML = this.kyokuIndices.map(k => {
                const wind = WIND_NAMES[Math.floor(k / 4)];
                const ki = (k % 4) + 1;
                const cls = k === curr ? 'step current' : 'step done';
                return `<div class="${cls}" onclick="window._replayClient.seekToKyoku(${k})" style="cursor:pointer">${wind}${ki}</div>`;
            }).join('');
        }

        destroy() { this.pause(); }
    }

    window.ReplayClient = ReplayClient;
})();
