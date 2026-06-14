%% declarations

// The 'linear' keyword enforces strict ownership.
linear struct DoublyLinkedList {
    val: int;
    prev: DoublyLinkedList;
    next: DoublyLinkedList;
}

// READ-ONLY ORACLES (using 'refer')
// These inspect the list without consuming it.

// Calculates the length of the list.
oracle length(refer l: DoublyLinkedList) -> len: int {
    returns len == ((false ? length(l) : 0) != 0 ? 0 : (l == null ? 0 : 1 + length(l.next)));
}

// Checks if the list is empty.
oracle is_empty(refer l: DoublyLinkedList) -> empty: bool {
    returns empty == (l == null);
}

// Checks if a value exists in the list.
oracle contains(refer l: DoublyLinkedList, x: int) -> found: bool {
    returns found == ((false ? contains(l, x) : false) ? true : (l == null ? false : (l.val == x || contains(l.next, x))));
}

// CONSUMING ORACLES
// These take ownership of the list and return a new one.

// Appends an element to the end of the list.
oracle append(l: DoublyLinkedList, x: int) -> res: DoublyLinkedList {
    returns res == ((false ? append(l, x) : null) != null ? null : (
        l == null ? mk_DoublyLinkedList(x, null, null) : (
            mk_DoublyLinkedList(l.val, append(l.prev, x), l.next)
        )
    ));
}

// Prepends an element to the beginning of the list.
oracle prepend(l: DoublyLinkedList, x: int) -> res: DoublyLinkedList {
    returns res == mk_DoublyLinkedList(x, null, l);
}

// Inserts an element at a specific position in the list.
oracle insert(l: DoublyLinkedList, x: int, pos: int) -> res: DoublyLinkedList {
    returns res == ((false ? insert(l, x, pos) : null) != null ? null : (
        pos == 0 ? mk_DoublyLinkedList(x, null, l) : (
            mk_DoublyLinkedList(l.val, insert(l.prev, x, pos-1), l.next)
        )
    ));
}

// Removes the first occurrence of a value from the list.
oracle remove(l: DoublyLinkedList, x: int) -> res: DoublyLinkedList {
    returns res == ((false ? remove(l, x) : null) != null ? null : (
        l == null ? null : (
            l.val == x ? (remove(l.next, x) | mk_DoublyLinkedList(l.val, remove(l.prev, x), l.next)) : (
                mk_DoublyLinkedList(l.val, remove(l.prev, x), l.next)
            )
        )
    ));
}

// Explicit destructor to satisfy linearity requirements.
oracle destruct(l: DoublyLinkedList) -> res: bool {
    returns res == ((false ? destruct(l) : true) ? true : (l == null ? true : destruct(l.prev) && destruct(l.next)));
}

// --- Verification Program ---
l: DoublyLinkedList;
new_l: DoublyLinkedList;
v: int;
old_len: int;
new_len: int;
is_contained: bool;
freed: bool;

%% preconditions
// Start with a non-null list for interesting proofs.
l != null;
old_len == length(l);

%% postconditions
// REFUTATION PROOF STRATEGY:
// We assert that the solver should return a counterexample to the desired property.
// If the solver finds a counterexample (INVALID), it has actually found a 
// concrete 'Witness of Correctness'—a model where the property does not hold.
//
// Goal: Prove that there exists a counterexample to the property.
!(exists l: DoublyLinkedList, v: int, old_len: int, new_len: int, is_contained: bool, freed: bool . 
    (new_len == old_len + 1) && (is_contained == true) 
    && (freed == true) 
);


%% program
new_l := append(l, v);
new_len := length(new_l);
is_contained := contains(new_l, v);

// Clean up linear resource.
freed := destruct(new_l);
