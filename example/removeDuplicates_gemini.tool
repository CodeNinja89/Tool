%% declarations
// Oracle to check if an element exists in a sequence within a given range [0, length)
oracle contains(s: seq[int], len: int, element: int) -> found: bool {
    returns found == (exists i: int . (i >= 0 && i < len) && s[i] == element);
}

// Oracle to represent the logical state of a sequence after appending a unique element
oracle append(old_seq: seq[int], len: int, val: int) -> new_seq: seq[int] {
    returns (new_seq[len] == val) && 
            (forall i: int . (i == len) || (new_seq[i] == old_seq[i]));
}

input_seq: seq[int];
input_len: int;

output_seq: seq[int];
output_len: int;

i: int;
current_val: int;
already_exists: bool;

%% preconditions
input_len >= 0;

%% postconditions
// 1. Every element in the output was present in the input
forall k: int . !(k >= 0 && k < output_len) || (exists j: int . (j >= 0 && j < input_len) && output_seq[k] == input_seq[j]);

// 2. Every element from the input is present in the output
forall j: int . !(j >= 0 && j < input_len) || (exists k: int . (k >= 0 && k < output_len) && input_seq[j] == output_seq[k]);

// 3. No duplicates: Every index in the output points to a unique value
forall a: int . forall b: int . !(a >= 0 && a < output_len && b >= 0 && b < output_len && a != b) || (output_seq[a] != output_seq[b]);

%% program
output_len := 0;
i := 0;

while (i < input_len)
    invariant (i >= 0 && i <= input_len) && 
              (output_len >= 0 && output_len <= i) &&
              (forall a: int . forall b: int . !(a >= 0 && a < output_len && b >= 0 && b < output_len && a != b) || (output_seq[a] != output_seq[b])) &&
              (forall j: int . !(j >= 0 && j < i) || (exists k: int . (k >= 0 && k < output_len) && input_seq[j] == output_seq[k]))
{
    current_val := input_seq[i];
    already_exists := contains(output_seq, output_len, current_val);

    if (!already_exists) {
        output_seq := append(output_seq, output_len, current_val);
        output_len := output_len + 1;
    }

    i := i + 1;
}