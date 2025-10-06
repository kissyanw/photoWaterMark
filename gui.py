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
        # 配置文件路径
        self._templates_path = Path(__file__).with_name("templates.json")
        self._last_settings_path = Path(__file__).with_name("last_settings.json")

        self.files = []  # 存储文件的绝对路径
        self.thumbnails = {}  # 防止被GC: path -> PhotoImage

        self._build_layout()
        self._bind_dnd_if_available()
        # 尝试加载上次设置或默认模板
        try:
            self._load_last_settings_or_default()
        except Exception:
            pass
        # 关闭时保存当前设置
        try:
            self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        except Exception:
            pass

    def _build_layout(self):
        # 使用可分割面板，左右可拖拽调整
        self.paned = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True)

        # 左侧：预览 + 文件区（拖拽/列表/按钮）
        left = ttk.Frame(self.paned)
        self.paned.add(left, weight=2)
        left.pack_propagate(False)

        # 预览区域
        # 左侧内部使用水平分割：左侧预览，右侧工作栏（列表/按钮）
        self.lpane = ttk.Panedwindow(left, orient=tk.HORIZONTAL)
        self.lpane.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        prev_wrap = ttk.Frame(self.lpane)
        self.lpane.add(prev_wrap, weight=1)
        work_panel = ttk.Frame(self.lpane)
        self.lpane.add(work_panel, weight=1)
        ttk.Label(prev_wrap, text="预览（可拖拽水印）").pack(anchor=tk.W)
        self.preview_canvas = tk.Canvas(prev_wrap, width=540, height=360, bg="#333", highlightthickness=1, highlightbackground="#ddd")
        self.preview_canvas.pack(fill=tk.BOTH, expand=True)
        self.preview_canvas.bind("<Button-1>", self._on_preview_mouse_down)
        self.preview_canvas.bind("<B1-Motion>", self._on_preview_mouse_drag)
        self.preview_canvas.bind("<ButtonRelease-1>", self._on_preview_mouse_up)
        self._dragging = False
        self._last_preview_tk = None  # PhotoImage for canvas
        self.selected_file = None
        self.manual_pos_rel = (0.0, 0.0)  # 相对坐标(0-1)，始终可拖动
        self._has_manual = False  # 是否使用手动定位（拖动后生效，选择预设则清空）
        self._preview_box = None  # (x0, y0, w, h) 图像在画布中的区域

        hint = ttk.Label(work_panel, text=(
            "将图片或文件夹拖拽到下方列表，或使用按钮添加\n"
            f"支持格式：{', '.join(sorted(e.upper().lstrip('.') for e in SUPPORTED_EXTS))}"
        ))
        hint.pack(pady=4)

        # 可滚动缩略图容器
        self.canvas = tk.Canvas(work_panel, borderwidth=0, highlightthickness=1, highlightbackground="#ddd")
        self.scroll = ttk.Scrollbar(work_panel, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.list_frame = ttk.Frame(self.canvas)
        self.list_window = self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.list_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        btn_bar = ttk.Frame(work_panel)
        btn_bar.pack(fill=tk.X, pady=8)
        ttk.Button(btn_bar, text="添加文件", command=self.add_files_dialog).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_bar, text="添加文件夹", command=self.add_folder_dialog).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_bar, text="清空列表", command=self.clear_files).pack(side=tk.LEFT, padx=4)

        # 右侧：设置区
        # 右侧改为可滚动面板，置于分割面板右侧
        right_wrap = ttk.Frame(self.paned)
        self.paned.add(right_wrap, weight=1)
        right_canvas = tk.Canvas(right_wrap, borderwidth=0, highlightthickness=0)
        right_scroll = ttk.Scrollbar(right_wrap, orient=tk.VERTICAL, command=right_canvas.yview)
        right_canvas.configure(yscrollcommand=right_scroll.set)
        right_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        right = ttk.Frame(right_canvas)
        self._right_window = right_canvas.create_window((0, 0), window=right, anchor="nw")
        def _on_right_config(event):
            right_canvas.configure(scrollregion=right_canvas.bbox("all"))
            # 固定右侧面板宽度
            right_canvas.itemconfig(self._right_window, width=event.width)
        right.bind("<Configure>", _on_right_config)
        def _on_right_canvas(event):
            right_canvas.configure(scrollregion=right_canvas.bbox("all"))
            # 让右侧随父容器分配的宽度伸缩，不再强制最小宽度
            right_canvas.itemconfig(self._right_window, width=event.width)
        right_canvas.bind("<Configure>", _on_right_canvas)
        # 默认始终添加 EXIF 文本；下方可选添加自定义文本与Logo
        wm_group = ttk.LabelFrame(right, text="EXIF 水印")
        wm_group.pack(fill=tk.X, padx=10, pady=8)
        ttk.Label(wm_group, text="默认会添加 EXIF 时间文本。可选：再添加自定义文本与图片Logo。").pack(anchor=tk.W)

        # 文本水印设置
        text_group = ttk.LabelFrame(right, text="文本水印")
        text_group.pack(fill=tk.X, padx=10, pady=8)
        self.text_content_var = tk.StringVar()
        tr = ttk.Frame(text_group); tr.pack(fill=tk.X, pady=4)
        ttk.Label(tr, text="文本:").pack(side=tk.LEFT)
        ttk.Entry(tr, textvariable=self.text_content_var, width=28).pack(side=tk.LEFT, padx=4)
        tsz = ttk.Frame(text_group); tsz.pack(fill=tk.X, pady=4)
        ttk.Label(tsz, text="字体大小:").pack(side=tk.LEFT)
        self.text_font_size_var = tk.IntVar(value=24)
        ttk.Spinbox(tsz, from_=8, to=128, textvariable=self.text_font_size_var, width=6).pack(side=tk.LEFT, padx=4)
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

        # 图片水印设置
        logo_group = ttk.LabelFrame(right, text="图片水印")
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

        # EXIF 水印
        style_group = ttk.LabelFrame(right, text="EXIF 水印")
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
        ttk.Button(r2, text="调色盘", command=lambda: self.pick_color(self.color_var)).pack(side=tk.LEFT)
        r3 = ttk.Frame(style_group); r3.pack(fill=tk.X, pady=4)
        ttk.Label(r3, text="位置:").pack(side=tk.LEFT)
        ttk.Combobox(r3, textvariable=self.position_var, values=['top-left', 'top', 'top-right', 'left', 'center', 'right', 'bottom-left', 'bottom', 'bottom-right'], state="readonly", width=14).pack(side=tk.LEFT, padx=4)
        # 九宫格快捷按钮
        grid = ttk.Frame(style_group); grid.pack(fill=tk.X, pady=4)
        def set_pos(p):
            self.position_var.set(p)
            self._has_manual = False
            self.update_preview()
        for row, labels in enumerate([
            ['top-left', 'top', 'top-right'],
            ['left', 'center', 'right'],
            ['bottom-left', 'bottom', 'bottom-right']
        ]):
            fr = ttk.Frame(grid); fr.pack()
            for lab in labels:
                ttk.Button(fr, text=lab, width=10, command=lambda v=lab: set_pos(v)).pack(side=tk.LEFT, padx=2)

        # 旋转控制
        rot_group = ttk.LabelFrame(right, text="变换")
        rot_group.pack(fill=tk.X, padx=10, pady=8)
        rr = ttk.Frame(rot_group); rr.pack(fill=tk.X, pady=4)
        ttk.Label(rr, text="旋转(°):").pack(side=tk.LEFT)
        self.rotation_var = tk.IntVar(value=0)
        self.rotation_scale = ttk.Scale(rr, from_=-180, to=180, orient=tk.HORIZONTAL, command=lambda v: self.update_preview())
        self.rotation_scale.set(0)
        self.rotation_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        # 操作
        action = ttk.Frame(right)
        action.pack(fill=tk.X, padx=10, pady=12)
        self.start_btn = ttk.Button(action, text="开始导出", command=self.start_export)
        self.start_btn.pack(side=tk.LEFT)

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(right, textvariable=self.status_var).pack(anchor=tk.W, padx=12)

        # 模板管理
        tpl_group = ttk.LabelFrame(right, text="模板管理")
        tpl_group.pack(fill=tk.X, padx=10, pady=8)
        tpl_row1 = ttk.Frame(tpl_group); tpl_row1.pack(fill=tk.X, pady=4)
        ttk.Label(tpl_row1, text="模板:").pack(side=tk.LEFT)
        self.template_choice_var = tk.StringVar()
        self.template_combo = ttk.Combobox(tpl_row1, textvariable=self.template_choice_var, state="readonly", width=22)
        self.template_combo.pack(side=tk.LEFT, padx=4)
        ttk.Button(tpl_row1, text="加载", command=self._load_selected_template).pack(side=tk.LEFT, padx=2)
        tpl_row2 = ttk.Frame(tpl_group); tpl_row2.pack(fill=tk.X, pady=4)
        ttk.Button(tpl_row2, text="保存为模板", command=self._save_as_template).pack(side=tk.LEFT)
        ttk.Button(tpl_row2, text="删除", command=self._delete_selected_template).pack(side=tk.LEFT, padx=6)
        ttk.Button(tpl_row2, text="设为默认", command=self._set_default_template).pack(side=tk.LEFT)
        # 初始化模板下拉
        self._refresh_template_combo()

        # 绑定值变化实时预览
        self._bind_live_updates()
        # 窗口尺寸变化时重绘预览
        try:
            self.root.bind('<Configure>', lambda e: self.update_preview())
        except Exception:
            pass
        # 初始设置分割条位置：预览canvas、工作区、工具栏三等分
        # 分两步进行：先设置主分割，再在尺寸刷新后设置左侧内部的分割
        def _set_main_split():
            try:
                self.root.update_idletasks()
                pw = max(1, self.paned.winfo_width())
                # 主分割：左侧(预览+工作区)=2/3，右侧(工具栏)=1/3
                self.paned.sashpos(0, int(pw * (2/3)))
            except Exception:
                pass

        def _set_left_split():
            try:
                self.root.update_idletasks()
                lw = max(1, self.lpane.winfo_width())
                # 左侧次分割：预览 与 工作区 各 1/2（总体各 1/3）
                self.lpane.sashpos(0, int(lw * 0.5))
            except Exception:
                pass

        # 设定为 1:1:1：先设主分割到 2/3，再在下一帧与稍后各设一次左分割为 1/2
        self.root.after_idle(_set_main_split)
        self.root.after(10, _set_left_split)
        self.root.after(120, _set_main_split)
        self.root.after(130, _set_left_split)

    def _bind_dnd_if_available(self):
        if not DND_AVAILABLE:
            return
        # 在左侧Canvas区域绑定拖拽
        self.canvas.drop_target_register(DND_FILES)
        self.canvas.dnd_bind('<<Drop>>', self._on_drop)

    # ------- 模板持久化 -------
    def _read_templates_store(self):
        try:
            if self._templates_path.exists():
                import json
                with open(self._templates_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict) and 'templates' in data:
                    return data
        except Exception:
            pass
        return {"default": None, "templates": {}}

    def _write_templates_store(self, data):
        try:
            import json
            with open(self._templates_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _refresh_template_combo(self):
        store = self._read_templates_store()
        names = sorted(list(store.get('templates', {}).keys()))
        self.template_combo['values'] = names
        # 若存在默认模板，选中默认
        default_name = store.get('default')
        if default_name in names:
            self.template_choice_var.set(default_name)
        elif names:
            self.template_choice_var.set(names[0])
        else:
            self.template_choice_var.set("")

    def _save_as_template(self):
        try:
            from tkinter import simpledialog
            name = simpledialog.askstring("保存为模板", "请输入模板名称:", parent=self.root)
        except Exception:
            name = None
        if not name:
            return
        store = self._read_templates_store()
        opts = self._gather_options()
        store.setdefault('templates', {})[name] = opts
        # 若之前无默认模板，则将第一个保存的模板设为默认
        if not store.get('default'):
            store['default'] = name
        self._write_templates_store(store)
        self._refresh_template_combo()
        self.status_var.set(f"模板已保存：{name}")

    def _load_selected_template(self):
        name = self.template_choice_var.get().strip()
        if not name:
            return
        store = self._read_templates_store()
        tpl = store.get('templates', {}).get(name)
        if not tpl:
            return
        self._apply_options(tpl)
        self.status_var.set(f"模板已加载：{name}")

    def _delete_selected_template(self):
        name = self.template_choice_var.get().strip()
        if not name:
            return
        store = self._read_templates_store()
        if name in store.get('templates', {}):
            del store['templates'][name]
            if store.get('default') == name:
                store['default'] = None
            self._write_templates_store(store)
            self._refresh_template_combo()
            self.status_var.set(f"模板已删除：{name}")

    def _set_default_template(self):
        name = self.template_choice_var.get().strip()
        if not name:
            return
        store = self._read_templates_store()
        if name in store.get('templates', {}):
            store['default'] = name
            self._write_templates_store(store)
            self.status_var.set(f"已设为默认模板：{name}")

    def _load_last_settings_or_default(self):
        # 尝试加载最近设置
        try:
            import json
            if self._last_settings_path.exists():
                with open(self._last_settings_path, 'r', encoding='utf-8') as f:
                    last = json.load(f)
                if isinstance(last, dict):
                    self._apply_options(last)
                    return
        except Exception:
            pass
        # 否则加载默认模板
        store = self._read_templates_store()
        default_name = store.get('default')
        if default_name:
            tpl = store.get('templates', {}).get(default_name)
            if isinstance(tpl, dict):
                self._apply_options(tpl)

    def _on_close(self):
        # 保存最近设置
        try:
            import json
            opts = self._gather_options()
            with open(self._last_settings_path, 'w', encoding='utf-8') as f:
                json.dump(opts, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

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
        lab = ttk.Label(item, text=name)
        lab.pack(side=tk.LEFT, padx=8)
        def on_select(*_):
            self.selected_file = path
            self.update_preview()
        item.bind("<Button-1>", on_select)
        lab.bind("<Button-1>", on_select)

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
                # 计算导出时的手动相对坐标直接传递
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
                    text_font_size=opts['text_font_size'],
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
                    rotation_angle=opts['rotation_angle'],
                    use_manual_position=opts['use_manual_position'],
                    manual_pos_rel=opts['manual_pos_rel'],
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
            'text_font_size': int(self.text_font_size_var.get()),
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
            'rotation_angle': int(float(self.rotation_scale.get())),
            'use_manual_position': bool(self._has_manual),
            'manual_pos_rel': self.manual_pos_rel,
        }

    def _apply_options(self, opts: dict):
        # 将字典中的值填回控件（若缺失则跳过）
        try:
            # 输出设置
            if 'output_dir' in opts: self.output_dir_var.set(opts['output_dir'] or '')
            if 'allow_same_dir' in opts: self.allow_same_dir_var.set(bool(opts['allow_same_dir']))
            if 'output_format' in opts:
                self.format_var.set(opts['output_format'] or 'auto')
            if 'jpeg_quality' in opts:
                self.quality_scale.set(int(opts['jpeg_quality']))
                if hasattr(self, 'quality_label'):
                    self.quality_label.config(text=str(int(opts['jpeg_quality'])))
            if 'name_prefix' in opts: self.prefix_var.set(opts['name_prefix'] or '')
            if 'name_suffix' in opts: self.suffix_var.set(opts['name_suffix'] or '')

            # 尺寸
            if 'resize_width' in opts: self.resize_w_var.set('' if opts['resize_width'] is None else str(opts['resize_width']))
            if 'resize_height' in opts: self.resize_h_var.set('' if opts['resize_height'] is None else str(opts['resize_height']))
            if 'resize_percent' in opts:
                rp = opts['resize_percent']
                self.resize_p_var.set('' if rp is None else (str(int(rp)) if float(rp).is_integer() else str(rp)))

            # EXIF 文本
            if 'font_size' in opts: self.font_size_var.set(int(opts['font_size']))
            if 'color' in opts: self.color_var.set(opts['color'] or 'white')
            if 'position' in opts: self.position_var.set(opts['position'] or 'bottom-right')

            # 文本水印
            if 'text_content' in opts: self.text_content_var.set(opts['text_content'] or '')
            if 'text_font_size' in opts: self.text_font_size_var.set(int(opts['text_font_size']))
            if 'text_color' in opts: self.text_color_var.set(opts['text_color'] or 'white')
            if 'text_opacity' in opts: self.text_opacity_scale.set(int(opts['text_opacity']))
            if 'font_path' in opts: self.font_path_var.set(opts['font_path'] or '')
            if 'text_stroke_width' in opts: self.stroke_width_var.set(int(opts['text_stroke_width']))
            if 'text_stroke_color' in opts: self.stroke_color_var.set(opts['text_stroke_color'] or 'black')
            if 'text_shadow' in opts: self.shadow_var.set(bool(opts['text_shadow']))
            if 'text_shadow_offset' in opts: self.shadow_offset_var.set(int(opts['text_shadow_offset']))
            if 'text_shadow_color' in opts: self.shadow_color_var.set(opts['text_shadow_color'] or 'black')
            if 'text_shadow_opacity' in opts: self.shadow_opacity_scale.set(int(opts['text_shadow_opacity']))

            # 图片水印
            if 'logo_path' in opts: self.logo_path_var.set(opts['logo_path'] or '')
            if 'logo_scale_percent' in opts:
                lsp = opts['logo_scale_percent']
                self.logo_scale_var.set('' if lsp is None else (str(int(lsp)) if float(lsp).is_integer() else str(lsp)))
            if 'logo_width' in opts: self.logo_w_var.set('' if opts['logo_width'] is None else str(opts['logo_width']))
            if 'logo_height' in opts: self.logo_h_var.set('' if opts['logo_height'] is None else str(opts['logo_height']))
            if 'logo_opacity' in opts: self.logo_opacity_scale.set(int(opts['logo_opacity']))

            # 变换
            if 'rotation_angle' in opts: self.rotation_scale.set(int(opts['rotation_angle']))

            # 手动坐标
            if 'use_manual_position' in opts: self._has_manual = bool(opts['use_manual_position'])
            if 'manual_pos_rel' in opts and isinstance(opts['manual_pos_rel'], (list, tuple)) and len(opts['manual_pos_rel']) == 2:
                self.manual_pos_rel = (float(opts['manual_pos_rel'][0]), float(opts['manual_pos_rel'][1]))

            # 应用后刷新预览
            self.update_preview()
        except Exception:
            pass

    # ------- 实时预览 -------
    def _bind_live_updates(self):
        def bind_var(var):
            if hasattr(var, 'trace_add'):
                var.trace_add('write', lambda *a: self.update_preview())
        for v in [self.text_content_var, self.text_color_var, self.font_path_var, self.stroke_color_var, self.shadow_color_var,
                  self.logo_path_var, self.logo_scale_var, self.logo_w_var, self.logo_h_var, self.prefix_var, self.suffix_var,
                  self.resize_w_var, self.resize_h_var, self.resize_p_var, self.color_var, self.position_var]:
            bind_var(v)
        # Scales don't use trace; we already bound rotation and opacity labels; bind update
        self.text_opacity_scale.configure(command=lambda v: self.update_preview())
        self.shadow_opacity_scale.configure(command=lambda v: self.update_preview())
        self.logo_opacity_scale.configure(command=lambda v: self.update_preview())

    def _on_preview_mouse_down(self, event):
        self._dragging = True
        self._has_manual = True
        self._update_manual_pos_from_canvas(event.x, event.y)

    def _on_preview_mouse_drag(self, event):
        if not self._dragging:
            return
        self._update_manual_pos_from_canvas(event.x, event.y)

    def _on_preview_mouse_up(self, event):
        self._dragging = False

    def _update_manual_pos_from_canvas(self, cx, cy):
        # 转为图像内容内的相对坐标
        if not self._preview_box:
            return
        x0, y0, iw, ih = self._preview_box
        rx = max(0.0, min(1.0, (cx - x0) / max(1, iw)))
        ry = max(0.0, min(1.0, (cy - y0) / max(1, ih)))
        self.manual_pos_rel = (rx, ry)
        self.update_preview()


    def update_preview(self):
        if not self.selected_file:
            self.preview_canvas.delete("all")
            return
        # 构造参数并渲染
        opts = self._gather_options()
        try:
            # 按导出尺寸逻辑先对原图缩放
            im = Image.open(self.selected_file)
            # 应用导出尺寸（与导出一致）
            rw = opts['resize_width']; rh = opts['resize_height']; rp = opts['resize_percent']
            if rw or rh or rp:
                try:
                    disp_src = self.watermark.apply_resize(im, width=rw, height=rh, percent=rp)
                except Exception:
                    disp_src = im
            else:
                disp_src = im

            # 再将导出图缩放以适配预览画布（等比，留边）
            cw = int(self.preview_canvas.winfo_width()) or 540
            ch = int(self.preview_canvas.winfo_height()) or 360
            w, h = disp_src.size
            scale = min(cw / w, ch / h)
            nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
            x = (cw - nw) // 2
            y = (ch - nh) // 2
            base = Image.new('RGBA', (cw, ch), (51, 51, 51, 255))
            prev_img = disp_src.resize((nw, nh), Image.LANCZOS)
            self._preview_box = (x, y, nw, nh)

            # 手动坐标换算为“缩放后图片内”的像素坐标
            mrel = opts['manual_pos_rel'] if opts['use_manual_position'] else None
            if mrel and self._preview_box:
                _, _, bw, bh = self._preview_box
                mx_img, my_img = int(mrel[0] * bw), int(mrel[1] * bh)
            else:
                mx_img = my_img = None

            # 只在缩放后的图片上绘制水印，然后粘贴到背景
            rendered = self.watermark.add_watermark_to_image(
                prev_img,
                image_path=self.selected_file,
                font_size=opts['font_size'],
                color=opts['color'],
                position=opts['position'],
                text_content=opts['text_content'],
                text_font_size=opts['text_font_size'],
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
                rotation_angle=opts['rotation_angle'],
                use_manual_position=opts['use_manual_position'],
                manual_xy=(mx_img, my_img) if mx_img is not None else None,
            )
            if rendered.mode != 'RGBA':
                rendered = rendered.convert('RGBA')
            base.alpha_composite(rendered, dest=(x, y))
            disp = base
            self._last_preview_tk = ImageTk.PhotoImage(disp)
            self.preview_canvas.delete("all")
            self.preview_canvas.create_image(0, 0, anchor=tk.NW, image=self._last_preview_tk)
        except Exception:
            pass

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = WatermarkGUI()
    app.run()


