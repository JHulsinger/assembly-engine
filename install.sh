#!/bin/bash
# Assembly Engine - Portable Install Script
# Creates a standalone package you can drop into any Python codebase

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="${1:-.assembly_engine}"

echo "Creating portable Assembly Engine package..."

mkdir -p "$INSTALL_DIR"

# Copy binary
cp "$SCRIPT_DIR/rust_compiler/target/release/rust_compiler" "$INSTALL_DIR/assembly-engine"

# Copy bridge script  
cp "$SCRIPT_DIR/src/assembler_bridge.py" "$INSTALL_DIR/assembler_bridge.py"

# Create launcher script
cat > "$INSTALL_DIR/run.sh" << 'EOF'
#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$(pwd)"  # Stay in current directory for indexing
"$DIR/assembly-engine"
EOF
chmod +x "$INSTALL_DIR/run.sh"

# Show what was created
echo ""
echo "✓ Created package in: $INSTALL_DIR/"
echo ""
echo "Contents:"
ls -la "$INSTALL_DIR/"
echo ""
echo "Usage:"
echo "  1. Copy the '$INSTALL_DIR' folder to any Python project"
echo "  2. Run: ./$INSTALL_DIR/run.sh"
echo "  3. It will index all .py files and start the TUI"
echo ""
echo "Requirements:"
echo "  - Python 3 with: pip install mlx-lm"
echo "  - Or just Python 3 (will use deterministic mode)"
