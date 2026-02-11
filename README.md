# paperReaderX

论文X光机 Web 版 — 上传 PDF，自动生成三语言（EN/JA/ZH）X-ray 分析报告，支持 PDF 在线阅读和基于论文的 AI 对话。

基于 [lijigang/ljg-skill-xray-paper](https://github.com/lijigang/ljg-skill-xray-paper) 的 Claude Code Skill 扩展开发，新增 Web 前端。

## 功能

- 支持 PDF 路径、文本内容或论文链接输入
- 认知提取算法：去噪 → 提取 → 批判
- 五维分析：核心痛点、解题机制、创新增量、批判性边界、餐巾纸公式
- 生成 Org-mode 格式报告，含 ASCII 逻辑流程图

## 安装

```bash
/plugin marketplace add lijigang/ljg-skill-xray-paper
/plugin install ljg-xray-paper
```

## 使用

在 Claude Code 中输入：

```
/ljg-xray-paper <论文PDF路径、URL或粘贴内容>
```

## 输出示例

生成的 Org-mode 报告包含：

- **NAPKIN FORMULA** — 餐巾纸公式，一句话浓缩核心
- **PROBLEM** — 痛点定义与前人困境
- **INSIGHT** — 作者的灵光一闪
- **DELTA** — 相比 SOTA 的创新增量
- **CRITIQUE** — 隐形假设与未解之谜
- **LOGIC FLOW** — ASCII 逻辑结构图
- **NAPKIN SKETCH** — ASCII 餐巾纸图

## Credits

- 原始 Skill 插件：[lijigang/ljg-skill-xray-paper](https://github.com/lijigang/ljg-skill-xray-paper)（分析 prompt 和模板源自此项目）

## License

MIT
