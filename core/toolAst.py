"""
What's happening here:
The Forward Declarations: In the ASTVisitor, we use strings like 'BinaryExpr' so Python doesn't throw a NameError trying to find classes we haven't defined yet.

The -> Any return type: Because different visitors return different things (e.g., Z3Translator returns z3.ExprRef, while a TypeChecker might return a string like "bool"),
we let the accept method return Any.

The Trapdoor: If we ever add a new node and forget to write an accept method, the base ASTNode will crash immediately with a helpful error message pointing exactly 
to the class we missed.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any

class ASTVisitor:
    """
    Abstract base visitor class for traversing the TOOL AST.
    All concrete visitors (like Z3Translator or TypeChecker) will inherit from this.
    """
    def visit_Program(self, node: 'Program'): pass
    def visit_VarDecl(self, node: 'VarDecl'): pass
    def visit_InvisibleDecl(self, node: 'InvisibleDecl'): pass
    def visit_StructDef(self, node: 'StructDef'): pass
    def visit_FunctionDef(self, node: 'FunctionDef'): pass

    # Expressions
    def visit_BinaryExpr(self, node: 'BinaryExpr'): pass
    def visit_TernaryExpr(self, node: 'TernaryExpr'): pass
    def visit_UnaryExpr(self, node: 'UnaryExpr'): pass
    def visit_Quantifier(self, node: 'Quantifier'): pass
    def visit_VarRef(self, node: 'VarRef'): pass
    def visit_Literal(self, node: 'Literal'): pass
    def visit_FuncCall(self, node: 'FuncCall'): pass
    def visit_FieldAccess(self, node: 'FieldAccess'): pass
    def visit_SeqAccess(self, node: 'SeqAccess'): pass
    def visit_StructUpdate(self, node: 'StructUpdate'): pass
    def visit_SeqUpdate(self, node: 'SeqUpdate'): pass
    def visit_LoopTransition(self, node: 'LoopTransition'): pass
    def visit_CallSiteCheck(self, node: 'CallSiteCheck'): pass
    
    # Statements / Formal Constructs
    def visit_Assume(self, node: 'Assume'): pass
    def visit_Returns(self, node: 'Returns'): pass
    def visit_AssignStmt(self, node: 'AssignStmt'): pass
    def visit_AssertStmt(self, node: 'AssertStmt'): pass
    def visit_BlockStmt(self, node: 'BlockStmt'): pass
    def visit_IfStmt(self, node: 'IfStmt'): pass
    def visit_WhileStmt(self, node: 'WhileStmt'): pass

@dataclass
class ASTNode:
    """Root class for all AST nodes."""
    def accept(self, visitor: 'ASTVisitor') -> Any:
        raise NotImplementedError(f"Each concrete AST node must implement accept(). Missing in {self.__class__.__name__}")

@dataclass
class Expr(ASTNode):
    """Base class for all expressions."""
    pass

@dataclass
class VarRef(Expr):
    name: str

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_VarRef(self)

@dataclass
class Literal(Expr):
    value: str

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_Literal(self)
    
@dataclass
class Program(ASTNode):
    declarations: List[ASTNode]
    preconditions: List[ASTNode]
    postconditions: List[ASTNode]
    specProgram: List[ASTNode]

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_Program(self)

@dataclass
class VarDecl(ASTNode):
    name: str
    typeName: str
    is_refer: bool = False

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_VarDecl(self)

@dataclass
class InvisibleDecl(ASTNode):
    name: str
    typeName: str

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_InvisibleDecl(self)

@dataclass
class StructDef(ASTNode):
    name: str 
    fields: Dict[str, str] 
    is_linear: bool = False 

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_StructDef(self)

@dataclass
class FunctionDef(ASTNode):
    name: str
    args: List[VarDecl]
    retName: str
    retType: str
    clauses: List[ASTNode]

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_FunctionDef(self)
    
@dataclass
class BinaryExpr(Expr):
    left: Expr
    op: str
    right: Expr

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_BinaryExpr(self)

@dataclass
class TernaryExpr(Expr):
    condition: Expr
    true_expr: Expr
    false_expr: Expr

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_TernaryExpr(self)

@dataclass
class UnaryExpr(Expr):
    op: str
    operand: Expr

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_UnaryExpr(self)

@dataclass
class Quantifier(Expr):
    quant_type: str
    bound_var: str
    var_type: str
    formula: Expr

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_Quantifier(self)

@dataclass
class FuncCall(Expr):
    name: str
    args: List[Expr]

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_FuncCall(self)

@dataclass
class FieldAccess(Expr):
    obj: Expr
    field: str

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_FieldAccess(self)

@dataclass
class SeqAccess(Expr):
    seq_obj: Expr
    index: Expr

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_SeqAccess(self)

@dataclass
class StructUpdate(Expr):
    obj: Expr
    field: str
    new_value: Expr

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_StructUpdate(self)

@dataclass
class SeqUpdate(Expr):
    seq_obj: Expr
    index: Expr
    new_value: Expr

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_SeqUpdate(self)
    
@dataclass
class LoopTransition(Expr):
    pre_loop_scope: Dict[str, int]
    read_scope: Dict[str, int]     
    write_scope: Dict[str, int]    
    
    inv_pre: Expr                  
    inv_read: Expr                 
    inv_write: Expr                
    
    cond_read: Expr
    
    body_formulas: List[Expr]      

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_LoopTransition(self)

@dataclass
class CallSiteCheck(ASTNode):
    formula: 'Expr'

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_CallSiteCheck(self)

@dataclass
class Assume(ASTNode):
    formula: Expr

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_Assume(self)

@dataclass
class Returns(ASTNode):
    formula: Expr

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_Returns(self)

@dataclass
class Stmt(ASTNode):
    pass

@dataclass
class AssignStmt(Stmt):
    lvalue: VarRef
    expr: Expr

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_AssignStmt(self)

@dataclass
class AssertStmt(Stmt):
    formula: Expr

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_AssertStmt(self)

@dataclass
class BlockStmt(Stmt):
    statements: List[Stmt]

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_BlockStmt(self)

@dataclass
class IfStmt(Stmt):
    condition: Expr
    then_block: BlockStmt
    else_block: Optional[BlockStmt]

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_IfStmt(self)

@dataclass
class WhileStmt(Stmt):
    condition: Expr
    invariant: Optional[Expr]
    body: BlockStmt

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_WhileStmt(self)
