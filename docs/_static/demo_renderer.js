/**
 * Mahjong table renderer.
 *
 * The renderer uses a fixed logical board (1600x1000) and scales it to the
 * canvas viewport. This keeps proportions stable across different resolutions.
 */

const BOARD_W = 2200;
const BOARD_H = 1400;
const BOARD_ASPECT = BOARD_W / BOARD_H;

const TABLE = {
    margin: 40,
    feltInset: 18,
    centerX: BOARD_W / 2,
    centerY: BOARD_H / 2,
};

const SEAT_ANGLES = [0, -Math.PI / 2, Math.PI, Math.PI / 2];

const HAND_TILE = { w: 40, h: 56, gap: 4, drawGap: 14 };
const SIDE_HAND_TILE = { w: 34, h: 48, gap: 2, drawGap: 10 };
// 日麻惯例：牌河每行 6 张，最多 4 行 (24 张可覆盖任何实际情况)
const RIVER_TILE = { w: 32, h: 44, gap: 5, vgap: 6, cols: 6 };
const MELD_TILE = { w: 32, h: 44, gap: 3, groupGap: 10 };
const DORA_TILE = { w: 32, h: 44, gap: 6 };

// y 坐标在每个座位的局部坐标系下从中心向外延伸。
// 中心面板半高 ~110，因此 riverY 必须 >= 120。
const LOCAL_LAYOUT = {
    riverY: 130,
    badgeY: 360,
    handY: 440,
};

const TILE_ASSET_ROOT = (typeof window !== 'undefined' && window.__MAHJONG_TILE_ASSET_ROOT__) || '/static/assets/tiles/Regular';
const TILE_ASSET_MAP = {
    '1m': 'Man1',
    '2m': 'Man2',
    '3m': 'Man3',
    '4m': 'Man4',
    '5m': 'Man5',
    '6m': 'Man6',
    '7m': 'Man7',
    '8m': 'Man8',
    '9m': 'Man9',
    '1p': 'Pin1',
    '2p': 'Pin2',
    '3p': 'Pin3',
    '4p': 'Pin4',
    '5p': 'Pin5',
    '6p': 'Pin6',
    '7p': 'Pin7',
    '8p': 'Pin8',
    '9p': 'Pin9',
    '1s': 'Sou1',
    '2s': 'Sou2',
    '3s': 'Sou3',
    '4s': 'Sou4',
    '5s': 'Sou5',
    '6s': 'Sou6',
    '7s': 'Sou7',
    '8s': 'Sou8',
    '9s': 'Sou9',
    '1z': 'Ton',
    '2z': 'Nan',
    '3z': 'Shaa',
    '4z': 'Pei',
    '5z': 'Haku',
    '6z': 'Hatsu',
    '7z': 'Chun',
};

const assetCache = new Map();
let invalidateRenderer = null;

function setInvalidateHandler(fn) {
    invalidateRenderer = fn;
}

function resizeCanvasToContainer(canvas, options = {}) {
    const dpr = window.devicePixelRatio || 1;
    const maxWidth = options.maxWidth || 1700;
    const aspectRatio = options.aspectRatio || BOARD_ASPECT;
    const containerWidth = Math.max(320, Math.min(canvas.parentElement.clientWidth - 4, maxWidth));
    const maxHeight = Math.max(360, Math.floor(window.innerHeight * (options.maxHeightRatio || 0.78)));

    let cssWidth = containerWidth;
    let cssHeight = Math.floor(cssWidth / aspectRatio);

    if (cssHeight > maxHeight) {
        cssHeight = maxHeight;
        cssWidth = Math.floor(cssHeight * aspectRatio);
    }

    canvas.style.width = `${cssWidth}px`;
    canvas.style.height = `${cssHeight}px`;
    canvas.width = Math.floor(cssWidth * dpr);
    canvas.height = Math.floor(cssHeight * dpr);

    return { cssWidth, cssHeight, dpr };
}

function computeViewport(width, height) {
    const scale = Math.min(width / BOARD_W, height / BOARD_H);
    return {
        scale,
        offsetX: (width - BOARD_W * scale) / 2,
        offsetY: (height - BOARD_H * scale) / 2,
    };
}

