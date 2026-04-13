%% declarations
oracle sort(old_seq: seq[int], len: int) -> new_seq: seq[int] {
    assumes len >= 0;
    returns (forall i: int . forall j: int . !(i >= 0 && i < len && j > i && j < len) || (new_seq[i] <= new_seq[j])) &&
            (forall i: int . !(i >= 0 && i < len) || (exists j: int . (j >= 0 && j < len) && new_seq[i] == old_seq[j])) &&
            (forall j: int . !(j >= 0 && j < len) || (exists i: int . (i >= 0 && i < len) && old_seq[j] == new_seq[i])) &&
            (forall k: int . (k >= 0 && k < len) || (new_seq[k] == old_seq[k]));
}

arr: seq[int];
arr_len: int;

sorted_arr: seq[int];
is_correct: bool;

%% preconditions
arr_len >= 0;

%% postconditions
is_correct == true;

%% program
sorted_arr := sort(arr, arr_len);

is_correct := (forall a: int . forall b: int . !(a >= 0 && a < arr_len && b > a && b < arr_len) || (sorted_arr[a] <= sorted_arr[b]));