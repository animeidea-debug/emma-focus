#!/bin/sh
# ==============================================================================
# 🧪 FPS 优化对比测试脚本
#
# 目的：验证两种 30 倍速延时策略的差异
#
# 方案 A（当前）：setpts=0.033333*PTS   + -r 20（全帧编码，时间戳压缩）
# 方案 B（优化）：select + setpts           + -r 20（每30帧取1帧，丢掉29/30）
#
# 输出到 /mnt/export_videos_test/fps_test/，不影响生产数据
#
# 测试数据：
#   1. 书房主机位（小米）：选 1 天数据，720P H.264 QSV
#   2. 客厅 4K：选 1 天数据，2160P H.265 QSV
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTDIR="/mnt/export_videos_test/fps_test"

echo ""
echo "=================================================="
echo " 🧪 FPS 优化对比测试"
echo "=================================================="
echo ""

# ----- 1. 清理并创建测试目录 -----
docker exec tdarr_node rm -rf "$OUTDIR"
docker exec tdarr_node mkdir -p "$OUTDIR"
echo "✅ 测试目录已清理"

# ----- 2. 准备测试数据 -----
echo ""
echo "📦 准备测试数据..."

# 小米：一次 find 取最早日期的文件
docker exec tdarr_node sh -c 'find /mnt/source_videos -type f -name "*.mp4" | sort > /tmp/xm_all.txt'
XIAOMI_DATE=$(docker exec tdarr_node sh -c 'grep -oE "2026[0-9]{4}" /tmp/xm_all.txt | cut -c1-8 | sort -u | head -1')
echo "小米测试日期: $XIAOMI_DATE"

docker exec tdarr_node sh -c "
    grep -E '${XIAOMI_DATE}(09|10|11|12|13|14|15|16|17|18|19|20|21|22)' /tmp/xm_all.txt | head -3 > /tmp/xm_day.txt
    > /tmp/xm_list.txt
    while read -r f; do
        ffprobe -v error -show_format \"\$f\" < /dev/null > /dev/null 2>&1 && echo \"file '\$f'\" >> /tmp/xm_list.txt
    done < /tmp/xm_day.txt
"
XM_FILES=$(docker exec tdarr_node sh -c 'wc -l < /tmp/xm_list.txt')
echo "   有效文件: ${XM_FILES}"
echo "   小米数据准备完成"

# 客厅
docker exec tdarr_node sh -c 'find /mnt/source_videos_livingroom -maxdepth 1 -type f -name "*.mp4" | sort > /tmp/lr_all.txt'
LR_DATE=$(docker exec tdarr_node sh -c 'grep -oE "2026[0-9]{4}" /tmp/lr_all.txt | sort -u | head -1')
echo "客厅测试日期: $LR_DATE"

docker exec tdarr_node sh -c "
    grep '${LR_DATE}' /tmp/lr_all.txt | head -3 > /tmp/lr_day.txt
    > /tmp/lr_list.txt
    while read -r f; do
        basename \"\$f\" | grep -qE '^[0-9]+_2026[0-9]{4}(0[9-9]|1[0-9]|2[0-2])[0-9]{4}_' && echo \"file '\$f'\" >> /tmp/lr_list.txt
    done < /tmp/lr_day.txt
"
LR_FILES=$(docker exec tdarr_node sh -c 'wc -l < /tmp/lr_list.txt')
echo "   有效文件: ${LR_FILES}"
echo "   客厅数据准备完成"
echo ""

# ----- 3. 测试：小米 -----
echo "=================================================="
echo " 📹 书房主机位（小米）720P H.264"
echo "=================================================="

echo ""
echo "⏳ 方案 A（setpts + -r 20）开始..."
START_A=$(date +%s)
docker exec tdarr_node ffmpeg -y -loglevel warning -nostats -f concat -safe 0 -i /tmp/xm_list.txt \
    -vf "scale=-2:720,format=nv12,setpts=0.033333*PTS" \
    -an -c:v h264_qsv -preset veryfast -r 20 \
    "$OUTDIR/xiaomi_a_setpts.mp4" < /dev/null 2>&1
END_A=$(date +%s)
ELAPSED_A=$((END_A - START_A))
echo "✅ 方案 A 完成，耗时: ${ELAPSED_A}s"

echo ""
echo "⏳ 方案 B（select + -r 20）开始..."
START_B=$(date +%s)
docker exec tdarr_node ffmpeg -y -loglevel warning -nostats -f concat -safe 0 -i /tmp/xm_list.txt \
    -vf "scale=-2:720,format=nv12,select=not(mod(n\,30)),setpts=N/20/TB" \
    -an -c:v h264_qsv -preset veryfast -r 20 \
    "$OUTDIR/xiaomi_b_select.mp4" < /dev/null 2>&1
END_B=$(date +%s)
ELAPSED_B=$((END_B - START_B))
echo "✅ 方案 B 完成，耗时: ${ELAPSED_B}s"

