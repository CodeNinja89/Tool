// ============================================================================
// CHECKSUM: 60fed709dedcc364fa79377faabbc8e0a3778355fce9a972b28343931a1af6b4
// NOTE: This file is GENERATED, NOT ENGINEERED.
// If this file is manually modified, the checksum will become invalid.
// ============================================================================

// ============================================================================
// AI Interpretation of the TOOL Specification
// ============================================================================
// The original `.tool` files describe a reactive finite state machine modeling 
// a ticket-based mutual exclusion protocol.
// 
// Key aspects of the TOOL language interpreted here:
// 1. Functional State: The 'struct' definitions act as immutable records.
// 2. Oracles as Predicates: 'oracle' blocks define pure logical relations or 
//    functions. Our Dafny implementation maps these directly to 'predicate's.
// 3. Environment Non-determinism: The 'env' declarations (Cfg, PhilAt, ActionAt) 
//    represent non-deterministic inputs from the environment at each time step.
// 4. Trace & Induction: The 'trace' recursively unfolds the state over time. 
//    The 'program' block performs a 1-step k-induction proof, asserting that 
//    if invariants hold at step t-1 (prev), applying the transition relation 
//    (StepProtocol) guarantees they hold at step t (next).
// 5. Progress/Liveness: 'ticket_progress.tool' demonstrates that since TOOL 
//    lacks temporal logic (LTL) to prove "eventually" properties natively, it 
//    relies on a ranking function (distance to eating never increases) to 
//    prove bounded progress safety instead.
// ============================================================================
// ============================================================================
// The Ticket System - With Progress Safety
// ============================================================================
// This specification matches `ticket_progress.tool` using exact names for 
// datatypes and functions, and includes a bounded progress safety proof.

// ------------------------------------------------------------------------
// Static System Configuration
// ------------------------------------------------------------------------
datatype SysConfig = SysConfig(
    numPhil: int
)

// ------------------------------------------------------------------------
// Dynamic Protocol State
// ------------------------------------------------------------------------
// 0 = THINKING, 1 = HUNGRY, 2 = EATING
datatype TicketState = TicketState(
    ticket: int,
    serving: int,
    states: seq<int>,
    t_local: seq<int>
)

// ------------------------------------------------------------------------
// Basic Configuration Predicates
// ------------------------------------------------------------------------
predicate ValidPhilId(philId: int, cfg: SysConfig) {
    philId > 0 && philId <= cfg.numPhil
}

predicate ValidConfig(cfg: SysConfig) {
    cfg.numPhil > 0
}

// ------------------------------------------------------------------------
// Safety & Invariants
// ------------------------------------------------------------------------
predicate MutualExclusion(s: TicketState, cfg: SysConfig)
  requires |s.states| == cfg.numPhil + 1
{
    forall i, j :: i > 0 && i <= cfg.numPhil && j > 0 && j <= cfg.numPhil && s.states[i] == 2 && s.states[j] == 2 ==> i == j
}

predicate StateInvariant(s: TicketState, cfg: SysConfig)
  requires |s.states| == cfg.numPhil + 1
  requires |s.t_local| == cfg.numPhil + 1
{
    s.ticket >= s.serving &&
    (forall i :: i > 0 && i <= cfg.numPhil && (s.states[i] == 1 || s.states[i] == 2) ==> s.serving <= s.t_local[i] < s.ticket) &&
    (forall i, j :: i > 0 && i <= cfg.numPhil && j > 0 && j <= cfg.numPhil && i != j && (s.states[i] == 1 || s.states[i] == 2) && (s.states[j] == 1 || s.states[j] == 2) ==> s.t_local[i] != s.t_local[j]) &&
    (forall i :: i > 0 && i <= cfg.numPhil && s.states[i] == 2 ==> s.t_local[i] == s.serving)
}

predicate Valid(s: TicketState, cfg: SysConfig)
{
    ValidConfig(cfg) &&
    |s.states| == cfg.numPhil + 1 &&
    |s.t_local| == cfg.numPhil + 1 &&
    MutualExclusion(s, cfg) &&
    StateInvariant(s, cfg)
}

// ------------------------------------------------------------------------
// Protocol Transitions
// ------------------------------------------------------------------------
predicate InitState(cfg: SysConfig, s: TicketState)
{
    ValidConfig(cfg) &&
    s.ticket == 0 &&
    s.serving == 0 &&
    |s.states| == cfg.numPhil + 1 && (forall i :: 0 <= i <= cfg.numPhil ==> s.states[i] == 0) &&
    |s.t_local| == cfg.numPhil + 1 && (forall i :: 0 <= i <= cfg.numPhil ==> s.t_local[i] == 0)
}

predicate Request(s: TicketState, cfg: SysConfig, philId: int, ns: TicketState)
  requires |s.states| == cfg.numPhil + 1 && |s.t_local| == cfg.numPhil + 1
{
    ValidPhilId(philId, cfg) &&
    s.states[philId] == 0 &&
    ns.ticket == s.ticket + 1 &&
    ns.serving == s.serving &&
    ns.states == s.states[philId := 1] &&
    ns.t_local == s.t_local[philId := s.ticket]
}

predicate Enter(s: TicketState, cfg: SysConfig, philId: int, ns: TicketState)
  requires |s.states| == cfg.numPhil + 1 && |s.t_local| == cfg.numPhil + 1
{
    ValidPhilId(philId, cfg) &&
    s.states[philId] == 1 &&
    s.serving == s.t_local[philId] &&
    ns.ticket == s.ticket &&
    ns.serving == s.serving &&
    ns.states == s.states[philId := 2] &&
    ns.t_local == s.t_local
}

predicate Leave(s: TicketState, cfg: SysConfig, philId: int, ns: TicketState)
  requires |s.states| == cfg.numPhil + 1 && |s.t_local| == cfg.numPhil + 1
{
    ValidPhilId(philId, cfg) &&
    s.states[philId] == 2 &&
    ns.ticket == s.ticket &&
    ns.serving == s.serving + 1 &&
    ns.states == s.states[philId := 0] &&
    ns.t_local == s.t_local
}

predicate StepProtocol(s: TicketState, cfg: SysConfig, philId: int, action: int, ns: TicketState)
  requires |s.states| == cfg.numPhil + 1 && |s.t_local| == cfg.numPhil + 1
{
    if (action == 1 && ValidPhilId(philId, cfg) && s.states[philId] == 0) then Request(s, cfg, philId, ns)
    else if (action == 2 && ValidPhilId(philId, cfg) && s.states[philId] == 1 && s.serving == s.t_local[philId]) then Enter(s, cfg, philId, ns)
    else if (action == 3 && ValidPhilId(philId, cfg) && s.states[philId] == 2) then Leave(s, cfg, philId, ns)
    else ns == s
}

// ------------------------------------------------------------------------
// Progress Safety (Ranking Function)
// ------------------------------------------------------------------------
// Represents the Bounded Progress Safety condition from ticket_progress.tool.
lemma BoundedProgressSafety(prev: TicketState, next: TicketState, sym_cfg: SysConfig, phil: int, act: int, p: int)
  requires Valid(prev, sym_cfg)
  requires StepProtocol(prev, sym_cfg, phil, act, next)
  requires ValidPhilId(p, sym_cfg)
  requires prev.states[p] == 1
  requires |next.states| == sym_cfg.numPhil + 1
  requires next.states[p] == 1
  ensures next.t_local[p] - next.serving <= prev.t_local[p] - prev.serving
{
}
