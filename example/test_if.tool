%% declarations
x: int;
y: int;
is_safe: bool;

%% preconditions
x == 5;
y == 0;

%% postconditions
is_safe == true;

%% program
if (x > 0) {
    y := x + 10;
} else {
    y := x - 10;
}

is_safe := (y == 0);