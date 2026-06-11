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

oracle is_sorted(refer l: List) -> res: bool { // the list is sorted in ascending order
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
new_list: List;
invisible temp: List; // ghost variable!
is_free: bool;
is_correct: bool;
val: int; // value to be inserted

%% preconditions

is_sorted(original_list);
length(original_list) > 1;

%% postconditions

is_correct == false; // invoke proof-by-refutation to generate a witness

%% program

temp := original_list; // we save the old state of the list in a specification only variable. This does not consume the linear struct.

new_list := insertSorted(original_list, val);
is_correct := (
    (length(new_list) == length(temp) + 1) && 
    (is_sorted(new_list))
);

// if we try to re-assign "original_list" to "temp", it will fail because original_list was already consumed. We cannot make an alias!
// temp := original_list;

// is_free := destruct(original_list); // no need to explicitly consume the "original_list". It was consumed by insertSorted
is_free := destruct(temp);
is_free := destruct(new_list);