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

// recursive insert.
// essentially, we construct and return a new list.
// let "i" be the position we want to insert an element.
// insertion is:
// upto = list[0 .. i - 1]
// from = list[i + 1 .. len(list)]
// new_l = upto ++ [i] ++ from (++ is the append operator for sequences in Dafny)

oracle insertSorted(l: List, x: int) -> new_l: List {
    assumes is_sorted(l);
    returns new_l == (
        (l == null ? mk_List(x, l) : (
            (x <= l.val) ? mk_List(x, l) : mk_List(l.val, insertSorted(l.next, x))
        ))
    );
}

oracle removeSorted(l: List, x: int) -> new_l: List {
    assumes l != null && is_sorted(l) && contains(l, x);
    returns new_l == (
        l == null ? null : (
            l.val == x ? removeSorted(l.next, x) : (
                mk_List(l.val, removeSorted(l.next, x))
            )
        )
    );
}

// --- Variables for our Proof ---

original_list: List;
alias1: List;
alias2: List;
is_correct: bool;
v: int;

%% preconditions
is_sorted(original_list);
length(original_list) > 1;
!contains(original_list, v);

%% postconditions

is_correct == false;

%% program

alias1 := original_list;
alias2 := original_list; // since the List struct is not linear, aliasing is allowed.

original_list := insertSorted(alias1, v);
is_correct := is_sorted(original_list);

// TOOL does not have pointers so alias1 is completely independent of alias2.
// alias2 is unaware of any update alias1 makes to the list.
// this leads to call-site violation. because remove expects the element to be
// there in the list. however, since only alias1 updated the list, alias2's 
// copy of the list could not see the update.

original_list := removeSorted(alias2, v);
is_correct := (is_sorted(original_list) && !contains(original_list, v));