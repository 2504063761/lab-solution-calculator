# 材料配制功能的 GitHub 参考记录

1.6.0 摩尔浓度扩展继续核对 SoluForge 的单位源码和计算规则：质量 = 摩尔浓度 × 最终体积 × 摩尔质量，纯料不增加纯度修正。浓度和摩尔质量定义另核对 IUPAC：[amount concentration](https://goldbook.iupac.org/terms/view/A00295)、[molar mass](https://goldbook.iupac.org/terms/view/12214)。实现区分 M 与 mM，并将 g/mol、mg/mol 放在独立摩尔质量栏。

核实日期：2026-10-26。通过 GitHub 连接器读取项目的 README、相关计算源码及可取得的许可证文件。本功能参考下列项目的设计思路，计算代码独立实现，未复制这些项目的源码，也未将它们作为运行依赖。

## 1. SoluForge

- 项目：<https://github.com/MIGO-OvO/SoluForge>
- 单位源码：<https://github.com/MIGO-OvO/SoluForge/blob/main/crates/chemistry-core/src/units.rs>
- 设计与计算规则：<https://github.com/MIGO-OvO/SoluForge/blob/main/README.md>
- 许可证：<https://github.com/MIGO-OvO/SoluForge/blob/main/LICENSE>

已核实：源码将 `% w/w` 定义为质量分数，将 `% w/v` 定义为质量浓度，将 `% v/v` 定义为体积分数。`% w/v` 换算到基准单位 g/L 时的系数为 10，即 1% w/v = 10 g/L；另外两类百分数换算为分数时的系数为 0.01。README 明确区分“定容到最终体积”和“加入等于最终体积的溶剂”，并要求在输入发生变化后使上一次计算结果失效。

本功能参考其单位维度分离、最终体积说明、修改输入后作废旧结果的设计。选择 w/w、w/v、v/v 表示选择不同配制口径；没有密度等必要信息时，不将模式切换表述为同一溶液的等效浓度换算。

许可证实读为 PolyForm Noncommercial License 1.0.0。它是允许特定非商业用途的源码可见许可证，不属于 OSI 认证的开源许可证；商业用途需要另外满足其授权要求。本功能仅参考通用设计思路，未纳入其受许可约束的源码。

## 2. Solution Preparation Calculator

- 项目：<https://github.com/MarkNwilliam/solution-preparation-calculator>
- 计算源码：<https://github.com/MarkNwilliam/solution-preparation-calculator/blob/main/solution_calculator.py>
- 项目说明：<https://github.com/MarkNwilliam/solution-preparation-calculator/blob/main/README.md>

已核实：`smbs(target_l, target_pct)` 按 `质量(g) = 浓度百分数 / 100 × 最终体积(L) × 1000` 计算 w/v 配制所需质量，并在步骤中要求溶解后定容到最终体积。结果表格、配制说明和可复制配制记录分开组织，可以作为本功能输出结构的参考。

该项目部分 v/v 配制分支直接相加溶质和水的体积；这一做法不适合作为通用的精确定容算法，本功能不据此计算实际补水量。w/v、v/v 模式应输出各组分用量与最终定容目标，不能以“最终体积减去溶质质量”计算溶剂体积，也不能无条件假定液体混合前后体积可加。

README 声明许可证为 MIT；本次读取根目录列表时未发现独立 LICENSE 文件，因此该声明与完整独立许可文本的核实状态有所区别。本功能仅参考其计算与呈现分离的思路，未复制代码。

## 本功能采用的计算口径

- w/w：每 100 g 最终混合物中所含的组分质量(g)。按目标最终总质量计算组分质量，余量是需要补足的溶剂质量。
- w/v：每 100 mL 最终混合物中所含的组分质量(g)。按目标最终体积计算称量质量，溶解后补溶剂定容至目标体积。
- v/v：每 100 mL 最终混合物中所含的组分体积(mL)。按目标最终体积计算各组分量取体积，混合后补溶剂定容至目标体积；不默认各液体体积严格可加。

这些是配比和用量计算口径，不额外推断材料溶解度、反应性、稳定性或配制工艺条件。
