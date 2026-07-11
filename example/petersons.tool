// =============================================================
//  Peterson's Mutual Exclusion — TOOL oracle-based verification
// =============================================================
//
// Models the two-process Peterson protocol using sequences for
// per-process state, closely matching the Dafny TSState design.
//
// Design:
//   - cs : seq[int]    — process states indexed by process ID
//   - flags : seq[bool] — entry flags indexed by process ID
//   - turn : int        — shared turn variable (-1 initially, then {0,1})
//   - Each transition oracle takes (state, p) and returns new state
//     where only process p's fields change via sequence update.
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
    cs: seq[int];
    flags: seq[bool];
    turn: int;
}

// --- Valid predicate (pure oracle, no assumes) ---
// Returns true iff the global state satisfies all Peterson invariants.
oracle Valid(refer s: PetersonState) -> res: bool {
    returns res == (
        // Exactly two processes
        (s.cs.length == 2) &&
        (s.flags.length == 2) &&

        // Both processes in valid states
        (forall p: int . (!(p >= 0 && p < s.cs.length) || 
            (s.cs[p] >= Start && s.cs[p] <= Exit))) &&

        // Mutual exclusion — at most one process in Critical
        !(exists p: int . exists q: int . 
            p != q && s.cs[p] == Critical && s.cs[q] == Critical) &&

        // Flag consistency: flag[p] is true iff cs[p] past Start
        (forall p: int . (!(p >= 0 && p < s.cs.length) || 
            (s.flags[p] == (s.cs[p] >= Gate)))) &&

        // Turn bounds
        (s.turn >= -1 && s.turn <= 1)
    );
}

// --- Process 0 transition oracles ---
// Each oracle takes the full state and process ID, returns new state.
// Sequence updates use Store: new_seq = old_seq[i := val]

oracle StartToGate(s: PetersonState, p: int) -> ns: PetersonState {
    assumes s.cs[p] == Start && (p == 0 || p == 1);
    returns  (ns.cs[p] == Gate) &&
             (forall i: int . (i == p) || (ns.cs[i] == s.cs[i])) &&
             (ns.flags[p] == true) &&
             (forall i: int . (i == p) || (ns.flags[i] == s.flags[i])) &&
             (ns.turn == s.turn);
}

oracle GateToWait(s: PetersonState, p: int) -> ns: PetersonState {
    assumes s.cs[p] == Gate && (p == 0 || p == 1);
    returns  (ns.cs[p] == Wait) &&
             (forall i: int . (i == p) || (ns.cs[i] == s.cs[i])) &&
             (ns.flags == s.flags) &&
             (ns.turn == 1 - p);
}

oracle WaitToCritical(s: PetersonState, p: int) -> ns: PetersonState {
    assumes s.cs[p] == Wait && 
            (s.turn == p || !s.flags[1 - p]) && (p == 0 || p == 1);
    returns  (ns.cs[p] == Critical) &&
             (forall i: int . (i == p) || (ns.cs[i] == s.cs[i])) &&
             (ns.flags == s.flags) &&
             (ns.turn == s.turn);
}

oracle WaitToWait(s: PetersonState, p: int) -> ns: PetersonState {
    assumes s.cs[p] == Wait && 
            s.flags[1 - p] && 
            s.turn == 1 - p &&
            (p == 0 || p == 1);
    returns  (ns.cs == s.cs) &&
             (ns.flags == s.flags) &&
             (ns.turn == s.turn);
}

oracle CriticalToExit(s: PetersonState, p: int) -> ns: PetersonState {
    assumes s.cs[p] == Critical && (p == 0 || p == 1);
    returns  (ns.cs[p] == Exit) &&
             (forall i: int . (i == p) || (ns.cs[i] == s.cs[i])) &&
             (ns.flags[p] == false) &&
             (forall i: int . (i == p) || (ns.flags[i] == s.flags[i])) &&
             (ns.turn == s.turn);
}

oracle ExitToStart(s: PetersonState, p: int) -> ns: PetersonState {
    assumes s.cs[p] == Exit && (p == 0 || p == 1);
    returns  (ns.cs[p] == Start) &&
             (forall i: int . (i == p) || (ns.cs[i] == s.cs[i])) &&
             (ns.flags == s.flags) &&
             (ns.turn == s.turn);
}

// --- Initial state constructor oracle ---
// Creates the initial Peterson state with both processes at Start.
oracle InitState(dummy: int) -> s: PetersonState {
    returns  (s.cs[0] == Start) &&
             (s.cs[1] == Start) &&
             (s.flags[0] == false) &&
             (s.flags[1] == false) &&
             (s.turn == -1) &&
             (s.cs.length == 2) &&
             (s.flags.length == 2);
}

oracle NextProcess(step: int) -> p: int {
    returns p == 0 || p == 1;
}

struct Stack {
    val: int;
    next: Stack;
}

// 1. The Push Contract
// Pushing an element creates a stack where 'val' is the element, and 'next' is the old stack.

