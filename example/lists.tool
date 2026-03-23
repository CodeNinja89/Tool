%% declarations
struct ListNode {
    val: int;
    next: ListNode; // <-- Direct recursion! Z3 perfectly supports this.
}

is_safe: bool;
footprint: seq[ListNode]; // <-- The footprint is a global sequence of memory

null_ListNode: ListNode;

oracle is_acyclic(ghostFootprint: seq[ListNode]) -> acyclic: bool {
    assumes ghostFootprint.length > 0;
    returns acyclic == (
        forall i: int . forall j: int .
            !( (i < ghostFootprint.length) && (j < ghostFootprint.length) && (i != j) ) 
            || 
            (ghostFootprint[i] != ghostFootprint[j])
    );
}

oracle terminates(ghostFootprint: seq[ListNode], null: ListNode) -> ok: bool {
    assumes (ghostFootprint.length > 0 && 
        is_acyclic(ghostFootprint) == true);
    returns ok == (
        (forall i: int .
            !(
                (i >= 0) &&
                (i + 1 < ghostFootprint.length)
            )
            ||
            (ghostFootprint[i].next == ghostFootprint[i + 1])
        )

        &&

        (ghostFootprint[ghostFootprint.length - 1].next == null)
    );
}

%% preconditions
footprint.length > 0;
is_acyclic(footprint) == true;
terminates(footprint, null_ListNode) == true;

%% postconditions
is_safe == true;
%% program
is_safe := is_acyclic(footprint);