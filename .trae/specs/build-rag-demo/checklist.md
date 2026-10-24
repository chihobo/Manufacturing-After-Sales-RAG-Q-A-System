# Checklist

- [x] 内置示例手册覆盖 3 个型号（A-160 / B-200 / C-320）、故障代码表、A-160 新旧版本（active/archived）冲突样例，且含跨型号不同取值的安全参数
- [x] 解析切块保留真实页码标记，表格整块成 chunk 且表头完整，每条 chunk 的 metadata 六字段（chunk_id / doc / model / page / version / status）无空值
- [x] FAISS 向量与 chunks.json 按全局下标一一对应，持久化产物（kb.faiss / chunks.json / bm25.pkl）可离线加载复用
- [x] 型号识别：词表校验防数值误判、别名与归一化生效、故障代码与型号词表分离不串
- [x] Pre-filtering：单型号限定检索、无型号全库检索并列展示、多型号并集对比，active 版本优先于 archived
- [x] 混合检索双路 top20 合并去重后经 rerank 精排取 top10，语义问题与故障代码精确查询两类场景均召回正确
- [x] 答案强制携带 `[来源：手册名 P页码]` 引用且页码与 metadata 一致，检索无果时拒答不编造
- [x] 故障代码类答案固定附带"请与手册原件核对代码字样"
- [x] POST /ask 返回 answer + sources（doc / page / model），GET /health 反映索引加载状态，/docs 可调试
- [x] Streamlit 问答页可完成提问-回答-来源展示闭环
- [x] Streamlit 上传入口可上传 Markdown 手册并完成增量入库，入库后新型号问题可答
- [x] 评估脚本可运行，输出故障代码 / 操作 / 参数三类正确率与总正确率
- [x] `python -m pytest tests/ -q` 在无 API key、无网络环境下全量通过
- [x] 代码注释为中文 UTF-8、无 emoji，无 fallback / 旧兼容逻辑
