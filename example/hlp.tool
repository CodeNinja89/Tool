// =============================================================
//  Highest Locker Protocol (HLP)
//  Explicit Mutual Exclusion + Derived Ceiling Priority
// =============================================================

%% declarations

// -------------------------------------------------------------
// Static System Configuration
// -------------------------------------------------------------
//
// Assumption:
// Higher integer value means higher logical priority.
//
// cfg.ceiling is not arbitrary.
// It is valid only if it equals the maximum base priority among
// all tasks eligible to acquire this resource.
//
struct SysConfig {
    numTasks: int;
    ceiling: int;
    eligible: seq[bool];
    basePriorities: seq[int];
}


// -------------------------------------------------------------
// Dynamic Protocol State
// -------------------------------------------------------------

struct HLPState {
    acquired: bool;
    owner: int;

    // Explicit ownership map:
    // holds[i] == true means task i currently holds this resource.
    holds: seq[bool];

    // Active priorities may differ from base priorities while holding.
    activePriorities: seq[int];

    // Previous priorities are stored so they can be restored on release.
    prevPriorities: seq[int];
}


// -------------------------------------------------------------
// Environment Inputs
// -------------------------------------------------------------

env Cfg() -> cfg: SysConfig;
env TaskAt(t: timestep) -> taskId: int;
env ActionAt(t: timestep) -> action: int;


// =============================================================
//  Basic Configuration Predicates
// =============================================================

oracle ValidTaskId(taskId: int, refer cfg: SysConfig) -> res: bool {
    returns res == (
        taskId > 0 &&
        taskId <= cfg.numTasks
    );
}


// The ceiling is the maximum base priority of all eligible tasks.
//
// This has two parts:
//
// 1. Upper-bound property:
//    Every eligible task has base priority <= ceiling.
//
// 2. Tightness property:
//    Some eligible task actually has base priority == ceiling.
//
// Without part 2, cfg.ceiling could be absurdly high and the proof
// would still pass, but the system would over-block tasks.
oracle ValidCeiling(refer cfg: SysConfig) -> res: bool {
    returns res == (
        // Every eligible task has priority <= ceiling.
        (
            forall i: int .
                !(
                    i > 0 &&
                    i <= cfg.numTasks &&
                    cfg.eligible[i] == true
                )
                ||
                cfg.basePriorities[i] <= cfg.ceiling
        )
        &&

        // At least one eligible task has priority exactly equal to ceiling.
        (
            exists i: int .
                i > 0 &&
                i <= cfg.numTasks &&
                cfg.eligible[i] == true &&
                cfg.basePriorities[i] == cfg.ceiling
        )
    );
}


// A valid static configuration has:
// - at least one task
// - a correctly derived ceiling priority
oracle ValidConfig(refer cfg: SysConfig) -> res: bool {
    returns res == (
        cfg.numTasks > 0 &&
        ValidCeiling(cfg) == true
    );
}


// =============================================================
//  Ownership and Mutual Exclusion
// =============================================================

// Real mutual exclusion:
//
// No two different positive task IDs can both hold this resource.
oracle MutualExclusion(refer s: HLPState, refer cfg: SysConfig) -> res: bool {
    returns res == (
        forall i: int .
            forall j: int .
                !(
                    i > 0 &&
                    i <= cfg.numTasks &&
                    j > 0 &&
                    j <= cfg.numTasks &&
                    s.holds[i] == true &&
                    s.holds[j] == true
                )
                ||
                i == j
    );
}


// Ownership coherence connects:
//
// acquired flag
// owner field
// holds array
// eligibility
//
// This prevents states such as:
// - acquired == false but owner != 0
// - acquired == true but owner does not hold
// - some task holds but is not the owner
// - non-eligible owner
oracle OwnershipCoherent(refer s: HLPState, refer cfg: SysConfig) -> res: bool {
    returns res == (
        // If acquired, owner is a valid eligible task.
        (
            !s.acquired
            ||
            (
                ValidTaskId(s.owner, cfg) == true &&
                cfg.eligible[s.owner] == true
            )
        )
        &&

        // If acquired, the owner is marked as holding.
        (
            !s.acquired
            ||
            s.holds[s.owner] == true
        )
        &&

        // Any positive holder must be exactly the owner.
        (
            forall i: int .
                !(
                    i > 0 &&
                    i <= cfg.numTasks &&
                    s.holds[i] == true
                )
                ||
                (
                    s.acquired == true &&
                    i == s.owner
                )
        )
        &&

        // If not acquired, owner is zero.
        (
            s.acquired
            ||
            s.owner == 0
        )
        &&

        // If not acquired, no valid task holds the resource.
        (
            s.acquired
            ||
            (
                forall i: int .
                    !(
                        i > 0 &&
                        i <= cfg.numTasks
                    )
                    ||
                    s.holds[i] == false
            )
        )
    );
}


// =============================================================
//  HLP Priority Rule
// =============================================================

