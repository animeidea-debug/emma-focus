#!/bin/sh
# ==============================================================================
# 🧪 视频合并测试脚本 — 快速验证所有合并脚本是否工作正常
#
# 用法（在 NAS 宿主机上执行）：
#   cd /path/to/scripts && sh test_merge.sh
#
# 安全特性：
#   - 自动重启 tdarr_node 容器（杀死所有 ffmpeg 进程 + 清理临时文件）
#   - 自动清理测试输出目录 /mnt/export_videos_test/
#   - TEST_MODE=true → 每个脚本只处理 1 个日期各 2 个片段
#   - 输出到 /mnt/export_videos_test/，不影响生产数据
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "============================================="
echo " 🧪 视频合并测试开始"
echo "============================================="

# ----- 自清理：重启容器（杀进程 + 清 temp） -----
echo ""
echo "⏳ 重启 tdarr_node 容器..."
docker restart tdarr_node 2>&1
echo "⏳ 等待 10 秒让容器完全就绪..."
sleep 10

echo "⏳ 清理测试输出目录..."
docker exec tdarr_node sh -c 'rm -rf /mnt/export_videos_test 2>/dev/null; mkdir -p /mnt/export_videos_test' 2>&1
echo "✅ 清理完成"
echo ""

# ----- 设置测试模式 -----
export TEST_MODE=true

# ----- 运行测试 -----
echo "▶️ [1/3] 测试小米摄像头..."
sh "$SCRIPT_DIR/auto_merge.sh" && echo "  ✅ 小米测试完成" || echo "  ⚠️ 小米测试异常"

echo ""
echo "▶️ [2/3] 测试萤石摄像头..."
sh "$SCRIPT_DIR/yingshi_auto_merge.sh" && echo "  ✅ 萤石测试完成" || echo "  ⚠️ 萤石测试异常"

echo ""
echo "▶️ [3/3] 测试客厅 4K 摄像头..."
sh "$SCRIPT_DIR/livingroom_auto_merge.sh" && echo "  ✅ 客厅测试完成" || echo "  ⚠️ 客厅测试异常"

# ----- 结果汇总 -----
echo ""
echo "============================================="
echo " ✅ 全部测试完成！"
docker exec tdarr_node ls -lh /mnt/export_videos_test/ 2>/dev/null
echo "============================================="