# =============================================================================
# Implementation of Binary Tree Logic
# =============================================================================

class Tree:
    def __init__(self, val, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

    def __repr__(self):
        return f"Tree({self.val}, {self.left}, {self.right})"

def contains(t, x):
    """Recursively checks if value x exists in the tree."""
    if t is None:
        return False
    if t.val == x:
        return True
    return contains(t.left, x) or contains(t.right, x)

def all_less(t, v):
    """Checks if all nodes in subtree t are strictly less than v."""
    if t is None:
        return True
    return t.val < v and all_less(t.left, v) and all_less(t.right, v)

def all_greater(t, v):
    """Checks if all nodes in subtree t are strictly greater than v."""
    if t is None:
        return True
    return t.val > v and all_greater(t.left, v) and all_greater(t.right, v)

def is_bst(t):
    """Verifies the Binary Search Tree property for the entire tree."""
    if t is None:
        return True
    return (all_less(t.left, t.val) and 
            all_greater(t.right, t.val) and 
            is_bst(t.left) and 
            is_bst(t.right))

def insert(t, x):
    """Performs a BST-compliant insertion."""
    if t is None:
        return Tree(x)
    if x == t.val:
        return t
    if x < t.val:
        return Tree(t.val, insert(t.left, x), t.right)
    else:
        return Tree(t.val, t.left, insert(t.right, x))

# =============================================================================
# Modular Test Suite
# =============================================================================

def test_contains_negation():
    """
    Test Case: Verifying if inserting 'v' makes it searchable.
    Refutation Goal: is_contained == False
    """
    print("\n--- [TEST 1] Contains Property (Negation Check) ---")
    
    # Counter-example from Z3:
    # root = Tree(2, None, Tree(3, None, None)), v = 2
    root = Tree(2, None, Tree(3, None, None))
    v = 2
    
    print(f"Setup: root={root}, v={v}")
    new_root = insert(root, v)
    result = contains(new_root, v)
    
    # We expected the property 'is_contained == False' to be refutable
    print(f"Result of contains(new_root, {v}): {result}")
    if result == True:
        print("VERDICT: Negation Refuted (Implementation behaves correctly)")
    else:
        print("VERDICT: Negation Held (Implementation failure or bad test case)")

def test_bst_preservation_negation():
    """
    Test Case: Verifying if insert(root, v) preserves the BST property.
    Refutation Goal: is_bst(new_root) == False
    """
    print("\n--- [TEST 2] BST Preservation (Negation Check) ---")
    
    # Counter-example from Z3:
    # root = null, v = 0
    root = None
    v = 0
    
    print(f"Setup: root={root}, v={v}")
    new_root = insert(root, v)
    result = is_bst(new_root)
    
    # We expected the property 'is_bst == False' to be refutable
    print(f"Result of is_bst(new_root): {result}")
    if result == True:
        print("VERDICT: Negation Refuted (Implementation behaves correctly)")
    else:
        print("VERDICT: Negation Held (Implementation failure or bad test case)")

if __name__ == "__main__":
    print("=== Binary Tree Formal Verification Test Suite ===")
    test_contains_negation()
    test_bst_preservation_negation()
