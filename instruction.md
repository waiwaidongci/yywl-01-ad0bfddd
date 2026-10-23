# 巡检失效数据的非参数生存包络

设备保养组每月抽检一批同型部件，记录抽检时是否已经失效，没有真实失效时刻。工程师需要从这些 current-status 记录恢复单调失效分布、各时间段的概率质量，以及指定月末的生存率；直接使用每个月的原始比例会在噪声下失去单调性。

运行时传入输入表和报告路径：`python3 /app/analyze.py INPUT.json REPORT.json`。`python3 /app/analyze.py --help` 只打印版本、方法、时间单位和退出码；帮助成功不创建文件。

```text
nonparametric-current-status-mle
usage: python3 /app/analyze.py INPUT.json REPORT.json
help: python3 /app/analyze.py --help
time_unit=month
method=weighted-isotonic-cdf
exit=0 success-or-help;3 refusal
```

输入对象由版本、研究号、时间单位、巡查记录和查询月份五部分组成，键名以示例为准。版本栏 `schema_version` 写整数 `1`。研究号 `study_id` 采用 `^CS-[0-9A-F]{4}$`。时间单位 `time_unit` 固定为 `month`。`observations` 的记录总数落在 `36` 到 `60` 之间，月份覆盖 `12` 到 `30` 个不同值。`query_times` 有 `2` 到 `6` 个严格递增且已观测的月份。

一条巡查记录包含记录号、巡检月份与事件标记三个值，键名以示例为准。`record_id` 采用 `^CS-[0-9A-F]{4}-[0-9A-F]{3}$` 且全文唯一；`time` 是 `1` 到 `60` 的整数；`event` 只能取整数 `0` 或 `1`，布尔值不算整数。事件 `1` 表示该月抽检时已失效，`0` 表示尚未失效。

```json
{"schema_version":1,"study_id":"CS-7A31","time_unit":"month","observations":[{"record_id":"CS-1A2B-001","time":3,"event":1}],"query_times":[3,6]}
```

代码块展示记录结构，不是完整批次。UTF-8 JSON 中任何层级出现重复键都拒收。

失效时间的累积分布 `F(t)=P(T<=t)` 必须随 `time` 单调不减。在全部满足该约束的分布中，选取使 current-status 二项似然最大的非参数估计。相邻原始比例发生下降时就要合并成一个受约束块；比例相等也合并，使最终块按 `F` 严格递增。

每个块的 `cdf` 是块内事件数除以检查数，`mass` 是它与前一块 `cdf` 之差。所有概率写成约分后的分子、分母字符串，分母为正且 `gcd` 为 1。`survival` 等于 `1-cdf`。中位区间是第一个 `cdf >= 1/2` 的块；总体分布没有越过中位数时拒收。

报告顶层顺序固定为 `schema_version`、`study_id`、`time_unit`、`blocks`、`queries`、`median_interval`、`log_likelihood`。`blocks` 按起始月份升序，每项恰好有 `start_time`、`end_time`、`events`、`exposed`、`cdf`、`mass` 六栏。`queries` 保持输入月份顺序，每项恰好有 `time`、`cdf`、`survival` 三栏。`median_interval` 恰好有 `start_time`、`end_time`、`cdf` 三栏。`log_likelihood` 是自然对数有限数。

```json
{"schema_version":1,"study_id":"CS-7A31","time_unit":"month","blocks":[{"start_time":1,"end_time":3,"events":4,"exposed":8,"cdf":{"numerator":"1","denominator":"2"},"mass":{"numerator":"1","denominator":"2"}}],"queries":[{"time":3,"cdf":{"numerator":"1","denominator":"2"},"survival":{"numerator":"1","denominator":"2"}}],"median_interval":{"start_time":1,"end_time":3,"cdf":{"numerator":"1","denominator":"2"}},"log_likelihood":-5.2}
```

成功时写紧凑 UTF-8 JSON，末尾一个换行，标准输出和标准错误为空。同一冻结输入重复运行必须得到相同报告字节。

参数、路径、读取、解码、重复键、结构、类型、范围、月份覆盖或求解任一条件不满足时，以状态码 `3` 结束。标准错误只写一行 `survival refused: ` 后接简短原因，标准输出为空，不输出 traceback。拒收不得创建报告，已有报告保持原字节。

公开上限为 `60` 条记录和 `30` 个不同月份；先在入口的 `20` 秒内完成。可能的块划分至少为 `2^29` 种，逐块划分枚举不可作为正常实现。
