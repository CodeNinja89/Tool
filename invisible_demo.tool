%% declarations
linear struct Box {
    val: int;
}

// Declare a physical linear resource
real_box: Box;

// Declare an invisible ghost variable
invisible ghost_box: Box;

v1: int;
v2: int;
is_ok: bool;
is_free: bool;

// An oracle that reads the Box without consuming it (refer)
oracle read_val(refer b: Box) -> v: int {
    returns v == b.val;
}

// An oracle that consumes the Box
oracle destruct(b: Box) -> ok: bool {
    returns ok == true;
}

%% preconditions

real_box != null;
real_box.val == 42;

%% postconditions

// We expect our checks to pass
is_ok == true;

%% program

// 1. Snapshotting the state
// Because ghost_box is 'invisible', the assignment acts like a 'refer'.
// The physical real_box is NOT consumed here.
ghost_box := real_box;

// 2. We can still read from the physical real_box!
v1 := read_val(real_box);

// 3. We can read from our ghost variable to verify it matched the snapshot
v2 := read_val(ghost_box);

// Assert they are the same
assert v1 == v2;
is_ok := (v1 == 42);

// 4. Memory Cleanup
// We must consume the physical resource to prevent memory leaks
is_free := destruct(real_box);

// And we must consume our ghost reference to satisfy the linear type checker
is_free := destruct(ghost_box);
