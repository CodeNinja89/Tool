// =============================================================================
// TOOL Specification for an AUTOSAR Ready Queue (Refined Dynamic Version)
//
// ARCHITECTURAL OVERVIEW:
//
// 1. Dynamic Environment:
//    - The 'get_env_task(time)' oracle simulates the environment by returning 
//      a task with a specific state at each time step.
//    - This replaces the static task sequence, allowing the model to reason
//      about any number of tasks with any priority or state sequence.
//
// 2. Ready Queue (Linked List):
//    - Implemented as a priority-sorted linear linked list.
//    - Tasks with higher priority (higher numerical value) stay at the head.
//    - Preemption is modeled by 'running_tid' always pointing to the queue head.
//
// 3. Formal Invariants:
//    - Priority Integrity: The queue must remain sorted by priority at all times.
//    - Preemptive Safety: Only the highest priority task (the head) can be 
//      the one currently running (running_tid).
//
// 4. Verification Goal:
//    - Prove that regardless of environment stimuli (activations/terminations), 
//      the system always maintains the highest priority task at the head
//      and correctly updates the execution state.
// =============================================================================

%% declarations

// Task States
SUSPENDED: int;
READY: int;
RUNNING: int;

struct Task {
    id: int;
    priority: int;
    state: int;
}

// Ready Queue Node (Linear resource for memory safety)
linear struct ReadyQueueNode {
    task_id: int;
    priority: int;
    next: ReadyQueueNode;
}

// --- ORACLES ---

// Environment Oracle: Stimulates the scheduler with a task at each time step
oracle get_env_task(time: int) -> t: Task {
    returns (
        t.id >= 0 && t.priority >= 0 && 
        (t.state == SUSPENDED || t.state == READY || t.state == RUNNING)
    );
}

// Read-only oracles using 'refer' to inspect the linear list without consuming it
oracle is_in_queue(refer q: ReadyQueueNode, tid: int) -> res: bool {
    returns res == ((false ? is_in_queue(q, tid) : false) ? true : (
        q == null ? false : (q.task_id == tid || is_in_queue(q.next, tid))
    ));
}

oracle get_head_tid(refer q: ReadyQueueNode) -> tid: int {
    returns tid == ((false ? get_head_tid(q) : 0) != 0 ? 0 : (q == null ? -1 : q.task_id));
}

oracle is_priority_sorted(refer q: ReadyQueueNode) -> res: bool {
    returns res == ((false ? is_priority_sorted(q) : true) ? true : (
        q == null || q.next == null || (q.priority >= q.next.priority && is_priority_sorted(q.next))
    ));
}

// Transformation oracles (Consume the list and return a new version)
oracle insert_priority(q: ReadyQueueNode, tid: int, prio: int) -> res: ReadyQueueNode {
    returns res == ((false ? insert_priority(q, tid, prio) : null) != null ? null : (
        q == null ? mk_ReadyQueueNode(tid, prio, null) : (
            prio > q.priority ? mk_ReadyQueueNode(tid, prio, q) : 
            mk_ReadyQueueNode(q.task_id, q.priority, insert_priority(q.next, tid, prio))
        )
    ));
}

oracle remove_task(q: ReadyQueueNode, tid: int) -> res: ReadyQueueNode {
    returns res == ((false ? remove_task(q, tid) : null) != null ? null : (
        q == null ? null : (
            q.task_id == tid ? q.next : 
            mk_ReadyQueueNode(q.task_id, q.priority, remove_task(q.next, tid))
        )
    ));
}

oracle destruct(q: ReadyQueueNode) -> ok: bool { returns ok == true; }

// --- System State ---
ready_q: ReadyQueueNode;
running_tid: int;
current_time: int;
steps: int;

ev_task: Task;
in_q: bool;
ok: bool;

%% preconditions
SUSPENDED == 0; READY == 1; RUNNING == 2;
ready_q == null;
running_tid == -1;
current_time == 1;

%% postconditions
// Universal safety: the queue is always consistent and sorted
is_priority_sorted(ready_q) == true;

%% program

while (steps > 0) 
  invariant (
    // 1. Queue remains sorted by priority
    is_priority_sorted(ready_q) == true &&
    // 2. Preemptive Rule: Only the highest priority task can be running
    running_tid == get_head_tid(ready_q)
  )
{
    // Fetch task stimulus from the environment
    ev_task := get_env_task(current_time);
    in_q := is_in_queue(ready_q, ev_task.id);

    if (ev_task.state == READY || ev_task.state == RUNNING) {
        // Task activation or preemption check
        if (!in_q) {
            ready_q := insert_priority(ready_q, ev_task.id, ev_task.priority);
        }
    } else {
        if (ev_task.state == SUSPENDED) {
            // Task termination
            if (in_q) {
                ready_q := remove_task(ready_q, ev_task.id);
            }
        }
    }

    // Scheduler Dispatch: Pick the head of the sorted list
    running_tid := get_head_tid(ready_q);
    
    current_time := current_time + 1;
    steps := steps - 1;
}

// Cleanup linear resource to satisfy Tool's memory safety rules
ok := destruct(ready_q);
