#!/bin/sh
# ==============================================================================
# 🚀 Emma Focus — GAS 一键部署脚本 (macOS/Linux)
#
# 将 GAS 后端代码推送到 Google Apps Script。
# 公司网络下请使用 deploy/run_gas_deploy.bat（含代理配置）。
# macOS 家庭网络可直接运行本脚本。
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

echo ""
echo "============================================="
echo " 🚀 Emma Focus — GAS 部署"
echo "============================================="

# 检测网络连接
if ! curl -s --max-time 5 https://script.google.com > /dev/null 2>&1; then
    echo "⚠️  无法访问 Google Apps Script（可能需要代理）"
    echo "   请使用 deploy/run_gas_deploy.bat（Windows 公司网络）"
    read -p "是否仍继续？(y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo "📤 推送代码到 Google Apps Script..."
clasp push 2>&1
if [ $? -ne 0 ]; then
    echo "❌ clasp push 失败"
    exit 1
fi

echo ""
echo "🏷️  创建版本标签..."
VERSION_DESC="deploy-$(date +%Y%m%d-%H%M)"
VERSION_OUTPUT=$(clasp version "$VERSION_DESC" 2>&1)
echo "$VERSION_OUTPUT"

# 提取版本号
VERSION_NUM=$(echo "$VERSION_OUTPUT" | grep -oE '[0-9]+' | head -1)
if [ -n "$VERSION_NUM" ]; then
    echo ""
    echo "🚀 部署版本 $VERSION_NUM..."
    clasp deploy --versionNumber "$VERSION_NUM" 2>&1
fi

echo ""
echo "============================================="
echo -e "\033[0;32m✅ GAS 部署完成！\033[0m"
echo "============================================="