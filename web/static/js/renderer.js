/**
 * Mahjong Canvas Renderer
 * Draws tiles, hands, rivers, and game state on a Canvas element.
 */

// ─── Tile Drawing ────────────────────────────────────────────────────────────

const TILE_W = 32;
const TILE_H = 44;
const TILE_R = 4;  // corner radius

// Character to color mapping for tile faces
const TILE_BG = '#faf8f0';
const TILE_SHADOW = '#ccc';

// Font settings
const TILE_FONT = `bold ${TILE_W * 0.55}px 'SimHei', 'Microsoft YaHei', 'Hiragino Mincho Pro', serif`;

function drawTile(ctx, x, y, tileStr, isRed5, isHighlighted, isSelected, isTaken, options = {}) {
    const w = options.w || TILE_W;
    const h = options.h || TILE_H;

    // Highlight / selected background
    if (isSelected) {
        ctx.fillStyle = '#ffe066';
    } else if (isHighlighted) {
        ctx.fillStyle = '#fff3cd';
    } else if (isTaken) {
        ctx.fillStyle = '#e8e8e8';
    } else {
        ctx.fillStyle = TILE_BG;
    }

    // Draw rounded rect with shadow
    ctx.shadowColor = 'rgba(0,0,0,0.3)';
    ctx.shadowBlur = isSelected ? 8 : 3;
    ctx.shadowOffsetX = 1;
    ctx.shadowOffsetY = 2;
    roundRect(ctx, x, y, w, h, TILE_R);
    ctx.fill();
    ctx.shadowColor = 'transparent';

    // Border
    ctx.strokeStyle = isSelected ? '#f39c12' : (isHighlighted ? '#e67e22' : '#aaa');
    ctx.lineWidth = isSelected ? 2 : 1;
    roundRect(ctx, x, y, w, h, TILE_R);
    ctx.stroke();

    if (!tileStr) return;

    // Determine color based on tile type
    const ch = tileStr.charAt(tileStr.length - 1); // 'm', 'p', 's', 'z'
    let color = '#222';
    if (ch === 'z') {
        color = '#1a1a6e'; // 字牌深蓝
    } else if (ch === 'm') {
        color = '#1a5276'; // 万子蓝
    } else if (ch === 'p') {
        color = '#922b21'; // 筒子红
    } else if (ch === 's') {
        color = '#1e8449'; // 索子绿
    }

    // Red 5 tiles
    if (isRed5) color = '#e74c3c';

    // Draw tile character(s)
    ctx.fillStyle = color;
    ctx.font = TILE_FONT;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(tileStr, x + w / 2, y + h / 2 + 1);
}

// Round rect helper
function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
}

// ─── Dora Tile ───────────────────────────────────────────────────────────────

function drawDoraTile(ctx, x, y, tileStr, hidden = false) {
    if (hidden) {
        ctx.fillStyle = '#4a4a8a';
        ctx.shadowColor = 'rgba(0,0,0,0.3)';
        ctx.shadowBlur = 3;
        roundRect(ctx, x, y, TILE_W, TILE_H, TILE_R);
        ctx.fill();
        ctx.shadowColor = 'transparent';
        ctx.strokeStyle = '#888';
        ctx.lineWidth = 1;
        roundRect(ctx, x, y, TILE_W, TILE_H, TILE_R);
        ctx.stroke();
        ctx.fillStyle = '#aaa';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('?', x + TILE_W / 2, y + TILE_H / 2);
        return;
    }
    const isRed = tileStr.startsWith('5') && tileStr.length <= 2;
    drawTile(ctx, x, y, tileStr, isRed, false, false, false);
}

// ─── River Tile ─────────────────────────────────────────────────────────────

function drawRiverTile(ctx, x, y, tileData, options = {}) {
    const tileStr = tileData.tile ? tileData.tile.str : (tileData.str || '?');
    const isRed = tileStr.startsWith('5') && tileStr.length <= 2;
    const isRiichi = tileData.riichi || false;
    const isHighlighted = tileData.highlighted || false;
    drawTile(ctx, x, y, tileStr, isRed, isHighlighted, false, false, options);
    if (isRiichi) {
        // Draw riichi indicator (small red bar below tile)
        ctx.fillStyle = '#e74c3c';
        ctx.fillRect(x + 2, y + TILE_H + 1, TILE_W - 4, 3);
    }
}

// ─── Hand Renderer ──────────────────────────────────────────────────────────

function renderHand(ctx, tiles, x, y, options = {}) {
    // tiles: array of {str, red_dora, highlighted, selected}
    const gap = options.gap || 2;
    const faceUp = options.faceUp !== false;

    tiles.forEach((t, i) => {
        const tileX = x + i * (TILE_W + gap);
        if (faceUp) {
            const tileStr = t.str || String(t);
            const isRed = t.red_dora || (typeof t === 'string' && t.startsWith('5') && t.length <= 2);
            drawTile(ctx, tileX, y, tileStr, isRed, t.highlighted, t.selected, false);
        } else {
            // Back of tile
            drawTileBack(ctx, tileX, y);
        }
    });
}

