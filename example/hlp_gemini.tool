// ==========================================
// Parameterized Multi-Task HLP Formalization
// Flattened Array Architecture 
// ==========================================

// DESIGN CHOICES & STRUCT DEFINITIONS
// -----------------------------------
// Z3 arrays are mathematically pure Uninterpreted Functions.
// To bypass the TypeChecker's inability to overload the 'update_seq' built-in
// (which we must now explicitly declare to avoid Call Errors), we flatten 
// the Task struct into parallel global sequences.
// 
// 1. HLPState (Global System State)
//    - curr_prio  : Maps task_id -> current elevated priority.
//    - stack_ptr  : Maps task_id -> depth of nested locks.
//    - res_stack  : A flattened 2D array mapped via (task_id * 100 + ptr) -> res_id.
//                   Enforces strict chronological LIFO unwinding per task.
//    - prio_stack : A flattened 2D array mapped via (task_id * 100 + ptr) -> saved priority.
//                   Allows tasks to restore their previous priority upon unlocking.
//    - owner      : Maps res_id -> task_id (0 means unlocked). Serves as the 
//                   absolute global mutual exclusion arbiter.

%% declarations

struct HLPState {
    curr_prio: seq[int];
    stack_ptr: seq[int];
    res_stack: seq[int];
    prio_stack: seq[int];
    owner: seq[int];
}

// ------------------------------------------
// BUILT-IN STUBS FOR TYPECHECKER
// ------------------------------------------
// We must declare these so TypeChecker allows them. Z3Translator will 
// natively intercept and overwrite them with z3.K and z3.Store.
env mk_seq(val: int) -> res: seq[int];
env update_seq(arr: seq[int], idx: int, val: int) -> res: seq[int];

// ------------------------------------------
// Static System Configurations 
// ------------------------------------------
env base_prio(t: int) -> p: int;
env ceiling(r: int) -> c: int;
env can_access(t: int, r: int) -> acc: bool;

invisible init_prio: seq[int];

// Concrete state for base case instantiation
s_0: HLPState;

// ------------------------------------------
// System Call Oracles
// ------------------------------------------
oracle GetResource(s: HLPState, task_id: int, res_id: int) -> ns: HLPState {
    returns ns == mk_HLPState(
        update_seq(s.curr_prio, task_id, ceiling(res_id)), 
        update_seq(s.stack_ptr, task_id, s.stack_ptr[task_id] + 1),
        update_seq(s.res_stack, (task_id * 100) + s.stack_ptr[task_id], res_id),
        update_seq(s.prio_stack, (task_id * 100) + s.stack_ptr[task_id], s.curr_prio[task_id]),
        update_seq(s.owner, res_id, task_id)
    );
}

oracle ReleaseResource(s: HLPState, task_id: int, res_id: int) -> ns: HLPState {
    returns ns == mk_HLPState(
        update_seq(s.curr_prio, task_id, s.prio_stack[(task_id * 100) + s.stack_ptr[task_id] - 1]), 
        update_seq(s.stack_ptr, task_id, s.stack_ptr[task_id] - 1),
        s.res_stack,
        s.prio_stack,
        update_seq(s.owner, res_id, 0)
    );
}

// ------------------------------------------
// The Protocol Dispatcher
// ------------------------------------------
oracle StepProtocol(s: HLPState, task_id: int, action: int, res_id: int) -> ns: HLPState {
    returns ns == (
        (action == 1 && s.owner[res_id] == 0 && can_access(task_id, res_id) == true)
            ? GetResource(s, task_id, res_id) :
            
        (action == 2 && s.owner[res_id] == task_id && s.stack_ptr[task_id] > 0 && s.res_stack[(task_id * 100) + s.stack_ptr[task_id] - 1] == res_id)
            ? ReleaseResource(s, task_id, res_id) :
            
        s
    );
}

// ------------------------------------------
// The Dynamic Safety Oracle
// ------------------------------------------
oracle is_safe(s: HLPState) -> res: bool {
    returns res == (
        // RESOURCE AUTHORIZATION COMPLIANCE
        (forall t : int . 
            forall i : int . 
                !(t >= 0 && i >= 0 && i < s.stack_ptr[t]) || 
                (can_access(t, s.res_stack[(t * 100) + i]) == true)
        ) &&
        // GLOBAL MUTUAL EXCLUSION
        (forall t : int . 
            forall i : int . 
                !(t >= 0 && i >= 0 && i < s.stack_ptr[t]) || 
                (s.owner[s.res_stack[(t * 100) + i]] == t)
        ) &&
        // MEMORY SAFETY
        (forall t : int . s.stack_ptr[t] >= 0)
    );
}

// ------------------------------------------
// Environmental Drivers & Temporal Trace
// ------------------------------------------
env get_action(ts: timestep) -> act: int;
env get_task_id(ts: timestep) -> tid: int;
env get_res_id(ts: timestep) -> rid: int;

trace hlp_trace(t: timestep) -> s: HLPState {
    init: 
        s == mk_HLPState(init_prio, mk_seq(0), mk_seq(0), mk_seq(0), mk_seq(0));
    step: 
        s == StepProtocol(hlp_trace(t - 1), get_task_id(t), get_action(t), get_res_id(t));
}

// --- Variables for the Mathematical Proof ---
k: timestep;
s_k_minus1: HLPState;
s_k: HLPState;
s0: HLPState;

%% preconditions

k > 0;

// ==========================================
// STATIC SYSTEM AXIOMS
// ==========================================
// Ground truth definition of the resource ceilings
forall r : int . forall t : int . !(can_access(t, r) == true) || (ceiling(r) >= base_prio(t));

// Invisible sequence constrained to set the base priority of every task
forall t : int . init_prio[t] == base_prio(t);

%% postconditions

is_safe(s_k) == true;

%% program

// ==========================================
// TEMPORAL INDUCTIVE PROOF
// ==========================================

// Base Case Evaluation
s0 := mk_HLPState(init_prio, mk_seq(0), mk_seq(0), mk_seq(0), mk_seq(0));
assert is_safe(s0) == true;
fact hlp_trace(0) == s0;

// Inductive Hypothesis
fact is_safe(s_k_minus1) == true;
fact hlp_trace(k - 1) == s_k_minus1;

// Single Transition Unrolling
s_k := hlp_trace(k);