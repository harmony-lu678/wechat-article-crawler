#!/bin/bash
# 快速启动脚本

echo "======================================"
echo "微信公众号文章爬虫与总结系统"
echo "======================================"
echo ""

# 检查是否安装了依赖
if ! python -c "import requests" 2>/dev/null; then
    echo "正在安装依赖..."
    pip install -r requirements.txt -q
    echo "依赖安装完成"
    echo ""
fi

# 询问是否配置API
echo "是否需要配置AI总结功能？(y/n)"
read -r answer

if [ "$answer" = "y" ]; then
    echo ""
    echo "请输入OpenAI API Key (或直接回车跳过):"
    read -r api_key

    if [ -n "$api_key" ]; then
        # 使用sed更新config.yaml中的api_key
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' "s/api_key: \"your-api-key-here\"/api_key: \"$api_key\"/" config.yaml
        else
            # Linux
            sed -i "s/api_key: \"your-api-key-here\"/api_key: \"$api_key\"/" config.yaml
        fi
        echo "✓ API Key已配置"
    fi
fi

echo ""
echo "======================================"
echo "开始执行爬虫任务..."
echo "======================================"
echo ""

# 运行主程序
python main.py --mode full

echo ""
echo "======================================"
echo "任务完成！"
echo "======================================"
echo ""
echo "查看结果："
echo "  完整报告: output/summary_report.md"
echo "  原始数据: data/raw/articles.json"
echo "  日志文件: logs/main.log"
echo ""
