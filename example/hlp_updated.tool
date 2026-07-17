// =============================================================
//  Highest Locker Protocol (HLP) — Dafny-Aligned Specification
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
    activePriorities: seq[int]; 
    prevPriorities: seq[int];   
}

// --- The True Invariant (validRM) ---
oracle Valid(refer s: HLPState, refer cfg: SysConfig) -> res: bool {
    returns res == (
        // 1. Mutual Exclusion & Eligibility: If acquired, the single owner must be an eligible task
        (!s.acquired || (s.owner > 0 && cfg.eligible[s.owner] == true)) &&
        
        // 2. Consistency: If released, there is no owner
        (s.acquired || s.owner == 0) &&
        
        // 3. HLP Property: The owner's active priority MUST equal the resource ceiling
        (!s.acquired || s.activePriorities[s.owner] == cfg.ceiling)
    );
}

// --- Process Transition Oracles ---

oracle InitState(cfg: SysConfig) -> s: HLPState {
    returns s == mk_HLPState(
        false, 
        0, 
        cfg.basePriorities, 
        mk_seq(0, 0)        
    );
}

oracle GetResource(s: HLPState, cfg: SysConfig, taskId: int) -> ns: HLPState {
    assumes taskId > 0 && s.acquired == false && cfg.eligible[taskId] == true;
    returns ns == mk_HLPState(
        true, 
        taskId, 
        update_seq(s.activePriorities, taskId, cfg.ceiling), 
        update_seq(s.prevPriorities, taskId, s.activePriorities[taskId]) 
    );
}

oracle ReleaseResource(s: HLPState, cfg: SysConfig, taskId: int) -> ns: HLPState {
    assumes taskId > 0 && s.acquired == true && s.owner == taskId;
    returns ns == mk_HLPState(
        false,
        0,
        update_seq(s.activePriorities, taskId, s.prevPriorities[taskId]), 
        s.prevPriorities 
    );
}

oracle StepProtocol(s: HLPState, cfg: SysConfig, taskId: int, action: int) -> ns: HLPState {
    returns ns == (
        (action == 1 && s.acquired == false && cfg.eligible[taskId] == true) ? GetResource(s, cfg, taskId) :
        (action == 2 && s.acquired == true && s.owner == taskId) ? ReleaseResource(s, cfg, taskId) :
        s
    );
}

// --- Variables for our Proof ---
sym_s: HLPState;
sym_cfg: SysConfig;
sym_taskId: int;
sym_action: int;
is_safe: bool;
sym_init: HLPState; // Intermediate variable to flatten the base case

%% preconditions

sym_s == mk_HLPState(sym_s.acquired, sym_s.owner, sym_s.activePriorities, sym_s.prevPriorities);
sym_cfg == mk_SysConfig(sym_cfg.ceiling, sym_cfg.eligible, sym_cfg.basePriorities);
sym_taskId > 0;
sym_action == 1 || sym_action == 2;

// Evaluate and cache the InitState structurally before reaching the assertions
sym_init == InitState(sym_cfg);


%% postconditions
is_safe == true;


%% program

// AXIOM 1: The Base Case 
// Evaluates at depth 1 using the pre-flattened struct
assert Valid(sym_init, sym_cfg) == true;

// AXIOM 2: The Inductive Step 
assert !(Valid(sym_s, sym_cfg) == true) || (Valid(StepProtocol(sym_s, sym_cfg, sym_taskId, sym_action), sym_cfg) == true);

is_safe := true;