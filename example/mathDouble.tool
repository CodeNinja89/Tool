%% declarations

// Our new first-class trace!
// We perform the * 2 math directly in the inductive step
trace double_trace(t: timestep) -> s: int {
    init:
        s == 1;
    step:
        s == double_trace(t - 1) * 2;
}

is_correct: bool;

%% preconditions

%% postconditions
is_correct == true;

%% program

// Assert that at timestep 3, the value has doubled three times: 1 -> 2 -> 4 -> 8
assert double_trace(3) == 8;

is_correct := true;