// Pulsschleier-Rendering. Portiert aus dem artiq-Modul "lifeline"
// (~/Dokumente/04_Projekte/artiq/lifeline_v3.html) - dort mit Reglern fuer
// Seed/Dichte/Palette, hier mit festen Werten, damit Form und Farben nicht
// bei jedem Laden zufaellig ausfallen.
//
// Ersetzt nicht die CSS-Drift aus .pulse-bg (app.css) - die drei <i>-Kopien,
// ihre Perioden und die Theme-Maske bleiben unveraendert. Nur die Bildquelle
// ist jetzt ein hier erzeugtes Data-URI statt der Datei pulse.webp: einmal
// pro Seitenaufruf gezeichnet, dann wie zuvor per CSS bewegt.
//
// Dieses Skript setzt nur die Quelle (--pulse-src auf .pulse-bg), nicht wie
// sie benutzt wird. Ob sie als background-image oder als mask-image vor
// einem Verlauf erscheint, ist eine Theme-Frage und steht in app.css
// (EIP-T-109 - vorher setzte apply() beides direkt an den <i>-Elementen und
// loeschte damit in beiden Themes den groessten Teil des Motivs).
(function () {
  "use strict";

  const PHI = (1 + Math.sqrt(5)) / 2;

  // Feste Werte statt Regler. Seed/Dichte/Verbindungen/Chaos orientieren sich
  // an dem Referenzbild, aus dem app/static/pulse.webp seinerzeit exportiert
  // wurde (artiq_pulse_s5232065_..._x22.png).
  const SEED = 5232065;
  const DENSITY = 900;
  const CONNECTIONS = 10;
  const CHAOS = 22;

  // Kern weiss-lavendel, Hauptfaser blasses Periwinkle, seltene Akzente in
  // Violett/Teal/Amber - siehe eid-poll-visual-refresh-constraints (Memory).
  const PALETTE = ["#f3f0ff", "#c9bdf0", "#9a7de0", "#4fb3a0", "#e0a75a"];

  // Interne Aufloesung des erzeugten Bildes, unabhaengig vom Viewport - die
  // CSS-Regel `background: ... / 100% 100%` streckt es ohnehin passend. Nah
  // an der Anzeigeflaeche (Band, kein Quadrat): frueher 1600x420 gegen ein
  // ~198px hohes Band gestreckt, das stauchte jede Linie fast auf null und
  // liess ein Fuenftel des Bildes ungenutzt (EIP-T-110).
  const RENDER_W = 1600;
  const RENDER_H = 220;
  const EXPORT_SCALE = 2;

  // Fester Massstab fuer Knoten, Streuung und Linien - haengt bewusst nicht
  // an Math.min(drawW, drawH). Bei einer 1600x420-Flaeche bestimmte die
  // Hoehe (der kurze Rand) den Massstab, und alles klebte am Kurvenverlauf
  // statt ein Geflecht zu bilden (EIP-T-110). generateLifeLine() und
  // drawLifeLine() rechnen beide mit demselben Wert - vorher liefen sie mit
  // 0.024 bzw. 0.028 auseinander.
  const UNIT = 15;
  // Mindestbreite in Canvas-Pixeln, damit duenne Verbindungen nicht im
  // Antialiasing verschwinden (EIP-T-110).
  const MIN_LINE_WIDTH = 0.5;

  function mulberry32(seed) {
    seed = seed >>> 0;
    return function () {
      seed = (seed + 0x6d2b79f5) >>> 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function hexToRgb(hex) {
    const h = hex.replace("#", "");
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
  }

  // Puls-Gesetz: eine P-QRS-T-Komplexe aus Gauss-Summen, mittig auf der
  // Nulllinie. Details und Herleitung: artiq lifeline.info.md.
  const COMPLEX_SPAN = 1 / PHI;
  const COMPLEX_START = (1 - COMPLEX_SPAN) / 2;

  function ecgWave(bt) {
    const g = (x, mu, sigma, amp) => amp * Math.exp(-((x - mu) ** 2) / (2 * sigma * sigma));
    return (
      g(bt, 0.14, 0.035, 0.07) +
      g(bt, 0.28, 0.02, -0.06) +
      g(bt, 0.36, 0.026, 1.0) +
      g(bt, 0.44, 0.03, -0.55) +
      g(bt, 0.66, 0.055, 0.2)
    );
  }

  function buildBeats(rng, chaosFactor) {
    const widthRatio = [PHI, 1];
    const ampRatio = [1, 1 / PHI];
    const jittered = widthRatio.map((wr) => wr * (1 + (rng() - 0.5) * 0.3 * chaosFactor));
    const totalW = jittered.reduce((a, b) => a + b, 0);
    let cursor = 0;
    return jittered.map((w, i) => {
      const beat = { start: cursor, width: w / totalW, amp: ampRatio[i] * (1 + (rng() - 0.5) * 0.35 * chaosFactor) };
      cursor += beat.width;
      return beat;
    });
  }

  function ecgValue(t, beats) {
    const u = (t - COMPLEX_START) / COMPLEX_SPAN;
    if (u < 0 || u >= 1) return 0;
    for (const beat of beats) {
      if (u >= beat.start && u < beat.start + beat.width) {
        return ecgWave((u - beat.start) / beat.width) * beat.amp;
      }
    }
    return 0;
  }

  const CURVE_RES = 3000;

  function traceCurve(beats, drawW, centerY, ampY) {
    const pts = new Array(CURVE_RES + 1);
    for (let i = 0; i <= CURVE_RES; i++) {
      const t = i / CURVE_RES;
      const v = ecgValue(t, beats);
      pts[i] = { x: t * drawW, y: centerY - v * ampY, v };
    }
    const cum = new Float64Array(CURVE_RES + 1);
    for (let i = 1; i <= CURVE_RES; i++) {
      cum[i] = cum[i - 1] + Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y);
    }
    return { pts, cum, length: cum[CURVE_RES] };
  }

  function sampleByArcLength(curve, count) {
    const out = [];
    let idx = 1;
    for (let k = 0; k < count; k++) {
      const target = (k / (count - 1)) * curve.length;
      while (idx < CURVE_RES && curve.cum[idx] < target) idx++;
      const c0 = curve.cum[idx - 1];
      const c1 = curve.cum[idx];
      const f = c1 > c0 ? (target - c0) / (c1 - c0) : 0;
      const a = curve.pts[idx - 1];
      const b = curve.pts[idx];
      out.push({ x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f, v: a.v + (b.v - a.v) * f });
    }
    return out;
  }

  function generateLifeLine(seed, density, avgConnections, chaos, drawW, drawH) {
    const rng = mulberry32(seed);
    const unit = UNIT;
    // Naeher an der Mitte und mit mehr Ausschlag als vorher (0.56/0.38): die
    // Kurve allein soll schon einen Grossteil der Bildhoehe erreichen, sonst
    // bleibt der Rand leer, egal wie weit die Satellitenknoten streuen
    // (EIP-T-110, Akzeptanzkriterium getbbox >= 85 %).
    const centerY = drawH * 0.5;
    const ampY = drawH * 0.43;
    const nodes = [];
    const connections = [];
    const chaosFactor = chaos / 100;
    const beats = buildBeats(rng, chaosFactor);
    const curve = traceCurve(beats, drawW, centerY, ampY);

    const numMain = Math.max(80, Math.min(Math.round(density * 0.24), 450));
    const weights = [];
    for (const s of sampleByArcLength(curve, numMain)) {
      const intensity = Math.min(1, Math.abs(s.v));
      const noise = (rng() - 0.5) * 0.012 * chaosFactor * ampY;
      const size = unit * (0.09 + rng() * 0.16) * (0.6 + intensity * 0.9);
      nodes.push({ x: s.x, y: s.y + noise, size, glow: 0.1 + rng() * 0.22 + intensity * 0.2, clusterIdx: 0, intensity });
      weights.push(0.12 + intensity);
    }

    const cum = [];
    let wAcc = 0;
    for (const w of weights) {
      wAcc += w;
      cum.push(wAcc);
    }
    function pickWeighted() {
      const r = rng() * wAcc;
      let lo = 0;
      let hi = cum.length - 1;
      while (lo < hi) {
        const mid = (lo + hi) >> 1;
        if (cum[mid] < r) lo = mid + 1;
        else hi = mid;
      }
      return lo;
    }

    // Vertikal absichtlich weiter als horizontal: Ohne das haengen die
    // Satellitenknoten an der Kurve wie Rauhreif und das Bild bleibt eine
    // Linie mit Funken. VERTICAL_REACH ist keine CSS-Kompensation (die
    // Renderflaeche liegt jetzt selbst nah am Bandformat), sondern schafft
    // das Geflecht abseits der Kurve, das der Kommentar in app.css verspricht
    // (EIP-T-110).
    const VERTICAL_REACH = 2.2;
    for (let i = numMain; i < density; i++) {
      const parent = nodes[pickWeighted()];
      const angle = rng() * Math.PI * 2;
      const reach = unit * (0.9 + 2.8 * parent.intensity) * (0.5 + chaosFactor);
      const dist = reach * Math.sqrt(rng());
      const stretch = (1 + 1.6 * parent.intensity) * VERTICAL_REACH;
      const x = parent.x + Math.cos(angle) * dist;
      const y = parent.y + Math.sin(angle) * dist * stretch;
      const size = parent.size * (0.2 + rng() * 0.55);
      nodes.push({
        x,
        y,
        size,
        glow: parent.glow * (0.35 + rng() * 0.5),
        clusterIdx: parent.clusterIdx + 1 + Math.floor(rng() * 2),
        intensity: parent.intensity,
      });
    }

    const maxLink = unit * 3.4;
    const grid = new Map();
    const cellKey = (gx, gy) => gx + ":" + gy;
    nodes.forEach((n, i) => {
      const k = cellKey(Math.floor(n.x / maxLink), Math.floor(n.y / maxLink));
      let arr = grid.get(k);
      if (!arr) {
        arr = [];
        grid.set(k, arr);
      }
      arr.push(i);
    });

    for (let i = 0; i < nodes.length; i++) {
      const nodeA = nodes[i];
      const gx = Math.floor(nodeA.x / maxLink);
      const gy = Math.floor(nodeA.y / maxLink);
      const cand = [];
      for (let ox = -1; ox <= 1; ox++)
        for (let oy = -1; oy <= 1; oy++) {
          const arr = grid.get(cellKey(gx + ox, gy + oy));
          if (!arr) continue;
          for (const j of arr) {
            if (j === i) continue;
            const d = Math.hypot(nodes[j].x - nodeA.x, nodes[j].y - nodeA.y);
            if (d <= maxLink) cand.push({ node: nodes[j], dist: d });
          }
        }
      cand.sort((a, b) => a.dist - b.dist);

      const numConns = Math.max(2, Math.min(30, avgConnections + Math.floor((rng() - 0.5) * 6)));
      for (let j = 0; j < Math.min(numConns, cand.length); j++) {
        const skip = Math.floor(rng() * (2 + chaosFactor * 3));
        const pick = cand[Math.min(j + skip, cand.length - 1)];
        const near = 1 - Math.min(1, pick.dist / maxLink);
        const thickness = Math.max(MIN_LINE_WIDTH, unit * 0.02 * near * (0.4 + rng() * 0.6));
        const alpha = 0.03 + 0.4 * near * (0.6 + rng() * 0.4);
        connections.push({
          a: nodeA,
          b: pick.node,
          width: thickness,
          alpha,
          clusterIdx: (nodeA.clusterIdx + pick.node.clusterIdx) / 2,
          dist: pick.dist,
        });
      }
    }

    for (let i = 0; i < avgConnections * 4; i++) {
      const idxA = Math.floor(rng() * nodes.length);
      const idxB = Math.floor(rng() * nodes.length);
      if (idxA === idxB) continue;
      const dist = Math.hypot(nodes[idxB].x - nodes[idxA].x, nodes[idxB].y - nodes[idxA].y);
      if (dist < Math.max(drawW, drawH) * 0.15) continue;
      connections.push({
        a: nodes[idxA],
        b: nodes[idxB],
        width: Math.max(MIN_LINE_WIDTH, unit * 0.012 * (0.3 + rng() * 0.7)),
        alpha: 0.02 + rng() * 0.15,
        clusterIdx: (nodes[idxA].clusterIdx + nodes[idxB].clusterIdx) / 2,
        dist,
      });
    }

    connections.sort((a, b) => b.width * b.alpha - a.width * a.alpha);
    return { nodes, connections, curve };
  }

  function lineColor(clusterIdx, alpha) {
    const pool = PALETTE;
    const n = pool.length;
    const t = (clusterIdx * (1 / PHI)) % 1;
    const weights = Array.from({ length: n }, (_, i) => Math.pow(1 / PHI, i));
    const total = weights.reduce((a, b) => a + b, 0);
    let cumsum = 0;
    let palIdx = n - 1;
    for (let i = 0; i < n; i++) {
      cumsum += weights[i] / total;
      if (t < cumsum) {
        palIdx = i;
        break;
      }
    }
    const [r, g, b] = hexToRgb(pool[palIdx]);
    return `rgba(${r},${g},${b},${alpha})`;
  }

  function nodeColorRgb(clusterIdx) {
    return hexToRgb(PALETTE[Math.max(0, Math.min(Math.floor(clusterIdx), PALETTE.length - 1))]);
  }

  // Vier Lagen von breit/schwach nach duenn/hell, additiv gemischt - siehe
  // artiq lifeline.info.md. Auf dem transparenten Hintergrund hier bleibt nur
  // der Alphakanal stehen, keine eigene Flaechenfarbe.
  const CURVE_LAYERS = [
    { w: 1.1, a: 0.045 },
    { w: 0.42, a: 0.09 },
    { w: 0.15, a: 0.3 },
    { w: 0.05, a: 0.85 },
  ];

  function strokeCurve(ctx, curve, unit) {
    const [r, g, b] = nodeColorRgb(0);
    ctx.save();
    CURVE_LAYERS.forEach((layer, l) => {
      ctx.globalCompositeOperation = l < CURVE_LAYERS.length - 1 ? "lighter" : "source-over";
      ctx.beginPath();
      ctx.moveTo(curve.pts[0].x, curve.pts[0].y);
      for (let i = 1; i <= CURVE_RES; i++) ctx.lineTo(curve.pts[i].x, curve.pts[i].y);
      ctx.strokeStyle = `rgba(${r},${g},${b},${layer.a})`;
      ctx.lineWidth = Math.max(MIN_LINE_WIDTH, unit * layer.w);
      ctx.stroke();
    });
    ctx.restore();
  }

  function drawLifeLine(ctx, data, unit, drawRng) {
    const { nodes, connections, curve } = data;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    if (curve) strokeCurve(ctx, curve, unit);

    for (const conn of connections) {
      const a = conn.a;
      const b = conn.b;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const length = Math.hypot(dx, dy);
      const shouldCurve = length > unit && drawRng() < 0.6;
      ctx.beginPath();
      if (shouldCurve && length > 5) {
        const midX = (a.x + b.x) * 0.5;
        const midY = (a.y + b.y) * 0.5;
        const curveAmount = length * 0.06 * (drawRng() - 0.5) * 2;
        ctx.moveTo(a.x, a.y);
        ctx.quadraticCurveTo(
          midX + curveAmount * Math.sin(Math.atan2(dy, dx)),
          midY - curveAmount * Math.cos(Math.atan2(dy, dx)),
          b.x,
          b.y
        );
      } else {
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
      }
      ctx.strokeStyle = lineColor(conn.clusterIdx, conn.alpha);
      ctx.lineWidth = conn.width;
      ctx.stroke();
    }

    for (const node of nodes) {
      const [r, g, b] = nodeColorRgb(node.clusterIdx);
      const glowA = node.glow * 0.6;
      const rad = node.size * 5;
      const gradient = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, rad);
      gradient.addColorStop(0, `rgba(${r},${g},${b},${glowA})`);
      gradient.addColorStop(0.45, `rgba(${r},${g},${b},${glowA * 0.35})`);
      gradient.addColorStop(1, `rgba(${r},${g},${b},0)`);
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      ctx.beginPath();
      ctx.arc(node.x, node.y, rad, 0, Math.PI * 2);
      ctx.fillStyle = gradient;
      ctx.fill();
      ctx.restore();
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.size, 0, Math.PI * 2);
      ctx.fillStyle = `rgb(${r},${g},${b})`;
      ctx.fill();
    }
  }

  function renderDataUrl() {
    const canvas = document.createElement("canvas");
    canvas.width = RENDER_W * EXPORT_SCALE;
    canvas.height = RENDER_H * EXPORT_SCALE;
    const ctx = canvas.getContext("2d");
    ctx.scale(EXPORT_SCALE, EXPORT_SCALE);
    const data = generateLifeLine(SEED, DENSITY, CONNECTIONS, CHAOS, RENDER_W, RENDER_H);
    const drawRng = mulberry32(SEED + 12345);
    drawLifeLine(ctx, data, UNIT, drawRng);
    return canvas.toDataURL("image/png");
  }

  function apply() {
    const container = document.querySelector(".pulse-bg");
    if (!container) return;
    const url = `url("${renderDataUrl()}")`;
    // Nur die Quelle wird hier gesetzt - ob sie als background-image (dunkel)
    // oder als mask-image vor einem Verlauf (hell) verwendet wird, entscheidet
    // app.css ueber --pulse-src. Die Variable vererbt sich auf die drei <i>,
    // ein eigenes style-Attribut je Kopie ist nicht mehr noetig (EIP-T-109:
    // ein Inline-style hier schlug jede Stylesheet-Regel, auch die Verlaufs-
    // Maske des hellen Themes).
    container.style.setProperty("--pulse-src", url);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", apply);
  } else {
    apply();
  }
})();
