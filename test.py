import sys
import os
import z3
from lark import Lark
from core.toolParser import CHCTransformer
from core.toolSSA import SSATransformer
from core.toolTypes import TypeEnvironment
from core.toolTypeChecker import TypeChecker
from core.toolZ3 import Z3Translator

def main():
    if len(sys.argv) < 2:
        print("Usage: python test.py <filename>")
        return

    filename = sys.argv[1]
    grammar_path = "core/toolGrammar.lark"
    
    with open(filename, 'r') as f:
        code = f.read()
    with open(grammar_path) as f:
        grammar = f.read()

    bridge_parser = Lark(grammar, start='start', parser='lalr', debug=True)

    try:
        # 1. Parse and Build Environment
        tree = bridge_parser.parse(code)
        ast = CHCTransformer().transform(tree)
        env = TypeEnvironment()
        env.build(ast.declarations)

        # 2. Type Check
        checker = TypeChecker(env)
        checker.check_program(ast)
        
        # 3. Initialize Translator and Solver
        translator = Z3Translator(env)
        # Initialize Solver in test.py
        solver = z3.Solver(ctx=translator.z3_ctx)
        
        # 1. Macro Finder: This is the most important setting for your current error.
        # It tells Z3 to expand the 'is_acyclic' definition directly into the code.
        solver.set("smt.macro_finder", True)
        solver.set("smt.mbqi", True)
        solver.set("smt.array.extensional", False)

        # 4. Oracle Axioms
        print("\n--- [STEP 1] Oracle Axioms (SMT) ---")

        # 5. SSA Engine & Preconditions
        ssa_engine = SSATransformer(env)
        print("\n--- [STEP 2] SSA-Aligned Preconditions ---")
        for pre in ast.preconditions:
            ssa_pre = ssa_engine.transform_expr(pre)
            z3_pre = translator.translate_expr(ssa_pre, checker)
            solver.add(z3_pre)
            print(f"Z3_Pre: {z3_pre}")

        # 6. Program Transitions
        print("\n--- [STEP 3] SSA Program Formulas ---")
        transition_formulas = ssa_engine.generate_transition_predicate(ast.specProgram)
        for formula in transition_formulas:
            z3_formula = translator.translate_expr(formula, checker)
            solver.add(z3_formula)
            print(f"Z3_ρ: {z3_formula}")

        # 7. Postconditions
        print("\n--- [STEP 4] SSA-Aligned Postconditions ---")
        for post in ast.postconditions:
            ssa_post = ssa_engine.transform_expr(post)
            z3_post = translator.translate_expr(ssa_post, checker)
            # We add the NEGATION to the solver to look for counter-examples
            solver.add(z3.Not(z3_post))
            print(f"Z3_Post (Asserted as Not): {z3.Not(z3_post)}")

        # 8. Final Check
        print("\n--- [DEBUG] SOLVER STATE ---")
        # 1. Print all formulas currently in the solver to check for version mismatches
        for a in solver.assertions():
            print(f"Assertion: {a}")

        # 2. Check if the Axiom specifically has the correct Triggers (Patterns)
        # We search the assertions for the ForAll quantifier
        for a in solver.assertions():
            if z3.is_quantifier(a):
                # We use repr to see the internal Z3 structure, including {pattern}
                print(f"\n[Axiom Structure]: {repr(a)}")
                print("\n--- [STEP 5] Final Verdict ---")
        result = solver.check()
        
        if result == z3.unsat:
            print("✅ VERDICT: PROVED (The property holds for all executions)")
        elif result == z3.sat:
            print("❌ VERDICT: INVALID (Counter-example found)")
            print("\n--- Counter-Example Model ---")
            print(solver.model())
        elif result == z3.unknown:
            print(f"❓ Result: UNKNOWN")
            print(f"❓ Reason: {solver.reason_unknown()}")

    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()