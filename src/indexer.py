from tree_sitter import Language, Parser
import tree_sitter_python
import hashlib
import json
import os

class Indexer:
    """
    Component: The Source of Truth (Indexer)
    Mechanism: AST-Based Semantic Chunking
    """
    def __init__(self, target_schema: str = "python"):
        """
        Tools: ["tree-sitter", "python-bindings"]
        Logic: Initialize Parser with language grammar.
        """
        # Load the Python language grammar
        try:
            self.language = Language(tree_sitter_python.language())
            self.parser = Parser(self.language)
        except Exception as e:
            print(f"Error initializing Tree Sitter: {e}")
            self.parser = None
        
        self.index = {}
        self.current_file = None  # Track current file being parsed

    def parse_file(self, file_path: str) -> dict:
        """
        Task ID: INDEXER_01
        Logic:
          - Parse raw source code into Abstract Syntax Trees (AST).
          - Extract semantic nodes: Function definitions, Class declarations, Structs.
          - Hash each node to create a unique Chunk ID.
          - Map every significant token (function names, variable names) to a Set of Chunk IDs.
        Returns:
          Dictionary of {function_name: source_code_string}
        """
        if not self.parser:
            raise RuntimeError("Parser not initialized.")

        with open(file_path, "rb") as f:
            source_code = f.read()
        
        # Extract module name from file path (for imports)
        self.current_file = os.path.splitext(os.path.basename(file_path))[0]

        tree = self.parser.parse(source_code)
        
        # Helper to traverse and extract functions/classes
        # We want to capture the full source code of the node
        
        extracted_chunks = {}
        
        # Query to find match function/class definitions
        query_scm = """
        (function_definition
          name: (identifier) @name) @function

        (class_definition
          name: (identifier) @name) @class
        """
        
        # Note: tree-sitter query API varies slightly by version, adapting to standard usage
        if not hasattr(self, 'language'):
             self.language = Language(tree_sitter_python.language())
        
        # Use Query constructor as per deprecation warning if possible, but language.query is still working (returning Query)
        # The issue is execution.
        query = self.language.query(query_scm)
        
        from tree_sitter import QueryCursor
        cursor = QueryCursor(query)
        captures = cursor.captures(tree.root_node)

        # captures is a dict {name: [nodes]}
        for capture_name, nodes in captures.items():
            for node in nodes:
                # Logic for processing node
                if capture_name == "name":
                    pass # Handled in parent
                
                if capture_name in ["function", "class"]:
                    # Extract the source code
                    start_byte = node.start_byte
                    end_byte = node.end_byte
                    chunk_source = source_code[start_byte:end_byte].decode("utf8")
                    
                    # Extract name
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        func_name = source_code[name_node.start_byte:name_node.end_byte].decode("utf8")
                        
                        # SPEC COMPLIANCE: Extract function signature
                        signature = {"params": [], "returns": None}
                        
                        # Extract parameters from the 'parameters' field
                        params_node = node.child_by_field_name("parameters")
                        if params_node:
                            # Iterate through children to find identifiers (param names)
                            for child in params_node.children:
                                if child.type == "identifier":
                                    param_name = source_code[child.start_byte:child.end_byte].decode("utf8")
                                    signature["params"].append(param_name)
                                elif child.type == "typed_parameter":
                                    # Handle typed params like `x: int`
                                    name_child = child.child_by_field_name("name") or child.children[0] if child.children else None
                                    if name_child:
                                        param_name = source_code[name_child.start_byte:name_child.end_byte].decode("utf8")
                                        signature["params"].append(param_name)
                                elif child.type == "default_parameter":
                                    # Handle default params like `x=10`
                                    name_child = child.child_by_field_name("name") or child.children[0] if child.children else None
                                    if name_child:
                                        param_name = source_code[name_child.start_byte:name_child.end_byte].decode("utf8")
                                        signature["params"].append(param_name)
                        
                        # Generate ID (hash)
                        chunk_id = hashlib.sha256(chunk_source.encode("utf8")).hexdigest()
                        
                        # Store in index with filename metadata AND signature
                        self.index[func_name] = {
                            "source": chunk_source,
                            "filename": self.current_file,
                            "signature": signature
                        }
                        extracted_chunks[func_name] = chunk_source

        return extracted_chunks

    def export_index(self, output_path: str = "inverted_index.json") -> str:
        """
        Output Artifact: "inverted_index.json"
        """
        with open(output_path, "w") as f:
            json.dump(self.index, f, indent=2)
        return output_path

if __name__ == "__main__":
    # Test stub
    # Create a dummy python file to test
    with open("test_dummy.py", "w") as f:
        f.write("def hello_world():\n    print('Hello')\n\nclass Test:\n    def method(self):\n        pass")
    
    indexer = Indexer()
    extracted = indexer.parse_file("test_dummy.py")
    print("Extracted:", extracted.keys())
    indexer.export_index()
    print("Exported index.")
