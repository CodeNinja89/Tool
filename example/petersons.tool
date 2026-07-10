// =============================================================
//  Peterson's Mutual Exclusion — TOOL oracle-based verification
// =============================================================
//
// Models the two-process Peterson protocol as a sequence of
// axiomatic state transitions driven by an external schedule.
//
// Design:
//   - cs0, cs1 : per-process states (Start/Gate/Wait/Critical/Exit)
//   - f0,  f1  : entry flags
//   - turn     : shared turn variable (-1 initially, then {0,1})
//   - externalTurn : unconstrained scheduler choice each iteration
//
// Each state transition is an oracle (axiomatic function). The
// `assumes` clause guards the precondition; the `returns` clause
// specifies which fields change.  In the loop body, if-else chains
// dispatch to exactly one transition per scheduled process.
//
// We prove by induction that the Valid invariant is maintained
// throughout, which includes mutual exclusion: both processes can
// never be in Critical simultaneously.
// =============================================================

%% declarations

// --- Process state constants (constrained in preconditions) ---
Start: int;
Gate: int;
Wait: int;
Critical: int;
Exit: int;

// --- State struct for the Valid predicate ---
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
// Each oracle takes the current state fields and returns the new value
// for exactly one field. The `assumes` clause is checked at each call
// site; the `returns` clause is added as a solver axiom.

oracle StartToGate_cs0(cs0: int) -> ncs0: int {
    assumes cs0 == Start;
    returns ncs0 == Gate;
}

oracle GateToWait_cs0(cs0: int) -> ncs0: int {
    assumes cs0 == Gate;
    returns ncs0 == Wait;
}

oracle WaitToCritical_cs0(cs0: int, turn: int, f1: bool) -> ncs0: int {
    assumes cs0 == Wait && (turn == 0 || !f1);
    returns ncs0 == Critical;
}

oracle CriticalToExit_cs0(cs0: int) -> ncs0: int {
    assumes cs0 == Critical;
    returns ncs0 == Exit;
}

oracle ExitToStart_cs0(cs0: int) -> ncs0: int {
    assumes cs0 == Exit;
    returns ncs0 == Start;
}

// --- Process 1 transition oracles (symmetric mirror) ---

oracle P1_StartToGate_cs1(cs1: int) -> ncs1: int {
    assumes cs1 == Start;
    returns ncs1 == Gate;
}

oracle P1_GateToWait_cs1(cs1: int) -> ncs1: int {
    assumes cs1 == Gate;
    returns ncs1 == Wait;
}

oracle P1_WaitToCritical_cs1(cs1: int, turn: int, f0: bool) -> ncs1: int {
    assumes cs1 == Wait && (turn == 1 || !f0);
    returns ncs1 == Critical;
}

oracle P1_CriticalToExit_cs1(cs1: int) -> ncs1: int {
    assumes cs1 == Critical;
    returns ncs1 == Exit;
}

oracle P1_ExitToStart_cs1(cs1: int) -> ncs1: int {
    assumes cs1 == Exit;
    returns ncs1 == Start;
}

// --- Global state variables ---
cs0: int;
cs1: int;
f0: bool;
f1: bool;
turn: int;
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
cs0 == Start;
cs1 == Start;
f0 == false;
f1 == false;
turn == -1;
i == 0;
steps == 10;

%% postconditions

// Mutual exclusion holds after the simulation:
// it is impossible for both processes to be in Critical.
!(cs0 == Critical && cs1 == Critical);

%% program

while (i < steps) invariant (
    // State bounds
    (cs0 >= Start && cs0 <= Exit) &&
    (cs1 >= Start && cs1 <= Exit) &&
    // Mutual exclusion
    (cs0 != Critical || cs1 != Critical) &&
    // Flag consistency
    (f0 == (cs0 >= Gate)) &&
    (f1 == (cs1 >= Gate)) &&
    // Turn bounds
    (turn >= -1 && turn <= 1)
) {

    // ---- Process 0 transitions (scheduled when externalTurn == 0) ----
    if (externalTurn == 0) {
        if (cs0 == Start) {
            cs0 := StartToGate_cs0(cs0);
            f0 := true;
        } else {
            if (cs0 == Gate) {
                cs0 := GateToWait_cs0(cs0);
                turn := 1;
            } else {
                if (cs0 == Wait && (turn == 0 || !f1)) {
                    cs0 := WaitToCritical_cs0(cs0, turn, f1);
                } else {
                    if (cs0 == Critical) {
                        cs0 := CriticalToExit_cs0(cs0);
                        f0 := false;
                    } else {
                        if (cs0 == Exit) {
                            cs0 := ExitToStart_cs0(cs0);
                        } else {
                            // WaitToWait: no state change (spin)
                        }
                    }
                }
            }
        }
    } else {
        // P0 not scheduled this iteration
    }

    // ---- Process 1 transitions (scheduled when externalTurn == 1) ----
    if (externalTurn == 1) {
        if (cs1 == Start) {
            cs1 := P1_StartToGate_cs1(cs1);
            f1 := true;
        } else {
            if (cs1 == Gate) {
                cs1 := P1_GateToWait_cs1(cs1);
                turn := 0;
            } else {
                if (cs1 == Wait && (turn == 1 || !f0)) {
                    cs1 := P1_WaitToCritical_cs1(cs1, turn, f0);
                } else {
                    if (cs1 == Critical) {
                        cs1 := P1_CriticalToExit_cs1(cs1);
                        f1 := false;
                    } else {
                        if (cs1 == Exit) {
                            cs1 := P1_ExitToStart_cs1(cs1);
                        } else {
                            // WaitToWait: no state change (spin)
                        }
                    }
                }
            }
        }
    } else {
        // P1 not scheduled this iteration
    }

    i := i + 1;
}
