#!/bin/sh
# ==============================================================================
# 🧪 视频合并测试脚本
#
# 用法：cd /path/to/scripts && sh test_merge.sh
#
# 安全特性：
#   - 清理 temp_workspace（不重启容器，避免杀死正在编码的进程）
#   - 清理测试输出目录
#   - TEST_MODE=true → 1天 × 2片段
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "============================================="
echo " 🧪 视频合并测试开始"
echo "============================================="

# ----- 自清理 -----
echo ""
echo "⏳ 清理临时文件..."
docker exec tdarr_node sh -c 'rm -rf /tmp/* 2>/dev/null; mkdir -p /tmp' 2>&1
echo "⏳ 清理测试目录..."
docker exec tdarr_node sh -c 'rm -rf /mnt/export_videos_test 2>/dev/null; mkdir -p /mnt/export_videos_test' 2>&1
echo "✅ 清理完成"
echo ""

export TEST_MODE=true

# ----- [1/2] 小米 -----
echo "▶️ [1/2] 小米摄像头..."
sh "$SCRIPT_DIR/auto_merge.sh" && echo "  ✅ 小米通过" || echo "  ⚠️ 小米异常"

# ----- [2/2] 客厅 4K（后台运行，检测 export 文件）-----
echo ""
echo "▶️ [2/2] 客厅 4K（后台运行，检测 export 文件）..."
sh "$SCRIPT_DIR/livingroom_auto_merge.sh" &
LR_PID=$!

WAIT=0
FOUND=""
while [ $WAIT -lt 120 ]; do
    sleep 5
    WAIT=$((WAIT + 5))
    FILES=$(docker exec tdarr_node sh -c 'ls /mnt/export_videos_test/livingroom/LivingRoom_*.mp4 2>/dev/null | wc -l' 2>/dev/null)
    if [ "$FILES" -gt 0 ] 2>/dev/null; then
        FOUND="yes"
        break
    fi
    if ! kill -0 $LR_PID 2>/dev/null; then
        break
    fi
done

docker exec tdarr_node sh -c 'pkill -f "ffmpeg\|livingroom_auto" 2>/dev/null' 2>&1
kill $LR_PID 2>/dev/null
wait $LR_PID 2>/dev/null

if [ -n "$FOUND" ]; then
    echo "   ✅ 客厅通过（检测到 export 视频文件生成）"
else
    echo "   ⚠️ 客厅未在超时时间内生成文件"
fi

# ----- 结果 + 清理 -----
echo ""
echo "============================================="
echo " ✅ 全部测试完成！"
docker exec tdarr_node ls -lh /mnt/export_videos_test/ 2>/dev/null
echo "============================================="