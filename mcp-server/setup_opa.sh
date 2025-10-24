#!/bin/bash
set -e

# -------------------------------
# Detect platform (amd64 or arm64)
# -------------------------------
ARCH=$(uname -m)
if [[ "$ARCH" == "x86_64" ]]; then
    OPA_BINARY="opa_linux_amd64"
elif [[ "$ARCH" == "arm64" || "$ARCH" == "aarch64" ]]; then
    OPA_BINARY="opa_darwin_arm64"
else
    echo "Unsupported architecture: $ARCH"
    exit 1
fi

# -------------------------------
# Resolve project root path (relative-safe)
# -------------------------------
# find project root by searching for 'data/opa'
if [ -d "./data/opa" ]; then
    OPA_SOURCE="./data/opa"
elif [ -d "../data/opa" ]; then
    OPA_SOURCE="../data/opa"
else
    echo "Could not find data/opa directory."
    exit 1
fi

# -------------------------------
# Install OPA binary globally
# -------------------------------
echo "Installing OPA binary for architecture: $ARCH"

sudo cp "$OPA_SOURCE/$OPA_BINARY" /usr/local/bin/opa
sudo chmod +x /usr/local/bin/opa

# Verify installation
if ! command -v opa >/dev/null 2>&1; then
    echo "OPA installation failed."
    exit 1
fi

echo "OPA installed successfully: $(opa version)"
