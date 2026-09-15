// =============================================================
//  The Ticket System
//  Mutual Exclusion with a Ticket Dispenser
// =============================================================
/*
 * =============================================================
 * GENERATED ARTIFACT WATERMARK
 * =============================================================
 * SOURCE: AUTO-GENERATED VIA ANTIGRAVITY
 * TIMESTAMP: 2026-09-13T00:07:44+02:00
 * INTEGRITY_CHECKSUM: 4a8b35a3d4550c541422b2178b61996eda0f5413e89be487565ba142f37f793a
 * NOTE: This specification was synthesized and formally verified 
 * automatically. It is not hand-engineered.
 * =============================================================
 *
 * SPECIFICATION SUMMARY:
 * This specification formalizes a Ticket-based Mutual Exclusion System.
 * A fixed number of philosophers compete for exclusive access to a shared 
 * resource (a kitchen). To avoid conflict, a ticket dispenser grants numbered 
 * tickets in sequential order, and only the philosopher whose ticket matches 
 * the current "serving" display may enter.
 *
 * THOUGHT PROCESS (Natural Language -> TOOL Spec):
 * 1. Analyze the NL Request: The prompt described philosophers cycling through 
 *    three states (thinking, hungry, eating) with atomic actions (Request, 
 *    Enter, Leave) accessing a shared ticket dispenser and serving display.
 * 2. Determine TOOL Idioms: By reviewing `hlp.tool` and `seq_insert_capacity.tool`, 
 *    I determined that concurrent systems in TOOL are modeled as discrete 
 *    state-transition functions (`StepProtocol`) wrapped in a temporal `trace`. 
 *    Multiple entities (philosophers) are best modeled using Z3 arrays (`seq[int]`).
 * 3. State Encoding: I mapped the NL state to a `TicketState` struct containing 
 *    the global `ticket` and `serving` integers, an array `states` encoding the 
 *    lifecycle (0=THINKING, 1=HUNGRY, 2=EATING), and `t_local` for drawn tickets.
 * 4. Transition Encoding: The atomic pseudo-code blocks were translated into 
 *    pure functional state-update oracles (`Request`, `Enter`, `Leave`).
 * 5. Invariant Discovery: To prove the NL constraint "dangerous to have more 
 *    than one person in the kitchen" (Mutual Exclusion), structural k-induction 
 *    needs strengthening lemmas. I deduced the mathematical rules governing the 
 *    system: tickets are strictly ascending, unique among active waiters, bounded 
 *    by the global dispenser, and exactly match the serving display when eating.
 * 6. Verification: The safety properties were packaged into a 1-step k-induction 
 *    proof block and verified using the Z3 solver via `verify.py`.
 *
 * DEFINITIONS & VARIABLES:
 * - SysConfig: Static configuration of the system containing `numPhil` (the 
 *   number of philosophers).
 * - TicketState: The dynamic state of the system at any given timestep.
 *    * ticket (int): The next available ticket number to be dispensed.
 *    * serving (int): The ticket number currently allowed to enter the kitchen.
 *    * states (seq[int]): An array tracking the state of each philosopher 
 *      (0 = THINKING, 1 = HUNGRY, 2 = EATING).
 *    * t_local (seq[int]): An array holding the ticket number pulled by each 
 *      hungry or eating philosopher.
 *
 * ENVIRONMENT INPUTS (env):
 * - Cfg(): Provides the static system configuration.
 * - PhilAt(t: timestep): Selects the philosopher ID taking an action at time t.
 * - ActionAt(t: timestep): Selects the action being performed (1 = Request, 
 *   2 = Enter, 3 = Leave, other = No-op).
 *
 * PREDICATES & CONDITIONS:
 * - ValidPhilId: Ensures a given philosopher ID is within the valid range [1, numPhil].
 * - ValidConfig: Ensures the system configuration is valid (e.g., numPhil > 0).
 * - MutualExclusion: The primary safety property. Asserts that no two distinct 
 *   philosophers can be in the EATING state simultaneously.
 * - StateInvariant: Auxiliary inductive invariants required to prove MutualExclusion.
 *   Ensures that:
 *     1) The ticket dispenser counter is always >= the serving counter.
 *     2) Any hungry/eating philosopher holds a ticket between the serving counter 
 *        and the dispenser counter.
 *     3) No two hungry/eating philosophers hold the same ticket number.
 *     4) Any eating philosopher's ticket matches the serving counter exactly.
 * - Valid: A composite predicate combining structural validity, mutual exclusion, 
 *   and all invariants.
 *
 * TRANSITIONS (oracles):
 * - InitState: Initializes the system (ticket=0, serving=0, all states=THINKING).
 * - Request: A THINKING philosopher takes the next available ticket, becoming HUNGRY.
 * - Enter: A HUNGRY philosopher whose ticket matches 'serving' transitions to EATING.
 * - Leave: An EATING philosopher transitions back to THINKING and increments 'serving'.
 * - StepProtocol: The transition function that applies the correct action based on 
 *   environmental inputs.
 *
 * TRACE & PROOF:
 * - TicketTrace: A temporal trace unwinding the sequence of states over time.
 * - The `program` block uses a 1-step k-induction proof to verify that if the 
 *   system is in a valid state at time t-1, applying `StepProtocol` guarantees 
 *   the system remains in a valid state at time t, proving mutual exclusion.
 */

