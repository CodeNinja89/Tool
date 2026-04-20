// =============================================================================
// BST Verification: Preservation of Binary Search Tree Property on Insertion
// =============================================================================

%% declarations
// Recursive data structure representing a Binary Tree node
struct Tree {
    val: int;
    left: Tree;
    right: Tree;
}

// Helper: Recursively verifies that every node's value in a given subtree 
// is strictly less than a bound (used to validate left subtrees against a root).
oracle all_less(tl: Tree, vl: int) -> resl: bool {
    returns resl == (tl == null ? true : (tl.val < vl && all_less(tl.left, vl) && all_less(tl.right, vl)));
}

// Helper: Recursively verifies that every node's value in a given subtree 
// is strictly greater than a bound (used to validate right subtrees against a root).
oracle all_greater(tg: Tree, vg: int) -> resg: bool {
    returns resg == (tg == null ? true : (tg.val > vg && all_greater(tg.left, vg) && all_greater(tg.right, vg)));
}

// Core Property: Asserts that for every node, left-subtree values are smaller, 
// right-subtree values are larger, and both subtrees satisfy the BST property.
oracle is_bst(t: Tree) -> res: bool {
    returns res == (t == null ? true : (all_less(t.left, t.val) && all_greater(t.right, t.val) && is_bst(t.left) && is_bst(t.right)));
}

// Functional Contract: Defines a pure recursive insertion that searches for the 
// correct leaf position to maintain the relative ordering required by a BST.
oracle insert(ti: Tree, xi: int) -> new_ti: Tree {
    returns new_ti == (ti == null ? mk_Tree(xi, null, null) : 
        (xi == ti.val ? ti : 
            (xi < ti.val ? mk_Tree(ti.val, insert(ti.left, xi), ti.right) : 
                        mk_Tree(ti.val, ti.left, insert(ti.right, xi)))));
}

// Symbolic variables for verification
root: Tree;
v: int;
new_root: Tree;
is_ok: bool;

%% preconditions
// Assume the input tree starts in a valid BST state.
is_bst(root) == true;

%% postconditions
// Refutation Goal: We assert the negation (is_ok == false). If Z3 finds a 
// counter-example, it proves the property (is_bst(new_root) == true) is reachable.
is_ok == false;

%% program
// Step 1: Execute the mathematical insertion
new_root := insert(root, v);

// Step 2: Evaluate if the resulting state preserves the BST invariant
is_ok := is_bst(new_root);
