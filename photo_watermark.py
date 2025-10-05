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
from PIL import Image, ImageDraw, ImageFont, ImageColor
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
                      output_format=None, jpeg_quality=95,
                      resize_width=None, resize_height=None, resize_percent=None,
                      text_content=None, text_color='white', text_opacity=100,
                      font_path=None, text_stroke_width=0, text_stroke_color='black',
                      text_shadow=False, text_shadow_offset=2, text_shadow_color='black', text_shadow_opacity=60,
                      logo_path=None, logo_scale_percent=None, logo_width=None, logo_height=None, logo_opacity=100):
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

                # 尺寸调整（优先使用新参数，其次兼容旧模式）
                img = self.apply_resize(img,
                                        width=resize_width,
                                        height=resize_height,
                                        percent=resize_percent)
                
                # 创建绘图对象
                # 若有透明通道，保证为 RGBA，便于在透明图层上绘制文本
                if has_alpha:
                    if img.mode != 'RGBA':
                        img = img.convert('RGBA')
                else:
                    if img.mode not in ('RGB', 'RGBA'):
                        img = img.convert('RGB')
                draw = ImageDraw.Draw(img)
                
                # 1) 默认始终添加 EXIF 时间文本（使用基本样式: color/font_size/无描边阴影）
                exif_text = self.get_watermark_text(image_path)
                base_font = self.get_font(font_size)
                bbox = draw.textbbox((0, 0), exif_text, font=base_font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                bx, by = self.calculate_position(img.width, img.height, tw, th, position)
                draw.text((bx, by), exif_text, fill=color, font=base_font)

                # 2) 可选：自定义文本水印
                if text_content:
                    cfont = self.get_font(font_size) if not font_path else self.load_font(font_path, font_size)
                    cbbox = draw.textbbox((0, 0), text_content, font=cfont, stroke_width=max(0, int(text_stroke_width)))
                    ctw = cbbox[2] - cbbox[0]
                    cth = cbbox[3] - cbbox[1]
                    cx, cy = self.calculate_position(img.width, img.height, ctw, cth, position)
                    self.draw_text_with_style(img, (cx, cy), text_content, cfont,
                                              fill_color=text_color, opacity=text_opacity,
                                              stroke_width=text_stroke_width, stroke_color=text_stroke_color,
                                              shadow=text_shadow, shadow_offset=text_shadow_offset,
                                              shadow_color=text_shadow_color, shadow_opacity=text_shadow_opacity)

                # 3) 可选：图片水印
                if logo_path:
                    wm_img = self.prepare_logo(logo_path, logo_scale_percent, logo_width, logo_height, logo_opacity)
                    if wm_img is None:
                        raise ValueError('无法加载图片水印')
                    wm_w, wm_h = wm_img.size
                    lx, ly = self.calculate_position(img.width, img.height, wm_w, wm_h, position)
                    if img.mode != 'RGBA':
                        img = img.convert('RGBA')
                    img.alpha_composite(wm_img, dest=(lx, ly))
                
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
                return True
                
        except Exception as e:
            print(f"✗ 处理图片失败 {os.path.basename(image_path)}: {e}")
            return False
    
    def apply_resize(self, img, width=None, height=None, percent=None):
        """统一的尺寸调整入口。
        当同时提供 width 和 height 时，按精确尺寸缩放；
        仅提供 width 或 height 时，按等比计算另一个边；
        仅提供 percent 时，按百分比缩放。
        """
        try:
            if width or height or percent:
                w, h = img.size
                if width and height:
                    tw = max(1, int(width))
                    th = max(1, int(height))
                    return img.resize((tw, th), Image.LANCZOS)
                if width:
                    tw = max(1, int(width))
                    th = max(1, int(h * (tw / w)))
                    return img.resize((tw, th), Image.LANCZOS)
                if height:
                    th = max(1, int(height))
                    tw = max(1, int(w * (th / h)))
                    return img.resize((tw, th), Image.LANCZOS)
                if percent:
                    scale = float(percent) / 100.0
                    tw = max(1, int(w * scale))
                    th = max(1, int(h * scale))
                    return img.resize((tw, th), Image.LANCZOS)
                return img
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

    def load_font(self, font_path, font_size):
        try:
            return ImageFont.truetype(font_path, font_size)
        except Exception:
            return self.get_font(font_size)

    def _parse_color_with_opacity(self, color_str, opacity_percent, fallback='white'):
        try:
            opacity = max(0, min(100, int(opacity_percent)))
        except Exception:
            opacity = 100
        try:
            rgb = ImageColor.getrgb(color_str)
        except Exception:
            rgb = (255, 255, 255) if fallback == 'white' else (0, 0, 0)
        a = int(round(opacity / 100.0 * 255))
        return (*rgb, a)

    def draw_text_with_style(self, img, xy, text, font, fill_color='white', opacity=100,
                              stroke_width=0, stroke_color='black', shadow=False,
                              shadow_offset=2, shadow_color='black', shadow_opacity=60):
        # 确保RGBA以便处理透明度
        if img.mode != 'RGBA':
            base_img = img.convert('RGBA')
        else:
            base_img = img
        text_layer = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(text_layer)

        # 阴影
        if shadow:
            shadow_rgba = self._parse_color_with_opacity(shadow_color, shadow_opacity, fallback='black')
            sx = xy[0] + int(shadow_offset)
            sy = xy[1] + int(shadow_offset)
            d.text((sx, sy), text, font=font, fill=shadow_rgba, stroke_width=int(stroke_width), stroke_fill=shadow_rgba)

        # 主文本
        fill_rgba = self._parse_color_with_opacity(fill_color, opacity, fallback='white')
        d.text(xy, text, font=font, fill=fill_rgba, stroke_width=int(stroke_width), stroke_fill=stroke_color)

        base_img.alpha_composite(text_layer)
        if img is not base_img:
            img.paste(base_img)

    def prepare_logo(self, logo_path, scale_percent=None, width=None, height=None, opacity=100):
        try:
            logo = Image.open(logo_path)
            if logo.mode != 'RGBA':
                logo = logo.convert('RGBA')
            lw, lh = logo.size
            # 尺寸
            if width and height:
                logo = logo.resize((int(width), int(height)), Image.LANCZOS)
            elif width:
                tw = int(width)
                th = max(1, int(lh * (tw / lw)))
                logo = logo.resize((tw, th), Image.LANCZOS)
            elif height:
                th = int(height)
                tw = max(1, int(lw * (th / lh)))
                logo = logo.resize((tw, th), Image.LANCZOS)
            elif scale_percent:
                scale = float(scale_percent) / 100.0
                tw = max(1, int(lw * scale))
                th = max(1, int(lh * scale))
                logo = logo.resize((tw, th), Image.LANCZOS)

            # 透明度
            a = max(0, min(100, int(opacity)))
            alpha = logo.split()[-1]
            alpha = alpha.point(lambda p: int(p * (a / 100.0)))
            logo.putalpha(alpha)
            return logo
        except Exception:
            return None
    
    def process_directory(self, input_dir, font_size=24, color='white', position='bottom-right',
                          output_dir=None, output_format=None, jpeg_quality=95,
                          name_prefix='', name_suffix='', forbid_export_to_input=True,
                          resize_width=None, resize_height=None, resize_percent=None,
                          text_content=None, text_color='white', text_opacity=100,
                          font_path=None, text_stroke_width=0, text_stroke_color='black', text_shadow=False,
                          text_shadow_offset=2, text_shadow_color='black', text_shadow_opacity=60,
                          logo_path=None, logo_scale_percent=None, logo_width=None, logo_height=None, logo_opacity=100):
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
        if any([resize_width, resize_height, resize_percent]):
            print(f"📐 缩放: width={resize_width}, height={resize_height}, percent={resize_percent}")
        print("-" * 50)
        
        # 处理每个图片
        success_count = 0
        for i, image_file in enumerate(image_files, 1):
            print(f"[{i}/{len(image_files)}] 处理: {image_file.name}")
            output_file = output_dir / self.build_output_filename(
                image_file.name, name_prefix, name_suffix, output_format
            )
            try:
                ok = self.add_watermark(
                    str(image_file),
                    str(output_file),
                    font_size,
                    color,
                    position,
                    output_format=output_format,
                    jpeg_quality=jpeg_quality,
                    resize_width=resize_width,
                    resize_height=resize_height,
                    resize_percent=resize_percent,
                    text_content=text_content,
                    text_color=text_color,
                    text_opacity=text_opacity,
                    font_path=font_path,
                    text_stroke_width=text_stroke_width,
                    text_stroke_color=text_stroke_color,
                    text_shadow=text_shadow,
                    text_shadow_offset=text_shadow_offset,
                    text_shadow_color=text_shadow_color,
                    text_shadow_opacity=text_shadow_opacity,
                    logo_path=logo_path,
                    logo_scale_percent=logo_scale_percent,
                    logo_width=logo_width,
                    logo_height=logo_height,
                    logo_opacity=logo_opacity,
                )
                if ok:
                    success_count += 1
            except Exception as e:
                print(f"✗ 处理失败: {e}")
        
        print("-" * 50)
        print(f"✅ 处理完成！成功处理 {success_count}/{len(image_files)} 个文件")
        print(f"📁 输出目录: {output_dir}")

    def process_files(self, files, output_dir, font_size=24, color='white', position='bottom-right',
                      output_format=None, jpeg_quality=95, name_prefix='', name_suffix='',
                      forbid_export_to_input=True,
                      resize_width=None, resize_height=None, resize_percent=None,
                      text_content=None, text_color='white', text_opacity=100,
                      font_path=None, text_stroke_width=0, text_stroke_color='black', text_shadow=False,
                      text_shadow_offset=2, text_shadow_color='black', text_shadow_opacity=60,
                      logo_path=None, logo_scale_percent=None, logo_width=None, logo_height=None, logo_opacity=100):
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
                ok = self.add_watermark(
                    str(f), str(output_file), font_size, color, position,
                    output_format=output_format, jpeg_quality=jpeg_quality,
                    resize_width=resize_width, resize_height=resize_height, resize_percent=resize_percent,
                    text_content=text_content,
                    text_color=text_color,
                    text_opacity=text_opacity,
                    font_path=font_path,
                    text_stroke_width=text_stroke_width,
                    text_stroke_color=text_stroke_color,
                    text_shadow=text_shadow,
                    text_shadow_offset=text_shadow_offset,
                    text_shadow_color=text_shadow_color,
                    text_shadow_opacity=text_shadow_opacity,
                    logo_path=logo_path,
                    logo_scale_percent=logo_scale_percent,
                    logo_width=logo_width,
                    logo_height=logo_height,
                    logo_opacity=logo_opacity,
                )
                if ok:
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
    parser = argparse.ArgumentParser(description='为图片添加水印（默认添加EXIF时间；可选添加自定义文本与图片Logo）')
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
    # 水印样式（默认总是添加EXIF文本；可另外添加自定义文本与Logo）
    parser.add_argument('--text-content', default=None, help='自定义文本内容')
    parser.add_argument('--text-color', default='white', help='文本颜色')
    parser.add_argument('--text-opacity', type=int, default=100, help='文本不透明度(0-100)')
    parser.add_argument('--font-path', default=None, help='字体文件路径(.ttf/.otf)')
    parser.add_argument('--text-stroke-width', type=int, default=0, help='文本描边宽度')
    parser.add_argument('--text-stroke-color', default='black', help='文本描边颜色')
    parser.add_argument('--text-shadow', action='store_true', help='启用文本阴影')
    parser.add_argument('--text-shadow-offset', type=int, default=2, help='文本阴影偏移像素')
    parser.add_argument('--text-shadow-color', default='black', help='文本阴影颜色')
    parser.add_argument('--text-shadow-opacity', type=int, default=60, help='文本阴影不透明度(0-100)')
    parser.add_argument('--logo-path', default=None, help='图片水印(Logo)路径(PNG支持透明)')
    parser.add_argument('--logo-scale-percent', type=float, default=None, help='按百分比缩放Logo')
    parser.add_argument('--logo-width', type=int, default=None, help='Logo目标宽度')
    parser.add_argument('--logo-height', type=int, default=None, help='Logo目标高度')
    parser.add_argument('--logo-opacity', type=int, default=100, help='Logo不透明度(0-100)')
    parser.add_argument('--name-prefix', default='', help='输出文件名前缀 (默认: 空)')
    parser.add_argument('--name-suffix', default='', help='输出文件名后缀 (默认: 空)')
    parser.add_argument('--allow-export-to-input', action='store_true', help='允许导出到原文件夹 (默认: 禁止)')
    # 尺寸参数
    parser.add_argument('--resize-width', type=int, default=None, help='输出宽度（像素）')
    parser.add_argument('--resize-height', type=int, default=None, help='输出高度（像素）')
    parser.add_argument('--resize-percent', type=float, default=None, help='输出百分比（0-100）')
    
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
        resize_width=args.resize_width,
        resize_height=args.resize_height,
        resize_percent=args.resize_percent,
        text_content=args.text_content,
        text_color=args.text_color,
        text_opacity=args.text_opacity,
        font_path=args.font_path,
        text_stroke_width=args.text_stroke_width,
        text_stroke_color=args.text_stroke_color,
        text_shadow=args.text_shadow,
        text_shadow_offset=args.text_shadow_offset,
        text_shadow_color=args.text_shadow_color,
        text_shadow_opacity=args.text_shadow_opacity,
        logo_path=args.logo_path,
        logo_scale_percent=args.logo_scale_percent,
        logo_width=args.logo_width,
        logo_height=args.logo_height,
        logo_opacity=args.logo_opacity,
    )


if __name__ == "__main__":
    main()
