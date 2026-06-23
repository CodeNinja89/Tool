from typing import Dict, List, Set, Any, cast
from core.toolAst import *
from core.toolTypes import TypeEnvironment
from core.toolOracles import OracleManager

class SSABuilder(ASTVisitor):
    """
    Transforms imperative statements (x = x + 1) into mathematical, 
    timeline-specific formulas (x_1 == x_0 + 1) using Static Single Assignment.
    """
    def __init__(self, env: TypeEnvironment):
        self.env = env
        self.oracle_manager = OracleManager(self.env)
        
        # SSA State Management
        self.max_versions: Dict[str, int] = {}       # The highest version ever assigned
        self.current_versions: Dict[str, int] = {}   # The active version in the current scope
        self.bound_vars: Set[str] = set()            # Variables shielded from SSA (e.g. forall i)

    def build_program(self, program: Program) -> List[Any]:
        """Entry point. Converts the procedural program block into pure math formulas."""
        formulas = []
        for stmt in program.specProgram:
            formulas.extend(stmt.accept(self))
        return formulas

    # --- Timeline Name Generators ---

    def _get_current_name(self, name: str) -> str:
        """Reads the current version of a variable for use on the right side of an equation."""
        if name not in self.current_versions:
            self.current_versions[name] = 0
            self.max_versions[name] = 0
        return f"{name}_{self.current_versions[name]}"
    
    def _get_next_name(self, name: str) -> str:
        """Generates a new, mathematically distinct version of a variable for an assignment."""
        if name not in self.max_versions:
            self.max_versions[name] = 0
        self.max_versions[name] += 1
        self.current_versions[name] = self.max_versions[name]
        return f"{name}_{self.current_versions[name]}"

    # ==========================================
    # --- PART 1: Basic Expressions ---
    # ==========================================

    def visit_Literal(self, node: Literal) -> Expr:
        return node

    def visit_VarRef(self, node: VarRef) -> Expr:
        # If the variable is bound by a quantifier (e.g., 'i' in 'forall i'), do not version it.
        if node.name in self.bound_vars:
            return node
        return VarRef(self._get_current_name(node.name))

    def visit_UnaryExpr(self, node: UnaryExpr) -> Expr:
        return UnaryExpr(op=node.op, operand=node.operand.accept(self))

    def visit_BinaryExpr(self, node: BinaryExpr) -> Expr:
        return BinaryExpr(
            left=node.left.accept(self),
            op=node.op,
            right=node.right.accept(self)
        )

    def visit_TernaryExpr(self, node: TernaryExpr) -> Expr:
        return TernaryExpr(
            condition=node.condition.accept(self),
            true_expr=node.true_expr.accept(self),
            false_expr=node.false_expr.accept(self)
        )
        
    def visit_Quantifier(self, node: Quantifier) -> Expr:
        # 1. Shield the bound variable from the SSA engine
        self.bound_vars.add(node.bound_var)
        
        # 2. Recursively transform the inner formula
        inner_transformed = node.formula.accept(self)
        
        # 3. Clean up the shield
        self.bound_vars.remove(node.bound_var)
        
        return Quantifier(
            quant_type=node.quant_type,
            bound_var=node.bound_var,
            var_type=node.var_type,
            formula=inner_transformed
        )
    
    def visit_FuncCall(self, node: FuncCall) -> Expr:
        return FuncCall(
            name=node.name,
            args=[arg.accept(self) for arg in node.args]
        )

    def visit_FieldAccess(self, node: FieldAccess) -> Expr:
        return FieldAccess(
            obj=node.obj.accept(self),
            field=node.field
        )

    def visit_SeqAccess(self, node: SeqAccess) -> Expr:
        return SeqAccess(
            seq_obj=node.seq_obj.accept(self),
            index=node.index.accept(self)
        )

    # ==========================================
    # --- PART 2: Memory Updates & Statements ---
    # ==========================================

    def visit_BlockStmt(self, node: BlockStmt) -> List[Any]:
        formulas = []
        for stmt in node.statements:
            formulas.extend(stmt.accept(self))
        return formulas

    def visit_AssertStmt(self, node: AssertStmt) -> List[Any]:
        return [AssertStmt(formula=node.formula.accept(self))]

    def visit_AssumeStmt(self, node: AssumeStmt) ->List[Any]:
        return [AssumeStmt(formula=node.formula.accept(self))]

    def visit_AssignStmt(self, node: AssignStmt) -> List[Any]:
        """Translates variable assignments and memory mutations into static mathematical facts."""
        formulas = []

        # 1. Oracle Contract Extraction
        # If the RHS is a function, we must extract and assert its preconditions before the assignment.
        if isinstance(node.expr, FuncCall) and node.expr.name in self.env.oracles:
            oracle_def = self.env.get_oracles(node.expr.name)
            grounded_assumes, grounded_returns = self.oracle_manager.extract_contract(node.expr)
            
            if grounded_assumes:
                ssa_assumes = grounded_assumes.accept(self)
                formulas.append(CallSiteCheck(formula=ssa_assumes))

            if not self.oracle_manager.is_recursive(oracle_def) and grounded_returns:
                ssa_returns = grounded_returns.accept(self)
                formulas.append(ssa_returns)

        # 2. Translate the RHS using the CURRENT timeline
        rhs_transformed = node.expr.accept(self)

        # 3. Translate the LHS and generate the NEW timeline state
        if isinstance(node.lvalue, VarRef):
            new_lhs_name = self._get_next_name(node.lvalue.name)
            formulas.append(BinaryExpr(left=VarRef(new_lhs_name), op='==', right=rhs_transformed))

        elif isinstance(node.lvalue, FieldAccess):
            base_obj = node.lvalue.obj
            if not isinstance(base_obj, VarRef):
                raise NotImplementedError("Compiler Error: Nested struct updates (e.g., a.b.c = 1) not yet supported!")
            
            base_name = base_obj.name
            old_version = VarRef(self._get_current_name(base_name))
            new_version = VarRef(self._get_next_name(base_name))

            update_expr = StructUpdate(
                obj=old_version,
                field=node.lvalue.field,
                new_value=rhs_transformed
            )
            formulas.append(BinaryExpr(left=new_version, op='==', right=update_expr))
            
        elif isinstance(node.lvalue, SeqAccess):
            base_obj = node.lvalue.seq_obj
            if not isinstance(base_obj, VarRef):
                raise NotImplementedError("Compiler Error: Multidimensional sequences not supported!")
            
            base_name = base_obj.name
            old_version = VarRef(self._get_current_name(base_name))
            new_version = VarRef(self._get_next_name(base_name))
            transformed_idx = node.lvalue.index.accept(self)

            update_expr = SeqUpdate(
                seq_obj=old_version,
                index=transformed_idx,
                new_value=rhs_transformed
            )
            formulas.append(BinaryExpr(left=new_version, op='==', right=update_expr))

        else:
            raise NotImplementedError(f"SSA Translation for {type(node.lvalue)} is not supported.")

        return formulas
    
    # ==========================================
    # --- PART 3: Control Flow & Hoare Logic ---
    # ==========================================

    def _get_write_set(self, stmt: Stmt) -> Set[str]:
        """Recursively scans a block of code to find every variable that gets modified."""
        writes = set()
        if isinstance(stmt, AssignStmt):
            # Drill down through arrays/structs to find the base variable name
            base_obj = stmt.lvalue
            while isinstance(base_obj, (FieldAccess, SeqAccess)):
                base_obj = base_obj.obj if isinstance(base_obj, FieldAccess) else base_obj.seq_obj
            if isinstance(base_obj, VarRef):
                writes.add(base_obj.name)
        elif isinstance(stmt, BlockStmt):
            for s in stmt.statements:
                writes.update(self._get_write_set(s))
        elif isinstance(stmt, IfStmt):
            writes.update(self._get_write_set(stmt.then_block))
            if stmt.else_block:
                writes.update(self._get_write_set(stmt.else_block))
        elif isinstance(stmt, WhileStmt):
            writes.update(self._get_write_set(stmt.body))
        return writes

    def visit_IfStmt(self, node: IfStmt) -> List[Any]:
        """Symbolically evaluates divergent paths and merges them using Phi-functions."""
        cond_expr = node.condition.accept(self)
        
        # Snapshot the Universe before the split
        base_versions = self.current_versions.copy()

        # 1. Explore the TRUE timeline
        then_formulas = node.then_block.accept(self)
        then_versions = self.current_versions.copy()

        # 2. Rewind time and explore the FALSE timeline
        self.current_versions = base_versions.copy()
        else_formulas = []
        else_versions = base_versions.copy()

        if node.else_block:
            else_formulas = node.else_block.accept(self)
            else_versions = self.current_versions.copy()

        # 3. State Merging (Phi Nodes)
        phi_formulas = []
        all_modified_vars = set(then_versions.keys()).union(set(else_versions.keys()))

        for var in all_modified_vars:
            v_base = base_versions.get(var, 0)
            v_then = then_versions.get(var, 0)
            v_else = else_versions.get(var, 0)

            # If the variable changed in EITHER timeline, we must merge realities
            if v_then != v_base or v_else != v_base:
                merged_name = self._get_next_name(var)
                phi_node = BinaryExpr(
                    left=VarRef(merged_name),
                    op='==',
                    right=TernaryExpr(
                        condition=cond_expr,
                        true_expr=VarRef(f"{var}_{v_then}"),
                        false_expr=VarRef(f"{var}_{v_else}")
                    )
                )
                phi_formulas.append(phi_node)

        return then_formulas + else_formulas + phi_formulas

    def visit_WhileStmt(self, node: WhileStmt) -> List[Any]:
        """Translates an infinite loop into a static, 3-step Mathematical Induction proof."""
        formulas = []
        
        # 1. Base Case (pre_loop_scope)
        # What is the exact state of the universe right before the loop starts?
        pre_loop_scope = self.current_versions.copy()
        inv_pre = node.invariant.accept(self) if node.invariant else Literal("true")

        # --- THE HAVOC STEP ---
        # Because we cannot mathematically unroll a loop 1,000 times, we tell the solver: 
        # "Imagine we are at some arbitrary iteration 'k'. I have no idea what values 
        # these variables hold right now, so treat them as completely unknown/symbolic."
        modified_vars = self._get_write_set(node.body)
        for var in modified_vars:
            self._get_next_name(var)

        # 2. Inductive Assumption (read_scope)
        # This is P(k). We assume the condition and the invariant hold true at the start of iteration 'k'.
        read_scope = self.current_versions.copy()
        cond_read = node.condition.accept(self)
        inv_read = node.invariant.accept(self) if node.invariant else Literal("true")

        # 3. Loop Body Transition
        # We process the math inside the loop. This maps iteration 'k' to iteration 'k+1'.
        body_formulas = node.body.accept(self)

        # 4. Inductive Step (write_scope)
        # This is P(k+1). Does the invariant STILL hold true after the math executed?
        write_scope = self.current_versions.copy()
        inv_write = node.invariant.accept(self) if node.invariant else Literal("true")

        loop_transition = LoopTransition(
            pre_loop_scope=pre_loop_scope,
            read_scope=read_scope,
            write_scope=write_scope,
            inv_pre=inv_pre,
            inv_read=inv_read,
            inv_write=inv_write,
            cond_read=cond_read, 
            body_formulas=body_formulas
        )
        formulas.append(loop_transition)

        # 5. Timeline Resolution
        # When a loop terminates, it bypassed the body entirely. Therefore, the variables 
        # flowing into the rest of the program must match the exact state when the 
        # condition was checked (the read_scope).
        self.current_versions = read_scope.copy()

        return formulas