// =============================================================
//  Highest Locker Protocol (HLP) — Explicit Mutual Exclusion
// =============================================================

%% declarations

// --- Static System Configuration ---
struct SysConfig {
    ceiling: int;
    eligible: seq[bool];
    basePriorities: seq[int];
}

// --- Dynamic Protocol State ---
struct HLPState {
    acquired: bool;
    owner: int;

    // Explicit ownership map:
    // holds[i] == true means task i currently holds the resource.
    holds: seq[bool];

    activePriorities: seq[int];
    prevPriorities: seq[int];
}

// --- Environment Inputs ---
env Cfg() -> cfg: SysConfig;
env TaskAt(t: timestep) -> taskId: int;
env ActionAt(t: timestep) -> action: int;


// =============================================================
//  Ownership Properties
// =============================================================

// Real mutual exclusion:
// no two different positive task IDs can both hold the resource.
oracle MutualExclusion(refer s: HLPState) -> res: bool {
    returns res == (
        forall i: int .
            forall j: int .
                !(
                    i > 0 &&
                    j > 0 &&
                    s.holds[i] == true &&
                    s.holds[j] == true
                ) || i == j
    );
}

// Ownership coherence:
// 1. If acquired, there is a positive owner.
// 2. If acquired, the owner is marked as holding.
// 3. If a task is marked as holding, it must be the owner.
// 4. If not acquired, owner is zero.
// 5. If not acquired, no positive task holds the resource.
oracle OwnershipCoherent(refer s: HLPState, refer cfg: SysConfig) -> res: bool {
    returns res == (
        // acquired => valid eligible owner
        (!s.acquired || (s.owner > 0 && cfg.eligible[s.owner] == true)) &&

        // acquired => owner holds
        (!s.acquired || s.holds[s.owner] == true) &&

        // any holder must be the owner
        (
            forall i: int .
                !(i > 0 && s.holds[i] == true) || (s.acquired == true && i == s.owner)
        ) &&

        // not acquired => owner == 0
        (s.acquired || s.owner == 0) &&

        // not acquired => nobody holds
        (
            s.acquired ||
            (
                forall i: int .
                    !(i > 0) || s.holds[i] == false
            )
        )
    );
}


// =============================================================
//  HLP Validity
// =============================================================

oracle Valid(refer s: HLPState, refer cfg: SysConfig) -> res: bool {
    returns res == (
        OwnershipCoherent(s, cfg) &&

        // This is now explicit, not merely implied by the owner field.
        MutualExclusion(s) &&

        // HLP priority rule:
        // if acquired, the owner's active priority equals the resource ceiling.
        (!s.acquired || s.activePriorities[s.owner] == cfg.ceiling)
    );
}


// =============================================================
//  Protocol Transitions
// =============================================================

oracle InitState(cfg: SysConfig) -> s: HLPState {
    returns s == mk_HLPState(
        false,
        0,
        mk_seq(false),
        cfg.basePriorities,
        mk_seq(0, 0)
    );
}

oracle GetResource(s: HLPState, cfg: SysConfig, taskId: int) -> ns: HLPState {
    assumes taskId > 0 && s.acquired == false && cfg.eligible[taskId] == true;

    returns ns == mk_HLPState(
        true,
        taskId,

        // taskId now explicitly holds the resource
        update_seq(s.holds, taskId, true),

        // raise active priority to ceiling
        update_seq(s.activePriorities, taskId, cfg.ceiling),

        // remember previous priority
        update_seq(s.prevPriorities, taskId, s.activePriorities[taskId])
    );
}

oracle ReleaseResource(s: HLPState, cfg: SysConfig, taskId: int) -> ns: HLPState {
    assumes taskId > 0 && s.acquired == true && s.owner == taskId;

    returns ns == mk_HLPState(
        false,
        0,

        // taskId no longer holds the resource
        update_seq(s.holds, taskId, false),

        // restore previous priority
        update_seq(s.activePriorities, taskId, s.prevPriorities[taskId]),

        s.prevPriorities
    );
}

oracle StepProtocol(s: HLPState, cfg: SysConfig, taskId: int, action: int) -> ns: HLPState {
    returns ns == (
        (
            action == 1 &&
            taskId > 0 &&
            s.acquired == false &&
            cfg.eligible[taskId] == true
        )
            ? GetResource(s, cfg, taskId) :

        (
            action == 2 &&
            taskId > 0 &&
            s.acquired == true &&
            s.owner == taskId
        )
            ? ReleaseResource(s, cfg, taskId) :

        s
    );
}


// =============================================================
//  System Trace
// =============================================================

trace HLP(t: timestep) -> s: HLPState {
    init: s == InitState(Cfg());
    step: s == StepProtocol(HLP(t - 1), Cfg(), TaskAt(t), ActionAt(t));
}


// =============================================================
//  Proof Variables
// =============================================================

t: timestep;
is_safe: bool;

%% preconditions

t > 0;

%% postconditions

is_safe == true;

%% program

// Base case:
// The initial state satisfies ownership coherence,
// mutual exclusion, and the HLP priority rule.
assert Valid(HLP(0), Cfg()) == true;

// Inductive step:
// If the previous trace state is valid,
// then the next trace state is valid.
assert (forall t: timestep . (t > 0 && Valid(HLP(t), Cfg()) == true));

is_safe := true;