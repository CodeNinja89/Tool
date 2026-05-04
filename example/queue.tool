%% declarations

// 1. The Enqueue Contract (The Frame Axiom)
// It returns a completely new sequence where index 't' equals 'element', 
// and EVERY other index 'i' is mathematically identical to the old sequence.

oracle enqueue(old_mem: seq[int], t: int, element: int) -> new_mem: seq[int] {
    assumes t >= 0; // the write pointer must be positive
    returns (new_mem[t] == element) && 
            (forall i: int . (i == t) || (new_mem[i] == old_mem[i])) &&
            (new_mem.length == old_mem.length + 1);
}

// 2. The Dequeue Contract
// Dequeuing simply reads the value at the current 'h' index.
oracle dequeue(mem: seq[int], h: int, t: int) -> val: int {
    // the read pointer must not be negative and is strictly less than the write pointer.
    // h == t indicates that the queue is empty

    assumes (h >= 0) && (h < t);
    returns val == mem[h];
}

// --- Variables for our Proof ---
mem: seq[int];
head: int;
tail: int;

x: int;
y: int;

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
mem := enqueue(mem, tail, x);
tail := tail + 1;

// 2. Enqueue 'y' and increment the tail pointer again
mem := enqueue(mem, tail, y);
tail := tail + 1;

// 3. Dequeue the first element and increment the head pointer
val1 := dequeue(mem, head, tail);
head := head + 1;

// 4. Dequeue the second element
val2 := dequeue(mem, head, tail);
head := head + 1;

// let's try to dequeue one more element. This should fail.

// val3 := dequeue(mem, head, tail);
// head := head + 1;

// 5. Verify the FIFO property: Did they come out in the exact order they went in?
is_fifo := (val1 == x) && (val2 == y);