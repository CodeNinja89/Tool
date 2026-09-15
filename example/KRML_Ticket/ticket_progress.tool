// =============================================================
//  The Ticket System - With Progress Safety
// =============================================================
/*
 * =============================================================
 * GENERATED ARTIFACT WATERMARK
 * =============================================================
 * SOURCE: AUTO-GENERATED VIA ANTIGRAVITY
 * TIMESTAMP: 2026-09-12T21:55:39.688888+00:00
 * INTEGRITY_CHECKSUM: 85fac77aca4c4f8443a8e14bac11a04a482f0a43123133271604c900934f0de5
 * NOTE: This specification was synthesized and formally verified 
 * automatically. It is not hand-engineered.
 * =============================================================
 *
 * SPECIFICATION SUMMARY:
 * This specification adds a bounded progress (ranking function)
 * safety refinement to the Ticket-based Mutual Exclusion System.
 * It formally verifies that the distance between a hungry
 * philosopher's ticket and the serving counter never increases.
 *
 * This provides the inductive core for a liveness proof, 
 * asserting that waiting processes do not move backwards in
 * priority.
 */


%% declarations

struct SysConfig {
    numPhil: int;
}

struct TicketState {
    ticket: int;
    serving: int;
    states: seq[int];   // 0 = THINKING, 1 = HUNGRY, 2 = EATING
    t_local: seq[int];  // The ticket held by each philosopher
}

env Cfg() -> cfg: SysConfig;
env PhilAt(t: timestep) -> philId: int;
env ActionAt(t: timestep) -> action: int;

oracle ValidPhilId(philId: int, refer cfg: SysConfig) -> res: bool {
    returns res == (philId > 0 && philId <= cfg.numPhil);
}

oracle ValidConfig(refer cfg: SysConfig) -> res: bool {
    returns res == (cfg != null && cfg.numPhil > 0);
}

oracle MutualExclusion(refer s: TicketState, refer cfg: SysConfig) -> res: bool {
    returns res == (
        forall i: int . forall j: int .
            !(i > 0 && i <= cfg.numPhil && j > 0 && j <= cfg.numPhil && s.states[i] == 2 && s.states[j] == 2) || i == j
    );
}

oracle StateInvariant(refer s: TicketState, refer cfg: SysConfig) -> res: bool {
    returns res == (
        s.ticket >= s.serving &&
        (forall i: int . !(i > 0 && i <= cfg.numPhil && (s.states[i] == 1 || s.states[i] == 2)) || (s.t_local[i] >= s.serving && s.t_local[i] < s.ticket)) &&
        (forall i: int . forall j: int . !(i > 0 && i <= cfg.numPhil && j > 0 && j <= cfg.numPhil && (s.states[i] == 1 || s.states[i] == 2) && (s.states[j] == 1 || s.states[j] == 2) && s.t_local[i] == s.t_local[j]) || i == j) &&
        (forall i: int . !(i > 0 && i <= cfg.numPhil && s.states[i] == 2) || s.t_local[i] == s.serving)
    );
}

oracle Valid(refer s: TicketState, refer cfg: SysConfig) -> res: bool {
    returns res == (s != null && ValidConfig(cfg) == true && MutualExclusion(s, cfg) == true && StateInvariant(s, cfg) == true);
}


oracle EnableAtomicity() -> ok: bool {
    returns ok == true;
}

oracle DisableAtomicity() -> ok: bool {
    returns ok == true;
}

oracle InitState(cfg: SysConfig) -> s: TicketState {
    returns s == mk_TicketState(0, 0, mk_seq(0), mk_seq(0));
}

oracle Request(s: TicketState, cfg: SysConfig, philId: int) -> ns: TicketState {
    assumes EnableAtomicity() == true;
    assumes ValidPhilId(philId, cfg) == true && s.states[philId] == 0;
    
    returns ns == (
        DisableAtomicity() == true ?
        mk_TicketState(s.ticket + 1, s.serving, update_seq(s.states, philId, 1), update_seq(s.t_local, philId, s.ticket)) : s
    );
}

oracle Enter(s: TicketState, cfg: SysConfig, philId: int) -> ns: TicketState {
    assumes EnableAtomicity() == true;
    assumes ValidPhilId(philId, cfg) == true && s.states[philId] == 1 && s.serving == s.t_local[philId];
    
    returns ns == (
        DisableAtomicity() == true ?
        mk_TicketState(s.ticket, s.serving, update_seq(s.states, philId, 2), s.t_local) : s
    );
}

oracle Leave(s: TicketState, cfg: SysConfig, philId: int) -> ns: TicketState {
    assumes EnableAtomicity() == true;
    assumes ValidPhilId(philId, cfg) == true && s.states[philId] == 2;
    
    returns ns == (
        DisableAtomicity() == true ?
        mk_TicketState(s.ticket, s.serving + 1, update_seq(s.states, philId, 0), s.t_local) : s
    );
}

oracle StepProtocol(s: TicketState, cfg: SysConfig, philId: int, action: int) -> ns: TicketState {
    returns ns == (
        (action == 1 && ValidPhilId(philId, cfg) == true && s.states[philId] == 0) ? Request(s, cfg, philId) :
        (action == 2 && ValidPhilId(philId, cfg) == true && s.states[philId] == 1 && s.serving == s.t_local[philId]) ? Enter(s, cfg, philId) :
        (action == 3 && ValidPhilId(philId, cfg) == true && s.states[philId] == 2) ? Leave(s, cfg, philId) : s
    );
}

trace TicketTrace(t: timestep) -> s: TicketState {
    init: s == InitState(Cfg());
    step: s == StepProtocol(TicketTrace(t - 1), Cfg(), PhilAt(t), ActionAt(t));
}

t: timestep;
sym_cfg: SysConfig;
base: TicketState;
prev: TicketState;
next: TicketState;
phil: int;
act: int;
is_safe: bool;

%% preconditions

t > 0;
ValidConfig(Cfg()) == true;

%% postconditions

is_safe == true;

%% program

sym_cfg := Cfg();
base := TicketTrace(0);
prev := TicketTrace(t - 1);
next := TicketTrace(t);
phil := PhilAt(t);
act := ActionAt(t);

assert base == InitState(sym_cfg);
assert next == StepProtocol(prev, sym_cfg, phil, act);

// Assume inductive hypothesis
fact (Valid(prev, sym_cfg) == true);

// -------------------------------------------------------------
// NEW REFINEMENT: Bounded Progress Safety (Ranking function)
// -------------------------------------------------------------
// We cannot prove "eventually eats" without LTL. 
// But we CAN prove that while a philosopher is hungry, 
// their distance to eating (t_local - serving) NEVER INCREASES.

assert (
    forall p: int . 
        !(
            ValidPhilId(p, sym_cfg) == true && 
            prev.states[p] == 1 && 
            next.states[p] == 1
        ) || 
        ( (next.t_local[p] - next.serving) <= (prev.t_local[p] - prev.serving) )
);

is_safe := true;
