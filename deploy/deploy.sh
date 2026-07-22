#!/bin/sh
# ==============================================================================
# 🚀 Emma Focus — NAS 一键部署脚本 (WebDAV)
#
# 将本地 repo 中的脚本、HTML 和基础设施文件部署到极空间 NAS。
# 使用 rclone + WebDAV 协议，内网 IP 优先，外网 Tailscale Funnel 降级。
#
# 连接策略：
#   📍 内网环境（检测到 192.168.x.x）:
#      → 4 次重试 LAN WebDAV (指数退避 2s/4s/8s/16s)
#      → 不尝试 Tailscale（在家不需要）
#   🌐 外网环境:
#      → 3 次重试 Tailscale Funnel (指数退避 5s/10s/20s)
#      → 全部失败则报错退出
#
# 目标路径（WebDAV 容器 clinedeploy-rclone-webdav, serve webdav /data）：
#   video merge/*      → /scripts/          → host scripts/
#   index.html/admin   → /docker/html/      → host docker/html
#   ⚠️ Docker Compose 文件由 NAS 项目的 deploy/deploy.sh 管理
#      本脚本不涉及任何 docker-compose.yml 的同步
#
# 用法：
#   sh deploy.sh
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 加载 ~/.nas-env 本地共享配置（如果存在），不提交 git，所有项目共享
[ -f ~/.nas-env ] && . ~/.nas-env

# WebDAV 用户: 用 WEBDAV_USER（来自 ~/.nas-env），不是 NAS_USER
#   NAS_USER = NAS 系统账号 (13918962622) — 用于 SSH
#   WEBDAV_USER = WebDAV 认证账号 (garychen) — 用于 rclone
WEBDAV_USER="${WEBDAV_USER:-garychen}"
NAS_IP="${NAS_IP:-192.168.6.108}"
NAS_PORT="${NAS_WEBDAV_PORT:-8889}"
NAS_TAILSCALE="${TAILSCALE_FUNNEL:-https://z4pro-xxel.tail1a5bb9.ts.net/}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "============================================="
echo " 🚀 Emma Focus — NAS 部署 (WebDAV)"
echo "============================================="

# ----- 1. 读取 WebDAV 密码（跨平台）-----
# 优先级：当前终端环境变量 > macOS Keychain > 交互输入
# 环境变量优先可以绕过 Keychain ACL/授权弹窗异常；变量只需在当前终端临时设置。
PASSWORD=""

# 当前终端临时变量（Windows/Linux/macOS 通用）
if [ -n "$WEBDAV_PASS" ]; then
    PASSWORD="$WEBDAV_PASS"
fi

# macOS: 未提供环境变量时才从 Keychain 读取
if [ -z "$PASSWORD" ] && [ "$(uname)" = "Darwin" ]; then
    PASSWORD=$(security find-generic-password -s "emma-webdav" -a "garychen" -w 2>/dev/null)
fi

# 最后：交互式输入
if [ -z "$PASSWORD" ]; then
    echo -e "${YELLOW}⚠️ 请输入 WebDAV 密码（输入时不显示），然后按回车：${NC}"
    if [ -r /dev/tty ]; then
        stty -echo < /dev/tty
        IFS= read -r PASSWORD < /dev/tty
        stty echo < /dev/tty
    else
        IFS= read -r PASSWORD
    fi
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

# ----- 2. 配置 rclone remote（只创建一次）-----
echo -e "${YELLOW}⏳ 检查本地 rclone 配置...${NC}"
OBSCURED=$(rclone obscure "$PASSWORD")

# 只检查本地配置名称；不要在此阶段连接 NAS。
if ! rclone listremotes 2>/dev/null | grep -qx "emma-focus-webdav:"; then
    echo "  创建 emma-focus-webdav 配置"
    rclone config delete emma-focus-webdav 2>/dev/null || true
    rclone config create emma-focus-webdav webdav \
        url "http://${NAS_IP}:${NAS_PORT}" \
        vendor other user "$WEBDAV_USER" pass "$OBSCURED" > /dev/null 2>&1
else
    echo "  ✅ emma-focus-webdav 已存在"
fi

# Tailscale remote（独立，不共用）
if ! rclone listremotes 2>/dev/null | grep -qx "emma-focus-tailscale:"; then
    echo "  创建 emma-focus-tailscale 配置"
    rclone config delete emma-focus-tailscale 2>/dev/null || true
    rclone config create emma-focus-tailscale webdav \
        url "$NAS_TAILSCALE" \
        vendor other user "$WEBDAV_USER" pass "$OBSCURED" > /dev/null 2>&1
