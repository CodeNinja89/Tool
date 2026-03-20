%% declarations
struct Node {
    value: uint32;
    next: uint32;
}

current_node: Node;
temp_val: uint32;

%% preconditions
current_node.value == 0;
current_node.next == 0;

%% postconditions
temp_val == 5;
current_node.value == 5;
current_node.next == 10;

%% program
// 1. Assign to a struct field (LHS update)
current_node.value := 5;

// 2. Read from a struct field (RHS access)
temp_val := current_node.value;

// 3. Assign to another field 
current_node.next := 10;