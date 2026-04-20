// =============================================================================
// Inter-Core Ring Buffer: Sender Protocol (Verified Model)
// =============================================================================

%% declarations
struct core {
    id: int;
    atomicity: bool;
    notification: bool;
}

struct message {
    toCore: int;
    fromCore: int;
    opcode: int;
    result: seq[int];
    params: seq[int];
}

struct messageQ {
    messages: seq[message];
    tail: int;
    head: int;
}

// Map from core index to its ring buffer
core_queues: seq[messageQ];

oracle next_idx(curr: int, cap: int) -> nxt: int {
    returns nxt == ((curr + 1) % cap);
}

// State
thisCore: core;
targetCore: core;
msg: message;
is_full: bool;
capacity: int;
old_tail: int;

// Working local variables to avoid nested SSA limitations
q: messageQ;
q_msgs: seq[message];
q_tail: int;
q_head: int;
target_id: int;

%% preconditions
capacity > 1;
target_id == targetCore.id;
q == core_queues[target_id];

// Pointer and capacity constraints
q.head >= 0 && q.head < capacity;
q.tail >= 0 && q.tail < capacity;
capacity == q.messages.length;

msg.fromCore == thisCore.id;
msg.toCore == targetCore.id;

%% postconditions
// NEGATION of the entire property
!( (core_queues[target_id].messages[old_tail].fromCore == thisCore.id) && 
   (core_queues[target_id].tail == (old_tail + 1) % capacity) &&
   (targetCore.atomicity == false) );

%% program
target_id := targetCore.id;
is_full := true;

while (is_full == true)
    invariant (true)
{
    targetCore.atomicity := true;
    
    // Pull from shared mapping into local working copy
    q := core_queues[target_id];
    q_msgs := q.messages;
    q_tail := q.tail;
    q_head := q.head;

    is_full := (next_idx(q_tail, capacity) == q_head);

    if (is_full == true) {
        targetCore.atomicity := false;
    }
}

// Logic: Atomicity is enabled.
old_tail := q_tail;

// DIRECT array write
q_msgs[old_tail] := msg;
q_tail := next_idx(q_tail, capacity);

// Reassemble the struct
q.messages := q_msgs;
q.tail := q_tail;
q.head := q_head;

// Commit back to mapping (Single-level assignment is supported)
core_queues[target_id] := q;

targetCore.atomicity := false;
targetCore.notification := true;
