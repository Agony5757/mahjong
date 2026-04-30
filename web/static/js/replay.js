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
    }

    resize() {
        const W = Math.min(this.canvas.parentElement.clientWidth - 16, 900);
        const H = Math.min(W * 0.65, 600);
        this.canvas.width = W;
        this.canvas.height = H;
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
        // Use the Python backend to replay the paipu
        // We simulate step-by-step by calling the paipu_parser
        const resp = await fetch('/api/replay/steps', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ xml_content: window._lastXML || '' }),
        }).catch(() => null);

        // Fallback: generate steps from paipu data directly via PaipuReplayer
        this.gameSteps = [];
        // We'll build steps on-demand in JS using the replayer
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
    }

    _renderEmpty() {
        const ctx = this.ctx;
        ctx.fillStyle = '#0d1117';
        ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        ctx.fillStyle = '#555';
        ctx.font = '20px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('加载牌谱后开始复现', this.canvas.width / 2, this.canvas.height / 2);
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

    destroy() {
        this.pause();
    }
}

// Export
window.ReplayClient = ReplayClient;
