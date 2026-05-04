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

oracle all_less(tl: BST, vl: int) -> resl: bool {
    returns resl == (tl == null ? true : (tl.val < vl && all_less(tl.left, vl) && all_less(tl.right, vl)));
}

oracle all_greater(tg: BST, vg: int) -> resg: bool {
    returns resg == (tg == null ? true : (tg.val > vg && all_greater(tg.left, vg) && all_greater(tg.right, vg)));
}

oracle is_bst(t: BST) -> res: bool {
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

oracle is_empty(n: BST) -> res: bool {
    returns res == (n == null); 
}

// --- Variables for our Proof ---
original_tree: BST;
v: int;
new_tree: BST;
is_correct: bool;

%% preconditions
// None needed!
original_tree != null;
is_bst(original_tree) == true;

%% postconditions
// Theorem: Inserting X into any arbitrary tree T guarantees 
// that contains(new_T, X) is mathematically true.
// We assert the contradiction to trigger a refutation proof.
is_correct == false;
// is_empty(new_tree) == true;

%% program
new_tree := insert(original_tree, v);
is_correct := is_bst(new_tree) && contains(new_tree, v);