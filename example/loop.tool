%% declarations
n: int;
sum: int;
i: int;

%% preconditions
n == 5;

%% postconditions
// Let's add a postcondition just to test the loop exit!
// If n=5, the sum of 0+1+2+3+4+5 = 15.
sum == 15;

%% program
sum := 0;
i := n;

while (i > 0) 
  invariant (sum == ((n * (n + 1) / 2) - 
    (i * (i + 1) / 2)) &&
    i >= 0)
{
    sum := sum + i;
    i := i - 1;
}