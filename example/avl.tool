%% declarations
struct AVLTree {
    val: int;
    height: int;
    left: AVLTree;
    right: AVLTree;
}

// By forcing a structural self-reference, we ensure the Tool compiler 
// treats this as a universally quantified z3.RecFunction, avoiding 
// spurious uninterpreted function counter-examples without relying on magic values.
oracle get_height(t: AVLTree) -> h: int {
    returns h == (t == null ? 0 : t.height + get_height(null));
}

oracle get_balance(t: AVLTree) -> bal: int {
    returns bal == (t == null ? 0 : get_height(t.left) - get_height(t.right) + get_balance(null));
}

oracle mk_node(v: int, l: AVLTree, r: AVLTree) -> n: AVLTree {
    returns n == (v == v ? mk_AVLTree(v, (get_height(l) > get_height(r) ? get_height(l) + 1 : get_height(r) + 1), l, r) : mk_node(v, l, r));
}

oracle right_rotate(y: AVLTree) -> res: AVLTree {
    returns res == (y == y ? 
        (y == null ? null : 
            (y.left == null ? y : 
                mk_node(y.left.val, y.left.left, mk_node(y.val, y.left.right, y.right))
            )
        ) : right_rotate(y)
    );
}

oracle left_rotate(x: AVLTree) -> res: AVLTree {
    returns res == (x == x ? 
        (x == null ? null : 
            (x.right == null ? x : 
                mk_node(x.right.val, mk_node(x.val, x.left, x.right.left), x.right.right)
            )
        ) : left_rotate(x)
    );
}

oracle balance(t: AVLTree) -> res: AVLTree {
    returns res == (t == t ? 
        (t == null ? null : (
            get_balance(t) > 1 ? (
                get_balance(t.left) < 0 ? 
                    right_rotate(mk_node(t.val, left_rotate(t.left), t.right)) : 
                    right_rotate(t)
            ) : (
                get_balance(t) < -1 ? (
                    get_balance(t.right) > 0 ? 
                        left_rotate(mk_node(t.val, t.left, right_rotate(t.right))) : 
                        left_rotate(t)
                ) : t
            )
        )) : balance(t)
    );
}

oracle insert_avl(t: AVLTree, x: int) -> new_t: AVLTree {
    returns new_t == (
        t == null ? mk_AVLTree(x, 1, null, null) : (
            x == t.val ? t : (
                balance(
                    x < t.val ? 
                        mk_node(t.val, insert_avl(t.left, x), t.right) : 
                        mk_node(t.val, t.left, insert_avl(t.right, x))
                )
            )
        )
    );
}

oracle contains(t: AVLTree, x: int) -> found: bool {
    returns found == (
        (t == null) ? false : (
            (x == t.val) ? true : (
                (x < t.val) ? contains(t.left, x) : contains(t.right, x)
            )
        )
    );
}

oracle all_less(tl: AVLTree, vl: int) -> resl: bool {
    returns resl == (tl == null ? true : (tl.val < vl && all_less(tl.left, vl) && all_less(tl.right, vl)));
}

oracle all_greater(tg: AVLTree, vg: int) -> resg: bool {
    returns resg == (tg == null ? true : (tg.val > vg && all_greater(tg.left, vg) && all_greater(tg.right, vg)));
}

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
    returns res == (t == t ? (is_bst(t) && is_balanced(t) && height_correct(t)) : is_avl(t));
}

root: AVLTree;
val_to_insert: int;
new_root: AVLTree;
is_valid: bool;

%% preconditions
is_avl(root) == true;
root != null;

%% postconditions
// We ask Z3 to refute this explicitly quantified property:
// "For ALL integers 'v', inserting 'v' into the tree results in a valid AVL tree."

(forall v: int . (is_avl(insert_avl(root, v)) == true)) == false;
// is_valid == true;

%% program
new_root := insert_avl(root, val_to_insert);
is_valid := (is_avl(new_root) && contains(new_root, val_to_insert));