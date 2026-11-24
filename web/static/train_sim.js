/* Meridian Circulation's simulation: a line-for-line copy of web/train_sim.py (read that file's notes first). The
   page runs it live to show what happens; the server runs the Python copy on the same actions to score the session,
   so the two must always agree (tests/test_web_train.py checks it). Whole numbers only; one tick is TICK ms.
   Works in the browser (window.TrainSim) and in node (module.exports, for the test). */
(function (root) {
  'use strict';
  var TICK = 50;
  var STABILITY = {start: 100, gold_lost: -10, dark_in: -15, burst: -10, clean: 2};

  function edge(a, b) { return a + '>' + b; }
  function keys(o) { return Object.keys(o).sort(); }

  function newState(plan) {
    return {tick: 0, cycle: 0, cycle_start: 0, pause_until: null, next_id: 0,
            pulses: [], junctions: {}, gates: {}, breath: plan.breath.max, breathing: false,
            stability: STABILITY.start, deviation: false, over: false, end_tick: null,
            gold: 0, gold_in: 0, dark: 0, dark_out: 0, lost: 0, dark_in: 0, bursts: 0,
            rival_dark: 0, rival_out: 0, spawned: 0, events: []};
  }
  function cycleOf(plan, st) { return plan.cycles[st.cycle]; }

  function enterCycle(plan, st, k) {
    var cyc = cycleOf(plan, st);
    st.cycle_start = k; st.spawned = 0; st.pulses = [];
    var junctions = {};
    keys(cyc.nodes).forEach(function (nid) {
      var n = cyc.nodes[nid];
      if (n.type === 'junction') junctions[nid] = st.junctions[nid] != null ? st.junctions[nid] : (n.way || 0);
    });
    st.junctions = junctions;
    var gates = {};
    keys(cyc.nodes).forEach(function (nid) { if (cyc.nodes[nid].type === 'gate') gates[nid] = {open: true, since: 0}; });
    st.gates = gates;
  }
  function bump(st, amount) {
    st.stability = Math.max(0, Math.min(STABILITY.start, st.stability + amount));
    if (st.stability === 0) st.deviation = true;
  }
  function scored(plan, st) { return cycleOf(plan, st).kind === 'cycle'; }

  function resolve(plan, st, p, how) {
    p.done = how;
    var sc = scored(plan, st);
    if (p.dark) {
      if (how === 'out') {
        if (sc) { st.dark_out += 1; bump(st, STABILITY.clean); } else st.rival_out += 1;
      } else if (how === 'in' && sc) { st.dark_in += 1; bump(st, STABILITY.dark_in); }
    } else {
      if (how === 'in') { if (sc) { st.gold_in += 1; bump(st, STABILITY.clean); } }
      else if (sc) {
        st.lost += 1;
        if (how !== 'burst') bump(st, STABILITY.gold_lost);
      }
    }
    st.events.push([st.tick, how, p.id, p.dark ? 1 : 0]);
  }

  function apply(plan, st, action) {
    var what = action[1], which = action[2];
    if (what === 'j' && st.junctions[which] != null) st.junctions[which] = 1 - st.junctions[which];
    else if (what === 'g' && st.gates[which]) {
      var g = st.gates[which];
      if (g.open) { g.open = false; g.since = st.tick; } else openGate(plan, st, which);
    } else if (what === 'b') { if (st.breath > 0) st.breathing = true; }
    else if (what === 'B') st.breathing = false;
  }
  function openGate(plan, st, gid) {
    st.gates[gid].open = true;
    var nxt = cycleOf(plan, st).nodes[gid].out[0], i = 0;
    st.pulses.forEach(function (p) {
      if (p.wait === gid && p.done == null) { p.wait = null; p.edge = edge(gid, nxt); p.pos = -i * plan.gate.gap; i++; }
    });
  }
  function speed(plan, st, p) {
    var s = plan.speed;
    if (plan.injured.indexOf(p.edge) >= 0) s = Math.floor(s * 3 / 5);
    if (st.breathing) s = Math.floor(s * 2 / 5);
    return s;
  }
  function arrive(plan, st, p, nid) {
    var n = cycleOf(plan, st).nodes[nid], t = n.type;
    if (t === 'dantian') { resolve(plan, st, p, 'in'); return false; }
    if (t === 'exit') { resolve(plan, st, p, p.dark ? 'out' : 'wrong'); return false; }
    if (t === 'knot') { resolve(plan, st, p, 'knot'); return false; }
    if (t === 'gate' && !st.gates[nid].open) { p.wait = nid; p.pos = 0; p.waited = st.tick; return false; }
    var nxt = t === 'junction' ? n.out[st.junctions[nid]] : n.out[0];
    p.edge = edge(nid, nxt);
    return true;
  }

  function step(plan, st, actions) {
    if (st.over) return st;
    var k = st.tick;
    st.events = [];
    if (st.pause_until != null && k >= st.pause_until) { st.pause_until = null; st.cycle += 1; enterCycle(plan, st, k); }
    (actions || []).forEach(function (a) { apply(plan, st, a); });
    var b = plan.breath;
    if (st.breathing) { st.breath = Math.max(0, st.breath - b.drain); if (st.breath === 0) st.breathing = false; }
    else st.breath = Math.min(b.max, st.breath + b.refill);
    var cyc = cycleOf(plan, st);
    if (st.pause_until == null) {
      while (st.spawned < cyc.pulses.length && cyc.pulses[st.spawned].at + st.cycle_start <= k) {
        var q = cyc.pulses[st.spawned], src = cyc.nodes[q.src];
        st.pulses.push({id: q.id, dark: q.dark, edge: edge(q.src, src.out[0]), pos: 0, wait: null, waited: 0, done: null});
        st.spawned += 1;
        if (cyc.kind === 'cycle') { if (q.dark) st.dark += 1; else st.gold += 1; } else st.rival_dark += 1;
      }
    }
    st.pulses.forEach(function (p) {
      if (p.done != null || p.wait != null) return;
      p.pos += speed(plan, st, p);
      while (p.done == null && p.wait == null && p.pos >= cyc.lens[p.edge]) {
        p.pos -= cyc.lens[p.edge];
        arrive(plan, st, p, p.edge.split('>')[1]);
      }
    });
    var g = plan.gate;
    keys(st.gates).forEach(function (gid) {
      var gate = st.gates[gid];
      if (gate.open) return;
      var waiting = st.pulses.filter(function (p) { return p.wait === gid && p.done == null; });
      if (!waiting.length) return;
      var oldest = Math.min.apply(null, waiting.map(function (p) { return p.waited; }));
      if (waiting.length >= g.most || k - oldest >= g.hold) {
        waiting.forEach(function (p) { resolve(plan, st, p, 'burst'); });
        st.bursts += scored(plan, st) ? 1 : 0;
        if (scored(plan, st)) bump(st, STABILITY.burst);
        st.events.push([k, 'gate_burst', gid, 0]);
        gate.open = true;
      }
    });
    if (st.deviation && scored(plan, st)) {
      st.over = true; st.end_tick = k; st.events.push([k, 'deviation', '', 0]);
    } else if (st.pause_until == null && st.spawned === cyc.pulses.length &&
               st.pulses.every(function (p) { return p.done != null; })) {
      st.events.push([k, 'cycle_done', cyc.kind, st.cycle]);
      if (st.cycle + 1 < plan.cycles.length) st.pause_until = k + 1 + plan.pause;
      else { st.over = true; st.end_tick = k; }
    }
    if (!st.over && k + 1 >= plan.max_ticks) { st.over = true; st.end_tick = k; }
    st.tick = k + 1;
    return st;
  }

  function start(plan) { var st = newState(plan); enterCycle(plan, st, 0); return st; }

  function run(plan, actions) {
    var st = start(plan), acts = actions.slice().sort(function (a, b) { return a[0] - b[0]; }), i = 0;
    while (!st.over) {
      var mine = [];
      while (i < acts.length && Math.floor(acts[i][0] / TICK) <= st.tick) mine.push(acts[i++]);
      step(plan, st, mine);
    }
    return st;
  }

  function totals(plan) {
    var gold = 0, dark = 0;
    plan.cycles.forEach(function (c) {
      if (c.kind === 'cycle') c.pulses.forEach(function (q) { if (q.dark) dark++; else gold++; });
    });
    return [gold, dark];
  }
  function score(plan, st) {
    var t = totals(plan), gold = t[0], dark = t[1];
    var g = gold ? st.gold_in / gold : 1, stab = st.deviation ? 0 : st.stability, s;
    if (dark) s = 0.60 * g + 0.25 * (st.dark_out / dark) + 0.15 * stab / 100;
    else s = 0.85 * g + 0.15 * stab / 100;
    return Math.round(Math.max(0, Math.min(1, s)) * 10000) / 10000;
  }

  var api = {TICK: TICK, STABILITY: STABILITY, edge: edge, start: start, step: step, run: run, apply: apply,
             totals: totals, score: score};
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.TrainSim = api;
})(this);
