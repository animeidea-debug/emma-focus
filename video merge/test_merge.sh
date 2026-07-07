#!/bin/sh
# ==============================================================================
# 🧪 视频合并测试脚本 — 快速验证所有合并脚本是否工作正常
#
# 在 NAS 宿主机上执行（不要 docker exec 进容器）：
#   cd /path/to/scripts && sh test_merge.sh
#
# 安全：TEST_MODE=true → 输出到 /mnt/export_videos_test/，不影响生产数据。
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

export TEST_MODE=true

echo ""
echo "============================================="
echo " 🧪 视频合并测试开始"
echo "============================================="
echo ""

# 测试 1：小米摄像头
echo "▶️ [1/3] 测试小米摄像头..."
sh "$SCRIPT_DIR/auto_merge.sh" && echo "  ✅ 小米测试完成" || echo "  ⚠️ 小米测试异常"

# 测试 2：萤石摄像头
echo ""
echo "▶️ [2/3] 测试萤石摄像头..."
sh "$SCRIPT_DIR/yingshi_auto_merge.sh" && echo "  ✅ 萤石测试完成" || echo "  ⚠️ 萤石测试异常"

# 测试 3：客厅 4K 摄像头
echo ""
echo "▶️ [3/3] 测试客厅 4K 摄像头..."
sh "$SCRIPT_DIR/livingroom_auto_merge.sh" && echo "  ✅ 客厅测试完成" || echo "  ⚠️ 客厅测试异常"

echo ""
echo "============================================="
echo " ✅ 全部测试完成！"
echo " 测试输出：/mnt/export_videos_test/"
echo "============================================="