function toCanvasRect(rect, viewport) {
    return {
        x: viewport.offsetX + rect.x * viewport.scale,
        y: viewport.offsetY + rect.y * viewport.scale,
        w: rect.w * viewport.scale,
        h: rect.h * viewport.scale,
    };
}

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

function fillRoundedRect(ctx, x, y, w, h, r, fillStyle, strokeStyle = null, strokeWidth = 1) {
    ctx.save();
    roundRect(ctx, x, y, w, h, r);
    ctx.fillStyle = fillStyle;
    ctx.fill();
    if (strokeStyle) {
        ctx.strokeStyle = strokeStyle;
        ctx.lineWidth = strokeWidth;
        ctx.stroke();
    }
    ctx.restore();
}

function makeGradient(ctx, x0, y0, x1, y1, stops) {
    const gradient = ctx.createLinearGradient(x0, y0, x1, y1);
    stops.forEach(([offset, color]) => gradient.addColorStop(offset, color));
    return gradient;
}

function getTileAssetPath(tileStr, redDora = false, faceDown = false) {
    if (faceDown) return `${TILE_ASSET_ROOT}/Back.svg`;
    const key = tileStr || '';
    const asset = TILE_ASSET_MAP[key];
    if (!asset) return `${TILE_ASSET_ROOT}/Front.svg`;
    const suffix = redDora ? '-Dora' : '';
    return `${TILE_ASSET_ROOT}/${asset}${suffix}.svg`;
}

function getAssetImage(path) {
    let entry = assetCache.get(path);
    if (!entry) {
        const img = new Image();
        img.decoding = 'async';
        img.onload = () => {
            if (invalidateRenderer) invalidateRenderer();
        };
        img.src = path;
        entry = { img };
        assetCache.set(path, entry);
    }
    return entry.img.complete ? entry.img : null;
}

function fallbackFaceColor(tileStr) {
    const suit = String(tileStr || '').slice(-1);
    if (suit === 'm') return '#a53b34';
    if (suit === 'p') return '#294d8f';
    if (suit === 's') return '#1e6a39';
    if (suit === 'z') return '#2f4294';
    return '#3a3a3a';
}

