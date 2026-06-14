%% declarations
<<<<<<< Updated upstream
struct HW_Channel { 
    is_active: bool; 
}

struct TaskState {
    hw: HW_Channel;
}

oracle activate(d: HW_Channel) -> res: HW_Channel {
    returns res.is_active == true;
}
oracle deactivate(d: HW_Channel) -> res: HW_Channel {
    returns res.is_active == false;
}

// --- Verification Program ---
hwc: HW_Channel;  // The actual hardware
taskA: TaskState; // Task A's pointer
taskB: TaskState; // Task B's pointer

stateA: HW_Channel;
stateB: HW_Channel;

%% preconditions
hwc != null;
hwc.is_active == false;

%% postconditions
// 4. Task A assumes its channel is still on.
stateA.is_active == true;

%% program
// 1. Both tasks grab a pointer to the exact same hardware module.
taskA.hw := hwc; 
taskB.hw := hwc; 

// 2. Task A turns it on.
stateA := activate(taskA.hw);

// 3. Task B turns it off.
stateB := deactivate(taskB.hw);
=======

linear struct Resource { // a shared resource
    val: int;
}

struct Task {
    id: int;
    resource: Resource; // the shared resource that the task acquires
}

oracle updateResource(res: Resource, value: int) -> ret: Resource {
    returns ret == mk_Resource(value);
}

oracle getValue(refer res: Resource) -> val: int {
    returns val == res.val;
}

oracle destruct(res: Resource) -> ret: bool {
    returns ret == true;
}

res: Resource ; // the shared resource

taskA: Task;
taskB: Task;

resourceVal: int;
resourceVal_Intermediate: int;

free: bool;

%% preconditions

%% postconditions

resourceVal_Intermediate == 42;
resourceVal == 34;

%% program

taskA.resource := res; // taskA "owns" the resource. This is a compile time guarantee!

// taskB tries to acquire the same resource
// taskB.resource := res; // this fails to compile because taskA already owns the resource.

res := updateResource(taskA.resource, 42); // update the value and now, we get a new resource with the updated value. the resource transitioned to a new state.
// keep in mind that "res" on line 48 is not the same "res" on line 43. The one on line 43 does not exist anymore because it was "consumed".

resourceVal_Intermediate := getValue(res);

taskB.resource := res; // now this is not a problem. taskB gets the updated value because the resource transitioned to a new state. TaskB now owns the resource.


res := updateResource(taskB.resource, 43); // taskB updates the value. The shared resource now transits to a new state.

resourceVal := getValue(res);

free := destruct(res); // linear types must be explicitly consumed in TOOL.
>>>>>>> Stashed changes
