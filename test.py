import sys
import os
import z3
from lark import Lark
from core.toolParser import CHCTransformer
from core.toolSSA import SSATransformer
from core.toolTypes import TypeEnvironment
from core.toolTypeChecker import TypeChecker
from core.toolZ3 import Z3Translator
from core.toolAst import LoopTransition

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
        solver = z3.Solver(ctx=translator.z3_ctx)

        # 4. SSA Engine & Preconditions
        ssa_engine = SSATransformer(env)
        print("\n--- [STEP 1] SSA-Aligned Preconditions ---")
        for pre in ast.preconditions:
            ssa_pre = ssa_engine.transform_expr(pre)
            z3_pre = translator.translate_expr(ssa_pre, checker)
            solver.add(z3_pre)
            print(f"Z3_Pre: {z3_pre}")

        # 5. Program Transitions (Macro Inlining happens automatically here!)
        print("\n--- [STEP 2] SSA Program Formulas ---")
        transition_formulas = ssa_engine.generate_transition_predicate(ast.specProgram)
        for formula in transition_formulas:
            z3_formula = translator.translate_expr(formula, checker)
            if isinstance(z3_formula, LoopTransition):
                print("\n--- [LOOP VERIFIER] Analyzing WhileStmt ---")
                is_loop_safe = translator.verify_loop_transition(z3_formula, checker, solver)
                if not is_loop_safe:
                    print("❌ Verification Aborted: Loop induction failed.")
                    exit(1)
            else:
                solver.add(z3_formula)
                print(f"Z3_ρ: {z3_formula}")

        # 6. Postconditions (Macro Inlining happens here too!)
        print("\n--- [STEP 3] SSA-Aligned Postconditions ---")
        for post in ast.postconditions:
            ssa_post = ssa_engine.transform_expr(post)
            z3_post = translator.translate_expr(ssa_post, checker)
            # We add the NEGATION to the solver to look for counter-examples
            solver.add(z3.Not(z3_post))
            print(f"Z3_Post (Asserted as Not): {z3.Not(z3_post)}")

        # 7. Final Check
        print("\n--- [DEBUG] SOLVER STATE ---")
        if hasattr(translator, 'side_loaded_contracts'):
            for contract in translator.side_loaded_contracts:
                solver.add(contract)
                print(f"Z3_Oracle_Contract: {contract}")
        
        for a in solver.assertions():
            print(f"Assertion: {a}")

        print("\n--- [STEP 4] Final Verdict ---")
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