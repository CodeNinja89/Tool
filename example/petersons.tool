// =============================================================
//  Peterson's Mutual Exclusion — TOOL oracle-based verification
// =============================================================
//
// Models the two-process Peterson protocol as a sequence of
// axiomatic state transitions driven by an external schedule.
//
// Design:
//   - PetersonState struct holds both process states, flags, turn
//   - Each transition is an oracle: takes old state -> returns new state
//   - env NextProcess(time) picks which process steps; constrained to {0,1} by invariant
//   - Loop invariant maintains the Valid predicate (inlined) over all iterations
// =============================================================

%% declarations

// --- Process state constants (constrained in preconditions) ---
Start: int;
Gate: int;
Wait: int;
Critical: int;
Exit: int;

// --- Global protocol state ---
struct PetersonState {
    cs0: int;
    cs1: int;
    f0: bool;
    f1: bool;
    turn: int;
}

// --- Valid predicate (pure oracle, no assumes) ---
// Returns true iff the global state satisfies all Peterson invariants.
oracle Valid(refer s: PetersonState) -> res: bool {
    returns res == (
        // Both processes in valid states
        (s.cs0 >= Start && s.cs0 <= Exit) &&
        (s.cs1 >= Start && s.cs1 <= Exit) &&

        // Mutual exclusion — the core safety property
        (s.cs0 != Critical || s.cs1 != Critical) &&

        // Flag consistency: flag is true iff process past Start
        (s.f0 == (s.cs0 >= Gate)) &&
        (s.f1 == (s.cs1 >= Gate)) &&

        // Turn bounds
        (s.turn >= -1 && s.turn <= 1)
    );
}

// --- Process 0 transition oracles ---
// Each oracle takes the full PetersonState and returns a new state.
// The `assumes` clause guards the precondition; the `returns` clause
// specifies exactly which fields change (others are preserved).

oracle StartToGate(s: PetersonState) -> ns: PetersonState {
    assumes s.cs0 == Start;
    returns  (ns.cs0 == Gate) &&
             (ns.cs1 == s.cs1) &&
             (ns.f0 == true) &&
             (ns.f1 == s.f1) &&
             (ns.turn == s.turn);
}

oracle GateToWait(s: PetersonState) -> ns: PetersonState {
    assumes s.cs0 == Gate;
    returns  (ns.cs0 == Wait) &&
             (ns.cs1 == s.cs1) &&
             (ns.f0 == s.f0) &&
             (ns.f1 == s.f1) &&
             (ns.turn == 1);
}

oracle WaitToCritical(s: PetersonState) -> ns: PetersonState {
    assumes s.cs0 == Wait && (s.turn == 0 || !s.f1);
    returns  (ns.cs0 == Critical) &&
             (ns.cs1 == s.cs1) &&
             (ns.f0 == s.f0) &&
             (ns.f1 == s.f1) &&
             (ns.turn == s.turn);
}

oracle WaitToWait(s: PetersonState) -> ns: PetersonState {
    assumes s.cs0 == Wait && s.f1 && s.turn == 1;
    returns  (ns.cs0 == s.cs0) &&
             (ns.cs1 == s.cs1) &&
             (ns.f0 == s.f0) &&
             (ns.f1 == s.f1) &&
             (ns.turn == s.turn);
}

oracle CriticalToExit(s: PetersonState) -> ns: PetersonState {
    assumes s.cs0 == Critical;
    returns  (ns.cs0 == Exit) &&
             (ns.cs1 == s.cs1) &&
             (ns.f0 == false) &&
             (ns.f1 == s.f1) &&
             (ns.turn == s.turn);
}

oracle ExitToStart(s: PetersonState) -> ns: PetersonState {
    assumes s.cs0 == Exit;
    returns  (ns.cs0 == Start) &&
             (ns.cs1 == s.cs1) &&
             (ns.f0 == s.f0) &&
             (ns.f1 == s.f1) &&
             (ns.turn == s.turn);
}

// --- Process 1 transition oracles (symmetric mirror) ---

oracle P1_StartToGate(s: PetersonState) -> ns: PetersonState {
    assumes s.cs1 == Start;
    returns  (ns.cs0 == s.cs0) &&
             (ns.cs1 == Gate) &&
             (ns.f0 == s.f0) &&
             (ns.f1 == true) &&
             (ns.turn == s.turn);
}

oracle P1_GateToWait(s: PetersonState) -> ns: PetersonState {
    assumes s.cs1 == Gate;
    returns  (ns.cs0 == s.cs0) &&
             (ns.cs1 == Wait) &&
             (ns.f0 == s.f0) &&
             (ns.f1 == s.f1) &&
             (ns.turn == 0);
}

