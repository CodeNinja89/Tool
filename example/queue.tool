%% declarations

// 1. The Enqueue Contract (The Frame Axiom)
// It returns a completely new sequence where index 't' equals 'element', 
// and EVERY other index 'i' is mathematically identical to the old sequence.

oracle enqueue(old_mem: seq[int], t: int, element: int) -> new_mem: seq[int] {
    returns (new_mem[t] == element) && 
            (forall i: int . (i == t) || (new_mem[i] == old_mem[i])) &&
            (new_mem.length == old_mem.length + 1);
}

// 2. The Dequeue Contract
// Dequeuing simply reads the value at the current 'h' index.
oracle dequeue(mem: seq[int], h: int, t: int) -> val: int {
    assumes mem.length > 0;
    returns val == mem[h];
}

// --- Variables for our Proof ---
mem: seq[int];
head: int;
tail: int;

x: int;
y: int;

temp_mem1: seq[int];
temp_mem2: seq[int];

val1: int;
val2: int;
val3: int;

is_fifo: bool;

%% preconditions
// Start with an empty queue at index 0
head == 0;
tail == 0;

%% postconditions
is_fifo == true;
head <= tail;

%% program

// 1. Enqueue 'x' and manually increment the tail pointer
temp_mem1 := enqueue(mem, tail, x);
tail := tail + 1;

assert temp_mem2.length > 0;

// 2. Enqueue 'y' and increment the tail pointer again
temp_mem2 := enqueue(temp_mem1, tail, y);
tail := tail + 1;

assert temp_mem2.length > 0;

// 3. Dequeue the first element and increment the head pointer
val1 := dequeue(temp_mem2, head);
head := head + 1;

// 4. Dequeue the second element
val2 := dequeue(temp_mem2, head);
head := head + 1;

val3 := dequeue(temp_mem2, head);
head := head + 1;

// 5. Verify the FIFO property: Did they come out in the exact order they went in?
is_fifo := (val1 == x) && (val2 == y);