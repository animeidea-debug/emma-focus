#!/bin/sh
# ==============================================================================
# 🚀 Emma Focus — NAS 一键部署脚本
#
# 将本地 repo 中的脚本和 HTML 文件部署到极空间 NAS。
# 通过 SMB 连接，使用 macOS Keychain 中的凭证自动挂载。
#
# 目标路径：
#   scripts/ →  /Volumes/nvme14-139XXXX2622/scripts/
#   HTML     →  /Volumes/nvme14-139XXXX2622/docker/html/
#
# 用法：
#   sh deploy.sh             首次需先在 Finder 中连接 SMB 保存凭证
#   sh deploy.sh             以后自动从 Keychain 读取密码挂载
# ==============================================================================

set -e

NAS_SHARE="nvme14-139XXXX2622"
NAS_USER="13918962622"
NAS_HOST="192.168.6.108"
MOUNT_POINT="/Volumes/${NAS_SHARE}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo "============================================="
echo " 🚀 Emma Focus — NAS 部署"
echo "============================================="
echo ""

# ----- 1. 检查/挂载 SMB -----
if [ -d "$MOUNT_POINT" ]; then
    echo -e "${GREEN}✅ NAS 已挂载: ${MOUNT_POINT}${NC}"
else
    echo -e "${YELLOW}⏳ NAS 未挂载，正在从 Keychain 读取凭证...${NC}"

    # 从 macOS Keychain 读取密码
    PASSWORD=$(security find-internet-password -s "$NAS_HOST" -a "$NAS_USER" -w 2>/dev/null)

    if [ -z "$PASSWORD" ]; then
        echo -e "${RED}❌ Keychain 中未找到 SMB 凭证。${NC}"
        echo "   请先在 Finder 中连接一次 SMB 并勾选'记住密码'："
        echo "     open smb://${NAS_USER}@${NAS_HOST}/${NAS_SHARE}"
        echo ""
        exit 1
    fi

    echo -e "${YELLOW}⏳ 正在挂载 SMB: //${NAS_USER}@${NAS_HOST}/${NAS_SHARE}...${NC}"
    mkdir -p "$MOUNT_POINT"

    # 使用 mount_smbfs 挂载（需要密码）
    echo "$PASSWORD" | mount_smbfs -s "//${NAS_USER}:@${NAS_HOST}/${NAS_SHARE}" "$MOUNT_POINT" 2>/dev/null

    if [ $? -ne 0 ]; then
        # 如果 mount_smbfs 失败，尝试使用 Finder 风格的挂载
        echo -e "${RED}⚠️ mount_smbfs 失败，尝试 osascript 方式...${NC}"
        osascript -e "mount volume \"smb://${NAS_USER}:${PASSWORD}@${NAS_HOST}/${NAS_SHARE}\""
    fi

    if [ -d "$MOUNT_POINT" ]; then
        echo -e "${GREEN}✅ NAS 挂载成功: ${MOUNT_POINT}${NC}"
    else
        echo -e "${RED}❌ NAS 挂载失败，请手动在 Finder 中连接：${NC}"
        echo "   open smb://${NAS_USER}@${NAS_HOST}"
        exit 1
    fi
fi

# ----- 2. 部署 scripts -----
echo ""
echo -e "${YELLOW}📄 部署 scripts...${NC}"
if [ -d "${SCRIPT_DIR}/video merge" ]; then
    rsync -av --delete "${SCRIPT_DIR}/video merge/" "${MOUNT_POINT}/scripts/" 2>&1 | grep -v "^$" | tail -5
    echo -e "${GREEN}✅ scripts 部署完成${NC}"
else
    echo -e "${RED}❌ 本地 video merge/ 目录不存在${NC}"
fi

# ----- 3. 部署 HTML -----
echo ""
echo -e "${YELLOW}📄 部署 HTML...${NC}"
for f in index.html admin.html; do
    if [ -f "${SCRIPT_DIR}/${f}" ]; then
        rsync -av "${SCRIPT_DIR}/${f}" "${MOUNT_POINT}/docker/html/${f}" 2>&1 | tail -1
    else
        echo "  ⚠️ ${f} 不存在，跳过"
    fi
done
echo -e "${GREEN}✅ HTML 部署完成${NC}"

# ----- 4. 临时文件清理 -----
# 清理 deploy.sh 运行时可能遗留的任何敏感变量
unset PASSWORD

# ----- 5. 完成 -----
echo ""
echo "============================================="
echo -e "${GREEN}✅ NAS 部署完成！${NC}"
echo "   脚本: ${MOUNT_POINT}/scripts/"
echo "   HTML: ${MOUNT_POINT}/docker/html/"
echo "   时间: $(date +%Y-%m-%d\ %H:%M:%S)"
echo "============================================="

# 尝试发送 Pushover 通知（如果 curl 可用）
if command -v curl >/dev/null 2>&1 && [ -f "${SCRIPT_DIR}/video merge/notify.sh" ]; then
    . "${SCRIPT_DIR}/video merge/notify.sh"
    COMMIT_MSG=$(cd "$SCRIPT_DIR" && git log -1 --oneline 2>/dev/null || echo "")
    pushover_notify "Emma Focus" "✅ NAS 部署完成
最新提交: ${COMMIT_MSG}
脚本 + HTML 已同步到 NAS" 2>/dev/null || true
fi