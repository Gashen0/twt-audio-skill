#!/usr/bin/env bash
# ===============================================================
# twt-audio-mcp — 一键安装脚本
# ===============================================================
# 用法:
#   bash setup.sh              # 安装依赖 + 创建目录
#   bash setup.sh --check      # 检查安装状态
#   bash setup.sh --cookie     # 引导配置 Twitter Cookie
# ===============================================================

set -e
cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)"
echo "📦 twt-audio-mcp"
echo "   项目目录: $PROJECT_DIR"
echo ""

# --- 解析参数 ---
if [ "$1" = "--check" ]; then
    echo "🔍 检查安装状态..."
    echo ""

    # Python
    if command -v python3 &>/dev/null; then
        echo "  ✅ Python: $(python3 --version)"
    else
        echo "  ❌ Python: 未安装"
        exit 1
    fi

    # 依赖
    for pkg in edge-tts requests mutagen pypinyin pyyaml; do
        if python3 -c "import $pkg" 2>/dev/null; then
            echo "  ✅ $pkg"
        else
            echo "  ❌ $pkg (pip install $pkg)"
        fi
    done

    # fastmcp
    if python3 -c "from fastmcp import FastMCP" 2>/dev/null; then
        echo "  ✅ fastmcp (MCP模式可用)"
    else
        echo "  ⚠  fastmcp (CLI模式可用，MCP模式需 pip install fastmcp)"
    fi

    # Cookie
    COOKIE_FILE="${PROJECT_DIR}/data/secrets/x_cookies.json"
    if [ -f "$COOKIE_FILE" ]; then
        echo "  ✅ Twitter Cookie: 已配置"
    else
        echo "  ❌ Twitter Cookie: 未配置"
        echo "     执行 bash setup.sh --cookie 引导配置"
    fi

    # 数据目录
    mkdir -p "${PROJECT_DIR}/data/twts" "${PROJECT_DIR}/data/secrets"
    echo "  ✅ 数据目录: 已就绪"
    echo ""
    echo "💡 如已全部通过，可将项目路径加入 MCP 客户端配置"
    exit 0
fi

if [ "$1" = "--cookie" ]; then
    COOKIE_FILE="${PROJECT_DIR}/data/secrets/x_cookies.json"
    echo "🍪 Twitter Cookie 配置"
    echo ""
    echo "请从浏览器 (chrome://settings/cookies) 或 EditThisCookie 扩展导出"
    echo "登录 x.com 后，在 DevTools > Application > Cookies > x.com 中获取以下三个值："
    echo ""
    echo "  1. auth_token  — 你的登录令牌"
    echo "  2. ct0         — CSRF Token"
    echo "  3. twid        — 用户ID"
    echo ""

    read -p "auth_token: " AUTH_TOKEN_VAL
    read -p "ct0: " CT0_VAL
    read -p "twid: " TWID_VAL

    mkdir -p "$(dirname "$COOKIE_FILE")"
    python3 -c "
import json, sys
data = {'auth_token': '${AUTH_TOKEN_VAL}', 'ct0': '${CT0_VAL}', 'twid': '${TWID_VAL}'}
with open('$COOKIE_FILE', 'w') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
"
    echo ""
    echo "✅ Cookie 已保存到: $COOKIE_FILE"
    echo ""
    echo "💡 测试一下: python scripts/twt_audio.py add https://x.com/elonmusk/status/123"
    exit 0
fi

# --- 安装 ---
echo "📥 安装 Python 依赖..."
echo ""

pip install -r requirements.txt -q 2>/dev/null || pip3 install -r requirements.txt -q 2>/dev/null
pip install fastmcp -q 2>/dev/null || pip3 install fastmcp -q 2>/dev/null

mkdir -p "${PROJECT_DIR}/data/twts" "${PROJECT_DIR}/data/secrets"

echo ""
echo "✅ 安装完成!"
echo ""
echo "下一步:"
echo "  1. 配置 Twitter Cookie:  bash setup.sh --cookie"
echo "  2. 配置 MCP 客户端（见 README.md）"
echo "  3. 测试: python scripts/twt_audio.py add https://x.com/用户/status/推文ID"
echo ""
echo "💡 使用 MCP 模式: python -m scripts.server"
