import z3

def prove_with_spacer():
    print("--- Verifying Algorithm using Z3 Spacer (CHC) ---")
    
    fp = z3.Fixedpoint()
    fp.set(engine='spacer')
    
    BV32 = z3.BitVecSort(32)
    
    # 1. Define Predicates
    Init  = z3.Function('Init', BV32, BV32, BV32, BV32, BV32, BV32, BV32, BV32, z3.BoolSort())
    Mid   = z3.Function('Mid',  BV32, BV32, BV32, BV32, BV32, BV32, BV32, BV32, z3.BoolSort())
    End   = z3.Function('End',  BV32, BV32, BV32, z3.BoolSort())
    Error = z3.Function('Error', z3.BoolSort())
    
    fp.register_relation(Init, Mid, End, Error)
    
    # 2. Declare ALL explicit variables
    x, y, D, Bx, By, Bz, BDiff, Bt = [z3.BitVec(n, 32) for n in ['x', 'y', 'D', 'Bx', 'By', 'Bz', 'BDiff', 'Bt']]
    D8, Dmin, t3, t4, tk, t5, t6, Avzc, zc, z_mid, z = [z3.BitVec(n, 32) for n in ['D8', 'Dmin', 't3', 't4', 'tk', 't5', 't6', 'Avzc', 'zc', 'z_mid', 'z']]
    
    A = z3.BitVecVal(31541, 32)
    MAGIC = z3.BitVecVal(4011867933, 32)

    def setup_rules(enforce_bounds):
        # RULE 1: Init State
        valid_inputs = z3.And(
            z3.ULT(x, 65536), z3.ULT(y, 65536),
            z3.UGT(D, 0),
            z3.UGT(Bx, 0), z3.ULT(Bx, A),
            z3.UGT(By, 0), z3.ULT(By, A),
            z3.UGT(Bz, 0), z3.ULT(Bz, A),
            z3.UGT(BDiff, 0), z3.ULT(BDiff, A)
        )
        if enforce_bounds:
            bt_constraint = z3.And(z3.UGE(Bt, 511), z3.ULT(Bt, 31400))
        else:
            bt_constraint = z3.And(z3.UGT(Bt, 0), z3.ULT(Bt, A), 
                                   z3.Or(z3.ULT(Bt, 511), z3.UGT(Bt, 31400)))
            
        body1 = z3.And(valid_inputs, bt_constraint)
        head1 = Init(x, y, D, Bx, By, Bz, BDiff, Bt)
        # EXPLICIT ForAll binding
        fp.rule(z3.ForAll([x, y, D, Bx, By, Bz, BDiff, Bt], z3.Implies(body1, head1)))

        # RULE 2: Init -> Mid
        xc = A * x + Bx + D
        yc = A * y + By + D
        Diffc = (yc + D) + ((z3.BitVecVal(0, 32) - xc) + Bx - By + BDiff)
        
        body2 = z3.And(
            Init(x, y, D, Bx, By, Bz, BDiff, Bt),
            D8 == D ^ z3.BitVecVal(0 - 256, 32),
            Dmin == D + D8 + 256,
            t3 == Diffc + D8 - BDiff + (2 * Bt),
            t4 == z3.LShR(t3 - 31540 * (t3 & 1), 1)
        )
        head2 = Mid(x, y, Bz, D, Dmin, D8, Bt, t4)
        fp.rule(z3.ForAll([x, y, D, Bx, By, Bz, BDiff, Bt, D8, Dmin, t3, t4], z3.Implies(body2, head2)))

        # RULE 3: Mid -> End
        cond = z3.UGE(t4, 1073741824)
        body3 = z3.And(
            Mid(x, y, Bz, D, Dmin, D8, Bt, t4),
            tk == z3.If(cond, z3.BitVecVal(4096655488, 32) - Bt + (2067070976 * Bz), 
                              z3.BitVecVal(128, 32) - Bt + (2067070976 * Bz)),
            t5 == t4 + tk,
            t6 == t5 + (2067070976 * Dmin),
            Avzc == t6 - z3.UDiv(Dmin, 2),
            zc == z3.LShR(MAGIC * Avzc, 16) - D8 - 256,
            z_mid == zc - Bz - D,
            z == z3.UDiv(z_mid, A)
        )
        head3 = End(x, y, z)
        fp.rule(z3.ForAll([x, y, Bz, D, Dmin, D8, Bt, t4, tk, t5, t6, Avzc, zc, z_mid, z], z3.Implies(body3, head3)))

        # RULE 4: End -> Error
        expected_z = z3.If(z3.UGT(x, y), z3.BitVecVal(1, 32), z3.BitVecVal(0, 32))
        body4 = z3.And(End(x, y, z), z != expected_z)
        head4 = Error()
        fp.rule(z3.ForAll([x, y, z], z3.Implies(body4, head4)))

    # -------------------------------------------------------------------
    # 3. Execute Spacer Queries
    # -------------------------------------------------------------------
    
    print("\nTEST 1: Querying Spacer with SAFE Bt bounds [511, 31400]...")
    setup_rules(enforce_bounds=True)
    res = fp.query(Error())
    if res == z3.unsat:
        print("✅ UNSAT: The Error state is unreachable. The algorithm is Safe.")
    else:
        print(f"Result was: {res}")
    
    print("\nTEST 2: Querying Spacer with UNSAFE Bt bounds (outside interval)...")
    # Reset Fixedpoint environment for fresh run
    fp = z3.Fixedpoint()
    fp.set(engine='spacer')
    fp.register_relation(Init, Mid, End, Error)
    
    setup_rules(enforce_bounds=False) 
    res = fp.query(Error())
    
    if res == z3.sat:
        print("❌ SAT: The Error state IS reachable. The bounds are strictly necessary!")
        print("   (Spacer found a path where an out-of-bounds Bt breaks the logic.)")
    else:
        print(f"Result was: {res}")

if __name__ == "__main__":
    prove_with_spacer()