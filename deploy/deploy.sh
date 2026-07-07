#!/bin/sh
# ==============================================================================
# 🚀 Emma Focus — NAS 一键部署脚本 (WebDAV)
#
# 将本地 repo 中的脚本、HTML 和基础设施文件部署到极空间 NAS。
# 使用 rclone + WebDAV 协议，内网 IP 优先，外网 Tailscale Funnel fallback。
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
NAS_TAILSCALE="https://z4pro-xxel.tail1a5bb9.ts.net/"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "============================================="
echo " 🚀 Emma Focus — NAS 部署 (WebDAV)"
echo "============================================="

# ----- 1. 读取 WebDAV 密码（跨平台）-----
# 优先级：macOS Keychain > 环境变量 > 交互输入
PASSWORD=""

# macOS: 从 Keychain 读取
if [ "$(uname)" = "Darwin" ]; then
    PASSWORD=$(security find-generic-password -s "emma-webdav" -a "garychen" -w 2>/dev/null)
fi

# 后备：从环境变量读取（Windows/Linux/macOS 通用）
if [ -z "$PASSWORD" ] && [ -n "$WEBDAV_PASS" ]; then
    PASSWORD="$WEBDAV_PASS"
fi

# 最后：交互式输入
if [ -z "$PASSWORD" ]; then
    echo -e "${YELLOW}⚠️ 请输入 WebDAV 密码（输入时不显示）：${NC}"
    read -s PASSWORD
    echo ""
fi

if [ -z "$PASSWORD" ]; then
    echo -e "${RED}❌ 未提供 WebDAV 密码。${NC}"
    echo "   macOS: security add-generic-password -s \"emma-webdav\" -a \"garychen\" -w \"密码\""
    echo "   Windows/macOS: export WEBDAV_PASS=\"密码\""
    exit 1
fi
# Strip trailing newline/carriage return (Windows env var issue)
PASSWORD=$(echo "$PASSWORD" | tr -d '\r\n')

# ----- 2. 检测网络环境（LAN vs 外网）-----
IS_LAN=false
if ip addr 2>/dev/null | grep -q "inet 192\.168\." || \
   ifconfig 2>/dev/null | grep -q "inet 192\.168\." || \
   hostname -I 2>/dev/null | grep -q "192\.168\."; then
    IS_LAN=true
fi

# ----- 3. 配置 rclone remotes -----
OBSCURED=$(rclone obscure "$PASSWORD")
rclone config delete emma-focus-ip 2>/dev/null || true
rclone config delete emma-focus-ts 2>/dev/null || true

rclone config create emma-focus-ip webdav \
    url "http://${NAS_IP}:${NAS_PORT}" \
    vendor other user "$NAS_USER" pass "$OBSCURED" > /dev/null 2>&1

rclone config create emma-focus-ts webdav \
    url "$NAS_TAILSCALE" \
    vendor other user "$NAS_USER" pass "$OBSCURED" > /dev/null 2>&1

unset OBSCURED

# ----- 4. 确定可用 remote（LAN > Tailscale）-----
REMOTE=""
if [ "$IS_LAN" = true ]; then
    echo -e "${YELLOW}⏳ 检测到内网环境，测试 LAN: http://${NAS_IP}:${NAS_PORT}...${NC}"
    if rclone lsd emma-focus-ip: --timeout 3s 2>/dev/null | grep -q "scripts\|docker\|tdarr"; then
        REMOTE="emma-focus-ip"
        echo -e "${GREEN}✅ 内网连接成功${NC}"
    else
        echo -e "${YELLOW}⚠️  LAN 不通，尝试 Tailscale Funnel...${NC}"
    fi
fi

if [ -z "$REMOTE" ]; then
    echo -e "${YELLOW}⏳ 测试 Tailscale Funnel: ${NAS_TAILSCALE}...${NC}"
    if rclone lsd emma-focus-ts: --timeout 15s 2>/dev/null | grep -q "scripts\|docker\|tdarr"; then
        REMOTE="emma-focus-ts"
        echo -e "${GREEN}✅ Tailscale Funnel 连接成功${NC}"
    fi
fi

if [ -z "$REMOTE" ]; then
    echo -e "${RED}❌ 所有连接均失败（LAN + Tailscale）。${NC}"
    exit 1
fi

unset PASSWORD

START_TS=$(date +%s)

# ----- 4. 同步 scripts -----
echo ""
echo -e "${YELLOW}📄 同步 scripts...${NC}"
if [ -d "${SCRIPT_DIR}/../../video merge" ]; then
    rclone sync --delete-excluded "${SCRIPT_DIR}/../../video merge/" "${REMOTE}:/scripts/" --exclude ".env" 2>&1 | grep -v "NOTICE" | tail -2 || true
    echo -e "${GREEN}✅ scripts 同步完成${NC}"
fi

# ----- 5. 同步 HTML -----
echo ""
echo -e "${YELLOW}📄 同步 HTML...${NC}"
for f in index.html admin.html; do
    if [ -f "${SCRIPT_DIR}/../${f}" ]; then
        rclone copy "${SCRIPT_DIR}/../${f}" "${REMOTE}:/docker/html/" 2>&1 | grep -v "NOTICE" | tail -1 || true
        echo "  ✅ ${f}"
    fi
done

# ----- 6. 同步 infra -----
echo ""
echo -e "${YELLOW}📄 同步 infra...${NC}"
if [ -f "${SCRIPT_DIR}/../../infra/web/docker-compose.yml" ]; then
    rclone copy "${SCRIPT_DIR}/../../infra/web/docker-compose.yml" "${REMOTE}:/docker/" 2>&1 | grep -v "NOTICE" | tail -1 || true
    echo "  ✅ web/docker-compose.yml"
fi
if [ -f "${SCRIPT_DIR}/../../infra/tdarr/docker-compose.yml" ]; then
    rclone copy "${SCRIPT_DIR}/../../infra/tdarr/docker-compose.yml" "${REMOTE}:/tdarr/" 2>&1 | grep -v "NOTICE" | tail -1 || true
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
if command -v curl >/dev/null 2>&1 && [ -f "${SCRIPT_DIR}/../../video merge/notify.sh" ]; then
    . "${SCRIPT_DIR}/../../video merge/notify.sh"
    COMMIT_MSG=$(cd "$SCRIPT_DIR/.." && git log -1 --oneline 2>/dev/null || echo "")
    pushover_notify "Emma Focus" "✅ NAS 部署完成 (${REMOTE})
${COMMIT_MSG}
耗时: ${ELAPSED}s" 2>/dev/null || true
fi