echo ""
echo "--- 小米对比 ---"
echo "┌─────────────────────────────────────────────────────────────┐"
docker exec tdarr_node sh -c '
    A=/mnt/export_videos_test/fps_test/xiaomi_a_setpts.mp4
    B=/mnt/export_videos_test/fps_test/xiaomi_b_select.mp4
    SA=$(ls -lh "$A" | awk "{print \$5}")
    SB=$(ls -lh "$B" | awk "{print \$5}")
    DA=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$A" 2>/dev/null)
    DB=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$B" 2>/dev/null)
    FA=$(ffprobe -v error -select_streams v -show_entries stream=r_frame_rate -of csv=p=0 "$A" 2>/dev/null)
    FB=$(ffprobe -v error -select_streams v -show_entries stream=r_frame_rate -of csv=p=0 "$B" 2>/dev/null)
    NA=$(ffprobe -v error -select_streams v -show_entries stream=nb_frames -of csv=p=0 "$A" 2>/dev/null)
    NB=$(ffprobe -v error -select_streams v -show_entries stream=nb_frames -of csv=p=0 "$B" 2>/dev/null)
    echo "│ 文件大小   │ 方案A(setpts) │ 方案B(select) │"
    echo "├───────────┼──────────────┼───────────────┤"
    printf "│ %-9s │ %-12s │ %-13s │\n" "大小" "$SA" "$SB"
    printf "│ %-9s │ %-12s │ %-13s │\n" "时长(秒)" "$DA" "$DB"
    printf "│ %-9s │ %-12s │ %-13s │\n" "帧率" "$FA" "$FB"
    printf "│ %-9s │ %-12s │ %-13s │\n" "帧数" "$NA" "$NB"
' 2>&1
echo "└───────────┴──────────────┴───────────────┘"

# ----- 4. 测试：客厅 -----
echo ""
echo "=================================================="
echo " 📹 客厅 4K H.265"
echo "=================================================="

echo ""
echo "⏳ 方案 A（setpts + -r 20）开始..."
START_LA=$(date +%s)
docker exec tdarr_node ffmpeg -y -loglevel warning -nostats -f concat -safe 0 -i /tmp/lr_list.txt \
    -vf "scale=-2:2160,format=nv12,setpts=0.033333*PTS" \
    -an -c:v hevc_qsv -preset veryfast -r 20 \
    "$OUTDIR/livingroom_a_setpts.mp4" < /dev/null 2>&1
END_LA=$(date +%s)
ELAPSED_LA=$((END_LA - START_LA))
echo "✅ 方案 A 完成，耗时: ${ELAPSED_LA}s"

echo ""
echo "⏳ 方案 B（select + -r 20）开始..."
START_LB=$(date +%s)
docker exec tdarr_node ffmpeg -y -loglevel warning -nostats -f concat -safe 0 -i /tmp/lr_list.txt \
    -vf "scale=-2:2160,format=nv12,select=not(mod(n\,30)),setpts=N/20/TB" \
    -an -c:v hevc_qsv -preset veryfast -r 20 \
    "$OUTDIR/livingroom_b_select.mp4" < /dev/null 2>&1
END_LB=$(date +%s)
ELAPSED_LB=$((END_LB - START_LB))
echo "✅ 方案 B 完成，耗时: ${ELAPSED_LB}s"

echo ""
echo "--- 客厅对比 ---"
echo "┌─────────────────────────────────────────────────────────────┐"
docker exec tdarr_node sh -c '
    A=/mnt/export_videos_test/fps_test/livingroom_a_setpts.mp4
    B=/mnt/export_videos_test/fps_test/livingroom_b_select.mp4
    SA=$(ls -lh "$A" | awk "{print \$5}")
    SB=$(ls -lh "$B" | awk "{print \$5}")
    DA=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$A" 2>/dev/null)
    DB=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$B" 2>/dev/null)
    FA=$(ffprobe -v error -select_streams v -show_entries stream=r_frame_rate -of csv=p=0 "$A" 2>/dev/null)
    FB=$(ffprobe -v error -select_streams v -show_entries stream=r_frame_rate -of csv=p=0 "$B" 2>/dev/null)
    NA=$(ffprobe -v error -select_streams v -show_entries stream=nb_frames -of csv=p=0 "$A" 2>/dev/null)
    NB=$(ffprobe -v error -select_streams v -show_entries stream=nb_frames -of csv=p=0 "$B" 2>/dev/null)
    echo "│ 文件大小   │ 方案A(setpts) │ 方案B(select) │"
    echo "├───────────┼──────────────┼───────────────┤"
    printf "│ %-9s │ %-12s │ %-13s │\n" "大小" "$SA" "$SB"
    printf "│ %-9s │ %-12s │ %-13s │\n" "时长(秒)" "$DA" "$DB"
    printf "│ %-9s │ %-12s │ %-13s │\n" "帧率" "$FA" "$FB"
    printf "│ %-9s │ %-12s │ %-13s │\n" "帧数" "$NA" "$NB"
' 2>&1
echo "└───────────┴──────────────┴───────────────┘"

# ----- 5. 总结果 -----
echo ""
echo "=================================================="
echo " 📊 总结"
echo "=================================================="
echo ""
echo "小米编码耗时:"
echo "  方案 A (setpts):  ${ELAPSED_A}s"
echo "  方案 B (select):  ${ELAPSED_B}s"
RATIO_XM=$(echo "scale=1; ${ELAPSED_A} / ${ELAPSED_B}" | bc 2>/dev/null)
echo "  提速比:           ${RATIO_XM}x"
echo ""
echo "客厅编码耗时:"
echo "  方案 A (setpts):  ${ELAPSED_LA}s"
echo "  方案 B (select):  ${ELAPSED_LB}s"
RATIO_LR=$(echo "scale=1; ${ELAPSED_LA} / ${ELAPSED_LB}" | bc 2>/dev/null)
echo "  提速比:           ${RATIO_LR}x"
echo ""
echo "输出文件列表:"
docker exec tdarr_node ls -lh "$OUTDIR/"
echo ""
echo "=================================================="
echo " ✅ 测试完成！"
echo "=================================================="