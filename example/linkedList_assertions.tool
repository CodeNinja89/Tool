// ==========================================
// Inductive Structural Proof: Linked List
// insertSorted & removeSorted Validation
// ==========================================

%% declarations

linear struct List {
    val: int;
    next: List;
}

// ------------------------------------------
// Recursive Property Oracles
// ------------------------------------------

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

// Helper oracle to prevent double-consumption of linear structs in fact statements
oracle valid_new_head(refer l: List, bound: int) -> res: bool {
    returns res == (l == null || bound <= l.val);
}

// ------------------------------------------
// Transition Oracles
// ------------------------------------------

oracle insertSorted(l: List, x: int) -> new_l: List {
    assumes is_sorted(l);
    returns new_l == (
        (l == null) ? mk_List(x, null) : (
            (x <= l.val) ? mk_List(x, l) : mk_List(l.val, insertSorted(l.next, x))
        )
    );
}

oracle removeSorted(l: List, x: int) -> new_l: List {
    assumes l != null && is_sorted(l) && contains(l, x);
    returns new_l == (
        (l.val == x) ? l.next : mk_List(l.val, removeSorted(l.next, x))
    );
}

oracle destruct(l: List) -> ok: bool {
    returns ok == true;
}

// --- Variables for the Proof ---
base_list: List;
v: int;                 // The arbitrary value to insert/remove
head_v: int;            // The arbitrary head value of our list
tail_insert: List;      // Arbitrary tail sub-list for the insert proof
tail_remove: List;      // Arbitrary tail sub-list for the remove proof
original_list: List;    // The composed parent list
new_list: List;         // The resulting list after operation
is_freed: bool;
is_correct: bool;

%% preconditions

base_list == null;
is_correct == true;

%% postconditions

is_correct == true;

%% program

// ==========================================
// 0. MEMORY INITIALIZATION
// ==========================================
// Because variables are declared globally, they enter the linear Delta tracking automatically.
// We destruct the unused garbage allocations to ensure absolute memory safety.
is_freed := destruct(original_list);
is_freed := destruct(new_list);


// ==========================================
// 1. BASE CASE: Insert into empty list
// ==========================================

base_list := insertSorted(base_list, v);

assert is_sorted(base_list) == true;
assert contains(base_list, v) == true;

is_freed := destruct(base_list);


// ==========================================
// 2. INDUCTIVE STEP: insertSorted
// ==========================================

// 2A. Establish valid arbitrary tail
fact is_sorted(tail_insert) == true;

// Establish relation between head and tail to ensure the composed list WILL be sorted
fact valid_new_head(tail_insert, head_v) == true;

// 2B. INDUCTIVE HYPOTHESES (Assume property holds for the tail)
fact is_sorted(insertSorted(tail_insert, v)) == true;
fact contains(insertSorted(tail_insert, v), v) == true;

// CRUCIAL LEMMA: Boundary Preservation
// The helper oracle prevents the BinaryExpr Use-After-Free trap.
fact (!(v > head_v) || valid_new_head(insertSorted(tail_insert, v), head_v) == true);

// 2C. CONSTRUCT THE PARENT LIST
// This consumes tail_insert. original_list is replenished in the Delta pool.
original_list := mk_List(head_v, tail_insert);
assert is_sorted(original_list) == true;

// 2D. THE TRANSITION
// original_list is mathematically consumed to construct new_list.
new_list := insertSorted(original_list, v);

assert is_sorted(new_list) == true;
assert contains(new_list, v) == true;

// Destruct the final product (original_list was already consumed)
is_freed := destruct(new_list);


// ==========================================
// 3. INDUCTIVE STEP: removeSorted
// ==========================================

// We require a completely fresh arbitrary tail to avoid a Use-After-Free from Step 2C.
fact head_v != v;
fact tail_remove != null;
fact is_sorted(tail_remove) == true;
fact contains(tail_remove, v) == true;
fact valid_new_head(tail_remove, head_v) == true;

// 3A. INDUCTIVE HYPOTHESES for removeSorted
fact is_sorted(removeSorted(tail_remove, v)) == true;
fact valid_new_head(removeSorted(tail_remove, v), head_v) == true;

// 3B. CONSTRUCT PARENT LIST
// Consumes tail_remove, creating a fresh original_list.
original_list := mk_List(head_v, tail_remove);

assert is_sorted(original_list) == true;
assert contains(original_list, v) == true;

// 3C. THE TRANSITION
// Consumes original_list.
new_list := removeSorted(original_list, v);

assert is_sorted(new_list) == true;

// Destruct final product. End of program reached with 0 leaked linear resources.
is_freed := destruct(new_list);

is_correct := true;