else
    echo "  ✅ emma-focus-tailscale 已存在"
fi

unset OBSCURED

# ----- 3. 重试辅助函数 -----
# 用法：retry_with_backoff <max_attempts> <initial_sleep> <command...>
# 返回：0=成功，1=全部失败
retry_with_backoff() {
    max_attempts=$1
    shift
    sleep_base=$1
    shift

    attempt=1
    while [ $attempt -le $max_attempts ]; do
        if "$@" 2>/dev/null; then
            return 0
        fi
        if [ $attempt -lt $max_attempts ]; then
            sleep_delay=$(( sleep_base * (1 << (attempt - 1)) ))
            [ $attempt -gt 1 ] && echo -e "${YELLOW}  ⏱  等待 ${sleep_delay}s 后重试（第 $((attempt+1))/${max_attempts} 次）...${NC}"
            sleep $sleep_delay
        fi
        attempt=$((attempt + 1))
    done
    return 1
}

# ----- 4. 检测网络环境并连接 -----
echo ""
echo -e "${YELLOW}⏳ 检测网络环境...${NC}"

IS_LAN=false
if ip addr 2>/dev/null | grep -q "inet 192\.168\." || \
   ifconfig 2>/dev/null | grep -q "inet 192\.168\." || \
   hostname -I 2>/dev/null | grep -q "192\.168\."; then
    IS_LAN=true
    echo -e "${GREEN}✅ 内网环境${NC}"
else
    echo -e "${YELLOW}🌐 外网环境${NC}"
fi

REMOTE=""
if [ "$IS_LAN" = true ]; then
    echo -e "${YELLOW}⏳ 连接 LAN WebDAV: http://${NAS_IP}:${NAS_PORT}...${NC}"
    if retry_with_backoff 4 2 sh -c "rclone lsd emma-focus-webdav: --timeout 5s 2>/dev/null | grep -q 'scripts\|docker\|tdarr'"; then
        REMOTE="emma-focus-webdav"
        echo -e "${GREEN}✅ 内网连接成功${NC}"
    else
        echo -e "${RED}❌ LAN WebDAV 连接失败（重试 4 次后放弃）${NC}"
        echo -e "${RED}   提示: 检查 NAS 是否开机、WebDAV 容器是否运行、网络是否正常${NC}"
        exit 1
    fi
else
    # 外网：重试 Tailscale Funnel
    echo -e "${YELLOW}⏳ 连接 Tailscale Funnel: ${NAS_TAILSCALE}...${NC}"
    if retry_with_backoff 3 5 sh -c "rclone lsd emma-focus-tailscale: --timeout 15s 2>/dev/null | grep -q 'scripts\|docker\|tdarr'"; then
        REMOTE="emma-focus-tailscale"
        echo -e "${GREEN}✅ Tailscale Funnel 连接成功${NC}"
    else
        echo -e "${RED}❌ 所有连接均失败。${NC}"
        exit 1
    fi
fi

unset PASSWORD

START_TS=$(date +%s)

# ----- 5. 同步 scripts -----
echo ""
echo -e "${YELLOW}📄 同步 scripts...${NC}"
if [ -d "${SCRIPT_DIR}/../video merge" ]; then
    # 同步脚本；remote .env 由 NAS 侧独立管理，常规应用部署不得读取、覆盖或删除。
    # notify.sh 与 .env 由 NAS 基础设施仓库统一管理，应用部署不得覆盖。
    rclone copy "${SCRIPT_DIR}/../video merge/" "${REMOTE}:/scripts/" --exclude ".env" --exclude "notify.sh" 2>&1 | grep -v "NOTICE" | tail -2 || true
    echo -e "${GREEN}✅ scripts 同步完成${NC}"
    # 真实备份 cron 从 /scripts/backup_data.sh 调用，显式同步包装器。
    rclone copy "${SCRIPT_DIR}/backup_data.sh" "${REMOTE}:/scripts/" 2>&1 | grep -v "NOTICE" || true
    # ⚠️ WebDAV 同步不保留 +x 权限（强制 644），通过 tdarr_node 容器（root）执行 chmod
    if command -v ssh >/dev/null 2>&1 && [ -f ~/.ssh/nas_ed25519 ] && [ "$(uname)" = "Darwin" ]; then
        retry_with_backoff 3 2 ssh -i ~/.ssh/nas_ed25519 -o StrictHostKeyChecking=no -o ConnectTimeout=5 \
            -p 10000 13918962622@192.168.6.108 \
            "docker exec tdarr_node chmod +x /app/scripts/*.sh" 2>/dev/null && \
        echo -e "${GREEN}✅ scripts 执行权限已设置（docker exec tdarr_node）${NC}" || \
        echo -e "${YELLOW}⚠️  无法通过 SSH 设置执行权限（忽略，可手动执行）${NC}"
    fi