%% declarations

// -------------------------------------------------------------
// Static System Configuration
// -------------------------------------------------------------
struct SysConfig {
    numPhil: int;
}

// -------------------------------------------------------------
// Dynamic Protocol State
// -------------------------------------------------------------
struct TicketState {
    ticket: int;
    serving: int;
    states: seq[int];   // 0 = THINKING, 1 = HUNGRY, 2 = EATING
    t_local: seq[int];  // The ticket held by each philosopher
    is_atomic: bool;    // Stateful atomicity flag
}

// -------------------------------------------------------------
// Environment Inputs
// -------------------------------------------------------------
env Cfg() -> cfg: SysConfig;
env PhilAt(t: timestep) -> philId: int;
env ActionAt(t: timestep) -> action: int;


// =============================================================
//  Basic Configuration Predicates
// =============================================================

oracle ValidPhilId(philId: int, refer cfg: SysConfig) -> res: bool {
    returns res == (
        philId > 0 &&
        philId <= cfg.numPhil
    );
}

oracle ValidConfig(refer cfg: SysConfig) -> res: bool {
    returns res == (
        cfg != null &&
        cfg.numPhil > 0
    );
}

// =============================================================
//  Safety & Invariants
// =============================================================

oracle MutualExclusion(refer s: TicketState, refer cfg: SysConfig) -> res: bool {
    returns res == (
        forall i: int .
            forall j: int .
                !(
                    i > 0 &&
                    i <= cfg.numPhil &&
                    j > 0 &&
                    j <= cfg.numPhil &&
                    s.states[i] == 2 &&
                    s.states[j] == 2
                )
                ||
                i == j
    );
}

// Invariants to help prove mutual exclusion
oracle StateInvariant(refer s: TicketState, refer cfg: SysConfig) -> res: bool {
    returns res == (
        // ticket is always >= serving
        s.ticket >= s.serving
        &&
        // for any hungry or eating philosopher, their ticket is between serving and ticket-1
        (
            forall i: int .
                !(
                    i > 0 &&
                    i <= cfg.numPhil &&
                    (s.states[i] == 1 || s.states[i] == 2)
                )
                ||
                (s.t_local[i] >= s.serving && s.t_local[i] < s.ticket)
        )
        &&
        // no two hungry or eating philosophers have the same ticket
        (
            forall i: int .
                forall j: int .
                    !(
                        i > 0 &&
                        i <= cfg.numPhil &&
                        j > 0 &&
                        j <= cfg.numPhil &&
                        (s.states[i] == 1 || s.states[i] == 2) &&
                        (s.states[j] == 1 || s.states[j] == 2) &&
                        s.t_local[i] == s.t_local[j]
                    )
                    ||
                    i == j
        )
        &&
        // if eating, their ticket is exactly serving
        (
            forall i: int .
                !(
                    i > 0 &&
                    i <= cfg.numPhil &&
                    s.states[i] == 2
                )
                ||
                s.t_local[i] == s.serving
        )
    );
}

oracle Valid(refer s: TicketState, refer cfg: SysConfig) -> res: bool {
    returns res == (
        s != null &&
        ValidConfig(cfg) == true &&
        MutualExclusion(s, cfg) == true &&
        StateInvariant(s, cfg) == true
    );
}

// =============================================================
//  Protocol Transitions
// =============================================================

oracle EnableAtomicity(s: TicketState, cfg: SysConfig) -> ns: TicketState {
    assumes s.is_atomic == false;
    returns ns == mk_TicketState(s.ticket, s.serving, s.states, s.t_local, true);
}

