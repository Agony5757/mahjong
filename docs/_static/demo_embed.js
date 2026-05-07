(function () {
    const canvas = document.getElementById('docs-demo-canvas');
    if (!canvas || !window.MahjongRenderer) return;

    const roundEl = document.getElementById('docs-demo-round');
    const stepEl = document.getElementById('docs-demo-step');
    const statusEl = document.getElementById('docs-demo-status');
    const playBtn = document.getElementById('docs-demo-play');
    const pauseBtn = document.getElementById('docs-demo-pause');
    const resetBtn = document.getElementById('docs-demo-reset');
    const speedInput = document.getElementById('docs-demo-speed');
    const speedValueEl = document.getElementById('docs-demo-speed-value');

    let states = [];
    let index = 0;
    let timer = null;
    let speed = Number(speedInput.value);

    const winds = ['East', 'South', 'West', 'North'];

    function wrapTile(tile) {
        return typeof tile === 'string' ? { str: tile, red_dora: false } : tile;
    }

    function wrapRiver(river, isRiichiStep) {
        return (river || []).map((tile, tileIndex, arr) => ({
            str: tile,
            red_dora: false,
            riichi: isRiichiStep && tileIndex === arr.length - 1,
        }));
    }

    function convertStep(step) {
        const actor = Number.isInteger(step.turn) ? (step.turn + 3) % 4 : -1;
        const players = (step.players || []).map((player, seatIndex) => ({
            wind: winds[seatIndex],
            is_oya: seatIndex === step.oya,
            score: player.score ?? (step.scores || [])[seatIndex] ?? 25000,
            riichi: !!player.riichi,
            hand: (player.hand || []).map(wrapTile),
            river: wrapRiver(player.river || [], step.last_action === 'riichi' && seatIndex === actor),
            calls: [],
            tenpai: [],
        }));

        return {
            game_wind: 'East',
            oya: step.oya ?? 0,
            honba: step.honba ?? 0,
            kyoutaku: step.riichibo ?? 0,
            river_counter: Math.max(0, 70 - players.reduce((sum, player) => sum + player.river.length, 0)),
            dora: step.dora || [],
            turn: step.turn ?? 0,
            phase: 0,
            players,
        };
    }

    function setStatus(message) {
        if (statusEl) statusEl.textContent = message;
    }

    function updateMeta(state) {
        if (!state) return;
        roundEl.textContent = `东${(state.oya ?? 0) + 1}局 · 本场 ${state.honba ?? 0} · 供托 ${state.kyoutaku ?? 0}`;
        stepEl.textContent = `Step ${index + 1} / ${states.length}`;
    }

    function renderCurrent() {
        window.MahjongRenderer.resizeCanvasToContainer(canvas, { maxWidth: 1900, maxHeightRatio: 1.10 });
        const ctx = canvas.getContext('2d');
        if (!states.length) {
            window.MahjongRenderer.renderSplash(ctx, canvas.width, canvas.height, '4 AI Demo', 'Documentation replay is loading');
            return;
        }
        window.MahjongRenderer.renderReplay(ctx, canvas.width, canvas.height, states[index], {});
        updateMeta(states[index]);
    }

    function stopTimer() {
        if (timer) {
            clearTimeout(timer);
            timer = null;
        }
    }

    function tick() {
        if (!states.length) return;
        index = (index + 1) % states.length;
        renderCurrent();
        timer = setTimeout(tick, speed);
    }

    function play() {
        stopTimer();
        tick();
        setStatus('Playing documentation replay');
    }

    function pause() {
        stopTimer();
        setStatus('Paused');
    }

    function reset() {
        stopTimer();
        index = 0;
        renderCurrent();
        setStatus('Reset to step 1');
    }

    playBtn.addEventListener('click', play);
    pauseBtn.addEventListener('click', pause);
    resetBtn.addEventListener('click', reset);
    speedInput.addEventListener('input', function () {
        speed = Number(speedInput.value);
        speedValueEl.textContent = `${speed} ms`;
        if (timer) {
            stopTimer();
            timer = setTimeout(tick, speed);
        }
    });

    window.MahjongRenderer.setInvalidateHandler(renderCurrent);
    window.addEventListener('resize', renderCurrent);

    fetch('_static/demo_game.json')
        .then(function (response) {
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return response.json();
        })
        .then(function (data) {
            states = (data.steps || []).map(convertStep);
            index = 0;
            renderCurrent();
            setStatus('Ready');
        })
        .catch(function (error) {
            console.error('Failed to load documentation demo data', error);
            const ctx = canvas.getContext('2d');
            window.MahjongRenderer.renderSplash(ctx, canvas.width, canvas.height, 'Demo Error', 'Failed to load replay data');
            setStatus(`Failed to load replay data: ${error.message}`);
        });

    renderCurrent();
})();