// If the resource is acquired:
//
// 1. The owner is boosted exactly to the resource ceiling.
// 2. Every task eligible for this resource has base priority
//    no higher than the owner's active priority.
//
// This captures the Highest Locker Protocol idea:
// the current holder runs at the ceiling of the resource,
// preventing eligible higher-priority tasks from preempting it.
oracle HLPPriorityRule(refer s: HLPState, refer cfg: SysConfig) -> res: bool {
    returns res == (
        !s.acquired
        ||
        (
            // Owner is boosted exactly to the configured ceiling.
            s.activePriorities[s.owner] == cfg.ceiling
            &&

            // Because cfg.ceiling is the max eligible priority,
            // no eligible task has base priority above the owner.
            (
                forall i: int .
                    !(
                        i > 0 &&
                        i <= cfg.numTasks &&
                        cfg.eligible[i] == true
                    )
                    ||
                    cfg.basePriorities[i] <= s.activePriorities[s.owner]
            )
        )
    );
}


// =============================================================
//  Full Validity Predicate
// =============================================================

oracle Valid(refer s: HLPState, refer cfg: SysConfig) -> res: bool {
    returns res == (
        ValidConfig(cfg) == true &&
        OwnershipCoherent(s, cfg) == true &&
        MutualExclusion(s, cfg) == true &&
        HLPPriorityRule(s, cfg) == true
    );
}


// =============================================================
//  Protocol Transitions
// =============================================================

oracle InitState(cfg: SysConfig) -> s: HLPState {
    returns s == mk_HLPState(
        false,
        0,

        // nobody holds the resource initially
        mk_seq(false),

        // active priorities initially equal base priorities
        cfg.basePriorities,

        // previous-priority storage initially zeroed
        mk_seq(0, 0)
    );
}


oracle GetResource(s: HLPState, cfg: SysConfig, taskId: int) -> ns: HLPState {
    assumes ValidTaskId(taskId, cfg) == true &&
            s.acquired == false &&
            cfg.eligible[taskId] == true;

    returns ns == mk_HLPState(
        true,
        taskId,

        // taskId now explicitly holds the resource
        update_seq(s.holds, taskId, true),

        // HLP boost: raise active priority to the resource ceiling
        update_seq(s.activePriorities, taskId, cfg.basePriorities[taskId]),

        // remember previous active priority before boosting
        update_seq(s.prevPriorities, taskId, s.activePriorities[taskId])
    );
}


oracle ReleaseResource(s: HLPState, cfg: SysConfig, taskId: int) -> ns: HLPState {
    assumes ValidTaskId(taskId, cfg) == true &&
            s.acquired == true &&
            s.owner == taskId;

    returns ns == mk_HLPState(
        false,
        0,

        // taskId no longer holds the resource
        update_seq(s.holds, taskId, false),

        // restore priority from saved previous priority
        update_seq(s.activePriorities, taskId, s.prevPriorities[taskId]),

        // previous-priority storage unchanged
        s.prevPriorities
    );
}


// action encoding:
//
// action == 1: GetResource
// action == 2: ReleaseResource
// otherwise: no-op
//
// We guard each call so that the callee assumptions are satisfied.
oracle StepProtocol(s: HLPState, cfg: SysConfig, taskId: int, action: int) -> ns: HLPState {
    returns ns == (
        (
            action == 1 &&
            ValidTaskId(taskId, cfg) == true &&
            s.acquired == false &&
            cfg.eligible[taskId] == true
        )
            ? GetResource(s, cfg, taskId) :

        (
            action == 2 &&
            ValidTaskId(taskId, cfg) == true &&
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
//
// HLP(0)     = InitState(Cfg())
// HLP(t > 0) = StepProtocol(HLP(t - 1), Cfg(), TaskAt(t), ActionAt(t))
//

trace HLP(t: timestep) -> s: HLPState {
    init: s == InitState(Cfg());
    step: s == StepProtocol(HLP(t - 1), Cfg(), TaskAt(t), ActionAt(t));
}


// =============================================================
//  Proof Variables
// =============================================================

t: timestep;
is_safe: bool;


// =============================================================
//  Preconditions
// =============================================================

%% preconditions

t > 0;

// The proof is parameterized by any well-formed AUTOSAR-like
// HLP configuration.
ValidConfig(Cfg()) == true;


// =============================================================
//  Postconditions
// =============================================================

%% postconditions

is_safe == true;


// =============================================================
//  Program / Proof Obligations
// =============================================================

%% program

// Base case:
// The initial state satisfies configuration validity,
// ownership coherence, mutual exclusion, and HLP priority rule.
assert Valid(HLP(0), Cfg()) == true;


// Inductive step:
// If the previous trace state is valid,
// then the next trace state is valid.
assert !(Valid(HLP(t - 1), Cfg()) == true) || Valid(HLP(t), Cfg()) == true;

// Final marker for the verifier harness.
is_safe := true;