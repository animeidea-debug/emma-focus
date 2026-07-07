#!/bin/sh

# ==============================================================================
# 🚀 极空间监控合并总控脚本：串行排队执行 (先小米，后萤石)
#
# 部署路径：将整个 video-merge 目录拷贝到 NAS 的脚本目录，
#           如 /tmp/zfsv3/nvme14/13918962622/data/scripts/
# 定时触发：crontab 每日 22:00
#           $ crontab -e
#           0 22 * * * cd /path/to/scripts && sh run_all.sh >> /var/log/video_merge.log 2>&1
#
# 可配置环境变量：
#   XIAOMI_RES     — 小米输出分辨率 (默认 720)
#   YINGSHI_RES    — 萤石输出分辨率 (默认 1080)
#   MAX_LOG_SIZE   — 日志轮转阈值 bytes (默认 10485760 = 10MB)
# ==============================================================================

# 自动获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 引入通知辅助
. "$SCRIPT_DIR/notify.sh"

# 启动通知
pushover_notify "Video Merge" "🚀 监控视频合并开始 | $(date +%Y-%m-%d\ %H:%M)
设备: 小米(${XIAOMI_RES:-720}P) + 萤石(${YINGSHI_RES:-1080}P)"

START_TS=$(date +%s)

echo "================================================="
echo " 🚀 开始执行监控视频自动合并任务 | $(date)"
echo "================================================="

# 记录当前日期，用于通知
TODAY=$(date +%Y%m%d)

# 第一步：小米（720P）任务
echo ""
echo "▶️ [1/3] 正在启动【小米】合并任务..."
sh "$SCRIPT_DIR/auto_merge.sh"
XIAOMI_EXIT=$?

# 读取小米结果
XIAOMI_SUCCESS=0
XIAOMI_FAIL=0
XIAOMI_TOTAL=0
if [ -f /tmp/xiaomi_result.json ]; then
    eval "$(cat /tmp/xiaomi_result.json | sed 's/[{}]/ /g; s/"//g; s/,/ /g' | awk '{for(i=1;i<=NF;i++){if($i ~ /success/) {getline; XIAOMI_SUCCESS=$i} if($i ~ /fail/) {getline; XIAOMI_FAIL=$i} if($i ~ /total/) {getline; XIAOMI_TOTAL=$i}} print "XIAOMI_SUCCESS="XIAOMI_SUCCESS"; XIAOMI_FAIL="XIAOMI_FAIL"; XIAOMI_TOTAL="XIAOMI_TOTAL}')"
    rm -f /tmp/xiaomi_result.json
fi

if [ $XIAOMI_EXIT -ne 0 ]; then
    pushover_notify "Video Merge" "⚠️ 小米合并异常 | ${TODAY}
成功: ${XIAOMI_SUCCESS} 天 | 失败: ${XIAOMI_FAIL} 天
脚本退出码: ${XIAOMI_EXIT}"
    echo "⚠️ 小米任务返回非零状态 ($XIAOMI_EXIT)，继续执行萤石任务..."
else
    pushover_notify "Video Merge" "✅ 小米合并完成 | ${TODAY}
成功: ${XIAOMI_SUCCESS} 天 | 失败: ${XIAOMI_FAIL} 天"
fi

# 第二步：萤石（1080P）任务
echo ""
echo "▶️ [2/3] 正在启动【萤石】合并任务..."
sh "$SCRIPT_DIR/yingshi_auto_merge.sh"
YINGSHI_EXIT=$?

# 读取萤石结果
YINGSHI_SUCCESS=0
YINGSHI_FAIL=0
YINGSHI_TOTAL=0
if [ -f /tmp/yingshi_result.json ]; then
    eval "$(cat /tmp/yingshi_result.json | sed 's/[{}]/ /g; s/"//g; s/,/ /g' | awk '{for(i=1;i<=NF;i++){if($i ~ /success/) {getline; YINGSHI_SUCCESS=$i} if($i ~ /fail/) {getline; YINGSHI_FAIL=$i} if($i ~ /total/) {getline; YINGSHI_TOTAL=$i}} print "YINGSHI_SUCCESS="YINGSHI_SUCCESS"; YINGSHI_FAIL="YINGSHI_FAIL"; YINGSHI_TOTAL="YINGSHI_TOTAL}')"
    rm -f /tmp/yingshi_result.json
