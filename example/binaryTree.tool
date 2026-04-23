%% declarations
struct BST {
    val: int;
    left: BST;
    right: BST;
}

// 1. The Recursive Contains Oracle
oracle contains(t: BST, x: int) -> found: bool {
    returns found == (
        (t == null) ? false : (
            (x == t.val) ? true : (
                (x < t.val) ? contains(t.left, x) : contains(t.right, x)
            )
        )
    );
}

// 2. The Recursive Insert Oracle
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

oracle is_empty(n: BST) -> res: bool {
    // BUG TRIGGER: 'null' is on the RIGHT side of the '=='
    returns res == (n == null); 
}

// --- Variables for our Proof ---
original_tree: BST;
v: int;
new_tree: BST;
is_correct: bool;

%% preconditions
// None needed! 

%% postconditions
// Theorem: Inserting X into any arbitrary tree T guarantees 
// that contains(new_T, X) is mathematically true.
// We assert the contradiction to trigger a refutation proof.
// is_correct == false;
is_empty(new_tree) == true;

%% program
new_tree := insert(original_tree, v);
// is_correct := contains(new_tree, v);