oracle P1_WaitToCritical(s: PetersonState) -> ns: PetersonState {
    assumes s.cs1 == Wait && (s.turn == 1 || !s.f0);
    returns  (ns.cs0 == s.cs0) &&
             (ns.cs1 == Critical) &&
             (ns.f0 == s.f0) &&
             (ns.f1 == s.f1) &&
             (ns.turn == s.turn);
}

oracle P1_WaitToWait(s: PetersonState) -> ns: PetersonState {
    assumes s.cs1 == Wait && s.f0 && s.turn == 0;
    returns  (ns.cs0 == s.cs0) &&
             (ns.cs1 == s.cs1) &&
             (ns.f0 == s.f0) &&
             (ns.f1 == s.f1) &&
             (ns.turn == s.turn);
}

oracle P1_CriticalToExit(s: PetersonState) -> ns: PetersonState {
    assumes s.cs1 == Critical;
    returns  (ns.cs0 == s.cs0) &&
             (ns.cs1 == Exit) &&
             (ns.f0 == s.f0) &&
             (ns.f1 == false) &&
             (ns.turn == s.turn);
}

oracle P1_ExitToStart(s: PetersonState) -> ns: PetersonState {
    assumes s.cs1 == Exit;
    returns  (ns.cs0 == s.cs0) &&
             (ns.cs1 == Start) &&
             (ns.f0 == s.f0) &&
             (ns.f1 == s.f1) &&
             (ns.turn == s.turn);
}

// --- Scheduler env function ---
// An unconstrained environment function that picks which process runs next.
// The loop invariant constrains externalTurn to {0, 1}.
env NextProcess(time: int) -> p: int;

// --- Global variables ---
state: PetersonState;
externalTurn: int;
i: int;
steps: int;

%% preconditions

Start == 0;
Gate == 1;
Wait == 2;
Critical == 3;
Exit == 4;

// Initial state: both processes at Start, flags off, turn = -1
state.cs0 == Start;
state.cs1 == Start;
state.f0 == false;
state.f1 == false;
state.turn == -1;
externalTurn == 0;
i == 0;
steps == 10;

%% postconditions

// Mutual exclusion holds after the simulation:
// it is impossible for both processes to be in Critical.
!(state.cs0 == Critical && state.cs1 == Critical);

%% program

while (i < steps) invariant (
    // Valid predicate inlined: state bounds, mutual exclusion, flag consistency, turn bounds
    (state.cs0 >= Start && state.cs0 <= Exit) &&
    (state.cs1 >= Start && state.cs1 <= Exit) &&
    (state.cs0 != Critical || state.cs1 != Critical) &&
    (state.f0 == (state.cs0 >= Gate)) &&
    (state.f1 == (state.cs1 >= Gate)) &&
    (state.turn >= -1 && state.turn <= 1) &&
    // Scheduler constraint: externalTurn is always {0, 1}
    (externalTurn == 0 || externalTurn == 1)
) {

    // Determine which process runs this iteration via environment function
    externalTurn := NextProcess(i);

    // ---- Process 0 transitions (scheduled when externalTurn == 0) ----
    if (externalTurn == 0) {
        if (state.cs0 == Start) {
            state := StartToGate(state);
        } else {
            if (state.cs0 == Gate) {
                state := GateToWait(state);
            } else {
                if (state.cs0 == Wait && (state.turn == 0 || !state.f1)) {
                    state := WaitToCritical(state);
                } else {
                    if (state.cs0 == Critical) {
                        state := CriticalToExit(state);
                    } else {
                        if (state.cs0 == Exit) {
                            state := ExitToStart(state);
                        } else {
                            // cs0 == Wait but cannot enter: spin in place
                            state := WaitToWait(state);
                        }
                    }
                }
            }
        }
    } else {
        // ---- Process 1 transitions (scheduled when externalTurn == 1) ----
        if (state.cs1 == Start) {
            state := P1_StartToGate(state);
        } else {
            if (state.cs1 == Gate) {
                state := P1_GateToWait(state);
            } else {
                if (state.cs1 == Wait && (state.turn == 1 || !state.f0)) {
                    state := P1_WaitToCritical(state);
                } else {
                    if (state.cs1 == Critical) {
                        state := P1_CriticalToExit(state);
                    } else {
                        if (state.cs1 == Exit) {
                            state := P1_ExitToStart(state);
                        } else {
                            // cs1 == Wait but cannot enter: spin in place
                            state := P1_WaitToWait(state);
                        }
                    }
                }
            }
        }
    }

    i := i + 1;
}
