import sys
import os
import z3
from lark import Lark
from core.toolParser import Z3Transformer
from core.toolSSA import SSATransformer
from core.toolTypes import TypeEnvironment
from core.toolTypeChecker import TypeChecker
from core.toolZ3 import Z3Translator
from core.toolAst import FactStmt, LoopTransition, CallSiteCheck, AssertStmt

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
        ast = Z3Transformer().transform(tree)
        env = TypeEnvironment()
        env.build(ast.declarations)

        # 2. Type Check
        checker = TypeChecker(env)
        checker.check_program(ast)
        checker.enforce_linearity = False
        
        # 3. Initialize Translator and Solver
        translator = Z3Translator(env)
        solver = z3.Solver(ctx=translator.z3_ctx)
        solver.set("timeout", 30000)

        # Track the mathematical timeline for cloned solvers
        timeline_facts = []

        # 4. SSA Engine & Preconditions
        ssa_engine = SSATransformer(env)
        print("\n--- [STEP 1] SSA-Aligned Preconditions ---")
        for pre in ast.preconditions:
            ssa_pre = ssa_engine.transform_expr(pre)
            z3_pre = translator.translate_expr(ssa_pre, checker)
            
            solver.add(z3_pre)
            timeline_facts.append(z3_pre)
            print(f"Z3_Pre: {z3_pre}")

        print("\n--- Precondition Consistency Check ---")
        if solver.check() == z3.unsat:
            print("❌ VERDICT: VACUOUS PROOF (Preconditions are contradictory!)")
            print("The program's initial state is mathematically impossible.")
            exit(1)
        print("✅ Preconditions are satisfiable. Universe created successfully.")

        # 5. Program Transitions
        print("\n--- [STEP 2] SSA Program Formulas ---")
        transition_items = ssa_engine.generate_transition_predicate(ast.specProgram)
        
        for item in transition_items:
            # 1. Check if it's a Loop Wrapper
            if isinstance(item, LoopTransition):
                print("\n--- [LOOP VERIFIER] Analyzing WhileStmt ---")
                is_loop_safe = translator.verify_loop_transition(item, checker, solver)
                if not is_loop_safe:
                    print("❌ Verification Aborted: Loop induction failed.")
                    exit(1)
                
                # The loop verifier implicitly injects these post-loop facts. 
                # We replicate them in timeline_facts for downstream assertions.
                inv_read_z3 = translator.translate_expr(item.inv_read, checker)
                cond_read_z3 = translator.translate_expr(item.cond_read, checker)
                timeline_facts.append(inv_read_z3)
                timeline_facts.append(z3.Not(cond_read_z3))
            
            # 2. Check if it's a CallSiteCheck Wrapper
            elif isinstance(item, CallSiteCheck):
                z3_formula = translator.translate_expr(item.formula, checker)
                print(f"\n[PROVING CALL-SITE CHECK]: {z3_formula}")
                
                check_solver = z3.Solver(ctx=translator.z3_ctx)
                check_solver.set("timeout", 30000)
                check_solver.add(timeline_facts)
                check_solver.add(z3.Not(z3_formula))

                result = check_solver.check()
                if result == z3.sat:
                    print("❌ VERDICT: INVALID (Precondition Violated at Call Site!)")
                    print("\n--- Counter-Example Model ---")
                    print(check_solver.model())
                    exit(1)
                elif result == z3.unknown:
                    print(f"❓ UNKNOWN (Could not prove call-site check): {z3_formula}")
                    print(f"Reason: {check_solver.reason_unknown()}")
                    exit(1)

                print("✅ Call-Site Check Passed!")
                solver.add(z3_formula)
                timeline_facts.append(z3_formula)

            # 3. Check if it's a Fact
            elif isinstance(item, FactStmt):
                print("\n--- [FACT VERIFIER] Analyzing FactStmt ---")
                z3_formula = translator.translate_expr(item.formula, checker)
                
                solver.add(z3_formula)
                timeline_facts.append(z3_formula)

                if solver.check() == z3.unsat:
                    print("❌ COMPILATION ERROR: Contradictory Mid-Program Fact!")
                    print(f"The statement '{z3_formula}' contradicts the established state of the program up to this point.")
                    print("Mathematically impossible scenario.")
                    exit(1)
                
                print(f"✅ Fact Added to Timeline: {z3_formula}")

            # 4. Check if it's an Assertion
            elif isinstance(item, AssertStmt):
                print("\n--- [ASSERTION VERIFIER] Analyzing AssertStmt ---")
                z3_formula = translator.translate_expr(item.formula, checker)
                
                check_solver = z3.Solver(ctx=translator.z3_ctx)
                check_solver.set("timeout", 30000)
                check_solver.add(timeline_facts)
                check_solver.add(z3.Not(z3_formula))

                result = check_solver.check()
                if result == z3.sat:
                    print(f"❌ INVALID (Assertion Violated!): {z3_formula}")
                    print("\n--- Counter-Example Model ---")
                    print(check_solver.model())
                    exit(1)
                elif result == z3.unknown:
                    print(f"❓ UNKNOWN (Could not prove assertion): {z3_formula}")
                    print(f"Reason: {check_solver.reason_unknown()}")
                    exit(1)

                print(f"✅ Assertion Check Passed!: {z3_formula}")
                solver.add(z3_formula)
                timeline_facts.append(z3_formula)
                
            # 5. Otherwise, it's a normal AST formula (Assignments, Frame Axioms)
            else:
                z3_formula = translator.translate_expr(item, checker)
                solver.add(z3_formula)
                timeline_facts.append(z3_formula)
                print(f"Z3_ρ: {z3_formula}")

        # 6. Postconditions
        print("\n--- [STEP 3] SSA-Aligned Postconditions ---")
        
        postcondition_exprs = []
        for post in ast.postconditions:
            ssa_post = ssa_engine.transform_expr(post)
            z3_post = translator.translate_expr(ssa_post, checker)
            postcondition_exprs.append(z3_post)
            print(f"Parsed Z3_Post: {z3_post}")

        if postcondition_exprs:
            if len(postcondition_exprs) > 1:
                combined_postconditions = z3.And(*postcondition_exprs)
            else:
                combined_postconditions = postcondition_exprs[0]

            goal_to_falsify = z3.Not(combined_postconditions)
            
            # Spin up a final cloned solver for the ultimate postcondition check
            post_solver = z3.Solver(ctx=translator.z3_ctx)
            post_solver.set("timeout", 30000)
            post_solver.add(timeline_facts)
            post_solver.add(goal_to_falsify)
            
            print(f"Z3_Combined_Post (Asserted as Not): {goal_to_falsify}")
        else:
            post_solver = solver
            print("No postconditions to verify.")

        # 7. Final Check
        print("\n--- [DEBUG] SOLVER STATE ---")
        for a in post_solver.assertions():
            print(f"Assertion: {a}")

        print("\n--- [STEP 4] Final Verdict ---")
        result = post_solver.check()
        
        if result == z3.unsat:
            print("✅ VERDICT: PROVED (The property holds for all executions)")
        elif result == z3.sat:
            print("❌ VERDICT: INVALID (Counter-example found)")
            print("\n--- Counter-Example Model ---")
            print(post_solver.model())
        elif result == z3.unknown:
            print(f"❓ Result: UNKNOWN")
            print(f"❓ Reason: {post_solver.reason_unknown()}")

    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()