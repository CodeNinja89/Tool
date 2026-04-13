%% declarations
struct EnqueueResult {
    new_mem: seq[int];
    new_tail: int;
}

oracle enqueue_circular(old_mem: seq[int], capacity: int, head: int, tail: int, value: int) -> res: EnqueueResult {
    assumes (capacity > 0) && (head >= 0) && (tail >= 0) && (((tail + 1) % capacity) != head);
    returns (res.new_mem[tail] == value) && 
            (res.new_tail == ((tail + 1) % capacity)) && 
            (forall i: int . (i == tail) || (res.new_mem[i] == old_mem[i]));
}

mem: seq[int];
capacity: int;
head: int;
tail: int;
new_value: int;

res: EnqueueResult;
is_correct: bool;

%% preconditions
capacity > 0;
head >= 0;
tail >= 0;
((tail + 1) % capacity) != head;

%% postconditions
is_correct == true;

%% program
res := enqueue_circular(mem, capacity, head, tail, new_value);

is_correct := (res.new_mem[tail] == new_value) && 
              (res.new_tail == ((tail + 1) % capacity));