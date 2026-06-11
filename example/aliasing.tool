%% declarations
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