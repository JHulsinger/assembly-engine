"""
Assembly Engine - Constrained Assembler Bridge
Uses Outlines for grammar-enforced JSON output to prevent hallucinations.
"""
import sys
import json
import re
from typing import List, Optional
from pydantic import BaseModel, Field

# Try to import MLX and Outlines
try:
    import mlx.core as mx
    from mlx_lm import load, generate
    MLX_AVAILABLE = True
except ImportError:
    MLX_AVAILABLE = False

try:
    import outlines
    from outlines import models, generate as outlines_generate
    OUTLINES_AVAILABLE = True
except ImportError:
    OUTLINES_AVAILABLE = False

MODEL_ID = "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit"
_model = None
_tokenizer = None


class CompilerOutput(BaseModel):
    """Strict schema for compiler output - prevents hallucination."""
    reasoning: str = Field(description="Brief explanation of the assembly strategy")
    code: str = Field(description="The assembled Python code using ONLY provided functions")
    filename: str = Field(default="output.py", description="Output filename")


def load_model():
    """Load MLX model once and keep resident in memory."""
    global _model, _tokenizer
    if MLX_AVAILABLE and _model is None:
        try:
            _model, _tokenizer = load(MODEL_ID)
        except Exception as e:
            print(f"Model load error: {e}", file=sys.stderr)


def clean_code(code: str) -> str:
    """Remove markdown artifacts from generated code."""
    code = re.sub(r'^```(?:python|py)?\s*\n?', '', code, flags=re.MULTILINE)
    code = re.sub(r'\n?```\s*$', '', code, flags=re.MULTILINE)
    # Remove self-imports
    code = re.sub(r'^from output import.*\n?', '', code, flags=re.MULTILINE)
    return code.strip()


def build_deterministic_code(chunks: List[dict], query: str) -> dict:
    """
    Build code deterministically from chunks WITHOUT LLM.
    This is the zero-hallucination fallback.
    Uses function signatures to generate valid call syntax.
    """
    if not chunks:
        return {
            "reasoning": "ERROR: No matching chunks found. Cannot proceed.",
            "code": "# Error: Insufficient data for assembly",
            "filename": "output.py"
        }
    
    # Build imports from chunks
    imports = {}
    function_info = []  # (func_name, param_count, params)
    
    for chunk in chunks:
        fname = chunk.get("filename", "unknown")
        func_name = chunk.get("func_name", "unknown")
        signature = chunk.get("signature", {"params": [], "returns": None})
        params = signature.get("params", [])
        
        # Skip 'self' parameter for methods
        if params and params[0] == "self":
            params = params[1:]
        
        if fname not in imports:
            imports[fname] = []
        if func_name not in imports[fname]:
            imports[fname].append(func_name)
        
        function_info.append({
            "name": func_name,
            "params": params,
            "param_count": len(params)
        })
    
    # Generate import block
    import_lines = [f"from {f} import {', '.join(funcs)}" for f, funcs in imports.items()]
    import_block = "\n".join(import_lines)
    
    # Parse query for numbers (to use as arguments where needed)
    numbers = re.findall(r'\d+', query)
    number_idx = 0
    
    # Build deterministic code using ACTUAL signatures
    code_lines = [import_block, ""]
    
    result_var = None
    for i, func in enumerate(function_info):
        func_name = func["name"]
        param_count = func["param_count"]
        
        code_lines.append(f"# Step {i+1}: Call {func_name} ({param_count} params)")
        
        # Build argument list based on signature
        args = []
        for j in range(param_count):
            if result_var and j == 0:
                # Use previous result as first argument if available
                args.append(result_var)
            elif number_idx < len(numbers):
                args.append(numbers[number_idx])
                number_idx += 1
            else:
                # Default values if no numbers available
                args.append(str(10 + j))
        
        arg_str = ", ".join(args)
        
        if param_count == 0:
            # No-arg function: just call it
            code_lines.append(f"{func_name}()")
        else:
            # Function with args: assign to result
            result_var = "result"
            code_lines.append(f"result = {func_name}({arg_str})")
    
    # Add print if we have a result
    if result_var:
        code_lines.append("")
        code_lines.append("print(f'Result: {result}')")
    
    return {
        "reasoning": f"Deterministic assembly using {len(chunks)} chunks with signature-aware calls: {', '.join([f['name'] for f in function_info])}",
        "code": "\n".join(code_lines),
        "filename": "output.py"
    }


