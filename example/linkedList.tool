%% declarations
struct List {
    val: int;
    next: List;
}

// 1. Recursive Length
oracle length(l: List) -> len: int {
    returns len == (l == null ? 0 : 1 + length(l.next));
}

// 2. Recursive Append
oracle append(l: List, x: int) -> new_l: List {
    returns new_l == (l == null ? mk_List(x, null) : mk_List(l.val, append(l.next, x)));
}

// 3. Recursive Contains
oracle contains(l: List, x: int) -> found: bool {
    returns found == (l == null ? false : (l.val == x ? true : contains(l.next, x)));
}

oracle is_sorted(l: List) -> res: bool {
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
            (x <= l.val) ? mk_List(x, l) : mk_List(x, insertSorted(l, x))
        ))
    );
}

// --- Variables for our Proof ---
original_list: List;
new_element: int;
new_list: List;
is_correct: bool;

%% preconditions
is_sorted(original_list);

%% postconditions
// We expect Z3 to return SAT, meaning our framework 
// successfully generated a refutation counter-example!
is_correct == true;

%% program
new_list := insertSorted(original_list, new_element);

// Validate the theorem: Appending exactly increases length by 1
is_correct := ((length(new_list) == length(original_list) + 1) && is_sorted(new_list) && contains(new_list, new_element));