fi

# ----- 6. 同步 HTML -----
echo ""
echo -e "${YELLOW}📄 同步 HTML...${NC}"
for f in index.html admin.html; do
    if [ -f "${SCRIPT_DIR}/../${f}" ]; then
        rclone copy "${SCRIPT_DIR}/../${f}" "${REMOTE}:/docker/html/" 2>&1 | grep -v "NOTICE" | tail -1 || true
        echo "  ✅ ${f}"
    fi
done

# PoC 测试页面
if [ -d "${SCRIPT_DIR}/../infra/web/html/poc" ]; then
    rclone sync "${SCRIPT_DIR}/../infra/web/html/poc/" "${REMOTE}:/docker/html/poc/" 2>&1 | grep -v "NOTICE" | tail -1 || true
    echo "  ✅ poc/"
fi

# ----- 6a. 同步本地 XLSX 备份文件（不进 git）-----
# Emma_Focus_DB.xlsx 是真实数据，不进 git，但应存到 NAS 宿主机
# 通过 WebDAV 同步到备份目录，贯彻"数据在外"原则
echo ""
echo -e "${YELLOW}📄 同步 XLSX 数据备份...${NC}"
XLSX_FILE="${SCRIPT_DIR}/../Emma_Focus_DB.xlsx"
if [ -f "$XLSX_FILE" ]; then
    rclone copy "$XLSX_FILE" "${REMOTE}:/backups/emma_data/" 2>&1 | grep -v "NOTICE" | tail -1 || true
    echo "  ✅ Emma_Focus_DB.xlsx → /data/backups/emma_data/"
else
    echo "  ⏭️  本地无 Emma_Focus_DB.xlsx，跳过"
fi

# ----- 6b. 同步后端 Python 文件 -----
echo ""
echo -e "${YELLOW}📄 同步后端...${NC}"
if [ -d "${SCRIPT_DIR}/../infra/web/backend" ]; then
    # /docker/backend is shared by Emma, TMOS and Family Time Flow. This must be
    # non-deleting copy: sync would erase sibling code and persistent data dirs.
    rclone copy "${SCRIPT_DIR}/../infra/web/backend/" "${REMOTE}:/docker/backend/" \
        --exclude "*.pyc" --exclude "__pycache__" --exclude ".gitkeep" \
        --exclude "data/" --exclude "data/poc.db" 2>&1 | grep -v "NOTICE" | tail -1 || true
    echo "  ✅ backend/ 非删除式上传（不会触碰 TMOS/FTF 目录）"
fi

# ----- 6c. 修复 HTML 文件权限（WebDAV 同步可能丢失 644）-----
echo ""
echo -e "${YELLOW}🔧 修复 HTML 文件权限...${NC}"
# 通过 SSH 连接到 NAS，用 docker exec 通过 WebDAV 容器（root）修复权限
if command -v ssh >/dev/null 2>&1 && [ -f ~/.ssh/nas_ed25519 ] && [ "$(uname)" = "Darwin" ]; then
    NAS_HOST="${NAS_IP}" NAS_PORT_SSH=10000
    retry_with_backoff 2 2 ssh -i ~/.ssh/nas_ed25519 -o StrictHostKeyChecking=no -o ConnectTimeout=5 \
        -p 10000 "13918962622@${NAS_IP}" \
        "docker exec clinedeploy-rclone-webdav chmod 644 /data/docker/html/*.html 2>/dev/null; echo '  ✅ HTML 权限已修复'" 2>/dev/null || \
    echo -e "  ⚠️  无法通过 SSH 修复权限，需手动执行：docker exec clinedeploy-rclone-webdav chmod 644 /data/docker/html/*.html"
else
    echo -e "  ⏭️  非 macOS 或 SSH 不可用，跳过"
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
if command -v curl >/dev/null 2>&1 && [ -f "${SCRIPT_DIR}/../video merge/notify.sh" ]; then
    . "${SCRIPT_DIR}/../video merge/notify.sh"
    COMMIT_MSG=$(cd "$SCRIPT_DIR/.." && git log -1 --oneline 2>/dev/null || echo "")
    pushover_notify "Emma Focus" "✅ NAS 部署完成 (${REMOTE})
${COMMIT_MSG}
耗时: ${ELAPSED}s" 2>/dev/null || true
fi
