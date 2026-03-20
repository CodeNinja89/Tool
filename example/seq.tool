%% declarations
my_array: seq[uint32];
x: uint32;

%% preconditions
my_array[0] == 0u32;
forall i: uint32 . forall j: uint32 . my_array[i] < my_array[j];

%% postconditions
x == 42u32;
my_array[1] == 42u32;

%% program
// 1. Mutate the sequence (LHS)
my_array[0] := 42u32;

// 2. Read from the sequence (RHS)
x := my_array[0];

// 3. Mutate again using the read variable
my_array[1] := x;