function drawTileBack(ctx, x, y) {
    ctx.fillStyle = '#2c3e50';
    ctx.shadowColor = 'rgba(0,0,0,0.3)';
    ctx.shadowBlur = 2;
    roundRect(ctx, x, y, TILE_W, TILE_H, TILE_R);
    ctx.fill();
    ctx.shadowColor = 'transparent';
    // Cross pattern
    ctx.strokeStyle = '#34495e';
    ctx.lineWidth = 1;
    for (let d = -1; d <= 1; d += 2) {
        ctx.beginPath();
        ctx.moveTo(x + 4, y + TILE_H / 2 + d * 8);
        ctx.lineTo(x + TILE_W - 4, y + TILE_H / 2 - d * 8);
        ctx.stroke();
    }
}

// ─── Player Name Label ───────────────────────────────────────────────────────

function drawPlayerLabel(ctx, x, y, label, isActive, isOya, isHuman) {
    const w = TILE_W * 1.5;
    const h = 20;
    ctx.fillStyle = isActive ? '#e94560' : (isHuman ? '#2980b9' : '#555');
    ctx.beginPath();
    roundRect(ctx, x, y, w, h, 4);
    ctx.fill();
    ctx.fillStyle = 'white';
    ctx.font = 'bold 11px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(label + (isOya ? ' ★' : ''), x + w / 2, y + h / 2);
}

// ─── Main Game Renderer ──────────────────────────────────────────────────────

/**
 * Main render function — renders the full game state on canvas.
 * @param {CanvasRenderingContext2D} ctx
 * @param {number} W canvas width
 * @param {number} H canvas height
 * @param {object} state game state from /api/game/{id}/state
 * @param {object} opts  rendering options
 */
