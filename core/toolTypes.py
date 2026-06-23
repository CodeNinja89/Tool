from typing import Dict, List, Set, Optional
from core.toolAst import FunctionDef

class TypeEnvironment:
    """
    Acts as a Symbol Table for the TypeChecker and Verifier passes.
    Handles scoping to prevent local variables from polluting global memory.
    """
    def __init__(self):
        # We use a stack of dictionaries to handle local function scopes.
        # Index 0 is the global scope.
        self.scopes: List[Dict[str, str]] = [{}] 
        
        self.structs: Dict[str, Dict[str, str]] = {}
        self.oracles: Dict[str, FunctionDef] = {}
        self.linear_structs: Set[str] = set()
        self.invisible_vars: Set[str] = set()

    @property
    def variables(self) -> Dict[str, str]:
        """
        Returns a flattened view of all variables in the current scope chain.
        Local variables shadow global variables with the same name.
        """
        flattened = {}
        for scope in self.scopes:
            flattened.update(scope)
        return flattened

    # --- Scope Management ---
    
    def push_scope(self):
        """Creates a new local memory sandbox (e.g., when entering a function)."""
        self.scopes.append({})

    def pop_scope(self):
        """Destroys the local memory sandbox."""
        if len(self.scopes) > 1:
            self.scopes.pop()
        else:
            raise Exception("Compiler Error: Attempted to pop the global scope.")

    # --- Registration ---

    def register_var(self, name: str, type_name: str):
        """Registers a variable in the CURRENT scope."""
        self.scopes[-1][name] = type_name

    def register_struct(self, name: str, fields: Dict[str, str]):
        self.structs[name] = fields

    def register_invisible(self, name: str, type_name: str):
        self.invisible_vars.add(name)
        self.register_var(name, type_name)

    # --- Validation & Retrieval ---

    def is_valid_type(self, type_name: str) -> bool:
        if type_name in ("int", "bool"):
            return True
        if type_name.startswith("seq[") and type_name.endswith("]"):
            inner_type = type_name[4:-1]
            return self.is_valid_type(inner_type)
        if type_name in self.structs:
            return True
        return False

    def is_linear_type(self, type_name: str) -> bool:
        return type_name in self.linear_structs

    def get_var_type(self, var_name: str) -> Optional[str]:
        # Search backwards from the most local scope up to the global scope
        for scope in reversed(self.scopes):
            if var_name in scope:
                return scope[var_name]
        return None # Return None instead of crashing so the caller can throw a formatted error
    
    def get_struct_fields(self, struct_name: str) -> Dict[str, str]:
        if struct_name not in self.structs:
            raise Exception(f"Type Error: Struct '{struct_name}' is not defined.")
        return self.structs[struct_name]
    
    def get_oracles(self, oracle_name: str) -> FunctionDef:
        if oracle_name not in self.oracles:
            raise Exception(f"Type Error: Oracle '{oracle_name}' is not defined.")
        return self.oracles[oracle_name]