fi

if [ $YINGSHI_EXIT -ne 0 ]; then
    pushover_notify "Video Merge" "⚠️ 萤石合并异常 | ${TODAY}
成功: ${YINGSHI_SUCCESS} 天 | 失败: ${YINGSHI_FAIL} 天
脚本退出码: ${YINGSHI_EXIT}"
else
    pushover_notify "Video Merge" "✅ 萤石合并完成 | ${TODAY}
成功: ${YINGSHI_SUCCESS} 天 | 失败: ${YINGSHI_FAIL} 天"
fi

# 第三步：客厅 4K（低优先级，需要容器新卷映射生效后启动）
echo ""
echo "▶️ [3/3] 正在启动【客厅 4K】合并任务..."
sh "$SCRIPT_DIR/livingroom_auto_merge.sh"
LIVINGROOM_EXIT=$?

# 读取客厅结果
LR_SUCCESS=0
LR_FAIL=0
if [ -f /tmp/livingroom_result.json ]; then
    eval "$(cat /tmp/livingroom_result.json | sed 's/[{}]/ /g; s/"//g; s/,/ /g' | awk '{for(i=1;i<=NF;i++){if($i ~ /success/) {getline; LR_SUCCESS=$i} if($i ~ /fail/) {getline; LR_FAIL=$i}} print "LR_SUCCESS="LR_SUCCESS"; LR_FAIL="LR_FAIL}')"
    rm -f /tmp/livingroom_result.json
fi

if [ $LIVINGROOM_EXIT -ne 0 ]; then
    pushover_notify "Video Merge" "⚠️ 客厅 4K 合并异常 | ${TODAY}
成功: ${LR_SUCCESS} 天 | 失败: ${LR_FAIL} 天
脚本退出码: ${LIVINGROOM_EXIT}"
else
    pushover_notify "Video Merge" "✅ 客厅 4K 合并完成 | ${TODAY}
成功: ${LR_SUCCESS} 天 | 失败: ${LR_FAIL} 天"
fi

# 总计
END_TS=$(date +%s)
ELAPSED_MIN=$(( (END_TS - START_TS) / 60 ))
ELAPSED_SEC=$(( (END_TS - START_TS) % 60 ))

TOTAL_SUCCESS=$(( XIAOMI_SUCCESS + YINGSHI_SUCCESS + LR_SUCCESS ))
TOTAL_FAIL=$(( XIAOMI_FAIL + YINGSHI_FAIL + LR_FAIL ))

pushover_notify "Video Merge" "🎉 全部完成 | ${TODAY}
小米: ${XIAOMI_SUCCESS}✅ ${XIAOMI_FAIL}❌
萤石: ${YINGSHI_SUCCESS}✅ ${YINGSHI_FAIL}❌
客厅: ${LR_SUCCESS}✅ ${LR_FAIL}❌
总计: ${TOTAL_SUCCESS}✅ ${TOTAL_FAIL}❌
耗时: ${ELAPSED_MIN}分${ELAPSED_SEC}秒"

echo ""
echo "✅ 所有监控视频延时处理全部完毕！"
echo "🎉 结束时间: $(date) | 总耗时: ${ELAPSED_MIN}m${ELAPSED_SEC}s"
echo "📊 小米: 成功 ${XIAOMI_SUCCESS} / 失败 ${XIAOMI_FAIL}"
echo "📊 萤石: 成功 ${YINGSHI_SUCCESS} / 失败 ${YINGSHI_FAIL}"
echo "📊 客厅: 成功 ${LR_SUCCESS} / 失败 ${LR_FAIL}"
echo "================================================="
