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
            return node 
            
        return node
    
class OracleManager:
    def __init__(self, env: TypeEnvironment) -> None:
        self.env = env

    