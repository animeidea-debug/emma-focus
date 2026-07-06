#!/bin/sh
# ==============================================================================
# 🚀 Emma Focus — NAS 一键部署脚本 (WebDAV)
#
# 将本地 repo 中的脚本、HTML 和基础设施文件部署到极空间 NAS。
# 使用 rclone + WebDAV 协议，内网 IP 优先，外网 DDNS fallback。
# 脚本由 `sh xxx.sh` 调用，644 权限不影响运行。
#
# 目标路径（WebDAV 容器 clinedeploy-webdav）：
#   video merge/*      → /scripts/          (脚本)
#   index.html/admin   → /docker/html/      (nginx 静态页)
#   infra/web/*        → /docker/           (nginx + fastapi docker-compose)
#   infra/tdarr/*      → /tdarr/            (tdarr docker-compose)
#
# 用法：
#   sh deploy.sh
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

NAS_USER="garychen"
NAS_IP="192.168.6.108"
NAS_PORT="8889"
NAS_DDNS="https://zy12683em2039.vicp.fun"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "============================================="
echo " 🚀 Emma Focus — NAS 部署 (WebDAV)"
echo "============================================="

# ----- 1. 读取密码 -----
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

unset PASSWORD OBSCURED

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

# ----- 7. 完成 -----
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
