# holds all the semantic information

from dataclasses import dataclass
from typing import List, Optional, Union, Dict

@dataclass
class ASTNode:
    pass

@dataclass
class Program(ASTNode):
    declarations: List[ASTNode]
    preconditions: List[ASTNode]
    postconditions: List[ASTNode]
    specProgram: List[ASTNode]

@dataclass
class VarDecl(ASTNode):
    name: str
    typeName: str

@dataclass
class StructDef(ASTNode):
    name: str # name of the struct
    fields: Dict[str, str] # fields of a struct

@dataclass
class FunctionDef(ASTNode):
    name: str
    args: List[VarDecl]
    retName: str
    retType: str
    clauses: List[ASTNode]

@dataclass
class Expr(ASTNode):
    pass

@dataclass
class BinaryExpr(Expr):
    left: Expr
    op: str
    right: Expr

@dataclass
class TernaryExpr(Expr):
    condition: Expr
    true_expr: Expr
    false_expr: Expr

@dataclass
class UnaryExpr(Expr):
    op: str
    operand: Expr

@dataclass
class Quantifier(Expr):
    quant_type: str
    bound_var: str
    var_type: str
    formula: Expr

@dataclass
class VarRef(Expr):
    name: str

@dataclass
class Literal(Expr):
    value: str

@dataclass
class FuncCall(Expr):
    name: str
    args: List[Expr]

@dataclass
class FieldAccess(Expr):
    # access the field of a struct
    obj: Expr
    field: str

@dataclass
class SeqAccess(Expr):
    # access a specific index in a sequence
    seq_obj: Expr
    index: Expr

@dataclass
class StructUpdate(Expr):
    # turn a field assignement into a SSA
    obj: Expr
    field: str
    new_value: Expr

@dataclass
class SeqUpdate(Expr):
    seq_obj: Expr
    index: Expr
    new_value: Expr

@dataclass
class LoopTransition(Expr):
    invariant: Expr # loop invariant
    condition: Expr # loop condition
    measure: Optional[Expr] # loop measure
    body_formulas: List[Expr] # the loop body as transformed formulas
    read_scope: Dict[str, int] # variable versions at the start of the iteration
    write_scope: Dict[str, int] # variable versions at the end of the iteration

@dataclass
class Assume(ASTNode):
    formula: Expr

@dataclass
class Returns(ASTNode):
    formula: Expr

@dataclass
class Stmt(ASTNode):
    pass

@dataclass
class AssignStmt(Stmt):
    lvalue: VarRef
    expr: Expr

@dataclass
class AssertStmt(Stmt):
    formula: Expr

@dataclass
class BlockStmt(Stmt):
    statements: List[Stmt]

@dataclass
class IfStmt(Stmt):
    condition: Expr
    then_block: BlockStmt
    else_block: Optional[BlockStmt]

@dataclass
class WhileStmt(Stmt):
    condition: Expr
    invariant: Optional[Expr]
    measure: Optional[Expr]
    body: BlockStmt
