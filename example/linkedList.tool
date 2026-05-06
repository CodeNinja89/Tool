%% declarations
linear struct List {
    val: int;
    next: List;
}

oracle destruct(l: List) -> ok: bool {
    returns ok == true;
}

// 1. Recursive Length
oracle length(refer l: List) -> len: int {
    returns len == (l == null ? 0 : 1 + length(l.next));
}

// 2. Recursive Append
oracle append(l: List, x: int) -> new_l: List {
    returns new_l == (l == null ? mk_List(x, null) : mk_List(l.val, append(l.next, x)));
}

// 3. Recursive Contains
oracle contains(refer l: List, x: int) -> found: bool {
    returns found == (l == null ? false : (l.val == x ? true : contains(l.next, x)));
}

oracle is_sorted(refer l: List) -> res: bool {
    returns res == (
        (l == null) ? true : (
            (l.next == null) ? true : (
                (l.val <= l.next.val) ? is_sorted(l.next) : false
            )
        )
    );
}

oracle insertSorted(l: List, x: int) -> new_l: List {
    assumes is_sorted(l);
    returns new_l == (
        (l == null ? mk_List(x, l) : (
            (x <= l.val) ? mk_List(x, l) : mk_List(l.val, insertSorted(l.next, x))
        ))
    );
}

// --- Variables for our Proof ---

original_list: List;
is_free: bool;
is_correct: bool;

%% preconditions
is_sorted(original_list);
length(original_list) > 1;

%% postconditions

is_correct == false;

%% program

is_correct := (
    (forall v: int . length(insertSorted(original_list, v)) == length(original_list) + 1) &&
    (forall v: int . is_sorted(insertSorted(original_list, v)) == true) &&
    (forall v: int . contains(insertSorted(original_list, v), v) == true)
);

is_free := destruct(original_list);