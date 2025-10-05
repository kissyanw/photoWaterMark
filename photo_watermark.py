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
        self.supported_formats = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp'}
        
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
    
    def add_watermark(self, image_path, output_path, font_size=24, color='white', position='bottom-right',
                      output_format=None, jpeg_quality=95, resize_mode=None, resize_value=None):
        """为图片添加水印并导出

        参数:
        - output_format: 可选 'jpeg' 或 'png'，不填则依据 output_path 后缀
        - jpeg_quality: 0-100，仅当输出为jpeg时生效
        - resize_mode: 可选 'width' | 'height' | 'percent' | None
        - resize_value: 对应的数值 (int 或 float)，如宽度像素/高度像素/百分比(0-100)
        """
        try:
            # 打开图片
            with Image.open(image_path) as img:
                # 记录是否含透明通道
                has_alpha = (img.mode in ('RGBA', 'LA')) or ('transparency' in img.info)

                # 尺寸调整
                if resize_mode and resize_value:
                    img = self.resize_image(img, resize_mode, resize_value)
                
                # 创建绘图对象
                # 若有透明通道，保证为 RGBA，便于在透明图层上绘制文本
                if has_alpha:
                    if img.mode != 'RGBA':
                        img = img.convert('RGBA')
                else:
                    if img.mode not in ('RGB', 'RGBA'):
                        img = img.convert('RGB')
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
                fmt = (output_format or Path(output_path).suffix.lstrip('.')).lower()
                if fmt in ('jpg', 'jpeg'):
                    # JPEG 不支持透明，确保转换为 RGB
                    if img.mode == 'RGBA':
                        img = img.convert('RGB')
                    img.save(output_path, quality=int(jpeg_quality), format='JPEG')
                elif fmt == 'png':
                    # PNG 保留透明
                    img.save(output_path, format='PNG')
                else:
                    # 回退到原Pillow推断
                    img.save(output_path)
                print(f"✓ 已处理: {os.path.basename(image_path)} -> {os.path.basename(output_path)}")
                
        except Exception as e:
            print(f"✗ 处理图片失败 {os.path.basename(image_path)}: {e}")
    
    def resize_image(self, img, mode, value):
        """按给定模式调整尺寸"""
        try:
            if mode == 'width':
                target_w = int(value)
                w, h = img.size
                target_h = max(1, int(h * (target_w / w)))
                return img.resize((target_w, target_h), Image.LANCZOS)
            elif mode == 'height':
                target_h = int(value)
                w, h = img.size
                target_w = max(1, int(w * (target_h / h)))
                return img.resize((target_w, target_h), Image.LANCZOS)
            elif mode == 'percent':
                scale = float(value) / 100.0
                w, h = img.size
                target_w = max(1, int(w * scale))
                target_h = max(1, int(h * scale))
                return img.resize((target_w, target_h), Image.LANCZOS)
            else:
                return img
        except Exception:
            return img

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
    
    def process_directory(self, input_dir, font_size=24, color='white', position='bottom-right',
                          output_dir=None, output_format=None, jpeg_quality=95,
                          name_prefix='', name_suffix='', forbid_export_to_input=True,
                          resize_mode=None, resize_value=None):
        """处理目录中的所有图片"""
        input_path = Path(input_dir)
        if not input_path.exists():
            print(f"❌ 错误: 目录不存在 {input_dir}")
            return
        
        # 输出目录
        if output_dir:
            output_dir = Path(output_dir)
            if forbid_export_to_input and output_dir.resolve() == input_path.resolve():
                print("❌ 为防止覆盖原图，禁止导出到原文件夹，请选择其他输出目录")
                return
        else:
            # 默认作为原目录的子目录
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
        if output_format:
            print(f"💾 输出格式={output_format}")
        print(f"🧩 命名: prefix='{name_prefix}', suffix='{name_suffix}'")
        if resize_mode and resize_value:
            print(f"📐 缩放: 模式={resize_mode}, 值={resize_value}")
        print("-" * 50)
        
        # 处理每个图片
        success_count = 0
        for i, image_file in enumerate(image_files, 1):
            print(f"[{i}/{len(image_files)}] 处理: {image_file.name}")
            output_file = output_dir / self.build_output_filename(
                image_file.name, name_prefix, name_suffix, output_format
            )
            try:
                self.add_watermark(
                    str(image_file),
                    str(output_file),
                    font_size,
                    color,
                    position,
                    output_format=output_format,
                    jpeg_quality=jpeg_quality,
                    resize_mode=resize_mode,
                    resize_value=resize_value,
                )
                success_count += 1
            except Exception as e:
                print(f"✗ 处理失败: {e}")
        
        print("-" * 50)
        print(f"✅ 处理完成！成功处理 {success_count}/{len(image_files)} 个文件")
        print(f"📁 输出目录: {output_dir}")

    def process_files(self, files, output_dir, font_size=24, color='white', position='bottom-right',
                      output_format=None, jpeg_quality=95, name_prefix='', name_suffix='',
                      forbid_export_to_input=True, resize_mode=None, resize_value=None):
        """处理一组指定文件（用于GUI批量导入）"""
        files = [Path(p) for p in files]
        if not files:
            print("❌ 未提供文件")
            return
        # 校验输出目录
        output_dir = Path(output_dir)
        # 如果所有文件都来自同一个目录，且禁止导出到相同目录，则拒绝
        if forbid_export_to_input:
            parent_dirs = {f.parent.resolve() for f in files}
            if len(parent_dirs) == 1 and output_dir.resolve() in parent_dirs:
                print("❌ 为防止覆盖原图，禁止导出到原文件夹")
                return
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 输出目录: {output_dir}")
        print(f"📦 文件数: {len(files)}")
        success_count = 0
        for i, f in enumerate(files, 1):
            print(f"[{i}/{len(files)}] 处理: {f.name}")
            output_file = output_dir / self.build_output_filename(
                f.name, name_prefix, name_suffix, output_format
            )
            try:
                self.add_watermark(
                    str(f), str(output_file), font_size, color, position,
                    output_format=output_format, jpeg_quality=jpeg_quality,
                    resize_mode=resize_mode, resize_value=resize_value
                )
                success_count += 1
            except Exception as e:
                print(f"✗ 处理失败 {f.name}: {e}")
        print("-" * 50)
        print(f"✅ 处理完成！成功处理 {success_count}/{len(files)} 个文件")

    def build_output_filename(self, original_name, prefix, suffix, output_format):
        stem = Path(original_name).stem
        ext = (output_format.lower() if output_format else Path(original_name).suffix.lstrip('.')).lower()
        if ext == 'jpg':
            ext = 'jpeg'
        return f"{prefix}{stem}{suffix}.{ext}"


