%% declarations
// 1. The Oracles (Our Axiomatic Hardware Boundaries)
oracle enter_critical(current_state: bool) -> next_state: bool {
    assumes current_state == false;
    returns next_state == true;
}

oracle exit_critical(current_state: bool) -> next_state: bool {
    assumes current_state == true;
    returns next_state == false;
}

// 2. The Global State
is_atomic: bool;
shared_resource: uint32;

%% preconditions
is_atomic == false;
shared_resource == 0;

%% postconditions
shared_resource == 1;
is_atomic == false;

%% program
// The implementation intent: Safely increment the resource
is_atomic := enter_critical(is_atomic);
shared_resource := shared_resource + 1;
is_atomic := exit_critical(is_atomic);