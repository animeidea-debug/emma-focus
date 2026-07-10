#!/bin/sh
# ==============================================================================
# 🧪 V2 测试脚本
#
# 验证新一代合并脚本，TEST_MODE=true
# 输出到 /mnt/export_videos_test/，不影响生产数据
#
# 用法：
#   单个摄像头：CAMERA=Study SOURCE=/mnt/source_study sh test_v2.sh
#   全部摄像头：sh test_v2.sh
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "============================================="
echo " 🧪 V2 测试开始 | $(date)"
echo "============================================="

echo ""
echo "⏳ 清理测试目录..."
docker exec tdarr_node sh -c 'rm -rf /mnt/export_videos_test 2>/dev/null; mkdir -p /mnt/export_videos_test' 2>&1
echo "✅ 测试目录已清理"
echo ""

export TEST_MODE=true

# ----- 如果指定了单摄像头，只测它 -----
if [ -n "$CAMERA" ] && [ -n "$SOURCE" ]; then
    echo "▶️ 测试【${CAMERA}】(单摄像头模式)..."
    CAMERA="$CAMERA" SOURCE="$SOURCE" sh "$SCRIPT_DIR/merge_v2.sh" && echo "  ✅ ${CAMERA} 通过" || echo "  ⚠️ ${CAMERA} 异常"
    echo ""
    echo "输出文件:"
    docker exec tdarr_node ls -lh /mnt/export_videos_test/ 2>/dev/null
    echo ""
    echo "============================================="
    echo " ✅ 测试完成！"
    echo "============================================="
    exit 0
fi

# ----- 批量测试所有摄像头（安装新摄像头后启用）-----
# echo "▶️ 测试【Study】..."
# CAMERA=Study SOURCE=/mnt/source_study sh "$SCRIPT_DIR/merge_v2.sh" && echo "  ✅ Study 通过" || echo "  ⚠️ Study 异常"

echo ""
echo "============================================="
echo " ✅ V2 测试完成！"
docker exec tdarr_node ls -lh /mnt/export_videos_test/ 2>/dev/null
echo "============================================="