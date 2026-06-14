%% declarations

SUSPENDED: int;
READY: int;
RUNNING: int;

struct Task {
    id: int;
    priority: int;
    state: int;
}

linear struct TaskQueue {
    t: Task;
    next: TaskQueue;
}

oracle get_env_task(time: int) -> t: Task {
    returns (
        t.id >= 0 && t.priority >= 0 && 
        (t.state == SUSPENDED || t.state == READY || t.state == RUNNING)
    );
}

oracle destruct(q: TaskQueue) -> ok: bool {
    returns ok == true;
}

oracle insert_sorted(q: TaskQueue, t: Task) -> new_q: TaskQueue {
    returns new_q == (
        q == null ? mk_TaskQueue(t, null) :
        (t.priority > q.t.priority ? 
            mk_TaskQueue(t, q) : 
            mk_TaskQueue(q.t, insert_sorted(q.next, t))
        )
    );
}

oracle activate_task(q: TaskQueue, t: Task) -> new_q: TaskQueue {
    // Dummy recursion trick for non-recursive ADT transformer
    returns new_q == (false ? activate_task(null, t) : insert_sorted(q, mk_Task(t.id, t.priority, READY)));
}

oracle set_all_ready(q: TaskQueue) -> new_q: TaskQueue {
    returns new_q == (
        q == null ? null :
        mk_TaskQueue(
            mk_Task(q.t.id, q.t.priority, READY),
            set_all_ready(q.next)
        )
    );
}

oracle enforce_states(q: TaskQueue) -> valid_q: TaskQueue {
    // Dummy recursion trick for non-recursive ADT transformer
    returns valid_q == (false ? enforce_states(null) :
        (q == null ? null :
            mk_TaskQueue(
                mk_Task(q.t.id, q.t.priority, RUNNING),
                set_all_ready(q.next)
            )
        )
    );
}

oracle terminate_running(q: TaskQueue) -> new_q: TaskQueue {
    // Dummy recursion trick for non-recursive ADT transformer
    returns new_q == (false ? terminate_running(null) : enforce_states(q.next));
}

oracle is_sorted(refer q: TaskQueue) -> res: bool {
    returns res == (
        q == null ? true :
        (q.next == null ? true :
            (q.t.priority >= q.next.t.priority && is_sorted(q.next))
        )
    );
}

oracle all_ready(refer q: TaskQueue) -> res: bool {
    returns res == (
        q == null ? true :
        (q.t.state == READY && all_ready(q.next))
    );
}

oracle is_valid_state(refer q: TaskQueue) -> res: bool {
    // Dummy recursion trick for non-recursive ADT transformer
    returns res == (false ? is_valid_state(null) :
        (q == null ? true :
        (q.t.state == RUNNING && all_ready(q.next)))
    );
}

oracle is_not_null(refer q: TaskQueue) -> res: bool {
    // Dummy recursion trick for non-recursive ADT transformer
    returns res == (false ? is_not_null(null) : (q != null));
}

// --- Variables ---
q: TaskQueue;
time: int;
env_t: Task;
ok: bool;

%% preconditions
SUSPENDED == 0;
READY == 1;
RUNNING == 2;
q == null; // starts empty
time == 0;

%% postconditions
is_sorted(q) == true;
is_valid_state(q) == true;

%% program

while (time < 5) 
  invariant (is_sorted(q) && is_valid_state(q) && time >= 0) 
{
    env_t := get_env_task(time);
    
    // We only simulate activations of suspended tasks
    if (env_t.state == SUSPENDED) {
        q := activate_task(q, env_t);
        q := enforce_states(q); 
    }

    if (is_not_null(q)) {
        // Terminate running task on even time steps
        if (time % 2 == 0) {
            q := terminate_running(q);
        }
    }

    time := time + 1;
}

ok := destruct(q);
