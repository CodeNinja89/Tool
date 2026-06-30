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


// --- Variables for our Proof ---
base_tree: BST; // base tree
original_tree: BST;
v: int;
is_correct: bool;
is_freed: bool;

%% preconditions

base_tree == null; // base case for induction hypothesis
original_tree != null;
is_bst(original_tree) == true;

%% postconditions

is_correct == true;

%% program

// base case

base_tree := insert(base_tree, v);
assert is_bst(base_tree);
assert contains(base_tree, v);

is_freed := destruct(base_tree);

// induction hypothesis: "assume" that the theorem holds for left and right subtrees.
// the problem is, in TOOL, we use "fact" to add an assumption but that assumption could
// be unjustified. TOOL does check if the fact is consistent with the current state of the
// spec but it does not proof if the fact is correct. So we use an assertion here.
// assertions here act as intermediary lemmas that must hold to prove that final property.

assert (forall x: int . is_bst(insert(original_tree.left, x)) == true);
assert (forall x: int . contains(insert(original_tree.left, x), x) == true);
assert (forall x: int . !(x < original_tree.val) || (all_less(insert(original_tree.left, x), original_tree.val)));

assert (forall x: int . is_bst(insert(original_tree.right, x)) == true);
assert (forall x: int . contains(insert(original_tree.right, x), x) == true);
assert (forall x: int . !(x > original_tree.val) || (all_greater(insert(original_tree.right, x), original_tree.val)));

// inductive step

original_tree := insert(original_tree, v);
assert is_bst(original_tree) == true;
assert contains(original_tree, v) == true;
is_freed := destruct(original_tree);

is_correct := true; // if we reach here, all assertions pass.