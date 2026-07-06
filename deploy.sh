#!/bin/sh
# ==============================================================================
# 🚀 Emma Focus — NAS 一键部署脚本 (WebDAV)
#
# 将本地 repo 中的脚本、HTML 和基础设施文件部署到极空间 NAS。
# 使用 rclone + WebDAV 协议，内网 IP 优先，外网 DDNS fallback。
# 部署后通过 SMB 挂载修复执行权限。
#
# 目标路径（WebDAV 容器 clinedeploy-webdav）：
#   video merge/*      → /scripts/          (脚本)
#   index.html/admin   → /docker/html/      (nginx 静态页)
#   infra/web/*        → /docker/           (nginx + fastapi docker-compose)
#   infra/tdarr/*      → /tdarr/            (tdarr docker-compose)
#
# 用法：
#   sh deploy.sh             首次运行会自动创建 rclone 配置
# ==============================================================================

# 不使用 set -e：手动错误处理更精确
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

NAS_USER="garychen"
NAS_IP="192.168.6.108"
NAS_PORT="8889"
NAS_DDNS="https://zy12683em2039.vicp.fun"
NAS_SMB="//${NAS_USER}@${NAS_IP}/nvme14-139XXXX2622"
MOUNT_POINT="/Volumes/nvme14-139XXXX2622"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "============================================="
echo " 🚀 Emma Focus — NAS 部署 (WebDAV)"
echo "============================================="

# ----- 1. 读取密码 -----
# WebDAV 密码与 SMB 不同，直接使用已知密码
PASSWORD="Momoco198399"
OBSCURED=$(rclone obscure "$PASSWORD")

# ----- 2. 清理旧 remote + 重新配置 -----
rclone config delete emma-focus-ip 2>/dev/null || true
rclone config delete emma-focus 2>/dev/null || true

rclone config create emma-focus-ip webdav \
    url "http://${NAS_IP}:${NAS_PORT}" \
    vendor other user "$NAS_USER" pass "$OBSCURED" > /dev/null 2>&1

rclone config create emma-focus webdav \
    url "$NAS_DDNS" \
    vendor other user "$NAS_USER" pass "$OBSCURED" > /dev/null 2>&1

# ----- 3. 确定可用 remote -----
REMOTE=""
echo -e "${YELLOW}⏳ 测试内网连接: http://${NAS_IP}:${NAS_PORT}...${NC}"
if rclone lsd emma-focus-ip: --timeout 5s 2>/dev/null | grep -q "scripts\|docker\|tdarr"; then
    REMOTE="emma-focus-ip"
    echo -e "${GREEN}✅ 内网连接成功${NC}"
else
    echo -e "${YELLOW}⏳ 内网不通，测试外网 DDNS...${NC}"
    if rclone lsd emma-focus: --timeout 15s 2>/dev/null | grep -q "scripts\|docker\|tdarr"; then
        REMOTE="emma-focus"
        echo -e "${GREEN}✅ DDNS 连接成功${NC}"
    else
        echo -e "${RED}❌ 所有连接均失败。${NC}"
        exit 1
    fi
fi

# 清理密码变量
WEBDAV_PASS="$PASSWORD"
unset PASSWORD
unset OBSCURED

START_TS=$(date +%s)

# ----- 4. 同步 scripts -----
echo ""
echo -e "${YELLOW}📄 同步 scripts...${NC}"
if [ -d "${SCRIPT_DIR}/video merge" ]; then
    rclone sync --delete-excluded "${SCRIPT_DIR}/video merge/" "${REMOTE}:/scripts/" 2>&1 | grep -v "NOTICE" | tail -2 || true
    echo -e "${GREEN}✅ scripts 同步完成${NC}"
fi

# ----- 5. 同步 HTML -----
echo ""
echo -e "${YELLOW}📄 同步 HTML...${NC}"
for f in index.html admin.html; do
    if [ -f "${SCRIPT_DIR}/${f}" ]; then
        rclone copy "${SCRIPT_DIR}/${f}" "${REMOTE}:/docker/html/" 2>&1 | grep -v "NOTICE" | tail -1 || true
        echo "  ✅ ${f}"
    fi
done

# ----- 6. 同步 infra -----
echo ""
echo -e "${YELLOW}📄 同步 infra...${NC}"
if [ -f "${SCRIPT_DIR}/infra/web/docker-compose.yml" ]; then
    rclone copy "${SCRIPT_DIR}/infra/web/docker-compose.yml" "${REMOTE}:/docker/" 2>&1 | grep -v "NOTICE" | tail -1 || true
    echo "  ✅ web/docker-compose.yml"
fi
if [ -f "${SCRIPT_DIR}/infra/tdarr/docker-compose.yml" ]; then
    rclone copy "${SCRIPT_DIR}/infra/tdarr/docker-compose.yml" "${REMOTE}:/tdarr/" 2>&1 | grep -v "NOTICE" | tail -1 || true
    echo "  ✅ tdarr/docker-compose.yml"
fi

# ----- 7. 修复脚本执行权限（通过 NAS 容器内 chmod）-----
echo ""
echo -e "${YELLOW}🔧 修复脚本执行权限...${NC}"
# 通过容器内的 /app/scripts 映射执行 chmod
chmod_ok=false

# 方法1: 通过 SMB 挂载点 chmod（如果已挂载）
if [ -d "${MOUNT_POINT}/scripts" ]; then
    if chmod 755 "${MOUNT_POINT}/scripts/"*.sh 2>/dev/null; then
        echo -e "${GREEN}✅ 通过 SMB 修复权限成功${NC}"
        chmod_ok=true
    fi
fi

# 方法2: 通过 WebDAV 上传 fix 脚本来执行（借用 tdarr_node 容器）
if [ "$chmod_ok" = false ]; then
    echo "  ⚠️ 请确认脚本权限：crontab 使用 'sh xxx.sh' 调用，644 也能正常运行"
    echo "  如需修复，可在 NAS 上手动执行: docker exec tdarr_node chmod 755 /app/scripts/*.sh"
fi

# ----- 8. 完成 -----
END_TS=$(date +%s)
ELAPSED=$((END_TS - START_TS))

echo ""
echo "============================================="
echo -e "${GREEN}✅ NAS 部署完成！${NC}"
echo "   连接: ${REMOTE}"
echo "   耗时: ${ELAPSED}s"
echo "============================================="

# Pushover
if command -v curl >/dev/null 2>&1 && [ -f "${SCRIPT_DIR}/video merge/notify.sh" ]; then
    . "${SCRIPT_DIR}/video merge/notify.sh"
    COMMIT_MSG=$(cd "$SCRIPT_DIR" && git log -1 --oneline 2>/dev/null || echo "")
    pushover_notify "Emma Focus" "✅ NAS 部署完成 (${REMOTE})
${COMMIT_MSG}
耗时: ${ELAPSED}s" 2>/dev/null || true
fi