%% declarations

struct BST {
    val: int;
    left: BST;
    right: BST;
}

// --- Recursive Oracles ---
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
    returns resl == (
        (t == null) ? true : (t.val < vl && all_less(t.left, vl) && all_less(t.right, vl))
    );
}

oracle all_greater(refer t: BST, vg: int) -> resg: bool {
    returns resg == (
        (t == null) ? true : (t.val > vg && all_greater(t.left, vg) && all_greater(t.right, vg))
    );
}

oracle is_bst(refer t: BST) -> res: bool {
    returns res == (
        (t == null) ? true : (
            all_less(t.left, t.val) && 
            all_greater(t.right, t.val) && 
            is_bst(t.left) && 
            is_bst(t.right)
        )
    );
}

// The pure functional insertion yielding a mathematically new tree.
oracle insert(t: BST, x: int) -> new_t: BST {
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

// --- Variables for the Proof ---
base_tree: BST;
v: int;                // The arbitrary value to insert
root_val: int;         // The arbitrary root value of our tree
left_tree: BST;        // The arbitrary left subtree
right_tree: BST;       // The arbitrary right subtree
original_tree: BST;    // The composed parent tree
new_tree: BST;         // The resulting tree after insertion

%% preconditions
base_tree == null;

%% postconditions

is_bst(new_tree) == true;
contains(new_tree, v) == true;

%% program

// ==========================================
// 1. BASE CASE: t == null
// ==========================================
base_tree := insert(base_tree, v);

assert is_bst(base_tree) == true;
assert contains(base_tree, v) == true;

// ==========================================
// 2. INDUCTIVE STEP
// ==========================================

// Establish that our arbitrary subtrees are valid BSTs
fact is_bst(left_tree) == true;
fact is_bst(right_tree) == true;
fact all_less(left_tree, root_val) == true;
fact all_greater(right_tree, root_val) == true;

// 2A. INDUCTIVE HYPOTHESES
// We assume the insertion property already holds for the subtrees.
fact is_bst(insert(left_tree, v)) == true;
fact contains(insert(left_tree, v), v) == true;
fact (!(v < root_val) || all_less(insert(left_tree, v), root_val) == true);

fact is_bst(insert(right_tree, v)) == true;
fact contains(insert(right_tree, v), v) == true;
fact (!(v > root_val) || all_greater(insert(right_tree, v), root_val) == true);

// 2B. CONSTRUCT THE PARENT TREE
// This triggers Z3 to unroll 'insert' and 'is_bst' exactly one level.
original_tree := mk_BST(root_val, left_tree, right_tree);

// 2C. THE TRANSITION
new_tree := insert(original_tree, v);