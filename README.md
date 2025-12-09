# Assembly Engine

A RAG-based code compiler that uses **deterministic assembly** instead of probabilistic generation. It guarantees **zero hallucination** by only generating code using functions that actually exist in your codebase.

## Features

- 🔍 **Auto-indexes** your Python codebase
- 🧠 **Understands** function signatures (parameters, return types)
- 🔒 **Zero Hallucination** - only uses existing functions
- ⚡ **MLX-optimized** for Apple Silicon (with fallback for any Python)
- 🖥️ **Interactive TUI** built with Ratatui

## Quick Start

```bash
# 1. Clone this repo
git clone https://github.com/YOUR_USERNAME/assembly-engine.git
cd assembly-engine

# 2. Build the Rust binary
cd rust_compiler && cargo build --release && cd ..

# 3. Install Python dependencies (optional, for LLM mode)
pip install mlx-lm

# 4. Run it!
./rust_compiler/target/release/rust_compiler
```

## Usage

1. Drop the binary in any Python project folder
2. Run it - it will auto-index all `.py` files
3. Query using function names: `rocket_add 100 50`
4. Generated code uses only existing functions

## How It Works

```
User Query → Retrieval (Set Intersection) → Assembly → Verified Code
                    ↓                            ↓
             Only matches if              Uses actual function
             function EXISTS              signatures
```

## Project Structure

```
├── rust_compiler/        # Rust TUI binary
│   └── src/
│       ├── main.rs       # TUI application
│       ├── indexer.rs    # AST-based code indexer
│       ├── retriever.rs  # Set intersection search
│       └── assembler.rs  # MLX bridge
├── src/
│   ├── assembler_bridge.py  # Python MLX integration
│   ├── indexer.py           # Python indexer
│   └── retriever.py         # Python retriever
└── emoji_lib.py             # Example library
```

## Requirements

- **Rust** (for building)
- **Python 3.8+**
- **Optional**: `mlx-lm` for LLM-powered assembly (Apple Silicon only)

## License

MIT
