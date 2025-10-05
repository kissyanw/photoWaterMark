#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图形界面：支持拖拽/选择导入、缩略图预览、导出设置（格式、质量、命名、尺寸）
"""

import os
from pathlib import Path
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    # 拖拽依赖
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except Exception:
    DND_AVAILABLE = False

from PIL import Image, ImageTk

from photo_watermark import PhotoWatermark


SUPPORTED_EXTS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp'}


class WatermarkGUI:
    def __init__(self):
        self.watermark = PhotoWatermark()
        self.root = (TkinterDnD.Tk() if DND_AVAILABLE else tk.Tk())
        self.root.title("图片水印工具 - GUI")
        self.root.geometry("980x640")

        self.files = []  # 存储文件的绝对路径
        self.thumbnails = {}  # 防止被GC: path -> PhotoImage

        self._build_layout()
        self._bind_dnd_if_available()

    def _build_layout(self):
        main = ttk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True)

        # 左侧：文件区（拖拽/列表/按钮）
        left = ttk.Frame(main, width=560)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        left.pack_propagate(False)

        hint = ttk.Label(left, text=(
            "将图片或文件夹拖拽到此区域，或使用下方按钮添加\n"
            f"支持格式：{', '.join(sorted(e.upper().lstrip('.') for e in SUPPORTED_EXTS))}"
        ))
        hint.pack(pady=8)

        # 可滚动缩略图容器
        self.canvas = tk.Canvas(left, borderwidth=0, highlightthickness=1, highlightbackground="#ddd")
        self.scroll = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.list_frame = ttk.Frame(self.canvas)
        self.list_window = self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.list_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        btn_bar = ttk.Frame(left)
        btn_bar.pack(fill=tk.X, pady=8)
        ttk.Button(btn_bar, text="添加文件", command=self.add_files_dialog).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_bar, text="添加文件夹", command=self.add_folder_dialog).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_bar, text="清空列表", command=self.clear_files).pack(side=tk.LEFT, padx=4)

        # 右侧：设置区
        right = ttk.Frame(main)
        right.pack(side=tk.RIGHT, fill=tk.Y)
        # 默认始终添加 EXIF 文本；下方可选添加自定义文本与Logo
        wm_group = ttk.LabelFrame(right, text="水印")
        wm_group.pack(fill=tk.X, padx=10, pady=8)
        ttk.Label(wm_group, text="默认会添加 EXIF 时间文本。可选：再添加自定义文本与图片Logo。").pack(anchor=tk.W)

        # 文本水印设置
        text_group = ttk.LabelFrame(right, text="文本水印")
        text_group.pack(fill=tk.X, padx=10, pady=8)
        self.text_content_var = tk.StringVar()
        tr = ttk.Frame(text_group); tr.pack(fill=tk.X, pady=4)
        ttk.Label(tr, text="文本:").pack(side=tk.LEFT)
        ttk.Entry(tr, textvariable=self.text_content_var, width=28).pack(side=tk.LEFT, padx=4)
        tc = ttk.Frame(text_group); tc.pack(fill=tk.X, pady=4)
        ttk.Label(tc, text="颜色:").pack(side=tk.LEFT)
        self.text_color_var = tk.StringVar(value='white')
        ttk.Entry(tc, textvariable=self.text_color_var, width=10).pack(side=tk.LEFT, padx=4)
        ttk.Button(tc, text="调色盘", command=lambda: self.pick_color(self.text_color_var)).pack(side=tk.LEFT)
        to = ttk.Frame(text_group); to.pack(fill=tk.X, pady=4)
        ttk.Label(to, text="不透明度:").pack(side=tk.LEFT)
        self.text_opacity_scale = ttk.Scale(to, from_=0, to=100, orient=tk.HORIZONTAL)
        self.text_opacity_scale.set(100)
        self.text_opacity_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        font_row = ttk.Frame(text_group); font_row.pack(fill=tk.X, pady=4)
        ttk.Label(font_row, text="字体文件:").pack(side=tk.LEFT)
        self.font_path_var = tk.StringVar()
        ttk.Entry(font_row, textvariable=self.font_path_var, width=24).pack(side=tk.LEFT, padx=4)
        ttk.Button(font_row, text="选择...", command=self.choose_font_file).pack(side=tk.LEFT)
        style_row = ttk.Frame(text_group); style_row.pack(fill=tk.X, pady=4)
        ttk.Label(style_row, text="描边宽度:").pack(side=tk.LEFT)
        self.stroke_width_var = tk.IntVar(value=0)
        ttk.Spinbox(style_row, from_=0, to=10, textvariable=self.stroke_width_var, width=5).pack(side=tk.LEFT, padx=4)
        ttk.Label(style_row, text="描边颜色:").pack(side=tk.LEFT)
        self.stroke_color_var = tk.StringVar(value='black')
        ttk.Entry(style_row, textvariable=self.stroke_color_var, width=10).pack(side=tk.LEFT, padx=4)
        ttk.Button(style_row, text="调色盘", command=lambda: self.pick_color(self.stroke_color_var)).pack(side=tk.LEFT)
        shadow_row = ttk.Frame(text_group); shadow_row.pack(fill=tk.X, pady=4)
        self.shadow_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(shadow_row, text="阴影", variable=self.shadow_var).pack(side=tk.LEFT)
        ttk.Label(shadow_row, text="偏移:").pack(side=tk.LEFT)
        self.shadow_offset_var = tk.IntVar(value=2)
        ttk.Spinbox(shadow_row, from_=0, to=20, textvariable=self.shadow_offset_var, width=5).pack(side=tk.LEFT, padx=4)
        ttk.Label(shadow_row, text="阴影颜色:").pack(side=tk.LEFT)
        self.shadow_color_var = tk.StringVar(value='black')
        ttk.Entry(shadow_row, textvariable=self.shadow_color_var, width=10).pack(side=tk.LEFT, padx=4)
        ttk.Button(shadow_row, text="调色盘", command=lambda: self.pick_color(self.shadow_color_var)).pack(side=tk.LEFT)
        ttk.Label(shadow_row, text="不透明度:").pack(side=tk.LEFT)
        self.shadow_opacity_scale = ttk.Scale(shadow_row, from_=0, to=100, orient=tk.HORIZONTAL)
        self.shadow_opacity_scale.set(60)
        self.shadow_opacity_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        # 图片水印设置（Logo 尺寸为水印尺寸）
        logo_group = ttk.LabelFrame(right, text="图片水印(Logo) 尺寸 = 水印尺寸")
        logo_group.pack(fill=tk.X, padx=10, pady=8)
        lr = ttk.Frame(logo_group); lr.pack(fill=tk.X, pady=4)
        ttk.Label(lr, text="Logo路径:").pack(side=tk.LEFT)
        self.logo_path_var = tk.StringVar()
        ttk.Entry(lr, textvariable=self.logo_path_var, width=24).pack(side=tk.LEFT, padx=4)
        ttk.Button(lr, text="选择...", command=self.choose_logo_file).pack(side=tk.LEFT)
        ls = ttk.Frame(logo_group); ls.pack(fill=tk.X, pady=4)
        ttk.Label(ls, text="缩放%:").pack(side=tk.LEFT)
        self.logo_scale_var = tk.StringVar()
        ttk.Entry(ls, textvariable=self.logo_scale_var, width=6).pack(side=tk.LEFT, padx=4)
        ttk.Label(ls, text="宽(px):").pack(side=tk.LEFT)
        self.logo_w_var = tk.StringVar()
        ttk.Entry(ls, textvariable=self.logo_w_var, width=6).pack(side=tk.LEFT, padx=4)
        ttk.Label(ls, text="高(px):").pack(side=tk.LEFT)
        self.logo_h_var = tk.StringVar()
        ttk.Entry(ls, textvariable=self.logo_h_var, width=6).pack(side=tk.LEFT, padx=4)
        lo = ttk.Frame(logo_group); lo.pack(fill=tk.X, pady=4)
        ttk.Label(lo, text="不透明度:").pack(side=tk.LEFT)
        self.logo_opacity_scale = ttk.Scale(lo, from_=0, to=100, orient=tk.HORIZONTAL)
        self.logo_opacity_scale.set(100)
        self.logo_opacity_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        # 输出目录
        out_group = ttk.LabelFrame(right, text="导出设置")
        out_group.pack(fill=tk.X, padx=10, pady=8)
        self.output_dir_var = tk.StringVar()
        row = ttk.Frame(out_group)
        row.pack(fill=tk.X, pady=4)
        ttk.Label(row, text="输出目录:").pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=self.output_dir_var, width=30).pack(side=tk.LEFT, padx=4)
        ttk.Button(row, text="选择...", command=self.choose_output_dir).pack(side=tk.LEFT)
        self.allow_same_dir_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(out_group, text="允许导出到原文件夹（不推荐）", variable=self.allow_same_dir_var).pack(anchor=tk.W, pady=4)

        # 导出格式/质量
        fmt_group = ttk.LabelFrame(right, text="格式与质量")
        fmt_group.pack(fill=tk.X, padx=10, pady=8)
        self.format_var = tk.StringVar(value="auto")
        fmt_row = ttk.Frame(fmt_group)
        fmt_row.pack(fill=tk.X, pady=4)
        ttk.Label(fmt_row, text="输出格式:").pack(side=tk.LEFT)
        ttk.Combobox(fmt_row, textvariable=self.format_var, values=["auto", "jpeg", "png"], width=8, state="readonly").pack(side=tk.LEFT, padx=4)
        q_row = ttk.Frame(fmt_group)
        q_row.pack(fill=tk.X, pady=4)
        ttk.Label(q_row, text="JPEG质量:").pack(side=tk.LEFT)
        self.quality_var = tk.IntVar(value=95)
        # 先创建label，再绑定scale，避免回调在label未就绪时报错
        self.quality_label = ttk.Label(q_row, text="95")
        self.quality_label.pack(side=tk.LEFT)
        self.quality_scale = ttk.Scale(q_row, from_=0, to=100, orient=tk.HORIZONTAL, command=self._on_quality_change)
        self.quality_scale.set(95)
        self.quality_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        # 命名
        name_group = ttk.LabelFrame(right, text="命名规则")
        name_group.pack(fill=tk.X, padx=10, pady=8)
        self.prefix_var = tk.StringVar()
        self.suffix_var = tk.StringVar()
        r1 = ttk.Frame(name_group); r1.pack(fill=tk.X, pady=4)
        ttk.Label(r1, text="前缀:").pack(side=tk.LEFT)
        ttk.Entry(r1, textvariable=self.prefix_var, width=16).pack(side=tk.LEFT, padx=4)
        r2 = ttk.Frame(name_group); r2.pack(fill=tk.X, pady=4)
        ttk.Label(r2, text="后缀:").pack(side=tk.LEFT)
        ttk.Entry(r2, textvariable=self.suffix_var, width=16).pack(side=tk.LEFT, padx=4)

        # 尺寸（输出图片尺寸）
        size_group = ttk.LabelFrame(right, text="输出图片尺寸 (宽/高/百分比)")
        size_group.pack(fill=tk.X, padx=10, pady=8)
        # 尺寸输入：宽、高、百分比
        dims = ttk.Frame(size_group); dims.pack(fill=tk.X, pady=4)
        self.resize_w_var = tk.StringVar()
        self.resize_h_var = tk.StringVar()
        self.resize_p_var = tk.StringVar()
        ttk.Label(dims, text="宽(px):").pack(side=tk.LEFT)
        ttk.Entry(dims, textvariable=self.resize_w_var, width=8).pack(side=tk.LEFT, padx=4)
        ttk.Label(dims, text="高(px):").pack(side=tk.LEFT)
        ttk.Entry(dims, textvariable=self.resize_h_var, width=8).pack(side=tk.LEFT, padx=4)
        ttk.Label(dims, text="百分比(%):").pack(side=tk.LEFT)
        ttk.Entry(dims, textvariable=self.resize_p_var, width=8).pack(side=tk.LEFT, padx=4)

        # 水印样式
        style_group = ttk.LabelFrame(right, text="水印样式")
        style_group.pack(fill=tk.X, padx=10, pady=8)
        self.font_size_var = tk.IntVar(value=24)
        self.color_var = tk.StringVar(value="white")
        self.position_var = tk.StringVar(value="bottom-right")
        r = ttk.Frame(style_group); r.pack(fill=tk.X, pady=4)
        ttk.Label(r, text="字体大小:").pack(side=tk.LEFT)
        ttk.Spinbox(r, from_=8, to=128, textvariable=self.font_size_var, width=6).pack(side=tk.LEFT, padx=4)
        r2 = ttk.Frame(style_group); r2.pack(fill=tk.X, pady=4)
        ttk.Label(r2, text="颜色:").pack(side=tk.LEFT)
        ttk.Entry(r2, textvariable=self.color_var, width=12).pack(side=tk.LEFT, padx=4)
        r3 = ttk.Frame(style_group); r3.pack(fill=tk.X, pady=4)
        ttk.Label(r3, text="位置:").pack(side=tk.LEFT)
        ttk.Combobox(r3, textvariable=self.position_var, values=['top-left', 'top-right', 'bottom-left', 'bottom-right', 'center'], state="readonly", width=14).pack(side=tk.LEFT, padx=4)

        # 操作
        action = ttk.Frame(right)
        action.pack(fill=tk.X, padx=10, pady=12)
        self.start_btn = ttk.Button(action, text="开始导出", command=self.start_export)
        self.start_btn.pack(side=tk.LEFT)

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(right, textvariable=self.status_var).pack(anchor=tk.W, padx=12)

    def _bind_dnd_if_available(self):
        if not DND_AVAILABLE:
            return
        # 在左侧Canvas区域绑定拖拽
        self.canvas.drop_target_register(DND_FILES)
        self.canvas.dnd_bind('<<Drop>>', self._on_drop)

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.list_window, width=event.width)

    def add_files_dialog(self):
        paths = filedialog.askopenfilenames(title="选择图片", filetypes=[("Images", "*.jpg;*.jpeg;*.png;*.tif;*.tiff;*.bmp")])
        if paths:
            self.add_paths(list(paths))

    def add_folder_dialog(self):
        path = filedialog.askdirectory(title="选择文件夹")
        if path:
            files = self._collect_images_in_dir(Path(path))
            self.add_paths(files)

    def _on_drop(self, event):
        data = event.data
        # Windows 路径可能包含空格，tkdnd 用空格分隔，带大括号包裹
        raw = self.root.splitlist(data)
        paths = [Path(p) for p in raw]
        expanded = []
        for p in paths:
            if p.is_dir():
                expanded.extend(self._collect_images_in_dir(p))
            else:
                expanded.append(str(p))
        self.add_paths(expanded)

    def _collect_images_in_dir(self, directory: Path):
        results = []
        for ext in SUPPORTED_EXTS:
            results.extend([str(p) for p in directory.glob(f"**/*{ext}")])
            results.extend([str(p) for p in directory.glob(f"**/*{ext.upper()}")])
        return results

    def add_paths(self, paths):
        added = 0
        for path in paths:
            p = str(Path(path).resolve())
            if p in self.files:
                continue
            if Path(p).suffix.lower() not in SUPPORTED_EXTS:
                continue
            self.files.append(p)
            self._add_thumbnail_item(p)
            added += 1
        if added:
            self.status_var.set(f"已添加 {added} 个文件，总计 {len(self.files)}")

    def _add_thumbnail_item(self, path: str):
        item = ttk.Frame(self.list_frame)
        item.pack(fill=tk.X, padx=8, pady=6)
        # 缩略图
        try:
            im = Image.open(path)
            im.thumbnail((120, 120), Image.LANCZOS)
            photo = ImageTk.PhotoImage(im)
            self.thumbnails[path] = photo
            tk.Label(item, image=photo).pack(side=tk.LEFT)
        except Exception:
            tk.Label(item, text="预览失败", width=16, anchor=tk.CENTER).pack(side=tk.LEFT)

        # 文件名
        name = os.path.basename(path)
        ttk.Label(item, text=name).pack(side=tk.LEFT, padx=8)

        # 删除按钮
        ttk.Button(item, text="移除", command=lambda: self._remove_item(item, path)).pack(side=tk.RIGHT)

    def _remove_item(self, frame, path):
        try:
            frame.destroy()
        except Exception:
            pass
        if path in self.files:
            self.files.remove(path)
        if path in self.thumbnails:
            del self.thumbnails[path]
        self.status_var.set(f"已移除。剩余 {len(self.files)}")

    def clear_files(self):
        for child in list(self.list_frame.children.values()):
            child.destroy()
        self.files.clear()
        self.thumbnails.clear()
        self.status_var.set("已清空列表")

    def choose_output_dir(self):
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self.output_dir_var.set(path)

    def choose_font_file(self):
        path = filedialog.askopenfilename(title="选择字体文件", filetypes=[("Fonts", "*.ttf;*.otf")])
        if path:
            self.font_path_var.set(path)

    def choose_logo_file(self):
        path = filedialog.askopenfilename(title="选择Logo图片", filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.bmp;*.tif;*.tiff")])
        if path:
            self.logo_path_var.set(path)

    def pick_color(self, var: tk.StringVar):
        try:
            from tkinter import colorchooser
            c = colorchooser.askcolor()
            if c and c[1]:
                var.set(c[1])
        except Exception:
            pass

    def _on_quality_change(self, value):
        try:
            if hasattr(self, 'quality_label') and self.quality_label:
                self.quality_label.config(text=str(int(float(value))))
        except Exception:
            pass

    def start_export(self):
        if not self.files:
            messagebox.showwarning("提示", "请先添加图片文件")
            return
        output_dir = self.output_dir_var.get().strip()
        if not output_dir:
            messagebox.showwarning("提示", "请选择输出目录")
            return

        opts = self._gather_options()

        self.start_btn.config(state=tk.DISABLED)
        self.status_var.set("正在处理，请稍候...")

        def run():
            try:
                self.watermark.process_files(
                    files=self.files,
                    output_dir=opts['output_dir'],
                    font_size=opts['font_size'],
                    color=opts['color'],
                    position=opts['position'],
                    output_format=opts['output_format'],
                    jpeg_quality=opts['jpeg_quality'],
                    name_prefix=opts['name_prefix'],
                    name_suffix=opts['name_suffix'],
                    forbid_export_to_input=(not opts['allow_same_dir']),
                    resize_width=opts['resize_width'],
                    resize_height=opts['resize_height'],
                    resize_percent=opts['resize_percent'],
                    text_content=opts['text_content'],
                    text_color=opts['text_color'],
                    text_opacity=opts['text_opacity'],
                    font_path=opts['font_path'],
                    text_stroke_width=opts['text_stroke_width'],
                    text_stroke_color=opts['text_stroke_color'],
                    text_shadow=opts['text_shadow'],
                    text_shadow_offset=opts['text_shadow_offset'],
                    text_shadow_color=opts['text_shadow_color'],
                    text_shadow_opacity=opts['text_shadow_opacity'],
                    logo_path=opts['logo_path'],
                    logo_scale_percent=opts['logo_scale_percent'],
                    logo_width=opts['logo_width'],
                    logo_height=opts['logo_height'],
                    logo_opacity=opts['logo_opacity'],
                )
                self.status_var.set("处理完成")
                messagebox.showinfo("完成", "导出完成！")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {e}")
            finally:
                self.start_btn.config(state=tk.NORMAL)

        threading.Thread(target=run, daemon=True).start()

    def _gather_options(self):
        fmt = self.format_var.get()
        output_format = None if fmt == 'auto' else fmt
        # 尺寸输入
        rw = self.resize_w_var.get().strip()
        rh = self.resize_h_var.get().strip()
        rp = self.resize_p_var.get().strip()
        rw_i = int(rw) if rw.isdigit() else None
        rh_i = int(rh) if rh.isdigit() else None
        try:
            rp_f = float(rp) if rp else None
        except Exception:
            rp_f = None
        return {
            'output_dir': self.output_dir_var.get().strip(),
            'allow_same_dir': bool(self.allow_same_dir_var.get()),
            'output_format': output_format,
            'jpeg_quality': int(self.quality_scale.get()),
            'name_prefix': self.prefix_var.get(),
            'name_suffix': self.suffix_var.get(),
            'resize_width': rw_i,
            'resize_height': rh_i,
            'resize_percent': rp_f,
            'font_size': int(self.font_size_var.get()),
            'color': self.color_var.get().strip() or 'white',
            'position': self.position_var.get(),
            'text_content': self.text_content_var.get().strip() or None,
            'text_color': self.text_color_var.get().strip() or 'white',
            'text_opacity': int(self.text_opacity_scale.get()),
            'font_path': self.font_path_var.get().strip() or None,
            'text_stroke_width': int(self.stroke_width_var.get()),
            'text_stroke_color': self.stroke_color_var.get().strip() or 'black',
            'text_shadow': bool(self.shadow_var.get()),
            'text_shadow_offset': int(self.shadow_offset_var.get()),
            'text_shadow_color': self.shadow_color_var.get().strip() or 'black',
            'text_shadow_opacity': int(self.shadow_opacity_scale.get()),
            'logo_path': self.logo_path_var.get().strip() or None,
            'logo_scale_percent': float(self.logo_scale_var.get()) if self.logo_scale_var.get().strip() else None,
            'logo_width': int(self.logo_w_var.get()) if self.logo_w_var.get().strip().isdigit() else None,
            'logo_height': int(self.logo_h_var.get()) if self.logo_h_var.get().strip().isdigit() else None,
            'logo_opacity': int(self.logo_opacity_scale.get()),
        }

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = WatermarkGUI()
    app.run()


