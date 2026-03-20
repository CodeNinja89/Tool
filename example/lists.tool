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
footprint.length == 1000;
footprint[2] == footprint[3]; // FORCE A COLLISION (A CYCLE)

%% postconditions
is_safe == true;
%% program

is_safe := is_acyclic(footprint);