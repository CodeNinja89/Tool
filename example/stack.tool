%% declarations
struct Stack {
    val: int;
    next: Stack;
}

// 1. The Push Contract
// Pushing an element creates a stack where 'val' is the element, and 'next' is the old stack.

oracle push(old_stack: Stack, element: int) -> new_stack: Stack {
    // A pushed stack is NEVER null, and its fields match the inputs
    returns (new_stack != null) && (new_stack.val == element) && (new_stack.next == old_stack);
}

// 2. The Pop (Value) Contract
// Popping returns the value at the top of the stack.
oracle pop_val(s: Stack) -> v: int {
    assumes s != null;
    returns v == s.val;
}

// 3. The Pop (State) Contract
// Popping also returns the rest of the stack underneath.

oracle pop_next(s: Stack) -> rest: Stack {
    assumes s != null;
    returns rest == s.next;
}


// --- Variables for our Proof ---
original_stack: Stack;
x: int;

temp_stack: Stack;
popped_val: int;
final_stack: Stack;

is_correct: bool;

%% preconditions
// We start with ANY arbitrary stack and ANY arbitrary integer 'x'.
// No preconditions are needed.

%% postconditions

// we deliberately try to verify a contradiction
// 1. if the solver returns UNSAT => the framework is broken. we verified a contradiction
// 2. if the solver returns SAT => the solver generates a counterexample and we know that the framework discharges correct VCs
// 3. if the solver times out => either the VCs are too complicated or we need to help the solver with some assertions.

is_correct == false;

%% program

// 1. Push 'x' onto the original stack
temp_stack := push(original_stack, x);

// 2. Pop the value and the rest of the stack
popped_val := pop_val(temp_stack);
final_stack := pop_next(temp_stack);

// 3. Verify the LIFO property: 
// Did we get 'x' back? Is the stack exactly the same as when we started?
is_correct := (popped_val == x) && (final_stack == original_stack);
