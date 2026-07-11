#!/bin/sh
# ==============================================================================
# 🧪 硬件加速 (VPP/scale_qsv) 对比测试
#
# 方案 A（当前）：无 -hwaccel qsv + scale(NV12) + setpts
# 方案 C（全硬件）：-hwaccel qsv + vpp_qsv + setpts
# 方案 D（半硬件）：-hwaccel qsv + scale_qsv + setpts
#
# 输出到 /mnt/export_videos_test/hwbench/，不影响生产数据
# 只测客厅 4K（最耗时的部分，最能体现差距）
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTDIR="/mnt/export_videos_test/hwbench"

echo ""
echo "===================================================="
echo " 🧪 硬件加速 (VPP/scale_qsv) 对比测试"
echo "===================================================="
echo ""

# ----- 1. 清理并创建测试目录 -----
docker exec tdarr_node rm -rf "$OUTDIR"
docker exec tdarr_node mkdir -p "$OUTDIR"
echo "✅ 测试目录已清理"

# ----- 2. 准备测试数据（只客厅 4K）-----
echo ""
echo "📦 准备测试数据（客厅 4K 3 片段）..."

docker exec tdarr_node sh -c 'find /mnt/source_videos_livingroom -maxdepth 1 -type f -name "*.mp4" | sort > /tmp/hw_all.txt'
LR_DATE=$(docker exec tdarr_node sh -c 'grep -oE "2026[0-9]{4}" /tmp/hw_all.txt | sort -u | head -1')
echo "客厅测试日期: $LR_DATE"

docker exec tdarr_node sh -c "
    grep '${LR_DATE}' /tmp/hw_all.txt | head -3 > /tmp/hw_day.txt
    > /tmp/hw_list.txt
    while read -r f; do
        basename \"\$f\" | grep -qE '^[0-9]+_2026[0-9]{4}(0[9-9]|1[0-9]|2[0-2])[0-9]{4}_' && echo \"file '\$f'\" >> /tmp/hw_list.txt
    done < /tmp/hw_day.txt
"
LR_FILES=$(docker exec tdarr_node sh -c 'wc -l < /tmp/hw_list.txt')
echo "   有效片段: ${LR_FILES}"
echo "✅ 数据准备完成"
echo ""

# ----- 3. 测试客厅 4K -----
echo "===================================================="
echo " 📹 客厅 4K H.265 — 方案对比"
echo "===================================================="

# 方案 A: 当前（CPU scale + NV12）
echo ""
echo "⏳ 方案 A（当前: scale + setpts）开始..."
START_A=$(date +%s)
docker exec tdarr_node ffmpeg -y -loglevel warning -nostats -f concat -safe 0 -i /tmp/hw_list.txt \
    -vf "scale=-2:2160,format=nv12,setpts=0.033333*PTS" \
    -an -c:v hevc_qsv -preset veryfast -r 20 \
    "$OUTDIR/lr_a_current.mp4" < /dev/null 2>&1
END_A=$(date +%s)
ELAPSED_A=$((END_A - START_A))
FILE_A=$(docker exec tdarr_node stat -c%s "$OUTDIR/lr_a_current.mp4" 2>/dev/null || echo 0)
echo "✅ 方案 A 完成，耗时: ${ELAPSED_A}s"

# 方案 C: 全硬件 vpp_qsv（有失败可能，单独捕获）
echo ""
echo "⏳ 方案 C（全硬件: vpp_qsv + setpts）开始..."
START_C=$(date +%s)
docker exec tdarr_node ffmpeg -y -hwaccel qsv -hwaccel_output_format qsv -loglevel warning -nostats \
    -f concat -safe 0 -i /tmp/hw_list.txt \
    -vf "vpp_qsv=w=3840:h=2160,setpts=0.033333*PTS" \
    -an -c:v hevc_qsv -preset speed -global_quality 25 -r 20 \
    "$OUTDIR/lr_c_vppqsv.mp4" < /dev/null 2>&1
C_EXIT=$?
END_C=$(date +%s)
ELAPSED_C=$((END_C - START_C))
FILE_C=$(docker exec tdarr_node stat -c%s "$OUTDIR/lr_c_vppqsv.mp4" 2>/dev/null || echo 0)
if [ $C_EXIT -ne 0 ]; then
    echo "⚠️ 方案 C 失败（exit=$C_EXIT），vpp_qsv 可能不兼容当前源"
else
    echo "✅ 方案 C 完成，耗时: ${ELAPSED_C}s"
fi

