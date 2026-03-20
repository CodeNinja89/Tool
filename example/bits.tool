%% declarations
status_reg: uint32;
mask: uint32;
is_ready: bool;

// Our oracle defines a pure mathematical contract for a bitwise flag check
oracle check_flag(state: uint32, m: uint32) -> res: bool {
    assumes m != 0;
    // Returns true if the bits defined by 'm' are fully set in 'state'
    returns res == ((state & m) == m);
}

%% preconditions
status_reg == 14;  // Binary: 1110
mask == 2;         // Binary: 0010

x == 0;

%% postconditions
is_ready == true;

%% program
// 1. Call the oracle
is_ready := check_flag(status_reg, mask);

// 2. Perform some local bitwise math just to test the AST
status_reg := status_reg ^ mask; // XOR to flip the bit
status_reg := status_reg << 1;   // Shift left

if (flag == true) {
    x := x + 1;
} else {
    x := x + 2;
}