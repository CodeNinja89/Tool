from core.toolTypes import TypeEnvironment
from core.toolAst import *
from typing import Dict

class ASTSubstitutor:
    def __init__(self, substitution_map: Dict[str, Expr]):
        self.sub_map = substitution_map

    def substitute(self, node: Expr) -> Expr:
        if isinstance(node, VarRef):
            if node.name in self.sub_map:
                return self.sub_map[node.name]
            return node
        
        elif isinstance(node, BinaryExpr):
            return BinaryExpr(
                left=self.substitute(node.left),
                op=node.op,
                right=self.substitute(node.right)
            )
        
        elif isinstance(node, UnaryExpr):
            return UnaryExpr(
                op=node.op,
                operand=self.substitute(node.operand)
            )
        
        elif isinstance(node, TernaryExpr):
            return TernaryExpr(
                condition=self.substitute(node.condition),
                true_expr=self.substitute(node.true_expr),
                false_expr=self.substitute(node.false_expr)
            )
        
        elif isinstance(node, FuncCall):
            return FuncCall(
                name=node.name,
                args=[self.substitute(arg) for arg in node.args]
            )
        
        elif isinstance(node, SeqAccess):
            return SeqAccess(
                seq_obj=self.substitute(node.seq_obj),
                index=self.substitute(node.index)
            )
        
        elif isinstance(node, FieldAccess):
            return FieldAccess(
                obj=self.substitute(node.obj),
                field=node.field
            )
        
        elif isinstance(node, Literal):
            return node
        
        elif isinstance(node, Quantifier):
            shadowed_val = None
            if node.bound_var in self.sub_map:
                shadowed_val = self.sub_map.pop(node.bound_var)
                
            # Recursively substitute inside the quantifier's formula
            new_formula = self.substitute(node.formula)
            
            # Restore the map if we shadowed something
            if shadowed_val is not None:
                self.sub_map[node.bound_var] = shadowed_val
                
            return Quantifier(
                quant_type=node.quant_type,
                bound_var=node.bound_var,
                var_type=node.var_type,
                formula=new_formula
            )
            
        return node
    
class OracleManager:
    def __init__(self, env: TypeEnvironment) -> None:
        self.env = env

    def is_recursive(self, oracle_def: FunctionDef) -> bool:
        """Walk the AST and detect if this is a self-recursion"""
        def check_node(node: ASTNode) -> bool:
            if isinstance(node, FuncCall):
                if node.name == oracle_def.name:
                    return True
                return any(check_node(arg) for arg in node.args)
            elif isinstance(node, BinaryExpr):
                return check_node(node.left) or check_node(node.right)
            elif isinstance(node, UnaryExpr):
                return check_node(node.operand)
            elif isinstance(node, TernaryExpr):
                return check_node(node.condition) or check_node(node.true_expr) or check_node(node.false_expr)
            elif isinstance(node, Quantifier):
                return check_node(node.formula)
            elif isinstance(node, FieldAccess):
                return check_node(node.obj)
            elif isinstance(node, SeqAccess):
                return check_node(node.seq_obj) or check_node(node.index)
            return False
        
        for clause in oracle_def.clauses:
            if isinstance(clause, Assume):
                if check_node(clause.formula): return True

            elif isinstance(clause, Returns):
                if check_node(clause.formula): return True

        return False
        
    def extract_contract(self, func_call: FuncCall) -> tuple[Optional[Expr], Expr]:
        oracle_name = func_call.name

        # look up the oracle definition
        if oracle_name not in self.env.oracles:
            raise Exception(f"Oralce {oracle_name} is not defined!")
        oracle_def = self.env.oracles[oracle_name]

        # check the number of arguments
        if len(func_call.args) != len(oracle_def.args):
            raise Exception(f"{oracle_name} expects {len(func_call.args)} arguments!")
        
        sub_map: Dict[str, Expr] = {} # the substitution map

        # Map formal parameters to the concrete arguments
        # e.g., "seq" -> VarRef("footprint_1")
        for i, formal_arg in enumerate(oracle_def.args):
            sub_map[formal_arg.name] = func_call.args[i]

        # Map the return variable to the actual function call
        # e.g., "res" -> FuncCall("is_acyclic", [VarRef("footprint_1")])
        sub_map[oracle_def.retName] = func_call

        # 4. Extract the assumes and returns clauses
        assumes_expr: Optional[Expr] = None
        returns_expr: Optional[Expr] = None

        for clause in oracle_def.clauses:
            if isinstance(clause, Assume):
                assumes_expr = clause.formula
            elif isinstance(clause, Returns):
                returns_expr = clause.formula

        # An oracle MUST have a returns clause to be mathematically useful
        if not returns_expr:
            raise Exception(f"OracleManager Error: Oracle '{oracle_name}' is missing a 'returns' clause.")

        # 5. Run the substitutions
        substitutor = ASTSubstitutor(sub_map)
        
        grounded_returns = substitutor.substitute(returns_expr)
        grounded_assumes = substitutor.substitute(assumes_expr) if assumes_expr else None

        return grounded_assumes, grounded_returns