# 方案 D: 半硬件 scale_qsv
echo ""
echo "⏳ 方案 D（半硬件: scale_qsv + setpts）开始..."
START_D=$(date +%s)
docker exec tdarr_node ffmpeg -y -hwaccel qsv -hwaccel_output_format qsv -loglevel warning -nostats \
    -f concat -safe 0 -i /tmp/hw_list.txt \
    -vf "scale_qsv=w=3840:h=2160,setpts=0.033333*PTS" \
    -an -c:v hevc_qsv -preset speed -global_quality 25 -r 20 \
    "$OUTDIR/lr_d_scaleqsv.mp4" < /dev/null 2>&1
D_EXIT=$?
END_D=$(date +%s)
ELAPSED_D=$((END_D - START_D))
FILE_D=$(docker exec tdarr_node stat -c%s "$OUTDIR/lr_d_scaleqsv.mp4" 2>/dev/null || echo 0)
if [ $D_EXIT -ne 0 ]; then
    echo "⚠️ 方案 D 失败（exit=$D_EXIT），scale_qsv 可能不兼容"
else
    echo "✅ 方案 D 完成，耗时: ${ELAPSED_D}s"
fi

# ----- 4. 对比结果 -----
echo ""
echo "===================================================="
echo " 📊 客厅 4K 对比结果"
echo "===================================================="
echo ""

# 获取各文件的编码信息
docker exec tdarr_node sh -c '
    A=/mnt/export_videos_test/hwbench/lr_a_current.mp4
    B=/mnt/export_videos_test/hwbench/lr_c_vppqsv.mp4
    C=/mnt/export_videos_test/hwbench/lr_d_scaleqsv.mp4

    echo "┌─────────────────┬──────────────────┬──────────────────┬──────────────────┐"
    echo "│ 指标            │ 方案A(当前)      │ 方案C(vpp_qsv)   │ 方案D(scale_qsv) │"
    echo "├─────────────────┼──────────────────┼──────────────────┼──────────────────┤"

    for f in "$A" "$B" "$C"; do
        if [ -f "$f" ] && [ -s "$f" ]; then
            NAME=$(basename "$f")
            case "$NAME" in
                *a_*) LABEL="耗时(秒)" ;;
                *c_*) LABEL="耗时(秒)" ;;
                *d_*) LABEL="耗时(秒)" ;;
            esac
        fi
    done

    # 耗时
    printf "│ %-15s │ %-16s │ %-16s │ %-16s │\n" "耗时(秒)" "'$ELAPSED_A'" "'$ELAPSED_C'" "'$ELAPSED_D'"
    printf "│ %-15s │ %-16s │ %-16s │ %-16s │\n" "文件大小" "'$(ls -lh "$A" 2>/dev/null | awk "{print \$5}")'" "'$(ls -lh "$B" 2>/dev/null | awk "{print \$5}")'" "'$(ls -lh "$C" 2>/dev/null | awk "{print \$5}")'"

    for f in "$A" "$B" "$C"; do
        if [ -f "$f" ] && [ -s "$f" ]; then
            CODEC=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$f" 2>/dev/null)
            FPS=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$f" 2>/dev/null)
            FRAMES=$(ffprobe -v error -select_streams v:0 -show_entries stream=nb_frames -of csv=p=0 "$f" 2>/dev/null)
            case "$(basename "$f")" in
                *a_*) printf "│ %-15s │ %-16s │ %-16s │ %-16s │\n" "编码" "$CODEC" "" "" ;;
                *c_*) printf "│ %-15s │ %-16s │ %-16s │ %-16s │\n" "帧率" "" "$FPS" "" ;;
                *d_*) printf "│ %-15s │ %-16s │ %-16s │ %-16s │\n" "帧数" "" "" "$FRAMES" ;;
            esac
        fi
    done
    echo "└─────────────────┴──────────────────┴──────────────────┴──────────────────┘"
' 2>&1

# ----- 5. 加速比 -----
echo ""
echo "--- 加速比 ---"
if [ "$ELAPSED_A" -gt 0 ] 2>/dev/null; then
    if [ "$C_EXIT" -eq 0 ] && [ "$ELAPSED_C" -gt 0 ] 2>/dev/null; then
        RATIO_C=$(echo "scale=2; ${ELAPSED_A} / ${ELAPSED_C}" | bc 2>/dev/null)
        echo "  方案 C (vpp_qsv) vs 方案 A: ${RATIO_C}x"
    fi
    if [ "$D_EXIT" -eq 0 ] && [ "$ELAPSED_D" -gt 0 ] 2>/dev/null; then
        RATIO_D=$(echo "scale=2; ${ELAPSED_A} / ${ELAPSED_D}" | bc 2>/dev/null)
        echo "  方案 D (scale_qsv) vs 方案 A: ${RATIO_D}x"
    fi
fi

echo ""
echo "输出文件:"
docker exec tdarr_node ls -lh "$OUTDIR/" 2>/dev/null
echo ""
echo "===================================================="
echo " ✅ 测试完成！"
echo "===================================================="