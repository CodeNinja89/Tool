%% declarations

struct Resource { // a shared resource
    val: int;
    acquired: bool;
    acquiredBy: int; // task id
}

struct Task {
    id: int;
}

oracle GetResource(r: Resource, taskId: int) -> ret: Resource {
    assumes taskId > 0 && r.acquired == false; // the mutual exclusion axiom
    // Construct a brand new ADT state: (val, acquired, acquiredBy)
    returns ret == mk_Resource(r.val, true, taskId);
}

oracle ReleaseResource(r: Resource, taskId: int) -> ret: Resource {
    assumes taskId > 0 && r.acquiredBy == taskId && r.acquired == true;
    // Reset the acquired flag and the owner ID, keeping the value
    returns ret == mk_Resource(r.val, false, 0);
}

oracle updateResource(r: Resource, value: int) -> ret: Resource {
    // Update the value, but explicitly copy the lock state
    returns ret == mk_Resource(value, r.acquired, r.acquiredBy);
}

oracle getValue(res: Resource) -> val: int {
    returns val == res.val;
}

resourceVal: int;
resourceVal_Intermediate: int;

sharedResource: Resource;
taskA: Task;
taskB: Task;

%% preconditions
sharedResource.acquired == false;
taskA.id > 0;
taskA.id > 0;

%% postconditions
resourceVal_Intermediate == 42;
resourceVal == 34;

%% program

// of course, GetResource provides a run-time guarantee of mutual exclusion.
// however, the compiler doesn't care if a task calls GetResource or not.

sharedResource := GetResource(sharedResource, taskA.id); // Task A gets the resource. This is a run-time guarantee.
// sharedResource := GetResource(sharedResource, taskB.id); // Task B tries to get the shared resource but fails!
sharedResource := updateResource(sharedResource, 42);
resourceVal_Intermediate := getValue(sharedResource);
sharedResource := ReleaseResource(sharedResource, taskA.id);

// sharedResource := GetResource(sharedResource, taskB.id); // Task B gets the resource.
sharedResource := updateResource(sharedResource, 43); // this is not a problem... compiler doesn't care if GetResource is called or not.
resourceVal := getValue(sharedResource);
// sharedResource := ReleaseResource(sharedResource, taskB.id);

// although the proof succeeds, the logic is completely flawed. LLM generates this code and TOOL doesn't generate a counterexample.
// if we ask an LLM to generate an implementation based on this code, the implementation would be flawed because the specs are.