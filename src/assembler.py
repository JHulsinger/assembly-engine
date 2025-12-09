from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel
import json
import sys
import re

# Import MLX
try:
    from mlx_lm import load, generate
    MLX_AVAILABLE = True
except ImportError:
    MLX_AVAILABLE = False
    print("Warning: mlx-lm not installed. Running in MOCK mode.")

class CompilerOutput(BaseModel):
    """
    Task ID: ASSEMBLER_01
    Details: Define a Pydantic model for 'CompilerOutput'
    """
    reasoning: str
    code: str
    filename: str

class Assembler:
    """
    Component: The Linker (SLM)
    Mechanism: Constrained Decoding (Grammar-Enforced)
    Model: "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit"
    """
    MODEL_ID = "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit"
    
    def __init__(self):
        self.model = None
        self.tokenizer = None
        
        if MLX_AVAILABLE:
            try:
                print(f"Loading model: {self.MODEL_ID}...")
                self.model, self.tokenizer = load(self.MODEL_ID)
                print("Model loaded successfully.")
            except Exception as e:
                print(f"Failed to load MLX model: {e}. Switching to Mock.")

    def _build_prompt(self, chunks: List[Dict[str, str]], user_request: str) -> str:
        """Build the structured prompt for the model with explicit import instructions."""
        
        # Group chunks by filename for import generation
        files = {}
        for chunk in chunks:
            fname = chunk.get("filename", "unknown")
            func_name = chunk.get("func_name", "unknown")
            if fname not in files:
                files[fname] = []
            files[fname].append(func_name)
        
        # Build import instructions
        import_lines = []
        for fname, funcs in files.items():
            import_lines.append(f"from {fname} import {', '.join(funcs)}")
        import_block = "\n".join(import_lines)
        
        # Build context with clear labeling
        context_parts = []
        for chunk in chunks:
            fname = chunk.get("filename", "unknown")
            func_name = chunk.get("func_name", "unknown")
            source = chunk.get("source", "")
            context_parts.append(f"# From {fname}.py - function: {func_name}\n{source}")
        context = "\n\n".join(context_parts)
        
        system_msg = f"""You are a deterministic code assembler. You MUST follow these rules EXACTLY:

1. OUTPUT FORMAT: Respond with ONLY valid JSON:
   {{"reasoning": "explanation", "code": "python code", "filename": "output.py"}}

2. REQUIRED IMPORTS - You MUST start your code with these exact imports:
{import_block}

3. RULES:
   - Use ONLY the functions provided below
   - Do NOT invent new functions
   - Do NOT use markdown fences in the code field
   - Output raw Python code only"""

        user_msg = f"""USER REQUEST: {user_request}

AVAILABLE FUNCTIONS:
{context}

Generate the glue code as JSON (remember to include the imports):"""

        return f"<|im_start|>system\n{system_msg}<|im_end|>\n<|im_start|>user\n{user_msg}<|im_end|>\n<|im_start|>assistant\n"

    def _clean_code(self, code: str) -> str:
        """Strip markdown artifacts and validate Python syntax."""
        # Remove markdown fences
        code = re.sub(r'^```(?:python|py)?\s*\n?', '', code, flags=re.MULTILINE)
        code = re.sub(r'\n?```\s*$', '', code, flags=re.MULTILINE)
        
        # Remove standalone 'python' or 'python3' at start
        code = re.sub(r'^python3?\s*\n', '', code, flags=re.MULTILINE)
        
        # Remove any remaining backticks
        code = code.replace('```', '')
        
        return code.strip()

    def _parse_response(self, response: str) -> CompilerOutput:
        """Parse JSON from model response."""
        try:
            # Try to find JSON in response
            json_match = re.search(r'\{[^{}]*"reasoning"[^{}]*\}', response, re.DOTALL)
            if not json_match:
                # Try more permissive match
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
            
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(response.strip())
            
            # Clean code field
            code = data.get('code', '')
            data['code'] = self._clean_code(code)
            
            return CompilerOutput(**data)
        except (json.JSONDecodeError, Exception) as e:
            # Fallback: extract what we can
            return CompilerOutput(
                reasoning=f"Parse error: {e}",
                code="# Failed to parse model output\npass",
                filename="generated_script.py"
            )

    def generate_glue_code(self, retrieved_chunks: Union[List[str], List[Dict]], user_request: str) -> CompilerOutput:
        """
        Task ID: ASSEMBLER_01
        Logic:
          - Input: The validated chunks from Phase 2.
          - Task: Write 'Glue Code' to invoke these chunks in the correct order.
          - Constraint: Output must adhere to a strict JSON Schema.
          - Prohibition: No new business logic implementation allowed.
        """
        # Handle both old format (list of strings) and new format (list of dicts)
        if retrieved_chunks and isinstance(retrieved_chunks[0], str):
            # Legacy format - wrap in dict
            chunks = [{"source": c, "filename": "unknown", "func_name": "unknown"} for c in retrieved_chunks]
        else:
            chunks = retrieved_chunks if retrieved_chunks else []
        
        print(f"Assembler Prompting with {len(chunks)} chunks...")

        if self.model is not None and chunks:
            prompt = self._build_prompt(chunks, user_request)
            
            try:
                response = generate(
                    self.model,
                    self.tokenizer,
                    prompt=prompt,
                    max_tokens=512,
                    verbose=False
                )
                print(f"Model response received ({len(response)} chars)")
                return self._parse_response(response)
            except Exception as e:
                print(f"Generation error: {e}")
                return self._mock_response()
        else:
            return self._mock_response()

    def _mock_response(self) -> CompilerOutput:
        """Fallback mock response."""
        return CompilerOutput(
            reasoning="MOCK MODE: Model not available or no chunks provided.",
            code='''def main():
    print('This is generated glue code stub.')
    # Invoking chunks would go here''',
            filename="generated_script.py"
        )

if __name__ == "__main__":
    assembler = Assembler()
    mock_chunks = [
        {"source": "def foo():\n    return 'foo'", "filename": "utils", "func_name": "foo"},
        {"source": "def bar():\n    return 'bar'", "filename": "utils", "func_name": "bar"}
    ]
    output = assembler.generate_glue_code(mock_chunks, "Call foo then bar and print results")
    print("Assembler Output:")
    print(f"  Reasoning: {output.reasoning}")
    print(f"  Filename: {output.filename}")
    print(f"  Code:\n{output.code}")
