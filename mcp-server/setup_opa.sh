#!/bin/bash
set -e

# -------------------------------
# Detect platform
# -------------------------------
ARCH=$(uname -m)
if [[ "$ARCH" == "x86_64" ]]; then
    OPA_BINARY="opa_linux_amd64"
elif [[ "$ARCH" == "arm64" || "$ARCH" == "aarch64" ]]; then
    OPA_BINARY="opa_linux_arm64"
else
    echo "Unsupported architecture: $ARCH"
    exit 1
fi

# -------------------------------
# Detect project root path
# -------------------------------
if [ -d "./data/opa" ]; then
    OPA_SOURCE="./data/opa"
elif [ -d "../data/opa" ]; then
    OPA_SOURCE="../data/opa"
else
    echo "Could not find data/opa directory."
    exit 1
fi

# -------------------------------
# Determine if sudo is needed
# -------------------------------
NEED_SUDO=""
if [ "$EUID" -ne 0 ]; then
    # 현재 사용자가 root가 아니면 sudo 필요
    NEED_SUDO="sudo"
fi

# -------------------------------
# Install OPA binary
# -------------------------------
echo "Installing OPA binary for architecture: $ARCH"

$NEED_SUDO cp "$OPA_SOURCE/$OPA_BINARY" /usr/local/bin/opa
$NEED_SUDO chmod +x /usr/local/bin/opa

# -------------------------------
# Verify installation
# -------------------------------
if ! command -v opa >/dev/null 2>&1; then
    echo "OPA installation failed."
    exit 1
fi

echo "OPA installed successfully: $(opa version)"
