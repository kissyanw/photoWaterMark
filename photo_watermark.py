#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片水印工具
基于EXIF拍摄时间信息为图片添加水印
"""

import os
import sys
import argparse
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import piexif
from pathlib import Path


class PhotoWatermark:
    def __init__(self):
        self.supported_formats = {'.jpg', '.jpeg', '.png', '.tiff', '.tif'}
        
    def get_exif_datetime(self, image_path):
        """从图片EXIF信息中获取拍摄时间"""
        try:
            exif_dict = piexif.load(image_path)
            if 'Exif' in exif_dict:
                # 尝试获取DateTimeOriginal
                if piexif.ExifIFD.DateTimeOriginal in exif_dict['Exif']:
                    datetime_str = exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal].decode('utf-8')
                    return datetime.strptime(datetime_str, '%Y:%m:%d %H:%M:%S')
                # 尝试获取DateTime
                elif piexif.ExifIFD.DateTime in exif_dict['Exif']:
                    datetime_str = exif_dict['Exif'][piexif.ExifIFD.DateTime].decode('utf-8')
                    return datetime.strptime(datetime_str, '%Y:%m:%d %H:%M:%S')
            return None
        except Exception as e:
            print(f"读取EXIF信息失败 {image_path}: {e}")
            return None
    
    def get_watermark_text(self, image_path):
        """获取水印文本（基于拍摄时间）"""
        dt = self.get_exif_datetime(image_path)
        if dt:
            return dt.strftime('%Y年%m月%d日')
        else:
            # 如果没有EXIF信息，使用文件修改时间
            file_time = datetime.fromtimestamp(os.path.getmtime(image_path))
            return file_time.strftime('%Y年%m月%d日')
    
    def calculate_position(self, img_width, img_height, text_width, text_height, position):
        """计算水印位置"""
        margin = 20
        
        if position == 'top-left':
            return (margin, margin)
        elif position == 'top-right':
            return (img_width - text_width - margin, margin)
        elif position == 'bottom-left':
            return (margin, img_height - text_height - margin)
        elif position == 'bottom-right':
            return (img_width - text_width - margin, img_height - text_height - margin)
        elif position == 'center':
            return ((img_width - text_width) // 2, (img_height - text_height) // 2)
        else:
            return (margin, margin)  # 默认左上角
    
    def add_watermark(self, image_path, output_path, font_size=24, color='white', position='bottom-right'):
        """为图片添加水印"""
        try:
            # 打开图片
            with Image.open(image_path) as img: 
                
                     
                # 转换为RGB模式（如果需要）
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 创建绘图对象
                draw = ImageDraw.Draw(img)
                
                # 获取水印文本
                watermark_text = self.get_watermark_text(image_path)
                
                # 尝试加载字体
                font = self.get_font(font_size)
                
                # 获取文本尺寸
                bbox = draw.textbbox((0, 0), watermark_text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                
                # 计算位置
                x, y = self.calculate_position(img.width, img.height, text_width, text_height, position)
                
                # 绘制文本
                draw.text((x, y), watermark_text, fill=color, font=font)
                
                # 保存图片
                img.save(output_path, quality=95)
                print(f"✓ 已处理: {os.path.basename(image_path)} -> {os.path.basename(output_path)}")
                
        except Exception as e:
            print(f"✗ 处理图片失败 {os.path.basename(image_path)}: {e}")
    
    def get_font(self, font_size):
        """获取字体对象"""
        font_paths = [
            "arial.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/msyh.ttf",  # 微软雅黑
            "C:/Windows/Fonts/simhei.ttf",  # 黑体
        ]
        
        for font_path in font_paths:
            try:
                return ImageFont.truetype(font_path, font_size)
            except:
                continue
        
        # 如果所有字体都加载失败，使用默认字体
        return ImageFont.load_default()
    
    def process_directory(self, input_dir, font_size=24, color='white', position='bottom-right'):
        """处理目录中的所有图片"""
        input_path = Path(input_dir)
        if not input_path.exists():
            print(f"❌ 错误: 目录不存在 {input_dir}")
            return
        
        # 创建输出目录（作为原目录的子目录）
        output_dir = input_path / f"{input_path.name}_watermark"
        output_dir.mkdir(exist_ok=True)
        print(f"📁 输出目录: {output_dir}")
        
        # 查找所有支持的图片文件
        image_files = []
        for ext in self.supported_formats:
            image_files.extend(input_path.glob(f"*{ext}"))
            image_files.extend(input_path.glob(f"*{ext.upper()}"))
        
        if not image_files:
            print("❌ 未找到支持的图片文件")
            print(f"支持的格式: {', '.join(self.supported_formats)}")
            return
        
        print(f"📸 找到 {len(image_files)} 个图片文件")
        print(f"🎨 设置: 字体大小={font_size}, 颜色={color}, 位置={position}")
        print("-" * 50)
        
        # 处理每个图片
        success_count = 0
        for i, image_file in enumerate(image_files, 1):
            print(f"[{i}/{len(image_files)}] 处理: {image_file.name}")
            output_file = output_dir / image_file.name
            try:
                self.add_watermark(str(image_file), str(output_file), font_size, color, position)
                success_count += 1
            except Exception as e:
                print(f"✗ 处理失败: {e}")
        
        print("-" * 50)
        print(f"✅ 处理完成！成功处理 {success_count}/{len(image_files)} 个文件")
        print(f"📁 输出目录: {output_dir}")


def main():
    parser = argparse.ArgumentParser(description='为图片添加基于EXIF拍摄时间的水印')
    parser.add_argument('input_dir', nargs='?', default='.', help='输入图片目录路径 (默认: 当前目录)')
    parser.add_argument('--font-size', type=int, default=24, help='字体大小 (默认: 24)')
    parser.add_argument('--color', default='white', help='水印颜色 (默认: white)')
    parser.add_argument('--position', 
                       choices=['top-left', 'top-right', 'bottom-left', 'bottom-right', 'center'],
                       default='bottom-right', 
                       help='水印位置 (默认: bottom-right)')
    
    args = parser.parse_args()
    
    # 创建水印工具实例
    watermark_tool = PhotoWatermark()
    
    # 处理目录
    watermark_tool.process_directory(
        args.input_dir, 
        args.font_size, 
        args.color, 
        args.position
    )


if __name__ == "__main__":
    main()
