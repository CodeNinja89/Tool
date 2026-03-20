import z3

def prove_bounds_necessity():
    print("--- Proving Necessity of the Safe Interval [511, 31400] ---")
    s = z3.Solver()
    
    # 1. The Parameter we want to test
    Bt = z3.BitVec('Bt', 32)
    A = z3.BitVecVal(31541, 32)
    
    # 2. THE INVERSION: Force Bt to be OUTSIDE the safe interval
    # It must still be a valid signature > 0 and < A, but outside our bounds
    s.add(z3.UGT(Bt, 0), z3.ULT(Bt, A))
    s.add(z3.Or(
        z3.ULT(Bt, 511),   # Too small (causes underflow)
        z3.UGT(Bt, 31400)  # Too large (causes overflow)
    ))
    
    # 3. The Logic Function (Parameterized for test cases)
    def run_algorithm(test_name, x_val, y_val, expected_z, Bt_val):
        x = z3.BitVecVal(x_val, 32)
        y = z3.BitVecVal(y_val, 32)
        
        # We treat randomizers as existential: "Is there ANY valid system state?"
        D = z3.BitVec(f'D_{test_name}', 32)
        Bx = z3.BitVec(f'Bx_{test_name}', 32)
        By = z3.BitVec(f'By_{test_name}', 32)
        Bz = z3.BitVec(f'Bz_{test_name}', 32)
        BDiff = z3.BitVec(f'BDiff_{test_name}', 32)
        
        reqs = [
            z3.UGT(D, 0),
            z3.UGT(Bx, 0), z3.ULT(Bx, A),
            z3.UGT(By, 0), z3.ULT(By, A),
            z3.UGT(Bz, 0), z3.ULT(Bz, A),
            z3.UGT(BDiff, 0), z3.ULT(BDiff, A)
        ]
        
        xc = A * x + Bx + D
        yc = A * y + By + D
        t1 = yc + D
        t2 = (z3.BitVecVal(0, 32) - xc) + Bx - By + BDiff
        Diffc = t1 + t2
        D8 = D ^ z3.BitVecVal(0 - 256, 32)
        Dmin = D + D8 + 256
        t3 = Diffc + D8 - BDiff + (2 * Bt_val)
        t4 = z3.LShR(t3 - 31540 * (t3 & 1), 1)
        
        cond = z3.UGE(t4, 1073741824)
        tk_then = z3.BitVecVal(4096655488, 32) - Bt_val + (2067070976 * Bz)
        tk_else = z3.BitVecVal(128, 32) - Bt_val + (2067070976 * Bz)
        tk = z3.If(cond, tk_then, tk_else)
        
        t5 = t4 + tk
        t6 = t5 + (2067070976 * Dmin)
        Avzc = t6 - z3.UDiv(Dmin, 2)
        MAGIC = z3.BitVecVal(4011867933, 32)
        zc = z3.LShR(MAGIC * Avzc, 16) - D8 - 256
        z_mid = zc - Bz - D
        z = z3.UDiv(z_mid, A)
        
        return reqs + [z == expected_z]

    # 4. We demand that this "out-of-bounds" Bt works for just the edge cases
    # If it can't even handle these, it is not a universally valid Bt.
    s.add(run_algorithm("Case1", 2, 1, 1, Bt)) # Expect True
    s.add(run_algorithm("Case2", 1, 2, 0, Bt)) # Expect False
    
    # 5. Check
    result = s.check()
    if result == z3.unsat:
        print("✅ VERIFIED: The solver returned UNSAT.")
        print("   This proves mathematically that NO VALID Bt exists outside")
        print("   the range [511, 31400]. The algorithm will always fail for")
        print("   at least one of the edge cases if Bt violates these bounds.")
    else:
        print("❌ FAILED TO PROVE: The solver returned SAT.")
        print("   It found a Bt outside the bounds that somehow works.")
        print("\n--- Counterexample State ---")
        
        # Extract the model and print all variable assignments
        m = s.model()
        for d in m.decls():
            print(f"  {d.name()} = {m[d]}")

if __name__ == "__main__":
    prove_bounds_necessity()