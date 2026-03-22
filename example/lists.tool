%% declarations
struct ListNode {
    val: int;
    next: ListNode; // <-- Direct recursion! Z3 perfectly supports this.
}

is_safe: bool;
footprint: seq[ListNode]; // <-- The footprint is a global sequence of memory

oracle is_acyclic(ghostFootprint: seq[ListNode]) -> acyclic: bool {
    assumes ghostFootprint.length > 0;
    returns acyclic == (
        forall i: int . forall j: int .
            !( (i < ghostFootprint.length) && (j < ghostFootprint.length) && (i != j) ) 
            || 
            (ghostFootprint[i] != ghostFootprint[j])
    );
}

%% preconditions
footprint.length > 0;

exists i: int . exists j: int . 
    (i >= 0 && i < footprint.length) && 
    (j >= 0 && j < footprint.length) && 
    (i != j) && 
    (footprint[i] == footprint[j]); // force a collision

%% postconditions
is_safe == true; // assert something wrong. in this case, we check if the list is acyclic. This is a contradiction because in the preconditions we explicitly forced a collision.
%% program

is_safe := is_acyclic(footprint);