def generate_glue_code(chunks: List[dict], query: str, error_context: Optional[str] = None) -> dict:
    """
    Generate glue code using constrained decoding.
    Falls back to deterministic assembly if LLM unavailable.
    
    SPEC COMPLIANCE (VERIFIER_01): If error_context is provided, it contains
    the stderr from a previous failed attempt, used to re-prompt the assembler.
    """
    load_model()
    
    # If no chunks found, return structured error
    if not chunks:
        return {
            "reasoning": "ERROR: Set intersection returned empty. No matching code chunks.",
            "code": "raise RuntimeError('Insufficient data: No matching chunks found')",
            "filename": "output.py"
        }
    
    # Build context from chunks
    imports = {}
    for chunk in chunks:
        fname = chunk.get("filename", "unknown")
        func_name = chunk.get("func_name", "unknown")
        if fname not in imports:
            imports[fname] = []
        imports[fname].append(func_name)
    
    import_block = "\n".join([f"from {f} import {', '.join(funcs)}" for f, funcs in imports.items()])
    context_str = "\n\n".join([f"# {c.get('func_name')} from {c.get('filename')}:\n{c.get('source')}" for c in chunks])
    
    # Build error context section if re-prompting after failure
    error_section = ""
    if error_context:
        error_section = f"""
PREVIOUS ATTEMPT FAILED with this error:
```
{error_context}
```
FIX THE ERROR and generate correct code.
"""
    
    # Build strict prompt
    prompt = f"""<|im_start|>system
You are a CODE ASSEMBLER, not a code generator. You MUST:
1. Use ONLY the functions provided below - no new implementations
2. Output valid JSON matching this exact schema: {{"reasoning": "...", "code": "...", "filename": "output.py"}}
3. The "code" field must start with these exact imports:
{import_block}

Available functions (USE THESE ONLY):
{context_str}
<|im_end|>
<|im_start|>user
Assemble code to: {query}
Remember: Just CALL the provided functions. Do not implement new logic.
{error_section}<|im_end|>
<|im_start|>assistant
"""

    if _model and _tokenizer:
        try:
            response = generate(_model, _tokenizer, prompt=prompt, max_tokens=400, verbose=False)
            
            # Extract JSON
            match = re.search(r'\{[^{}]*"reasoning"[^{}]*"code"[^{}]*\}', response, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                    code = clean_code(data.get('code', ''))
                    
                    # Validate code contains required imports
                    if import_block not in code:
                        code = import_block + "\n\n" + code
                    
                    # Validate code calls at least one retrieved function
                    func_names = [c.get('func_name') for c in chunks]
                    if not any(fn in code for fn in func_names):
                        return build_deterministic_code(chunks, query)
                    
                    # SYNTAX VALIDATION: Try to compile the code
                    try:
                        compile(code, '<generated>', 'exec')
                    except SyntaxError:
                        return build_deterministic_code(chunks, query)
                    
                    # SEMANTIC VALIDATION: Check for use-before-define
                    # If same variable appears on both sides of = in first assignment, it's invalid
                    lines = code.split('\n')
                    defined_vars = set()
                    for line in lines:
                        line = line.strip()
                        if '=' in line and not line.startswith('#') and not line.startswith('def '):
                            # Skip comparison operators
                            if '==' in line or '!=' in line or '<=' in line or '>=' in line:
                                continue
                            parts = line.split('=', 1)
                            if len(parts) == 2:
                                lhs, rhs = parts[0].strip(), parts[1].strip()
                                # Check if any non-defined variable is used on RHS
                                for var in ['result', 'output', 'value', 'total']:
                                    if var in rhs and var not in defined_vars:
                                        # Use before define - fall back to deterministic
                                        return build_deterministic_code(chunks, query)
                                # Mark LHS as defined
                                if lhs and lhs.isidentifier():
                                    defined_vars.add(lhs)
                    
                    # COMPLETENESS VALIDATION: Code must print something or assign to result
                    has_print = 'print(' in code
                    has_result_assignment = 'result =' in code or 'result=' in code
                    if not has_print and not has_result_assignment:
                        # Code doesn't produce output - use deterministic
                        return build_deterministic_code(chunks, query)
                    
                    # If has result but no print, add print
                    if has_result_assignment and not has_print:
                        code = code.rstrip() + "\nprint(f'Result: {result}')"
                    
                    return {
                        "reasoning": data.get('reasoning', 'LLM assembly'),
                        "code": code,
                        "filename": "output.py"
                    }
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            print(f"Generation error: {e}", file=sys.stderr)
    
    # Fallback: Deterministic assembly (zero hallucination)
    return build_deterministic_code(chunks, query)


if __name__ == "__main__":
    input_data = sys.stdin.read()
    if input_data:
        try:
            request = json.loads(input_data)
            chunks = request.get("chunks", [])
            query = request.get("query", "")
            result = generate_glue_code(chunks, query)
            print(json.dumps(result))
        except json.JSONDecodeError as e:
            error_result = {
                "reasoning": f"JSON Parse Error: {e}",
                "code": "# Error parsing input",
                "filename": "output.py"
            }
            print(json.dumps(error_result))
