%% declarations

%% preconditions

%% postconditions

%% program

n := 5;
sum := 0;
i := 0;

while (i < n) 
  invariant sum == (i * (i - 1)) / 2
{
    sum := sum + i;
    i := i + 1;
}

assert sum == (n * (n - 1)) / 2;