def main():
    parser = argparse.ArgumentParser(description='为图片添加基于EXIF拍摄时间的水印')
    parser.add_argument('input_dir', nargs='?', default='.', help='输入图片目录路径 (默认: 当前目录)')
    parser.add_argument('--font-size', type=int, default=24, help='字体大小 (默认: 24)')
    parser.add_argument('--color', default='white', help='水印颜色 (默认: white)')
    parser.add_argument('--position',
                        choices=['top-left', 'top-right', 'bottom-left', 'bottom-right', 'center'],
                        default='bottom-right',
                        help='水印位置 (默认: bottom-right)')
    parser.add_argument('--output-dir', default=None, help='输出目录 (默认: 原目录下 *_watermark)')
    parser.add_argument('--output-format', choices=['jpeg', 'png'], default=None, help='输出格式 (可选: jpeg 或 png)')
    parser.add_argument('--jpeg-quality', type=int, default=95, help='JPEG质量 0-100 (默认:95)')
    parser.add_argument('--name-prefix', default='', help='输出文件名前缀 (默认: 空)')
    parser.add_argument('--name-suffix', default='', help='输出文件名后缀 (默认: 空)')
    parser.add_argument('--allow-export-to-input', action='store_true', help='允许导出到原文件夹 (默认: 禁止)')
    parser.add_argument('--resize-mode', choices=['width', 'height', 'percent'], default=None, help='缩放模式')
    parser.add_argument('--resize-value', default=None, help='缩放数值: 像素或百分比')
    
    args = parser.parse_args()
    
    # 创建水印工具实例
    watermark_tool = PhotoWatermark()
    
    # 处理目录
    watermark_tool.process_directory(
        args.input_dir,
        args.font_size,
        args.color,
        args.position,
        output_dir=args.output_dir,
        output_format=args.output_format,
        jpeg_quality=args.jpeg_quality,
        name_prefix=args.name_prefix,
        name_suffix=args.name_suffix,
        forbid_export_to_input=(not args.allow_export_to_input),
        resize_mode=args.resize_mode,
        resize_value=args.resize_value,
    )


if __name__ == "__main__":
    main()