function renderGame(ctx, W, H, state, opts = {}) {
    ctx.clearRect(0, 0, W, H);

    const T = TILE_W;
    const TH = TILE_H;
    const GAP = 2;
    const RIVER_COLS = 6;

    // ── Dora indicators (top center) ──────────────────────────────────────
    const doraX = W / 2 - ((state.dora.length + 1) * (T + 3)) / 2;
    ctx.fillStyle = 'rgba(0,0,0,0.3)';
    roundRect(ctx, doraX - 10, 8, (state.dora.length + 1) * (T + 3) + 20, TH + 16, 6);
    ctx.fill();

    ctx.fillStyle = '#888';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText('宝牌', doraX - 8, 10);
    state.dora.forEach((d, i) => {
        drawDoraTile(ctx, doraX + i * (T + 3), 20, d);
    });
    // Uradora
    if (state.ura_dora && state.ura_dora.length > 0) {
        ctx.fillStyle = '#888';
        ctx.fillText('里宝', doraX + (state.dora.length + 0.5) * (T + 3), 10);
        state.ura_dora.forEach((d, i) => {
            drawDoraTile(ctx, doraX + (state.dora.length + i) * (T + 3), 20, d);
        });
    }

    // ── Player info and rivers ─────────────────────────────────────────────
    const players = state.players;
    const curr = state.turn;

    // Player 2 (top, across from us) — partial view
    const p2RiverX = W / 2 - (RIVER_COLS * (T * 0.75 + 1)) / 2;
    const p2RiverY = TH + 50;
    drawPlayerLabel(ctx, W / 2 - T * 0.75, p2RiverY - 20, 'P2', curr === 2, players[2].is_oya, false);
    const p2River = players[2].river || [];
    for (let i = 0; i < p2River.length; i++) {
        const col = i % RIVER_COLS;
        const row = Math.floor(i / RIVER_COLS);
        const rx = p2RiverX + col * (T * 0.75 + 1);
        const ry = p2RiverY + row * (TH * 0.6 + 1);
        drawTileBack(ctx, rx, ry);
    }
    // Show P2's hand count
    if (players[2].hand && players[2].hand.length > 0 && typeof players[2].hand[0] === 'object') {
        // Full hand — draw face up in smaller tiles
        const hand = players[2].hand;
        const handX = W / 2 - (hand.length * (T * 0.6 + 1)) / 2;
        hand.forEach((t, i) => {
            const tileStr = t.str || '?';
            const isRed = t.red_dora;
            // small tile
            const sw = T * 0.6, sh = TH * 0.6;
            ctx.fillStyle = TILE_BG;
            roundRect(ctx, handX + i * (sw + 1), p2RiverY + (Math.ceil(RIVER_COLS / 6) + 1) * (TH * 0.6 + 1), sw, sh, 3);
            ctx.fill();
            ctx.fillStyle = '#1a5276';
            ctx.font = `bold ${sw * 0.5}px sans-serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(tileStr, handX + i * (sw + 1) + sw / 2, p2RiverY + (Math.ceil(RIVER_COLS / 6) + 1) * (TH * 0.6 + 1) + sh / 2);
        });
    } else {
        ctx.fillStyle = '#555';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`手牌: ${players[2].hand?.[0]?.count || '?'}枚`, W / 2, p2RiverY + (Math.ceil(RIVER_COLS / 6) + 1) * (TH * 0.6 + 1) + TH * 0.6 / 2);
    }

    // Player 3 (left side)
    const p3RiverX = 8;
    const p3RiverY = H / 2 - 3 * (TH + 2) / 2;
    drawPlayerLabel(ctx, 8, p3RiverY - 22, 'P3', curr === 3, players[3].is_oya, false);
    const p3River = players[3].river || [];
    for (let i = 0; i < Math.min(p3River.length, 6); i++) {
        drawTileBack(ctx, p3RiverX, p3RiverY + i * (TH * 0.75 + 1));
    }

    // Player 1 (right side)
    const p1RiverX = W - T * 0.75 - 8;
    const p1RiverY = H / 2 - 3 * (TH + 2) / 2;
    drawPlayerLabel(ctx, W - T * 0.75 - 8, p1RiverY - 22, 'P1', curr === 1, players[1].is_oya, false);
    const p1River = players[1].river || [];
    for (let i = 0; i < Math.min(p1River.length, 6); i++) {
        drawTileBack(ctx, p1RiverX, p1RiverY + i * (TH * 0.75 + 1));
    }

    // ── Player 0 — Our hand (bottom center) ────────────────────────────────
    const p0Hand = players[0]?.hand || [];
    const p0X = W / 2 - (p0Hand.length * (T + GAP)) / 2;
    const p0Y = H - TH - 60;
    drawPlayerLabel(ctx, p0X - T * 0.5, p0Y - 22, '你', curr === 0, players[0]?.is_oya, true);

    // Sort and draw tiles
    const sortedHand = [...p0Hand].sort((a, b) => {
        const order = { m: 0, p: 1, s: 2, z: 3 };
        const sa = String(a.str || a).slice(-1);
        const sb = String(b.str || b).slice(-1);
        return (order[sa] || 0) - (order[sb] || 0) || ((a.str || a) > (b.str || b) ? 1 : -1);
    });

    sortedHand.forEach((t, i) => {
        const tileStr = typeof t === 'string' ? t : (t.str || '?');
        const isRed = typeof t === 'object' ? !!t.red_dora : (tileStr.startsWith('5') && tileStr.length <= 2);
        const isHl = typeof t === 'object' ? !!t.highlighted : false;
        const isSel = typeof t === 'object' ? !!t.selected : false;
        drawTile(ctx, p0X + i * (T + GAP), p0Y, tileStr, isRed, isHl, isSel, false);
    });

    // Highlight atari tiles
    const atari = players[0]?.tenpai || [];
    if (atari.length > 0) {
        ctx.fillStyle = '#f1c40f';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`听: ${atari.join(' ')}`, W / 2, p0Y - 4);
    }

    // Player 0 River
    const p0River = players[0]?.river || [];
    const p0RiverY = H - TH - 20 - 60;
    for (let i = 0; i < p0River.length; i++) {
        const col = i % RIVER_COLS;
        const row = Math.floor(i / RIVER_COLS);
        const rx = W / 2 - (RIVER_COLS * (T + GAP)) / 2 + col * (T + GAP);
        const ry = p0RiverY + row * (TH + 2);
        drawRiverTile(ctx, rx, ry, p0River[i]);
    }

    // ── Current turn indicator ─────────────────────────────────────────────
    ctx.fillStyle = 'rgba(0,0,0,0.5)';
    ctx.beginPath();
    ctx.arc(W / 2, H / 2, 16, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#e94560';
    ctx.font = 'bold 16px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(`P${curr}`, W / 2, H / 2);

    // ── Riichi indicator ────────────────────────────────────────────────────
    if (state.kyoutaku > 0) {
        ctx.fillStyle = '#f1c40f';
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(`立直棒: ${state.kyoutaku}`, 10, H - 10);
    }
}

// ─── Replay Renderer ─────────────────────────────────────────────────────────

/**
 * Render game state for replay (all 4 hands visible).
 */
function renderReplay(ctx, W, H, state, opts = {}) {
    // Same as renderGame but with all 4 hands visible
    renderGame(ctx, W, H, state, { ...opts, showAllHands: true });
}

// Export for use in HTML
window.MahjongRenderer = {
    renderGame,
    renderReplay,
    drawTile,
    drawDoraTile,
    drawRiverTile,
    renderHand,
    TILE_W,
    TILE_H,
};
