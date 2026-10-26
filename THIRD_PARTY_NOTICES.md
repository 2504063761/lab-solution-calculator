# 开源来源

本工具的单菌稀释模块来自 MichaelJLewis98/sub-culturing-volume-calculator，并在分别稀释模式中用于计算每管的原液量和补液量。中文界面、多菌 OD 贡献计算和模板管理为本次新增功能。

- 项目：https://github.com/MichaelJLewis98/sub-culturing-volume-calculator
- 原文件：https://github.com/MichaelJLewis98/sub-culturing-volume-calculator/blob/main/calculator.py
- calculator.py Git blob SHA：caf216ab9c4ece76acb070a9a03ef3520b90c982
- LICENSE Git blob SHA：1f77fea50b7a2f7967a1cb6d392f5b4a974b7e67
- 获取日期：2026-10-12
- 许可：MIT，完整原始许可保存在 LICENSE 中。

upstream/calculator.py 保留原文件内容。所有新增源码以同一 MIT 许可提供。

## 1.3.0 玻璃显示层

玻璃版新增本地 WebView2 显示层，计算和模板模块沿用原文件。下列第三方组件不适用上方的项目 MIT 声明，分别按其上游许可分发，完整许可保存在 `third_party_licenses/`：

- pywebview 6.2.1：BSD 3-Clause，项目 https://github.com/r0x0r/pywebview 。
- pythonnet 3.2.1、clr-loader 0.3.1、bottle 0.13.4：MIT。
- cffi 2.1.1：MIT-0；pycparser 3.11：BSD-3-Clause；typing-extensions 4.16.0：PSF-2.0。
- proxy-tools 0.1.0：包元数据声明 MIT；其源文件注明 Copyright (c) 2013 Armin Ronacher，adapted by Jonathan Tushman 2014，BSD（提取自 Werkzeug）。相应来源与许可一并保留。
- Microsoft.Web.WebView2 SDK 1.0.3856.49：保留该版本 NuGet 包中的 Microsoft 许可；打包的 Core、WinForms 与 Loader 组件按该许可分发。系统 WebView2 Runtime 由 Windows 环境提供，不在本程序中复制或自动安装。

玻璃版所有界面文件随程序离线提供，没有外部字体、图片或脚本地址。运行 EXE 无需 Python；需要本机已有 Microsoft Edge WebView2 Runtime。当前公开发行包仅包含现代 WebView2 版本。

## 1.5.0 材料配制参考
材料计算与存储为独立实现，没有复制参考项目源码，不引入新的运行依赖。GitHub 参考项目为 MIGO-OvO/SoluForge（PolyForm Noncommercial 1.0.0，非 OSI 开源许可）和 MarkNwilliam/solution-preparation-calculator（README 声明 MIT，未发现独立 LICENSE 文件）。具体核实范围、源码链接与未沿用的算法见 GITHUB_REFERENCES.md。参考不改变本工具原有源码许可；参考项目不作为本程序第三方分发组件。

## 1.6.1 标题字标
实验配液计算器的七字标题使用 ZCOOL XiaoWei Regular 字形转为矢量路径，再调整字距、比例与深蓝切面效果。Copyright 2018 The ZCOOL XiaoWei Project Authors；SIL Open Font License 1.1。字体及字标不适用本项目的 MIT 声明，完整许可保存在 third_party_licenses/ZCOOLXiaoWei-OFL.txt。程序只内置七字 SVG，不需要系统安装字体。来源：https://github.com/google/fonts/tree/main/ofl/zcoolxiaowei 。