oracle push(old_stack: Stack, element: int) -> new_stack: Stack {
    // A pushed stack is NEVER null, and its fields match the inputs
    returns (new_stack != null) && (new_stack.val == element) && (new_stack.next == old_stack);
}

// 2. The Peek (Value) Contract
// Popping returns the value at the top of the stack.
oracle peek(s: Stack) -> v: int {
    assumes s != null;
    returns v == s.val;
}

// 3. The Pop (State) Contract
// Popping also returns the rest of the stack underneath.

oracle pop(s: Stack) -> rest: Stack {
    assumes s != null;
    returns rest == s.next;
}

oracle length(s: Stack) -> l: int {
    returns l == (s == null ? 0 : 1 + length(s.next));
}

// --- Scheduler env function ---
// Picks which process runs next; constrained to {0, 1} by invariant.
// env NextProcess(time: int) -> p: int;

// --- Global variables ---
state: PetersonState;
externalTurn: int;
i: int;
x: int;
counta: int;
countb: int;
steps: int;
astack: Stack;
bstack: Stack;

%% preconditions

Start == 0;
Gate == 1;
Wait == 2;
Critical == 3;
Exit == 4;
astack == null;
bstack == null;

// Initial state is constructed by InitState oracle before the loop.
externalTurn == 0;
i == 0;
counta == 0;
countb == 0;
x == 0;
steps == 100;

%% postconditions

// Mutual exclusion holds after the simulation:
// it is impossible for both processes to be in Critical.
!(state.cs[0] == Critical && state.cs[1] == Critical) && (x == counta + countb);

%% program

// Initialize the protocol state
state := InitState(0);
assert (state.cs.length == 2);
assert (state.flags.length == 2);
assert (forall p: int . (!(p >= 0 && p < state.cs.length) || (state.cs[p] >= Start && state.cs[p] <= Exit)));
assert !(exists p: int . exists q: int .  p != q && (p >= 0 && p < state.cs.length) && (q >= 0 && q < state.cs.length) && state.cs[p] == Critical && state.cs[q] == Critical);
assert (forall p: int . (!(p >= 0 && p < state.cs.length) || (state.flags[p] == (state.cs[p] >= Gate))));
assert (state.turn >= -1 && state.turn <= 1);
assert (externalTurn == 0 || externalTurn == 1);

while (i < steps) invariant (
    // Valid predicate inlined:
    // Exactly two processes
    (state.cs.length == 2) &&
    (state.flags.length == 2) &&
    // Both processes in valid states
    (forall p: int . (!(p >= 0 && p < state.cs.length) || 
        (state.cs[p] >= Start && state.cs[p] <= Exit))) &&
    // Mutual exclusion
    !(exists p: int . exists q: int . 
        p != q && (p >= 0 && p < state.cs.length) && (q >= 0 && q < state.cs.length) && state.cs[p] == Critical && state.cs[q] == Critical) &&
    // Flag consistency
    (forall p: int . (!(p >= 0 && p < state.cs.length) || 
        (state.flags[p] == (state.cs[p] >= Gate)))) &&
    // Turn bounds
    (state.turn >= -1 && state.turn <= 1) &&
    // Scheduler constraint
    (externalTurn == 0 || externalTurn == 1) && 
    (counta == length(astack)) &&
    (countb == length(bstack)) &&
    (x == counta + countb)
) {

    // Determine which process runs this iteration via environment function
    externalTurn := NextProcess(i);

    // ---- Process transitions dispatched by externalTurn ----
    if (externalTurn == 0) {
        if (state.cs[0] == Start) {
            state := StartToGate(state, 0);
        } else {
            if (state.cs[0] == Gate) {
                state := GateToWait(state, 0);
            } else {
                if (state.cs[0] == Wait && 
                    (state.turn == 0 || !state.flags[1])) {
                    state := WaitToCritical(state, 0);
                } else {
                    if (state.cs[0] == Critical) {
                        astack := push(astack, i);
                        counta := counta + 1;
                        x := x + 1;
                        state := CriticalToExit(state, 0);
                    } else {
                        if (state.cs[0] == Exit) {
                            state := ExitToStart(state, 0);
                        } else {
                            // cs[0] == Wait but cannot enter: spin in place
                            state := WaitToWait(state, 0);
                        }
                    }
                }
            }
        }
    } else {
        if (state.cs[1] == Start) {
            state := StartToGate(state, 1);
        } else {
            if (state.cs[1] == Gate) {
                state := GateToWait(state, 1);
            } else {
                if (state.cs[1] == Wait && 
                    (state.turn == 1 || !state.flags[0])) {
                    state := WaitToCritical(state, 1);
                } else {
                    if (state.cs[1] == Critical) {
                        //I would expect commenting out the next line to break things but it doesn't?
                        bstack := push(bstack, i);
                        // countb := countb+1;
                        x := x + 1;
                        state := CriticalToExit(state, 1);
                    } else {
                        if (state.cs[1] == Exit) {
                            state := ExitToStart(state, 1);
                        } else {
                            // cs[1] == Wait but cannot enter: spin in place
                            state := WaitToWait(state, 1);
                        }
                    }
                }
            }
        }
    }

    i := i + 1;
}
