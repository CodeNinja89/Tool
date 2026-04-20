// =============================================================================
// AVL Tree Specification: Essential Theorems and Structural Properties
// =============================================================================

%% declarations
// Recursive data structure for AVL Tree node
struct AVLTree {
    val: int;
    height: int;
    left: AVLTree;
    right: AVLTree;
}

// --- Basic Oracles ---

oracle get_height(t: AVLTree) -> h: int {
    returns h == (t == null ? 0 : t.height);
}

oracle all_less(tl: AVLTree, vl: int) -> resl: bool {
    returns resl == (tl == null ? true : (tl.val < vl && all_less(tl.left, vl) && all_less(tl.right, vl)));
}

oracle all_greater(tg: AVLTree, vg: int) -> resg: bool {
    returns resg == (tg == null ? true : (tg.val > vg && all_greater(tg.left, vg) && all_greater(tg.right, vg)));
}

// --- AVL Invariants ---

oracle is_bst(t: AVLTree) -> res: bool {
    returns res == (t == null ? true : (all_less(t.left, t.val) && all_greater(t.right, t.val) && is_bst(t.left) && is_bst(t.right)));
}

oracle is_balanced(t: AVLTree) -> res: bool {
    returns res == (t == null ? true : (
        is_balanced(t.left) && 
        is_balanced(t.right) &&
        (get_height(t.left) - get_height(t.right) <= 1) && 
        (get_height(t.right) - get_height(t.left) <= 1)
    ));
}

oracle height_correct(t: AVLTree) -> res: bool {
    returns res == (t == null ? true : (
        t.height == (get_height(t.left) > get_height(t.right) ? get_height(t.left) + 1 : get_height(t.right) + 1) &&
        height_correct(t.left) && 
        height_correct(t.right)
    ));
}

oracle is_avl(t: AVLTree) -> res: bool {
    returns res == (is_bst(t) && is_balanced(t) && height_correct(t));
}

// --- Essential Theorems Oracles ---

// The minimum number of nodes in an AVL tree of height 'h'
// Theorem: N(h) = N(h-1) + N(h-2) + 1, with N(0)=0, N(1)=1.
// This recurrence leads to the O(log n) height bound.
oracle min_nodes(h: int) -> m: int {
    returns m == (h <= 0 ? 0 : (h == 1 ? 1 : 1 + min_nodes(h-1) + min_nodes(h-2)));
}

// Counts the actual number of nodes in the tree.
oracle count_nodes(t: AVLTree) -> c: int {
    returns c == (t == null ? 0 : 1 + count_nodes(t.left) + count_nodes(t.right));
}

// Variables for verification
root: AVLTree;
n_nodes: int;
h_root: int;
m_nodes: int;

%% preconditions
// Assume the input is a valid AVL tree.
is_avl(root) == true;

%% postconditions
// --- Essential Theorems of AVL Trees ---

// Theorem 1 (Search): An AVL tree is always a valid Binary Search Tree.
(is_bst(root) == true && 

// Theorem 2 (Balance): The height difference between any two sibling subtrees is at most 1.
is_balanced(root) == true && 

// Theorem 3 (Metadata): The stored height field is consistent with the actual tree structure.
height_correct(root) == true && 

// Theorem 4 (Height-Node Bound): An AVL tree of height 'h' has at least 'min_nodes(h)' nodes.
// This is the core structural theorem that guarantees h = O(log n).
n_nodes >= m_nodes && 

// Theorem 5 (Non-negativity): The height of any node is non-negative.
h_root >= 0);

%% program
n_nodes := count_nodes(root);
h_root  := get_height(root);
m_nodes := min_nodes(h_root);
