%% declarations
linear struct BST {
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

oracle destruct(n: BST) -> res: bool {
    returns res == true; 
}

env values(timestep: int) -> val: int;

oracle trace(t: int) -> s: BST {
    assumes t >= 0;
    returns s == (t == 0 ? 
        null : 
        insert(trace(t - 1), values(t))
    );
}


// --- Variables for our Proof ---

is_correct: bool;

%% preconditions

%% postconditions

is_correct == true;

%% program

assert forall t: int . (!(t >= 0) || is_bst(trace(t)) == true);
assert forall t: int . (!(t >= 0) || contains(trace(t), values(t)) == true);

is_correct := true; // if we reach here, all assertions pass.