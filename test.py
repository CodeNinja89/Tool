import sys
import z3
from lark import Lark

from core.toolParser import ToolASTBuilder
from core.toolTypes import TypeEnvironment
from core.toolTypeChecker import TypeChecker
from core.toolSSA import SSABuilder
from core.toolZ3 import Z3Verifier
from core.toolAst import Expr

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

    print(f"\n[*] Compiling: {filename}")
    bridge_parser = Lark(grammar, start='start', parser='lalr')

    try:
        # ==========================================
        # PHASE 1: Parsing
        # ==========================================
        tree = bridge_parser.parse(code)
        ast = ToolASTBuilder().transform(tree)
        print("✅ Phase 1: AST Parsing Complete")

        # ==========================================
        # PHASE 2: Semantic Analysis & Type Checking
        # ==========================================
        env = TypeEnvironment()
        tc = TypeChecker(env)
        
        # The TypeChecker traverses the file, registers structs/variables, 
        # and enforces your strict linear resource constraints.
        tc.check_program(ast)
        print("✅ Phase 2: Type Checking Complete")

        # ==========================================
        # PHASE 3: Static Single Assignment (SSA)
        # ==========================================
        ssa = SSABuilder(env)
        
        # This converts procedural loops and assignments into mathematical formulas
        ssa_formulas = ssa.build_program(ast)
        
        # We physically swap the procedural AST block with the compiled math block
        ast.specProgram = ssa_formulas
        print("✅ Phase 3: SSA Compilation Complete")

        # ==========================================
        # PHASE 4: Z3 Theorem Proving
        # ==========================================
        verifier = Z3Verifier(env, tc)
        
        print("\n--- [DEBUG] SMT Axioms ---")
        
        # 1. Assert Global Preconditions (Axiomatic Truths)
        for pre in ast.preconditions:
            pre_z3 = pre.accept(verifier)
            verifier.solver.add(pre_z3)
            print(f"Precondition: {pre_z3}")
            
        # 2. Evaluate Program Body
        for formula in ast.specProgram:
            # If the formula is a pure math equation (e.g. x_1 == x_0 + 1), 
            # we must explicitly add it to the SMT solver's timeline.
            if isinstance(formula, Expr):
                f_z3 = formula.accept(verifier)
                verifier.solver.add(f_z3)
                print(f"SSA Math Fact: {f_z3}")
            
            # If the formula is a Control Flow Node (LoopTransition, Assert, Assume),
            # we just accept it. The Z3Verifier visitor inherently handles its own 
            # push/pop sandboxing and solver injections for these nodes.
            else:
                formula.accept(verifier)
                print(f"Control Flow: {type(formula).__name__} Evaluated")

        # 3. Postcondition Refutation
        if ast.postconditions:
            post_z3_list = [post.accept(verifier) for post in ast.postconditions]
            combined_post = z3.And(*post_z3_list) if len(post_z3_list) > 1 else post_z3_list[0]
            
            # REFUTATION STRATEGY: We assert the NEGATION of the postconditions.
            # We are asking Z3: "Is there any possible timeline where the program succeeds, 
            # but the postcondition fails?"
            verifier.solver.add(z3.Not(combined_post))
            print(f"Refutation Target: {z3.Not(combined_post)}")
            
        print("\n--- [VERDICT] ---")
        result = verifier.solver.check()
        
        if result == z3.unsat:
            print("✅ VERDICT: PROVED (The specification holds for all valid executions)")
        elif result == z3.sat:
            print("❌ VERDICT: INVALID (Counter-example found)")
            print("\n--- Counter-Example Model ---")
            print(verifier.solver.model())
        else:
            print("❓ Result: UNKNOWN (Solver timeout or logic too complex)")

    except Exception as e:
        print(f"\n❌ COMPILATION ERROR: {str(e)}")

if __name__ == "__main__":
    main()