oracle DisableAtomicity(s: TicketState, cfg: SysConfig) -> ns: TicketState {
    assumes s.is_atomic == true;
    returns ns == mk_TicketState(s.ticket, s.serving, s.states, s.t_local, false);
}

oracle InitState(cfg: SysConfig) -> s: TicketState {
    returns s == mk_TicketState(
        0,          // ticket
        0,          // serving
        mk_seq(0),  // states
        mk_seq(0),  // t_local
        false       // is_atomic
    );
}

oracle Request(s: TicketState, cfg: SysConfig, philId: int) -> ns: TicketState {
    assumes s.is_atomic == true;
    assumes ValidPhilId(philId, cfg) == true && s.states[philId] == 0;
    
    returns ns == mk_TicketState(
        s.ticket + 1,
        s.serving,
        update_seq(s.states, philId, 1),
        update_seq(s.t_local, philId, s.ticket),
        s.is_atomic
    );
}

oracle Enter(s: TicketState, cfg: SysConfig, philId: int) -> ns: TicketState {
    assumes s.is_atomic == true;
    assumes ValidPhilId(philId, cfg) == true && s.states[philId] == 1 && s.serving == s.t_local[philId];
    
    returns ns == mk_TicketState(
        s.ticket,
        s.serving,
        update_seq(s.states, philId, 2),
        s.t_local,
        s.is_atomic
    );
}

oracle Leave(s: TicketState, cfg: SysConfig, philId: int) -> ns: TicketState {
    assumes s.is_atomic == true;
    assumes ValidPhilId(philId, cfg) == true && s.states[philId] == 2;
    
    returns ns == mk_TicketState(
        s.ticket,
        s.serving + 1,
        update_seq(s.states, philId, 0),
        s.t_local,
        s.is_atomic
    );
}

// action encoding:
// 1: Request
// 2: Enter
// 3: Leave
// 4: EnableAtomicity
// 5: DisableAtomicity
// otherwise: no-op
oracle StepProtocol(s: TicketState, cfg: SysConfig, philId: int, action: int) -> ns: TicketState {
    returns ns == (
        (
            action == 1 &&
            s.is_atomic == true &&
            ValidPhilId(philId, cfg) == true &&
            s.states[philId] == 0
        ) ? Request(s, cfg, philId) :
        
        (
            action == 2 &&
            s.is_atomic == true &&
            ValidPhilId(philId, cfg) == true &&
            s.states[philId] == 1 &&
            s.serving == s.t_local[philId]
        ) ? Enter(s, cfg, philId) :
        
        (
            action == 3 &&
            s.is_atomic == true &&
            ValidPhilId(philId, cfg) == true &&
            s.states[philId] == 2
        ) ? Leave(s, cfg, philId) :
        
        (
            action == 4 &&
            s.is_atomic == false
        ) ? EnableAtomicity(s, cfg) :
        
        (
            action == 5 &&
            s.is_atomic == true
        ) ? DisableAtomicity(s, cfg) :
        
        s
    );
}

// =============================================================
//  System Trace
// =============================================================

trace TicketTrace(t: timestep) -> s: TicketState {
    init: s == InitState(Cfg());
    step: s == StepProtocol(TicketTrace(t - 1), Cfg(), PhilAt(t), ActionAt(t));
}


// =============================================================
//  Proof Variables
// =============================================================

t: timestep;
sym_cfg: SysConfig;
base: TicketState;
prev: TicketState;
next: TicketState;
phil: int;
act: int;
is_safe: bool;

// =============================================================
//  Preconditions
// =============================================================

%% preconditions

t > 0;
ValidConfig(Cfg()) == true;

// =============================================================
//  Postconditions
// =============================================================

%% postconditions

is_safe == true;

// =============================================================
//  Program
// =============================================================

%% program

sym_cfg := Cfg();
base := TicketTrace(0);
prev := TicketTrace(t - 1);
next := TicketTrace(t);

phil := PhilAt(t);
act := ActionAt(t);


// -------------------------------------------------------------
// Trace unfolding obligations
// -------------------------------------------------------------
assert base == InitState(sym_cfg);
assert next == StepProtocol(prev, sym_cfg, phil, act);


// -------------------------------------------------------------
// Base Case
// -------------------------------------------------------------
assert base != null;
assert base.ticket == 0;
assert base.serving == 0;
assert Valid(base, sym_cfg) == true;


