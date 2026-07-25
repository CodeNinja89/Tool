%% declarations

struct BST {
    val: int;
    left: BST;
    right: BST;
}

// 1. The Recursive Contains Oracle
oracle contains(refer t: BST, x: int) -> found: bool {
    returns found == (
        (t == null) ? false : (
            (x == t.val) ? true : (
                (x < t.val) ? contains(t.left, x) : contains(t.right, x)
            )
        )
    );
}

oracle all_less(refer t: BST, vl: int) -> resl: bool {
    returns resl == (t == null ? true : (t.val < vl && all_less(t.left, vl) && all_less(t.right, vl)));
}

oracle all_greater(refer t: BST, vg: int) -> resg: bool {
    returns resg == (t == null ? true : (t.val > vg && all_greater(t.left, vg) && all_greater(t.right, vg)));
}

oracle is_bst(refer t: BST) -> res: bool {
    returns res == (t == null ? true : (all_less(t.left, t.val) && all_greater(t.right, t.val) && is_bst(t.left) && is_bst(t.right)));
}

// 2. The Recursive Insert Oracle
oracle insert(t: BST, x: int) -> new_t: BST {
    assumes is_bst(t);
    returns new_t == (
        (t == null) ? mk_BST(x, null, null) : (
            (x == t.val) ? t : (
                (x < t.val) ? 
                    mk_BST(t.val, insert(t.left, x), t.right) : 
                    mk_BST(t.val, t.left, insert(t.right, x))
            )
        )
    );
}

oracle is_empty(refer n: BST) -> res: bool {
    returns res == (n == null); 
}

env values(ts: timestep) -> val: int;

trace bst_trace(t: timestep) -> s: BST {
    init: 
        s == null;
    step: 
        s == insert(bst_trace(t - 1), values(t));
}

// --- Variables for our Proof ---
k: timestep;           // An arbitrary point in time
v: int;                // The environment value generated at time k
root_val: int;         // The arbitrary root value of our tree at k-1
left_tree: BST;        // The arbitrary left subtree at k-1
right_tree: BST;       // The arbitrary right subtree at k-1
tree_k_minus1: BST;   // The composed parent tree at k-1
tree_k: BST;           // The evaluated trace state at k
is_correct: bool;

%% preconditions

k > 0;
// Tie the environment value at step k to our explicit variable v for the proof
values(k) == v;

%% postconditions
is_bst(tree_k) == true;
contains(tree_k, v) == true;

%% program

// ==========================================
// 1. TEMPORAL BASE CASE (t = 0)
// ==========================================
// The trace definition mathematically guarantees bst_trace(0) == null.
assert is_bst(bst_trace(0)) == true;


// ==========================================
// 2. TEMPORAL & STRUCTURAL INDUCTIVE STEP
// ==========================================

// 2A. Structural Inductive Hypotheses
fact is_bst(left_tree) == true;
fact is_bst(right_tree) == true;
fact all_less(left_tree, root_val) == true;
fact all_greater(right_tree, root_val) == true;

fact is_bst(insert(left_tree, v)) == true;
fact contains(insert(left_tree, v), v) == true;
fact (!(v < root_val) || all_less(insert(left_tree, v), root_val) == true);

fact is_bst(insert(right_tree, v)) == true;
fact contains(insert(right_tree, v), v) == true;
fact (!(v > root_val) || all_greater(insert(right_tree, v), root_val) == true);

// 2B. Construct the state of the trace at the previous timestep
tree_k_minus1 := mk_BST(root_val, left_tree, right_tree);

// 2C. Temporal Inductive Hypothesis
// We assume the trace at time k-1 perfectly matches our explicit structural state
fact bst_trace(k - 1) == tree_k_minus1;

// 2D. Advance the trace
// Because k > 0, evaluating the trace at k naturally triggers the 'step' body:
// insert(bst_trace(k-1), values(k))
// Z3 substitutes our facts, resulting in: insert(mk_BST(...), v)
// This forces exactly ONE level of unrolling.
tree_k := bst_trace(k);