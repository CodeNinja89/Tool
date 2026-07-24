// =============================================================
//  Highest Locker Protocol (HLP)
//  Explicit Mutual Exclusion + Derived Ceiling Priority
//  DELIBERATE BUG: GetResource does not boost to cfg.ceiling
// =============================================================

%% declarations

// -------------------------------------------------------------
// Static System Configuration
// -------------------------------------------------------------
//
// Assumption:
// Higher integer value means higher logical priority.
//
// cfg.ceiling is valid only if it equals the maximum base priority
// among all tasks eligible to acquire this resource.
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

    // holds[i] == true means task i currently holds this resource.
    holds: seq[bool];

    activePriorities: seq[int];
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


oracle ValidCeiling(refer cfg: SysConfig) -> res: bool {
    returns res == (
        // Every eligible task has base priority <= ceiling.
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

        // Some eligible task has base priority exactly equal to ceiling.
        (
            exists i: int .
                i > 0 &&
                i <= cfg.numTasks &&
                cfg.eligible[i] == true &&
                cfg.basePriorities[i] == cfg.ceiling
        )
    );
}


oracle ValidConfig(refer cfg: SysConfig) -> res: bool {
    returns res == (
        cfg != null &&
        cfg.numTasks > 0 &&
        ValidCeiling(cfg) == true
    );
}


// =============================================================
//  Ownership and Mutual Exclusion
// =============================================================

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

        // Any valid holder must be exactly the owner.
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

oracle HLPPriorityRule(refer s: HLPState, refer cfg: SysConfig) -> res: bool {
    returns res == (
        !s.acquired
        ||
        (
            // Owner must be boosted exactly to the resource ceiling.
            s.activePriorities[s.owner] == cfg.ceiling
            &&

            // No eligible task has base priority above the owner's active priority.
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
        s != null &&
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

        update_seq(s.activePriorities, taskId, cfg.ceiling),

        // remember previous active priority before changing active priority
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

trace HLP(t: timestep) -> s: HLPState {
    init: s == InitState(Cfg());
    step: s == StepProtocol(HLP(t - 1), Cfg(), TaskAt(t), ActionAt(t));
}


// =============================================================
//  Proof Variables
// =============================================================

t: timestep;

sym_cfg: SysConfig;

base: HLPState;
prev: HLPState;
next: HLPState;

task: int;
act: int;

is_safe: bool;


// =============================================================
//  Preconditions
// =============================================================

%% preconditions

t > 0;
ValidConfig(Cfg()) == true;


%% postconditions

is_safe == true;


%% program

// =============================================================
//  Cache environment and trace states
// =============================================================

sym_cfg := Cfg();

base := HLP(0);

prev := HLP(t - 1);
next := HLP(t);

task := TaskAt(t);
act := ActionAt(t);


// =============================================================
//  Trace unfolding obligations
// =============================================================
//
// These two assertions make the trace real in the proof.
// We are not treating the trace as documentation anymore.

assert base == InitState(sym_cfg);

assert next == StepProtocol(prev, sym_cfg, task, act);


// =============================================================
//  Base Case: HLP(0) is valid
// =============================================================

assert base != null;
assert base.acquired == false;
assert base.owner == 0;

assert (
    forall i: int .
        !(
            i > 0 &&
            i <= sym_cfg.numTasks
        )
        ||
        base.holds[i] == false
);

assert OwnershipCoherent(base, sym_cfg) == true;
assert MutualExclusion(base, sym_cfg) == true;
assert HLPPriorityRule(base, sym_cfg) == true;

assert Valid(base, sym_cfg) == true;


// =============================================================
//  Inductive Step: HLP(t-1) valid implies HLP(t) valid
// =============================================================
//
// Since:
//     prev == HLP(t - 1)
//     next == HLP(t)
//     next == StepProtocol(prev, sym_cfg, task, act)
//
// the following proof is genuinely about the trace transition.


// -------------------------------------------------------------
// Acquire case
// -------------------------------------------------------------

assert !(
    Valid(prev, sym_cfg) == true &&
    act == 1 &&
    ValidTaskId(task, sym_cfg) == true &&
    prev.acquired == false &&
    sym_cfg.eligible[task] == true
)
||
OwnershipCoherent(next, sym_cfg) == true;


assert !(
    Valid(prev, sym_cfg) == true &&
    act == 1 &&
    ValidTaskId(task, sym_cfg) == true &&
    prev.acquired == false &&
    sym_cfg.eligible[task] == true
)
||
MutualExclusion(next, sym_cfg) == true;


// This is the important one.
// With the deliberate priority bug in GetResource,
// this assertion should fail.
assert !(
    Valid(prev, sym_cfg) == true &&
    act == 1 &&
    ValidTaskId(task, sym_cfg) == true &&
    prev.acquired == false &&
    sym_cfg.eligible[task] == true
)
||
HLPPriorityRule(next, sym_cfg) == true;


// -------------------------------------------------------------
// Release case
// -------------------------------------------------------------

assert !(
    Valid(prev, sym_cfg) == true &&
    act == 2 &&
    ValidTaskId(task, sym_cfg) == true &&
    prev.acquired == true &&
    prev.owner == task
)
||
OwnershipCoherent(next, sym_cfg) == true;


assert !(
    Valid(prev, sym_cfg) == true &&
    act == 2 &&
    ValidTaskId(task, sym_cfg) == true &&
    prev.acquired == true &&
    prev.owner == task
)
||
MutualExclusion(next, sym_cfg) == true;


assert !(
    Valid(prev, sym_cfg) == true &&
    act == 2 &&
    ValidTaskId(task, sym_cfg) == true &&
    prev.acquired == true &&
    prev.owner == task
)
||
HLPPriorityRule(next, sym_cfg) == true;


// -------------------------------------------------------------
// No-op case
// -------------------------------------------------------------
//
// If neither legal acquire nor legal release is enabled,
// StepProtocol returns the previous state.
// Since next == StepProtocol(...), next should equal prev.

assert !(
    Valid(prev, sym_cfg) == true &&

    !(
        act == 1 &&
        ValidTaskId(task, sym_cfg) == true &&
        prev.acquired == false &&
        sym_cfg.eligible[task] == true
    )
    &&

    !(
        act == 2 &&
        ValidTaskId(task, sym_cfg) == true &&
        prev.acquired == true &&
        prev.owner == task
    )
)
||
next == prev;


assert !(
    Valid(prev, sym_cfg) == true &&

    !(
        act == 1 &&
        ValidTaskId(task, sym_cfg) == true &&
        prev.acquired == false &&
        sym_cfg.eligible[task] == true
    )
    &&

    !(
        act == 2 &&
        ValidTaskId(task, sym_cfg) == true &&
        prev.acquired == true &&
        prev.owner == task
    )
)
||
Valid(next, sym_cfg) == true;


// -------------------------------------------------------------
// Full trace-step preservation
// -------------------------------------------------------------

assert !(
    Valid(prev, sym_cfg) == true
)
||
Valid(next, sym_cfg) == true;


is_safe := true;