// -------------------------------------------------------------
// Inductive Step
// -------------------------------------------------------------

// Request case
assert !(
    Valid(prev, sym_cfg) == true &&
    act == 1 &&
    prev.is_atomic == true &&
    ValidPhilId(phil, sym_cfg) == true &&
    prev.states[phil] == 0
) || MutualExclusion(next, sym_cfg) == true;

assert !(
    Valid(prev, sym_cfg) == true &&
    act == 1 &&
    prev.is_atomic == true &&
    ValidPhilId(phil, sym_cfg) == true &&
    prev.states[phil] == 0
) || StateInvariant(next, sym_cfg) == true;

// Enter case
assert !(
    Valid(prev, sym_cfg) == true &&
    act == 2 &&
    prev.is_atomic == true &&
    ValidPhilId(phil, sym_cfg) == true &&
    prev.states[phil] == 1 &&
    prev.serving == prev.t_local[phil]
) || MutualExclusion(next, sym_cfg) == true;

assert !(
    Valid(prev, sym_cfg) == true &&
    act == 2 &&
    prev.is_atomic == true &&
    ValidPhilId(phil, sym_cfg) == true &&
    prev.states[phil] == 1 &&
    prev.serving == prev.t_local[phil]
) || StateInvariant(next, sym_cfg) == true;

// Leave case
assert !(
    Valid(prev, sym_cfg) == true &&
    act == 3 &&
    prev.is_atomic == true &&
    ValidPhilId(phil, sym_cfg) == true &&
    prev.states[phil] == 2
) || MutualExclusion(next, sym_cfg) == true;

assert !(
    Valid(prev, sym_cfg) == true &&
    act == 3 &&
    prev.is_atomic == true &&
    ValidPhilId(phil, sym_cfg) == true &&
    prev.states[phil] == 2
) || StateInvariant(next, sym_cfg) == true;

// EnableAtomicity case
assert !(
    Valid(prev, sym_cfg) == true &&
    act == 4 &&
    prev.is_atomic == false
) || MutualExclusion(next, sym_cfg) == true;

assert !(
    Valid(prev, sym_cfg) == true &&
    act == 4 &&
    prev.is_atomic == false
) || StateInvariant(next, sym_cfg) == true;

// DisableAtomicity case
assert !(
    Valid(prev, sym_cfg) == true &&
    act == 5 &&
    prev.is_atomic == true
) || MutualExclusion(next, sym_cfg) == true;

assert !(
    Valid(prev, sym_cfg) == true &&
    act == 5 &&
    prev.is_atomic == true
) || StateInvariant(next, sym_cfg) == true;

// No-op case
assert !(
    Valid(prev, sym_cfg) == true &&
    !(
        act == 1 &&
        prev.is_atomic == true &&
        ValidPhilId(phil, sym_cfg) == true &&
        prev.states[phil] == 0
    ) &&
    !(
        act == 2 &&
        prev.is_atomic == true &&
        ValidPhilId(phil, sym_cfg) == true &&
        prev.states[phil] == 1 &&
        prev.serving == prev.t_local[phil]
    ) &&
    !(
        act == 3 &&
        prev.is_atomic == true &&
        ValidPhilId(phil, sym_cfg) == true &&
        prev.states[phil] == 2
    ) &&
    !(
        act == 4 &&
        prev.is_atomic == false
    ) &&
    !(
        act == 5 &&
        prev.is_atomic == true
    )
) || next == prev;

assert !(
    Valid(prev, sym_cfg) == true &&
    !(
        act == 1 &&
        prev.is_atomic == true &&
        ValidPhilId(phil, sym_cfg) == true &&
        prev.states[phil] == 0
    ) &&
    !(
        act == 2 &&
        prev.is_atomic == true &&
        ValidPhilId(phil, sym_cfg) == true &&
        prev.states[phil] == 1 &&
        prev.serving == prev.t_local[phil]
    ) &&
    !(
        act == 3 &&
        prev.is_atomic == true &&
        ValidPhilId(phil, sym_cfg) == true &&
        prev.states[phil] == 2
    ) &&
    !(
        act == 4 &&
        prev.is_atomic == false
    ) &&
    !(
        act == 5 &&
        prev.is_atomic == true
    )
) || Valid(next, sym_cfg) == true;


// Full trace-step preservation
assert !(
    Valid(prev, sym_cfg) == true
) || Valid(next, sym_cfg) == true;

is_safe := true;
