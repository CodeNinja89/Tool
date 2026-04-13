%% declarations
oracle sort(old_seq: seq[int], len: int) -> new_seq: seq[int] {
    assumes len >= 0;
    returns 
        // 1. The array is sorted in ascending order
        (forall i: int . forall j: int . !(i >= 0 && i < len && j > i && j < len) || (new_seq[i] <= new_seq[j])) &&
        
        // 2. The array is a permutation of the original array (this guarantees exact duplicate counts are preserved)
        // We assert there exists a bijective mapping from the new sequence's indices to the old sequence's indices
        (exists map: seq[int] . 
            // 2a. The mapping only points to valid indices within the array bounds
            (forall k: int . !(k >= 0 && k < len) || (map[k] >= 0 && map[k] < len)) &&
            // 2b. The mapping is injective (no two distinct indices map to the same target index)
            (forall a: int . forall b: int . !(a >= 0 && a < len && b >= 0 && b < len && a != b) || (map[a] != map[b])) &&
            // 2c. The values at the mapped indices are perfectly identical
            (forall c: int . !(c >= 0 && c < len) || (new_seq[c] == old_seq[map[c]]))
        )
}

arr: seq[int];
arr_len: int;

sorted_arr: seq[int];
is_correct: bool;

%% preconditions
arr_len >= 0;

%% postconditions
is_correct == false;

%% program
sorted_arr := sort(arr, arr_len);

is_correct := (forall i: int . forall j: int . !(i >= 0 && i < arr_len && j > i && j < arr_len) || (sorted_arr[i] <= sorted_arr[j]));