function drawFallbackTile(ctx, x, y, w, h, tileStr, options = {}) {
    ctx.save();
    ctx.shadowColor = 'rgba(0, 0, 0, 0.22)';
    ctx.shadowBlur = 10;
    ctx.shadowOffsetX = 0;
    ctx.shadowOffsetY = 6;
    fillRoundedRect(ctx, x, y, w, h, 10, '#f8f3ea', '#cdbfa7', 1.4);
    ctx.shadowColor = 'transparent';
    if (tileStr) {
        ctx.fillStyle = options.faceDown ? '#b8c6d8' : fallbackFaceColor(tileStr);
        ctx.font = `${Math.floor(h * 0.36)}px "Hiragino Mincho ProN", "Yu Mincho", serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(tileStr, x + w / 2, y + h / 2);
    }
    ctx.restore();
}

function drawTileImage(ctx, x, y, w, h, tileStr, options = {}) {
    const {
        redDora = false,
        faceDown = false,
        rotation = 0,
        selected = false,
        highlighted = false,
        dimmed = false,
        lifted = 0,
    } = options;

    const img = getAssetImage(getTileAssetPath(tileStr, redDora, faceDown));
    const cx = x + w / 2;
    const cy = y + h / 2 - lifted;
    const r = Math.max(3, Math.round(h * 0.08));

    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(rotation);

    if (dimmed) ctx.globalAlpha = 0.82;

    // Draw tile base (cream background) so tiles stand out against felt
    ctx.shadowColor = 'rgba(0,0,0,0.15)';
    ctx.shadowBlur = 6;
    ctx.shadowOffsetX = 0;
    ctx.shadowOffsetY = 3;
    fillRoundedRect(ctx, -w / 2, -h / 2, w, h, r, '#f5f0eb', '#cdbfab', 1);
    ctx.shadowColor = 'transparent';

    if (img) {
        ctx.drawImage(img, -w / 2, -h / 2, w, h);
    } else {
        drawFallbackTile(ctx, -w / 2, -h / 2, w, h, faceDown ? '' : tileStr, { faceDown });
    }

    // Selection / highlight glow on top
    if (selected || highlighted) {
        ctx.globalAlpha = 1;
        ctx.shadowColor = selected ? 'rgba(255, 190, 65, 0.65)' : 'rgba(120, 208, 255, 0.45)';
        ctx.shadowBlur = selected ? 12 : 8;
        fillRoundedRect(
            ctx,
            -w / 2 - 4,
            -h / 2 - 4,
            w + 8,
            h + 8,
            10,
            selected ? 'rgba(255, 224, 127, 0.28)' : 'rgba(190, 240, 255, 0.18)',
            selected ? '#f5c451' : '#8ed2ff',
            1.5
        );
    }

    ctx.restore();
}

function drawStick(ctx, x, y, length, color, text, rotation = 0) {
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(rotation);
    fillRoundedRect(ctx, -length / 2, -5, length, 10, 5, '#f1ede2', '#bbab91', 1);
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(-length / 2 + 10, 0, 3.5, 0, Math.PI * 2);
    ctx.arc(length / 2 - 10, 0, 3.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#584940';
    ctx.font = '10px "Hiragino Sans GB", "Microsoft YaHei", sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, 0, 0.4);
    ctx.restore();
}

function windToZh(wind) {
    return {
        East: '东',
        South: '南',
        West: '西',
        North: '北',
    }[wind] || wind || '?';
}

function buildRoundLabel(state) {
    return `${windToZh(state.game_wind)}${(state.oya ?? 0) + 1}局`;
}

function getRiverHighlightPlayer(state) {
    if (!state || state.phase < 4 || state.phase >= 16) return -1;
    return (state.turn + 3) % 4;
}

function normalizeHand(player) {
    if (!player || !Array.isArray(player.hand)) return { visible: false, count: 0, tiles: [] };
    const first = player.hand[0];
    if (first && typeof first === 'object' && typeof first.count === 'number' && !first.str) {
        return { visible: false, count: first.count, tiles: [] };
    }
    return { visible: true, count: player.hand.length, tiles: player.hand };
}

function computeHandRects(count, centerX, topY, tileSize) {
    if (!count) return [];
    const splitLast = count > 1 && count % 3 === 2;
    const normalCount = splitLast ? count - 1 : count;
    const totalWidth =
        normalCount * tileSize.w +
        Math.max(normalCount - 1, 0) * tileSize.gap +
        (splitLast ? tileSize.drawGap + tileSize.w : 0);
    const startX = centerX - totalWidth / 2;
    const rects = [];
    let cursor = startX;
    for (let i = 0; i < normalCount; i++) {
        rects.push({ x: cursor, y: topY, w: tileSize.w, h: tileSize.h });
        cursor += tileSize.w + tileSize.gap;
    }
    if (splitLast) {
        cursor += tileSize.drawGap;
        rects.push({ x: cursor, y: topY, w: tileSize.w, h: tileSize.h });
    }
    return rects;
}

function drawCenterPanel(ctx, state) {
    const panelW = 300;
    const panelH = 200;
    const x = TABLE.centerX - panelW / 2;
    const y = TABLE.centerY - panelH / 2;

    fillRoundedRect(
        ctx,
        x,
        y,
        panelW,
        panelH,
        26,
        makeGradient(ctx, x, y, x, y + panelH, [
            [0, 'rgba(17, 33, 26, 0.92)'],
            [1, 'rgba(8, 18, 14, 0.96)'],
        ]),
        'rgba(255, 255, 255, 0.08)',
        2
    );

    ctx.save();
    ctx.translate(TABLE.centerX, TABLE.centerY);
    ctx.rotate(Math.PI / 4);
    fillRoundedRect(ctx, -92, -92, 184, 184, 24, 'rgba(231, 245, 227, 0.05)', 'rgba(255,255,255,0.06)', 1.5);
    ctx.restore();

    ctx.fillStyle = '#f0e7d2';
    ctx.font = '600 17px "Hiragino Sans GB", "Microsoft YaHei", sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(buildRoundLabel(state), TABLE.centerX, y + 28);

    ctx.fillStyle = '#cabda0';
    ctx.font = '12px "Hiragino Sans GB", "Microsoft YaHei", sans-serif';
    const tilesLeft = (state.tiles_left !== undefined && state.tiles_left !== null)
        ? state.tiles_left
        : Math.max(0, 70 - (state.river_counter ?? 0));
    ctx.fillText(`牌山剩余 ${tilesLeft}`, TABLE.centerX, y + 50);

    const dora = state.dora || [];
    const doraTotalWidth = dora.length * DORA_TILE.w + Math.max(dora.length - 1, 0) * DORA_TILE.gap;
    const doraStartX = TABLE.centerX - doraTotalWidth / 2;
    ctx.fillStyle = '#ceb982';
    ctx.font = '11px "Hiragino Sans GB", "Microsoft YaHei", sans-serif';
    ctx.fillText('宝牌', TABLE.centerX, y + 74);
    dora.forEach((tile, index) => {
        drawTileImage(ctx, doraStartX + index * (DORA_TILE.w + DORA_TILE.gap), y + 84, DORA_TILE.w, DORA_TILE.h, tile, {});
    });

    const stickY = y + panelH - 28;
    drawStick(ctx, TABLE.centerX - 60, stickY, 84, '#b7473f', `供托 ${state.kyoutaku ?? 0}`);
    drawStick(ctx, TABLE.centerX + 60, stickY, 84, '#2d67b3', `本场 ${state.honba ?? 0}`);
}

function drawSeatBadge(ctx, player, seatIndex, active, revealDetails) {
    const x = -82;
    const y = LOCAL_LAYOUT.badgeY;
    const w = 164;
    const h = 44;
    const badgeFill = active ? 'rgba(255, 224, 133, 0.20)' : 'rgba(10, 12, 12, 0.46)';
    const badgeStroke = active ? '#f0c66e' : 'rgba(255, 255, 255, 0.08)';
    fillRoundedRect(ctx, x, y, w, h, 14, badgeFill, badgeStroke, active ? 2.4 : 1.4);

    const wind = windToZh(player.wind);
    const title = `P${seatIndex}·${wind}${player.is_oya ? '家' : ''}`;
    ctx.fillStyle = active ? '#fff7dd' : '#ece6d7';
    ctx.font = '600 12px "Hiragino Sans GB", "Microsoft YaHei", sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText(title, x + 10, y + 7);

    ctx.font = '700 16px "Hiragino Sans GB", "Microsoft YaHei", sans-serif';
    ctx.fillText(String(player.score ?? 0), x + 10, y + 24);

    const rightText = [];
    if (player.riichi) rightText.push('立直');
    if (revealDetails && player.tenpai && player.tenpai.length) rightText.push(`听 ${player.tenpai.join(' ')}`);
    ctx.textAlign = 'right';
    ctx.font = '11px "Hiragino Sans GB", "Microsoft YaHei", sans-serif';
    ctx.fillStyle = '#d6c8ab';
    ctx.fillText(rightText.join('·'), x + w - 10, y + 24);
}

function drawRiverLocal(ctx, river, seatIndex, highlightLast) {
    const cellW = RIVER_TILE.w + RIVER_TILE.gap;
    const cellH = RIVER_TILE.h + RIVER_TILE.vgap;
    const totalWidth = RIVER_TILE.cols * cellW - RIVER_TILE.gap;
    const startX = -totalWidth / 2;
    const startY = LOCAL_LAYOUT.riverY;

    river.forEach((tile, index) => {
        if (tile.remain === false) return;  // called tile (pon/chi/kan) — skip
        const col = index % RIVER_TILE.cols;
        const row = Math.floor(index / RIVER_TILE.cols);
        const cellX = startX + col * cellW;
        const cellY = startY + row * cellH;
        const sideways = !!tile.riichi;
        // Always pass natural tile dimensions; rotation lays the tile
        // sideways. Position the tile so it occupies the cell footprint.
        const occW = sideways ? RIVER_TILE.h : RIVER_TILE.w;
        const occH = sideways ? RIVER_TILE.w : RIVER_TILE.h;
        const cx = cellX + occW / 2;
        const cy = cellY + occH / 2;
        const tileStr = tile.tile?.str || tile.str || '';
        const isRed = !!tile.tile?.red_dora;
        drawTileImage(
            ctx,
            cx - RIVER_TILE.w / 2,
            cy - RIVER_TILE.h / 2,
            RIVER_TILE.w,
            RIVER_TILE.h,
            tileStr,
            {
                redDora: isRed,
                rotation: sideways ? Math.PI / 2 : 0,
                highlighted: highlightLast && index === river.length - 1,
            }
        );
    });
}

function meldDescriptors(call) {
    const tiles = Array.isArray(call.tiles) ? call.tiles : [];
    const type = call.type || '';
    const take = Number.isInteger(call.take) ? call.take : -1;
    const isAnKan = /An.?Kan|^Concealed/i.test(type);
    const isKaKan = /Ka.?Kan|^Added/i.test(type);

    if (isAnKan && tiles.length === 4) {
        // 暗杠：两端两张背面
        return tiles.map((tile, index) => ({
            tile,
            sideways: false,
            faceDown: index === 0 || index === tiles.length - 1,
            stacked: false,
        }));
    }

    // For Chi/Pon/MinKan/KaKan, the sideways tile is the one taken from another player.
    // The frontend uses `take` (index of the called tile in the meld layout from the C++ engine).
    return tiles.map((tile, index) => ({
        tile,
        sideways: index === take && tiles.length > 1,
        faceDown: false,
        // For KaKan the engine emits 4 tiles where the added tile sits on top of the
        // sideways tile from the original Pon. We render that as a stacked tile.
        stacked: isKaKan && tiles.length === 4 && index === Math.max(0, take + 1),
    }));
}

function measureMeldWidth(call) {
    return meldDescriptors(call).reduce((width, part, index, parts) => {
        if (part.stacked) return width;  // stacked tiles don't add to horizontal width
        width += part.sideways ? MELD_TILE.h : MELD_TILE.w;
        if (index < parts.length - 1 && !parts[index + 1]?.stacked) width += MELD_TILE.gap;
        return width;
    }, 0);
}

function drawMeldGroup(ctx, call, x, baselineY) {
    // baselineY = the bottom y where every tile in this meld is aligned.
    // Sideways tiles occupy MELD_TILE.h (40) wide × MELD_TILE.w (28) tall on screen.
    // Normal tiles occupy MELD_TILE.w (28) wide × MELD_TILE.h (40) tall.
    // KaKan added tile sits on top of the previously-drawn sideways tile,
    // also rotated.
    const parts = meldDescriptors(call);
    let cursor = x;
    let lastSideways = null;
    parts.forEach((part, index) => {
        const tw = MELD_TILE.w; // natural tile width
        const th = MELD_TILE.h; // natural tile height
        const tileStr = part.tile?.str || '';
        const opts = {
            redDora: !!part.tile?.red_dora,
            faceDown: part.faceDown,
            rotation: part.sideways || part.stacked ? Math.PI / 2 : 0,
        };

        if (part.stacked && lastSideways) {
            // Place stacked (KaKan added) tile directly above the previous
            // sideways tile, with the same orientation.
            const cx = lastSideways.cx;
            const cy = lastSideways.cy - tw; // shift up by sideways visual height (= tw=28)
            drawTileImage(ctx, cx - tw / 2, cy - th / 2, tw, th, tileStr, opts);
            return;
        }

        const occW = part.sideways ? th : tw; // visual width on screen
        const occH = part.sideways ? tw : th; // visual height on screen
        const cx = cursor + occW / 2;
        const cy = baselineY - occH / 2;
        // drawTileImage centers at (x+w/2, y+h/2), then rotates around that
        // center and draws an asset of size (w, h). Pass the *natural* size so
        // the rotation produces a proper sideways orientation.
        drawTileImage(ctx, cx - tw / 2, cy - th / 2, tw, th, tileStr, opts);

        if (part.sideways) {
            lastSideways = { cx, cy };
        }

        cursor += occW;
        if (index < parts.length - 1 && !parts[index + 1]?.stacked) {
            cursor += MELD_TILE.gap;
        }
    });
}

function drawMeldsLocal(ctx, player, handWidth) {
    const calls = Array.isArray(player.calls) ? player.calls : [];
    if (!calls.length) return;

    const widths = calls.map(measureMeldWidth);
    const totalWidth = widths.reduce((a, b) => a + b, 0) + Math.max(calls.length - 1, 0) * MELD_TILE.groupGap;
    let cursor = -handWidth / 2 - 32 - totalWidth;

    // Bottom-align meld tiles with the bottom of the hand row.
    const baselineY = LOCAL_LAYOUT.handY + HAND_TILE.h;
    calls.forEach((call, index) => {
        drawMeldGroup(ctx, call, cursor, baselineY);
        cursor += widths[index] + MELD_TILE.groupGap;
    });
}

function drawHandLocal(ctx, player, seatIndex, active, regions = null) {
    const handInfo = normalizeHand(player);
    const tileSize = seatIndex === 0 ? HAND_TILE : SIDE_HAND_TILE;
    const rects = computeHandRects(handInfo.count, 0, LOCAL_LAYOUT.handY, tileSize);

    rects.forEach((rect, index) => {
        const tile = handInfo.visible ? handInfo.tiles[index] : null;
        const tileStr = tile?.str || '';
        const redDora = !!tile?.red_dora;
        const highlighted = !!tile?.highlighted;
        const selected = !!tile?.selected;
        const lifted = selected ? 10 : highlighted ? 5 : 0;
        drawTileImage(ctx, rect.x, rect.y, rect.w, rect.h, tileStr, {
            redDora,
            faceDown: !handInfo.visible,
            selected,
            highlighted,
            lifted,
        });
    });

    if (regions && handInfo.visible) {
        rects.forEach((rect, index) => {
            regions.push({
                index,
                rect: {
                    x: TABLE.centerX + rect.x,
                    y: TABLE.centerY + rect.y,
                    w: rect.w,
                    h: rect.h,
                },
            });
        });
    }

    const handWidth = rects.length
        ? rects[rects.length - 1].x + rects[rects.length - 1].w - rects[0].x
        : 0;

    return { handWidth, rects, visible: handInfo.visible };
}

function drawSeat(ctx, player, seatIndex, state, options, interactiveRegions) {
    const highlightRiverPlayer = getRiverHighlightPlayer(state);
    const handInfo = normalizeHand(player);
    ctx.save();
    ctx.translate(TABLE.centerX, TABLE.centerY);
    ctx.rotate(SEAT_ANGLES[seatIndex]);

    const active = state.turn === seatIndex;
    drawSeatBadge(ctx, player, seatIndex, active, handInfo.visible);
    drawRiverLocal(ctx, player.river || [], seatIndex, highlightRiverPlayer === seatIndex);
    const handRender = drawHandLocal(ctx, player, seatIndex, active, seatIndex === 0 ? interactiveRegions : null);
    drawMeldsLocal(ctx, player, handRender.handWidth);

    ctx.restore();
}

function drawBackground(ctx) {
    const outerGradient = makeGradient(ctx, 0, 0, 0, BOARD_H, [
        [0, '#533a1f'],
        [0.22, '#6a4a26'],
        [1, '#2f2010'],
    ]);
    fillRoundedRect(ctx, TABLE.margin, TABLE.margin, BOARD_W - TABLE.margin * 2, BOARD_H - TABLE.margin * 2, 42, outerGradient, '#a57e49', 2);

    const feltX = TABLE.margin + TABLE.feltInset;
    const feltY = TABLE.margin + TABLE.feltInset;
    const feltW = BOARD_W - (TABLE.margin + TABLE.feltInset) * 2;
    const feltH = BOARD_H - (TABLE.margin + TABLE.feltInset) * 2;
    const feltGradient = makeGradient(ctx, feltX, feltY, feltX, feltY + feltH, [
        [0, '#2b6d4d'],
        [0.35, '#1c5f42'],
        [1, '#144934'],
    ]);
    fillRoundedRect(ctx, feltX, feltY, feltW, feltH, 32, feltGradient, 'rgba(255,255,255,0.08)', 2);

    ctx.save();
    ctx.strokeStyle = 'rgba(255,255,255,0.06)';
    ctx.lineWidth = 2;
    roundRect(ctx, feltX + 32, feltY + 32, feltW - 64, feltH - 64, 22);
    ctx.stroke();

    ctx.setLineDash([14, 18]);
    ctx.beginPath();
    ctx.moveTo(TABLE.centerX - 360, TABLE.centerY);
    ctx.lineTo(TABLE.centerX + 360, TABLE.centerY);
    ctx.moveTo(TABLE.centerX, TABLE.centerY - 360);
    ctx.lineTo(TABLE.centerX, TABLE.centerY + 360);
    ctx.stroke();
    ctx.restore();
}

function renderTable(ctx, width, height, state, options = {}, interactiveRegions = []) {
    const viewport = computeViewport(width, height);
    ctx.save();
    ctx.translate(viewport.offsetX, viewport.offsetY);
    ctx.scale(viewport.scale, viewport.scale);

    drawBackground(ctx);
    drawCenterPanel(ctx, state);

    const players = state.players || [];
    for (let seat = 0; seat < 4; seat++) {
        drawSeat(ctx, players[seat] || {}, seat, state, options, interactiveRegions);
    }

    ctx.restore();
    return viewport;
}

function renderGame(ctx, width, height, state, options = {}) {
    ctx.clearRect(0, 0, width, height);
    if (!state) return;
    renderTable(ctx, width, height, state, options);
}

function renderReplay(ctx, width, height, state, options = {}) {
    renderGame(ctx, width, height, state, { ...options, showAllHands: true });
}

function getHandHitBoxes(width, height, state) {
    if (!state || !state.players || !state.players[0]) return [];
    const player = state.players[0];
    const handInfo = normalizeHand(player);
    if (!handInfo.visible) return [];

    const baseRects = computeHandRects(handInfo.count, TABLE.centerX, TABLE.centerY + LOCAL_LAYOUT.handY, HAND_TILE);
    const viewport = computeViewport(width, height);
    return baseRects.map((rect, index) => {
        const canvasRect = toCanvasRect(rect, viewport);
        return {
            index,
            tile: handInfo.tiles[index],
            x: canvasRect.x,
            y: canvasRect.y,
            w: canvasRect.w,
            h: canvasRect.h,
        };
    });
}

function renderSplash(ctx, width, height, title, subtitle = '') {
    ctx.clearRect(0, 0, width, height);
    const dummyState = {
        game_wind: 'East',
        oya: 0,
        honba: 0,
        kyoutaku: 0,
        river_counter: 70,
        dora: ['1z'],
        turn: -1,
        phase: 16,
        players: [
            { wind: 'East', score: 25000, is_oya: true, river: [], calls: [], hand: [{ count: 13 }], tenpai: [] },
            { wind: 'South', score: 25000, is_oya: false, river: [], calls: [], hand: [{ count: 13 }], tenpai: [] },
            { wind: 'West', score: 25000, is_oya: false, river: [], calls: [], hand: [{ count: 13 }], tenpai: [] },
            { wind: 'North', score: 25000, is_oya: false, river: [], calls: [], hand: [{ count: 13 }], tenpai: [] },
        ],
    };
    renderGame(ctx, width, height, dummyState);

    const viewport = computeViewport(width, height);
    ctx.save();
    ctx.translate(viewport.offsetX + viewport.scale * TABLE.centerX, viewport.offsetY + viewport.scale * (TABLE.centerY + 20));
    fillRoundedRect(ctx, -240, -58, 480, 116, 24, 'rgba(6, 15, 11, 0.72)', 'rgba(255,255,255,0.12)', 2);
    ctx.fillStyle = '#f7f2e7';
    ctx.font = '700 28px "Hiragino Sans GB", "Microsoft YaHei", sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(title, 0, -8);
    if (subtitle) {
        ctx.fillStyle = '#d7ccb7';
        ctx.font = '14px "Hiragino Sans GB", "Microsoft YaHei", sans-serif';
        ctx.fillText(subtitle, 0, 26);
    }
    ctx.restore();
}

window.MahjongRenderer = {
    BOARD_W,
    BOARD_H,
    BOARD_ASPECT,
    renderGame,
    renderReplay,
    renderSplash,
    resizeCanvasToContainer,
    getHandHitBoxes,
    setInvalidateHandler,
};
