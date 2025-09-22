#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试水印工具
"""

import os
import sys
from PIL import Image
from photo_watermark import PhotoWatermark


def create_test_image(filename, width=800, height=600):
    """创建一个测试图片"""
    img = Image.new('RGB', (width, height), color='lightblue')
    draw = ImageDraw.Draw(img)
    draw.text((50, 50), f"Test Image: {filename}", fill='black')
    img.save(filename)
    print(f"创建测试图片: {filename}")


def test_watermark():
    """测试水印功能"""
    print("开始测试水印工具...")
    
    # 创建测试目录
    test_dir = "test_images"
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)
    
    # 创建测试图片
    test_files = ["test1.jpg", "test2.png", "test3.jpg"]
    for filename in test_files:
        create_test_image(os.path.join(test_dir, filename))
    
    # 测试水印工具
    watermark_tool = PhotoWatermark()
    
    print("\n测试不同位置的水印:")
    positions = ['top-left', 'top-right', 'bottom-left', 'bottom-right', 'center']
    
    for i, position in enumerate(positions):
        output_dir = f"test_output_{position}"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        for filename in test_files:
            input_path = os.path.join(test_dir, filename)
            output_path = os.path.join(output_dir, f"{position}_{filename}")
            watermark_tool.add_watermark(input_path, output_path, 
                                       font_size=20, color='red', position=position)
    
    print("\n测试完成！请检查输出目录中的图片。")


if __name__ == "__main__":
    from PIL import ImageDraw
    test_watermark()
