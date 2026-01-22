#!/bin/bash

# ---------------------------------------------------------
# 🧰 AI Toolbox Migration Script
# usage: ./install_all.sh
# ---------------------------------------------------------

# The directory where this script is running (e.g. ~/ai/tools)
TOOLS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BIN_DIR="/usr/local/bin"

echo "🚀 Starting AI Tools Setup..."
echo "📂 Source: $TOOLS_DIR"

# Function to setup a generic Python tool
setup_python_tool() {
    TOOL_NAME=$1
    echo "------------------------------------------------"
    echo "🔧 Setting up: $TOOL_NAME"
    
    TOOL_PATH="$TOOLS_DIR/$TOOL_NAME"
    
    # 1. Check if tool source exists
    if [ ! -d "$TOOL_PATH" ]; then
        echo "⚠️  Skipping $TOOL_NAME (Folder not found)"
        return
    fi

    # 2. Setup Virtual Environment (Rebuilds it for the new OS)
    if [ -d "$TOOL_PATH/venv" ]; then
        echo "   - Cleaning old venv..."
        rm -rf "$TOOL_PATH/venv"
    fi
    
    echo "   - Creating fresh venv..."
    python3 -m venv "$TOOL_PATH/venv"
    
    # 3. Install Dependencies
    if [ -f "$TOOL_PATH/requirements.txt" ]; then
        echo "   - Installing dependencies (this may take a moment)..."
        "$TOOL_PATH/venv/bin/pip" install -r "$TOOL_PATH/requirements.txt" --quiet
    else
        echo "   ⚠️  No requirements.txt found!"
    fi
    
    # 4. Fix Shebang (The Secret Sauce for Portability)
    # This replaces the first line of main.py to point to the LOCAL venv
    ENTRY_POINT="$TOOL_PATH/main.py"
    if [ -f "$ENTRY_POINT" ]; then
        echo "   - Patching shebang in main.py..."
        # Regex to replace the first line with the correct venv python path
        sed -i "1s|.*|#!$TOOL_PATH/venv/bin/python|" "$ENTRY_POINT"
        chmod +x "$ENTRY_POINT"
        
        # 5. Global Link
        echo "   - Linking '$TOOL_NAME' to $BIN_DIR..."
        # We use sudo here because /usr/local/bin requires it
        sudo ln -sf "$ENTRY_POINT" "$BIN_DIR/$TOOL_NAME"
    fi
    
    echo "✅ $TOOL_NAME ready."
}

# --- REGISTER YOUR TOOLS HERE ---
setup_python_tool "hugin"
# setup_python_tool "aicap" 
# setup_python_tool "ostris"

echo "------------------------------------------------"
echo "🎉 Toolbox setup complete!"