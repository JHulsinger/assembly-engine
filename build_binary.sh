#!/bin/bash
echo "Building Assembly Engine Binary with MLX support..."

# Clean previous builds
rm -rf build dist
rm -f assembly-engine.spec

# PyInstaller Build Command with comprehensive MLX bundling
venv/bin/pyinstaller --noconfirm --onefile --console \
    --name "assembly-engine" \
    --collect-all mlx \
    --collect-all mlx_lm \
    --collect-all mlx.core \
    --collect-all tree_sitter \
    --collect-all tree_sitter_python \
    --collect-binaries mlx \
    --collect-binaries mlx_lm \
    --hidden-import="mlx" \
    --hidden-import="mlx.core" \
    --hidden-import="mlx.nn" \
    --hidden-import="mlx_lm" \
    --hidden-import="mlx_lm.models" \
    --hidden-import="mlx_lm.utils" \
    --hidden-import="tree_sitter" \
    --hidden-import="tree_sitter_python" \
    --hidden-import="pydantic" \
    --hidden-import="pydantic.fields" \
    --hidden-import="pydantic.main" \
    --hidden-import="rich" \
    --hidden-import="rich.console" \
    --hidden-import="rich.panel" \
    --hidden-import="rich.syntax" \
    --hidden-import="rich.markdown" \
    --hidden-import="rich.prompt" \
    --hidden-import="rich.spinner" \
    --hidden-import="rich.live" \
    --hidden-import="transformers" \
    --hidden-import="huggingface_hub" \
    --paths="src" \
    src/main.py

echo "Build complete. Binary is in dist/assembly-engine"
echo "Testing binary..."
./dist/assembly-engine <<< "exit"
