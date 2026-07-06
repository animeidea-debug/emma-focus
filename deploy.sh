#!/bin/sh
# ==============================================================================
# 🚀 Emma Focus — NAS 一键部署脚本
#
# 将本地 repo 中的脚本、HTML 和基础设施文件部署到极空间 NAS。
# 通过 SMB 连接，使用 macOS Keychain 中的凭证自动挂载。
#
# 目标路径（SMB 挂载点 /Volumes/nvme14-139XXXX2622/）：
#   video merge/*      → scripts/          (脚本)
#   index.html/admin   → docker/html/      (nginx 静态页)
#   infra/web/*        → docker/           (nginx + fastapi docker-compose)
#   infra/tdarr/*      → tdarr/            (tdarr docker-compose)
#
# 部署后自动修复权限（SMB 会重置权限为 600/700）：
#   *.sh  → 755 (rwxr-xr-x)
#   *.yml → 644 (rw-r--r--)
#   *.html→ 644 (rw-r--r--)
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
NC='\033[0m'

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

    PASSWORD=$(security find-internet-password -s "$NAS_HOST" -a "$NAS_USER" -w 2>/dev/null)

    if [ -z "$PASSWORD" ]; then
        echo -e "${RED}❌ Keychain 中未找到 SMB 凭证。${NC}"
        echo "   请先在 Finder 中连接一次 SMB 并勾选'记住密码'："
        echo "     open smb://${NAS_USER}@${NAS_HOST}/${NAS_SHARE}"
        echo ""
        exit 1
    fi

    echo -e "${YELLOW}⏳ 正在挂载 SMB...${NC}"
    mkdir -p "$MOUNT_POINT"
    echo "$PASSWORD" | mount_smbfs -s "//${NAS_USER}:@${NAS_HOST}/${NAS_SHARE}" "$MOUNT_POINT" 2>/dev/null || \
    osascript -e "mount volume \"smb://${NAS_USER}:${PASSWORD}@${NAS_HOST}/${NAS_SHARE}\"" 2>/dev/null || true

    if [ -d "$MOUNT_POINT" ]; then
        echo -e "${GREEN}✅ NAS 挂载成功${NC}"
    else
        echo -e "${RED}❌ 挂载失败，请手动连接: open smb://${NAS_USER}@${NAS_HOST}${NC}"
        exit 1
    fi
    unset PASSWORD
fi

# ----- 2. 同步 scripts（video merge/ → scripts/）-----
echo ""
echo -e "${YELLOW}📄 同步 scripts...${NC}"
if [ -d "${SCRIPT_DIR}/video merge" ]; then
    rsync -av --delete "${SCRIPT_DIR}/video merge/" "${MOUNT_POINT}/scripts/" 2>&1 | grep -v "^$" | grep -v "^\." | tail -3
    # 修复权限：脚本 755，配置文件 644
    chmod 755 "${MOUNT_POINT}/scripts/"*.sh 2>/dev/null || true
    chmod 644 "${MOUNT_POINT}/scripts/"*.json 2>/dev/null || true
    echo -e "${GREEN}✅ scripts 同步完成 (权限 755)${NC}"
else
    echo -e "${RED}❌ 本地 video merge/ 目录不存在${NC}"
fi

# ----- 3. 同步 HTML（→ docker/html/）-----
echo ""
echo -e "${YELLOW}📄 同步 HTML...${NC}"
for f in index.html admin.html; do
    if [ -f "${SCRIPT_DIR}/${f}" ]; then
        rsync -av "${SCRIPT_DIR}/${f}" "${MOUNT_POINT}/docker/html/${f}" 2>&1 | tail -1
        chmod 644 "${MOUNT_POINT}/docker/html/${f}"
    else
        echo "  ⚠️ ${f} 不存在，跳过"
    fi
done
echo -e "${GREEN}✅ HTML 同步完成 (权限 644)${NC}"

# ----- 4. 同步 infra 编排文件 -----
echo ""
echo -e "${YELLOW}📄 同步 infra 编排文件...${NC}"
if [ -f "${SCRIPT_DIR}/infra/web/docker-compose.yml" ]; then
    rsync -av "${SCRIPT_DIR}/infra/web/docker-compose.yml" "${MOUNT_POINT}/docker/docker-compose.yml" 2>&1 | tail -1
    chmod 644 "${MOUNT_POINT}/docker/docker-compose.yml"
    echo "  ✅ web/docker-compose.yml"
fi
if [ -f "${SCRIPT_DIR}/infra/tdarr/docker-compose.yml" ]; then
    rsync -av "${SCRIPT_DIR}/infra/tdarr/docker-compose.yml" "${MOUNT_POINT}/tdarr/docker-compose.yml" 2>&1 | tail -1
    chmod 644 "${MOUNT_POINT}/tdarr/docker-compose.yml"
    echo "  ✅ tdarr/docker-compose.yml"
fi

# ----- 5. 完成 -----
echo ""
echo "============================================="
echo -e "${GREEN}✅ NAS 部署完成！${NC}"
echo "   脚本:  ${MOUNT_POINT}/scripts/"
echo "   HTML:  ${MOUNT_POINT}/docker/html/"
echo "   infra: ${MOUNT_POINT}/docker/ + /tdarr/"
echo "   时间:  $(date +%Y-%m-%d\ %H:%M:%S)"
echo "============================================="

# Pushover 通知
if command -v curl >/dev/null 2>&1 && [ -f "${SCRIPT_DIR}/video merge/notify.sh" ]; then
    . "${SCRIPT_DIR}/video merge/notify.sh"
    COMMIT_MSG=$(cd "$SCRIPT_DIR" && git log -1 --oneline 2>/dev/null || echo "")
    pushover_notify "Emma Focus" "✅ NAS 部署完成
最新提交: ${COMMIT_MSG}
脚本 + HTML + infra 已同步到 NAS" 2>/dev/null || true
fi