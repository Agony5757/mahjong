/**
 * Paipu Replay Client — loads Tenhou XML or built-in paipu and replays step-by-step.
 */
class ReplayClient {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.replayer = null;
        this.paipuData = null;
        this.gameSteps = [];
        this.currentStep = -1;
        this.isPlaying = false;
        this.playInterval = null;
        this.speed = 800;  // ms per step

        if (window.MahjongRenderer?.setInvalidateHandler) {
            window.MahjongRenderer.setInvalidateHandler(() => this._renderStep());
        }
    }

    resize() {
        if (window.MahjongRenderer?.resizeCanvasToContainer) {
            window.MahjongRenderer.resizeCanvasToContainer(this.canvas, { maxWidth: 1240, maxHeightRatio: 0.7 });
        }
    }

    async _fetch(url, options = {}) {
        const resp = await fetch(url, options);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return resp.json();
    }

    // ─── Load Built-in Paipu ────────────────────────────────────────────────

    async listBuiltinPaipu() {
        try {
            const data = await this._fetch('/api/replay/builtin');
            return data.paipu_files || [];
        } catch {
            return [];
        }
    }

    async loadBuiltinPaipu(filename) {
        const resp = await fetch(`/api/replay/builtin/${filename}`);
        const xml = await resp.text();
        return this.loadFromXML(xml);
    }

    // ─── Load from XML ──────────────────────────────────────────────────────

    async loadFromXML(xmlContent) {
        window._lastXML = xmlContent;
        const resp = await fetch('/api/replay/load', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ xml_content: xmlContent }),
        });
        const data = await resp.json();
        if (!data.ok) throw new Error(data.detail || 'Parse failed');
        this.paipuData = data.paipu;
        await this._buildSteps();
        this.currentStep = -1;
        this._renderTimeline();
        return this.gameSteps.length;
    }

    // ─── Build Steps ────────────────────────────────────────────────────────

    async _buildSteps() {
        const resp = await fetch('/api/replay/steps', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ xml_content: window._lastXML || '' }),
        }).catch(() => null);
        if (!resp || !resp.ok) {
            this.gameSteps = [];
            return;
        }
        const data = await resp.json();
        this.gameSteps = data.steps || [];
    }

    // ─── Step Navigation ────────────────────────────────────────────────────

    stepForward() {
        if (this.currentStep >= this.gameSteps.length - 1) return;
        this.currentStep++;
        this._renderStep();
    }

    stepBackward() {
        if (this.currentStep <= 0) return;
        this.currentStep--;
        this._renderStep();
    }

    seekTo(step) {
        this.currentStep = Math.max(-1, Math.min(step, this.gameSteps.length - 1));
        this._renderStep();
    }

    play() {
        if (this.isPlaying) {
            this.pause();
            return;
        }
        this.isPlaying = true;
        document.getElementById('btnPlay').textContent = '⏸ 暂停';
        const tick = () => {
            if (!this.isPlaying) return;
            if (this.currentStep >= this.gameSteps.length - 1) {
                this.pause();
                return;
            }
            this.stepForward();
            this.playInterval = setTimeout(tick, this.speed);
        };
        tick();
    }

    pause() {
        this.isPlaying = false;
        if (this.playInterval) clearTimeout(this.playInterval);
        document.getElementById('btnPlay').textContent = '▶ 播放';
    }

    setSpeed(ms) {
        this.speed = ms;
        if (this.isPlaying) {
            this.pause();
            this.play();
        }
    }

    // ─── Rendering ──────────────────────────────────────────────────────────

    _renderStep() {
        if (!this.paipuData || this.currentStep < 0) {
            // Show initial state
            this._renderEmpty();
            return;
        }

        const step = this.gameSteps[this.currentStep];
        if (!step) return;

        // Render via renderer
        const { renderReplay } = window.MahjongRenderer;
        renderReplay(this.ctx, this.canvas.width, this.canvas.height, step.state || step);

        // Update timeline
        this._updateTimeline();
        this._updateInfoPanel(step);
        this._updateTopBar(step.state || step);
    }

    _renderEmpty() {
        window.MahjongRenderer.renderSplash(this.ctx, this.canvas.width, this.canvas.height, '牌谱复现', '上传天凤 XML 牌谱或加载内置示例');
    }

    _updateTimeline() {
        const slider = document.getElementById('timelineSlider');
        const progress = document.getElementById('timelineProgress');
        if (!slider || !progress) return;

        slider.max = Math.max(1, this.gameSteps.length - 1);
        slider.value = this.currentStep;
        const pct = this.gameSteps.length > 1
            ? (this.currentStep / (this.gameSteps.length - 1)) * 100
            : 0;
        progress.style.width = pct + '%';
        document.getElementById('stepCounter').textContent =
            `${this.currentStep + 1} / ${this.gameSteps.length}`;
    }

    _renderTimeline() {
        this._updateTimeline();
    }

    _updateInfoPanel(step) {
        const infoEl = document.getElementById('stepInfo');
        if (!infoEl || !step) return;

        const phaseNames = ['自摸', '自摸', '自摸', '自摸', '响应', '响应', '响应', '响应',
            '抢杠', '抢杠', '抢杠', '抢杠', '抢暗杠', '抢暗杠', '抢暗杠', '抢暗杠', '结束'];
        infoEl.innerHTML = `
            <div><strong>步骤:</strong> ${this.currentStep + 1}/${this.gameSteps.length}</div>
            <div><strong>阶段:</strong> ${phaseNames[step.phase] || step.phase}</div>
            <div><strong>行动者:</strong> P${step.player || step.turn || '?'}</div>
            <div><strong>动作:</strong> ${step.base_action || '?'}</div>
            <div><strong>分数:</strong> ${(step.scores || []).join(' | ')}</div>
        `;
    }

    _updateTopBar(state) {
        if (!state || !state.players) return;
        const windNames = ['东', '南', '西', '北'];
        const roundInfo = document.getElementById('roundInfo');
        const honbaInfo = document.getElementById('honbaInfo');
        const riichiInfo = document.getElementById('riichiInfo');
        const doraBar = document.getElementById('doraTiles');
        if (roundInfo) {
            const wind = windNames[state.game_wind === 'East' ? 0 : state.game_wind === 'South' ? 1 : state.game_wind === 'West' ? 2 : 3];
            roundInfo.textContent = `${wind}${(state.oya ?? 0) + 1}局`;
        }
        if (honbaInfo) honbaInfo.textContent = `本场${state.honba || 0}`;
        if (riichiInfo) riichiInfo.textContent = `供托${state.kyoutaku || 0}`;
        if (doraBar) {
            doraBar.innerHTML = (state.dora || []).map(d =>
                `<span class="mini-dora">${d}</span>`
            ).join('');
        }
        state.players.forEach((p, i) => {
            const chip = document.getElementById(`chip${i}`);
            if (!chip) return;
            chip.querySelector('.pid').textContent = `P${i} · ${windNames[p.wind === 'East' ? 0 : p.wind === 'South' ? 1 : p.wind === 'West' ? 2 : 3]}`;
            chip.querySelector('.pts').textContent = p.score;
            chip.classList.toggle('oya', !!p.is_oya);
            chip.classList.toggle('active', i === state.turn);
            chip.classList.toggle('riichi', !!p.riichi);
        });
    }

    destroy() {
        this.pause();
    }
}

// Export
window.ReplayClient = ReplayClient;
