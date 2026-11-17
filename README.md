# 农产品残留限量版本与复检裁决

面向农产品检测站复核员，处理采信、判定、核算、复核与归档。

## 启动

```bash
docker compose up --build -d
```

访问 http://localhost:18254 。初次启动自动运行脏样例，可切换 clean.csv 与 legacy.csv。顶部“运行批次”会重新计算，同源输入复用批次。

## 业务模块

- 报告采信：`/m1_ingest`、`/api/m1_ingest`
- 项目映射：`/m2_mapping`、`/api/m2_mapping`
- 限量选版：`/m3_versions`、`/api/m3_versions`
- 检出量换算：`/m4_segments`、`/api/m4_segments`
- 复检裁决：`/m5_calculate`、`/api/m5_calculate`
- 批次判级：`/m6_reconcile`、`/api/m6_reconcile`
- 报告归档：`/m7_archive`、`/api/m7_archive`
- 修订裁决：`/m8_revision`、`/api/m8_revision`

## 核心规则

按采样日期选择有效限量，低于检出限保留区间；复检不得越过样本关联与方法适用范围。完整数值、边界和异常定义见 `docs/DATA-DICTIONARY.md`。

## 修订裁决

批次签字出证后，上游更正限量版本或同批晚到复检报告时，在 `/m8_revision` 提交更正：更正后限量表经 `parameters.limits_csv` 注入限量选版，晚到报告按原表头对齐追加到原始来源后重跑全流程，两者共同决定项目结论与批次等级。原批记录永不改动，旧签字依据（结论、复核版本、校验签、证据CSV）可核对。

修订号为基批与更正内容的哈希：同一更正重跑返回原记录，不新增版本或重复项目。重跑结果须对账平衡且已签发项目不缺失，否则记为失败修订并留痕，旧版结论保持有效。页面列出项目级变化（结论、限量、采纳报告与成因）与批次升降级原因，失败与生效记录均保留。样例更正见 `sample_data/limits_corrected.csv` 与 `sample_data/retest_late.csv`。

## 验证

```bash
docker compose exec -T app pytest -q
docker compose config --quiet
```

原始样例在 `sample_data/`。测试在 `tests/`。封存文件是单份CSV，含运行清单、计算证据、隔离原因与对账。复核需提交当前版本，陈旧复核返回409。

## 数据与限制

SQLite保存在records命名卷，普通重启与构建不会清除。确认可丢弃本项目数据后，运行 `docker compose down -v` 再启动可重置。单文件上限2MB；不接入外部业务系统；历史规则由本项目样例定义，不代表实际行业标准。
