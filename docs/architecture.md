# V1 实施决策

## 保留的规格约束

Python 计算、LLM 解释；风控最终否决；结构化输入与输出；金额 Decimal；带时区时间；证据来源；每日快照；推荐与结果独立持久化；不连接任何下单接口。按 spec.md 的 12 个里程碑推进，每阶段通过测试再继续。

## 针对大陆公募基金的调整

- CNY / Asia/Shanghai；场外基金代码保留前导零，A/C、人民币/美元份额不能混用。
- 基金 NAV 是估值参考，不是成交报价。单位净值用于资产估值；由数据源日增长率链式生成的总回报指数用于收益、回撤、相关性，不能把累计净值当复权净值。
- 截图记录允许缺失代码、份额、日期、现金；缺失不是零，也不能反推份额。未核实记录只展示与观察。
- QDII 净值披露允许更长延迟。鲜度使用工作日近似并明确标注；法定节假日可导入基金估值日历，未知日历宁可阻止建议，不延长数据有效期。
- 公募基金短期信号仅用于观察。申购/赎回状态、限额、持有期、费率来源未确认时不生成对应买卖金额。赎回到账不计作当日可用现金。
- 行业标签是人工分类，用于粗粒度主题风险；不声称是基金实时底层持仓穿透。
- 本地默认 SQLite，金额以十进制文本准确存储；正式环境 PostgreSQL NUMERIC / TIMESTAMPTZ，使用 Alembic 迁移。单用户无需微服务和组合优化器。
- 第一个行情适配器直接读取 AKShare 使用的东方财富公开源，以 httpx 统一超时、重试与解析；不执行远程 JavaScript。保留 Protocol 替换接口。
- 新闻失效、缺失宏观数据、未设置模型密钥都显式显示 PARTIAL；不能静默填入中性分数或伪造证据。
- 初始候选池为空，由用户批准后导入；截图中的基金属于持仓范围，无需让 LLM 扩展候选池。

## 数据与安全

用户原图、持仓文件、数据库及报告默认忽略提交。网页和 LLM 文本视为不可信内容；结构化校验不接受动作、金额等越权字段。新闻引用必须来自搜索返回的来源集合，未能核实发布时间或未匹配基金范围的内容不进入信号。

## 接口依据

- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)：使用 Responses API 与 Pydantic 验证。
- [OpenAI Web Search](https://developers.openai.com/api/docs/guides/tools-web-search)：保留工具返回的来源 URL，用于核查研究输出。
- [AKShare 公募基金适配器源码](https://github.com/akfamily/akshare/blob/main/akshare/fund/fund_em.py)：东方财富净值源字段映射。

以上来源用于接口实现；并不构成对截图资产的当前投资判断。
