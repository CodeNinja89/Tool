from core.toolAst import *
from core.toolTypes import *
from typing import Dict, Any, cast
from core.toolOracles import OracleManager

class SSATransformer:
    def __init__(self, env: TypeEnvironment):
        self.max_versions: Dict[str, int] = {} # max version ever given to a variable (never rewinds)
        self.current_versions: Dict[str, int] = {} # current scope versions (rewinds on branches)
        self.env = env # set the universe
        self.bound_vars = set()
        self.oracle_manager = OracleManager(self.env)

    def _get_current_name(self, name: str) -> str:
        # reads the current version of a variable for the RHS
        if name not in self.current_versions:
            self.current_versions[name] = 0
            self.max_versions[name] = 0
        return f"{name}_{self.current_versions[name]}"
    
    def _get_next_name(self, name: str) -> str:
        # returns the new version of the variable being assigned to
        if name not in self.max_versions:
            self.max_versions[name] = 0
        self.max_versions[name] += 1
        self.current_versions[name] = self.max_versions[name]
        return f"{name}_{self.current_versions[name]}"
    
    def _get_write_set(self, stmt: Stmt) -> set:
        # when we hit a while statement, we don't know how many times it has run.
        # therefore, any variable that is modified inside the loop body must be
        # completely symbolic at the start of the analysis
        # this helper function peeks inside the loop block and finds all the 
        # variables that get assigned. This set of variables is called a 
        # write set.

        writes = set()
        if isinstance(stmt, AssignStmt):
            if isinstance(stmt.lvalue, VarRef):
                writes.add(stmt.lvalue.name)
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
    
    def transform_expr(self, node: Expr) -> Expr:
        # recursively update variable references in expressions to
        # their SSA versions
        if isinstance(node, VarRef):
            if node.name in self.bound_vars:
                return node
            return VarRef(self._get_current_name(node.name))
        
        elif isinstance(node, Literal):
            return node
        
        elif isinstance(node, BinaryExpr):
            return BinaryExpr(
                left=self.transform_expr(node.left),
                op=node.op,
                right=self.transform_expr(node.right)
            )
        
        elif isinstance(node, UnaryExpr):
            return UnaryExpr(
                op=node.op,
                operand=self.transform_expr(node.operand)
            )
        
        elif isinstance(node, Quantifier):
            # 1. Register the bound variable so it doesn't get SSA versioned
            self.bound_vars.add(node.bound_var)
            
            # 2. Recursively transform the inner formula
            inner_transformed = self.transform_expr(node.formula)
            
            # 3. Clean up the bound variable
            self.bound_vars.remove(node.bound_var)
            
            return Quantifier(
                quant_type=node.quant_type,
                bound_var=node.bound_var,
                var_type=node.var_type,
                formula=inner_transformed
            )
        
        elif isinstance(node, FuncCall):
            return FuncCall(
                name=node.name,
                args=[self.transform_expr(arg) for arg in node.args]
            )
        
        elif isinstance(node, TernaryExpr):
            return TernaryExpr(
                condition = self.transform_expr(node.condition),
                true_expr=self.transform_expr(node.true_expr),
                false_expr=self.transform_expr(node.false_expr)
            )
        
        elif isinstance(node, FieldAccess):
            return FieldAccess(
                obj=self.transform_expr(node.obj),
                field=node.field
            )
        
        elif isinstance(node, SeqAccess):
            return SeqAccess(
                seq_obj=self.transform_expr(node.seq_obj),
                index=self.transform_expr(node.index)
            )
        
        return node # fallback
    
    def transform_stmt(self, node: Stmt) -> List[Expr]:
        # transform an imperative statement into a list of math formulas
        formulas = []

        if isinstance(node, AssignStmt):
            if isinstance(node.expr, FuncCall) and node.expr.name in self.env.oracles:
                oracle_def = self.env.get_oracles(node.expr.name)
                
                grounded_assumes, grounded_returns = self.oracle_manager.extract_contract(node.expr)
                if grounded_assumes:
                    ssa_assumes = self.transform_expr(grounded_assumes)
                    formulas.append(CallSiteCheck(ssa_assumes))

                if not self.oracle_manager.is_recursive(oracle_def):
                    if grounded_returns:
                        ssa_returns = self.transform_expr(grounded_returns)
                        formulas.append(ssa_returns)

            # transform RHS
            rhs_transformed = self.transform_expr(node.expr)
            
            # transform LHS
            if isinstance(node.lvalue, VarRef):
                new_lhs = self._get_next_name(node.lvalue.name)
                lhs_transformed = VarRef(new_lhs)
                formulas.append(BinaryExpr(left=lhs_transformed,
                            op='==',
                            right=rhs_transformed))
            elif isinstance(node.lvalue, FieldAccess):
                base_obj = node.lvalue.obj
                if not isinstance(base_obj, VarRef):
                    raise NotImplementedError("Nested struct updatets not yet supported!")
                base_name = base_obj.name

                var_type = self.env.get_var_type(base_name)
                struct_fields = self.env.get_struct_fields(var_type)
                if node.lvalue.field not in struct_fields:
                    raise Exception(f"Struct {var_type} has no field {node.lvalue.field}")
                
                old_version = VarRef(self._get_current_name(base_name))
                new_version = VarRef(self._get_next_name(base_name))

                update_expr = StructUpdate(
                    obj=old_version,
                    field=node.lvalue.field,
                    new_value=rhs_transformed)
                formulas.append(BinaryExpr(
                    left=new_version,
                    op='==',
                    right=update_expr))
                
            elif isinstance(node.lvalue, SeqAccess):
                base_obj = node.lvalue.seq_obj
                if not isinstance(base_obj, VarRef):
                    raise NotImplementedError("Multidimensional sequences not supported!")
                base_name = base_obj.name

                var_type = self.env.get_var_type(base_name)
                if not var_type.startswith("seq["):
                    raise Exception(f"{base_name} not a sequence")
                
                old_version = VarRef(self._get_current_name(base_name))
                new_version = VarRef(self._get_next_name(base_name))
                transformed_idx = self.transform_expr(node.lvalue.index)

                update_expr = SeqUpdate(
                    seq_obj=old_version,
                    index=transformed_idx,
                    new_value=rhs_transformed
                )

                formulas.append(BinaryExpr(
                    left=new_version,
                    op='==',
                    right=update_expr
                ))

            else:
                raise NotImplementedError(f"SSA for {type(node.lvalue)} not yet supported")

        elif isinstance(node, AssertStmt):
            formulas.append(self.transform_expr(node.formula))

        elif isinstance(node, BlockStmt):
            for stmt in node.statements:
                formulas.extend(self.transform_stmt(stmt))

        elif isinstance(node, WhileStmt):
            '''
                We take a snapshot of the exact variable versions the moment the program arrives 
                at the loop (e.g., x_0, y_1). We then evaluate the invariant expression using 
                this specific timeline.

                This is Iteration 0. Before the loop even checks its condition, the invariant 
                must be true. If inv_pre evaluates to false, the user wrote a bad invariant.
            '''
            pre_loop_scope = self.current_versions.copy() # base case
            inv_pre = self.transform_expr(node.invariant) if node.invariant else Literal("true") # evaluate loop invariant upon entry to loop

            '''
                scan the inside of the loop to see what variables get changed. Then, we blindly 
                increment their SSA versions without assigning them concrete values.

                This is the most critical conceptual leap. Because we can't unroll the 
                loop 1,000 times, we tell the solver: "Imagine we are at some arbitrary iteration $i$. 
                I don't know what values these variables have anymore, so treat them as completely 
                unknown (symbolic)." This technique is formally called Havocing.
            '''

            modified_vars = self._get_write_set(node.body) # get the list of variables that are updated
            for var in modified_vars:
                self._get_next_name(var)

            '''
                take a second snapshot. Because of the Havoc step, modified variables now have new, 
                completely unconstrained versions (e.g., x_1). We evaluate the loop condition and 
                the invariant using this new timeline.

                 In induction, you assume $P(k)$ is true to prove $P(k+1)$. inv_read is our $P(k)$. We will 
                 eventually tell the SMT solver: "Assume the invariant holds for these unknown variables 
                 at the start of the loop."
            '''

            # inductive assumption
            read_scope = self.current_versions.copy()
            cond_read = self.transform_expr(node.condition)
            inv_read = self.transform_expr(cast(Expr, node.invariant)) if node.invariant else Literal("true")
            measure_read = self.transform_expr(cast(Expr, node.measure)) if node.measure else None

            '''
                We process the imperative statements inside the loop. The SSA engine naturally maps the 
                read_scope versions (e.g., x_1) to even newer versions (e.g., x_2) based on the math in 
                the loop.

                This generates the mathematical bridge between iteration $i$ and iteration $i+1$.
            '''

            # execute loop body
            body_formulas = []
            for stmt in node.body.statements:
                body_formulas.extend(self.transform_stmt(stmt))

            '''
                We take a third snapshot after the body has executed. We evaluate the invariant one 
                last time using these final variable versions (e.g., x_2).

                This is $P(k+1)$. We will eventually ask Z3 to prove that inv_write is true, given 
                that inv_read and body_formulas were true. If Z3 can't prove it, the loop body 
                breaks the invariant.
            '''

            write_scope = self.current_versions.copy()
            inv_write = self.transform_expr(cast(Expr, node.invariant)) if node.invariant else Literal("true")
            measure_write = self.transform_expr(cast(Expr, node.measure)) if node.measure else None

            loop_transition = LoopTransition(
                pre_loop_scope=pre_loop_scope,
                read_scope=read_scope,
                write_scope=write_scope,
                inv_pre=inv_pre,
                inv_read=inv_read,
                inv_write=inv_write,
                cond_read=cond_read,
                measure_read=measure_read,
                measure_write=measure_write,
                body_formulas=body_formulas
            )

            '''
                After packaging everything into the LoopTransition AST node, we rewind the SSA engine's 
                current state back to the read_scope (the start of the arbitrary iteration).

                When a loop actually terminates, it means it evaluated the condition, found it to be False,
                and bypassed the body. Therefore, the variables for the code running after the loop must
                match the variables at the moment the condition was checked (the read_scope).
            '''
            formulas.append(loop_transition)

            self.current_versions = read_scope.copy()

        elif isinstance(node, IfStmt):
            cond_expr = self.transform_expr(node.condition) # transform condition using current versions
            base_versions = self.current_versions.copy() # snapshot the current versions. base universe

            then_formulas = [] # explore the then-universe

            for stmt in node.then_block.statements:
                then_formulas.extend(self.transform_stmt(stmt))
            then_versions = self.current_versions.copy() # save the versions of then-universe

            self.current_versions = base_versions.copy() # revert back to the original universe
            else_formulas = []
            else_versions = base_versions.copy() # if no else block, default to base universe

            if node.else_block:
                for stmt in node.else_block.statements:
                    else_formulas.extend(self.transform_stmt(stmt))
                else_versions = self.current_versions.copy() # save the versions of the else-universe

            phi_formulas = []
            # find all variables that were modified in either branch
            all_vars = set(then_versions.keys()).union(set(else_versions.keys()))

            for var in all_vars:
                v_base = base_versions.get(var, 0)
                v_then = then_versions.get(var, 0)
                v_else = else_versions.get(var, 0)

                # check if the variable changed in either timeline. If it did, we create a Phi node
                if v_then != v_base or v_else != v_base:
                    # self.versions[var] = max(v_then, v_else) + 1
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

            formulas.extend(then_formulas)
            formulas.extend(else_formulas)
            formulas.extend(phi_formulas)

        return formulas
    
    def generate_transition_predicate(self, spec_program: List[Stmt]) -> List[Expr]:
        # convert the whole program into a list of formulas.

        transition_formulas = []
        for stmt in spec_program:
            transition_formulas.extend(self.transform_stmt(stmt))

        return transition_formulas