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
<<<<<<< Updated upstream
new_list: List;
invisible temp: List; // ghost variable!
is_free: bool;
is_correct: bool;
val: int; // value to be inserted
=======
alias1: List;
alias2: List;
is_free: bool;
is_correct: bool;
v: int;
>>>>>>> Stashed changes

%% preconditions

is_sorted(original_list);
length(original_list) > 1;
!contains(original_list, v);

%% postconditions

<<<<<<< Updated upstream
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
=======
is_correct == false; // proof-by-refutation. We use this approach because raw SMT struggles with recursive definitions. 
// Dafny and all emit a lot of metadata that help Z3 backend to verify such recursive definitions but that is not yet
// implemented in TOOL. And probably never will be... TOOL is a SPECIFICATION LANGUAGE and not a theorem prover!

%% program

alias1 := original_list;
// alias2 := original_list; // error... alias1 owns the list.

original_list := insertSorted(alias1, v); // the original_list is updated.
is_correct := is_sorted(original_list);

alias2 := original_list; // alias2 takes ownership

original_list := removeSorted(alias2, v); // updated list. 

// the "original_list" on line 58 and original_list in line 78 are two distinct lists with the same label. similarly, the original_list is again consumed on line 81.
// the one of line 58 does not exist any more. neither does the one at line 81.

is_correct := (is_sorted(original_list) && !contains(original_list, v));

is_free := destruct(original_list); // explicitly consume the list using a dummy function. this is akin to free().
>>>>>>> Stashed changes
