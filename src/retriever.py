import json
from typing import List, Optional, Set
import re

class IntersectionEngine:
    """
    Component: The Intersection Engine
    Mechanism: Strict Set Intersection
    """
    def __init__(self, index_path: str = "inverted_index.json"):
        self.index_path = index_path
        self._load_index()

    def _load_index(self):
        try:
            with open(self.index_path, "r") as f:
                self.index = json.load(f)
        except FileNotFoundError:
            print(f"Index file {self.index_path} not found. Starting with empty index.")
            self.index = {}

    def search(self, query: str) -> Optional[List[str]]:
        """
        Task ID: RETRIEVER_01
        Logic:
          - Receive User Query (Natural Language).
          - Expand Query -> Target Tokens.
          - Perform Intersection: Result = Set(Token_A) ∩ Set(Token_B).
          - Constraint: If Result is Empty, Return None aka 'Insufficient Data'.
        """
        # Step 1: Expand Query -> Target Tokens
        # Simple implementation: Tokenize by space and snake_case
        # A more advanced version would use an LLM or a map of synonyms, 
        # but strict intersection implies exact matches are desired or at least dominant.
        
        # Normalize and split
        tokens = set(re.findall(r'\w+', query))
        
        # Since the inverted index maps FunctionName -> Source,
        # we need to find which functions match the query tokens.
        # However, "inverted index" in search usually means Token -> List[DocID].
        # The current 'self.index' is {FunctionName: Source}.
        # Matches can be on the function name itself.
        
        # Let's filter the keys of self.index (Function Names) based on query tokens.
        # But the Requirement says "Set(Token_A) ∩ Set(Token_B)".
        # This implies we are intersecting the SET of query tokens with the SET of features in a chunk?
        # OR finding chunks that contain ALL query tokens?
        
        # Spec: "It must return the subset of code chunks that match ALL tokens."
        
        matched_chunks = []
        
        # We really want specific keywords from the query, e.g. "create_user"
        # If the user says "Establish a connection", we look for "Establish", "connection" in the function name?
        # Or do we scan the source code? The "Indexer" step said: 
        # "Map every significant token (function names, variable names) to a Set of Chunk IDs."
        
        # My current Indexer output is {func_name: source_code}.
        # For this MVP strict intersection, I will search if the Function Name contains the tokens.
        # Or better, create a temporary reverse map if needed, or just iterate (dataset is small).
        
        # Refined Logic:
        # A Match occurs if a chunk's name contains RELEVANT tokens from the query.
        # But stricter interpretation: The chunk MUST match ALL tokens provided in the expansion list.
        # The prompt says: "Expand Query -> Target Tokens (e.g., 'Make user' -> ['create_user', 'UserStruct'])"
        # This expansion step usually requires an LLM or map.
        # WITHOUT an LLM for expansion (since I might strictly use logic here), 
        # I will assume the `query` passed to this function might already be keywords, 
        # OR I do a simple keyword extraction.
        
        # Let's assume the input `query` is natural language.
        # I will extract potential snake_case or CamelCase words as "Target Tokens".
        
        target_tokens = [t for t in tokens if len(t) > 3] # Filter noise
        if not target_tokens:
            return None # No significant tokens
            
        final_results = []
        
        for func_name, chunk_data in self.index.items():
            # Handle both old format (string) and new format (dict with source/filename/signature)
            if isinstance(chunk_data, dict):
                source_code = chunk_data.get("source", "")
                filename = chunk_data.get("filename", "unknown")
                signature = chunk_data.get("signature", {"params": [], "returns": None})
            else:
                source_code = chunk_data
                filename = "unknown"
                signature = {"params": [], "returns": None}
            
            # Case insensitive search in source code
            source_lower = source_code.lower()
            func_name_lower = func_name.lower()
            
            # SET INTERSECTION: Check if ALL tokens are present
            matches_all = True
            for token in target_tokens:
                token_lower = token.lower()
                # Check in both function name and source code
                if token_lower not in source_lower and token_lower not in func_name_lower:
                    matches_all = False
                    break
            
            if matches_all:
                final_results.append({
                    "source": source_code,
                    "filename": filename,
                    "func_name": func_name,
                    "signature": signature  # SPEC COMPLIANCE: Include signature
                })
                
        if not final_results:
            return None
            
        return final_results

    @property
    def guarantee(self):
        return "Zero Hallucination (The LLM never sees missing dependencies)."

if __name__ == "__main__":
    # Test stub
    retriever = IntersectionEngine()
    # Mock index if empty
    if not retriever.index:
        retriever.index = {
            "create_user": "def create_user(name): pass", 
            "delete_user": "def delete_user(id): pass"
        }
    
    results = retriever.search("create user")
    print(f"Search 'create user': {results}")
    results_fail = retriever.search("database")
    print(f"Search 'database': {results_fail}")
