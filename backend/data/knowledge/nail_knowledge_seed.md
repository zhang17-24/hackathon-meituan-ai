# 美甲专业知识种子库

该文件用于补充 nailflow 的美甲 RAG 知识侧数据，内容整理自公开网页，便于后续转成标签体系、门店 SOP 和 prompt 增强。

## 指甲结构与前处理

指甲护理和上色前应重视甲板、甲床、甲小皮的结构差异，避免过度泡水和过度修剪角质层，以提升附着力并降低感染风险。

- 指甲由甲板、甲床和甲母质等部分构成，角质层不应被整圈深度剪除，否则会增加感染风险。
- 做美甲前应先去除旧甲油、软化角质层、推后角质层、轻微抛磨，再用酒精或卸甲产品去油。
- 泡水会让甲板暂时吸水膨胀，若在含水状态下上色，后续更容易崩边。
- 抛磨建议使用细目数缓冲条，过低目数会增加甲板损伤风险。

来源：
- The perfect at home DIY manicure!: https://www.essie.com/inspiration/tips-and-trends/how-to-prep-nail-for-manicure

## 常见甲型与适配规则

甲型选择要结合自然甲床宽度、长度和风格诉求，不同甲型在稳定性、显手长和维护成本上差异明显。

- 方形甲稳定性较高，适合短甲床或窄甲面，也适用于短甲和长甲。
- Squoval 兼具方形与椭圆的优点，普适性强，适合大多数日常款式库冷启动。
- 圆形甲最自然、低维护，适合通勤和基础纯色款。
- 椭圆甲和杏仁甲更显手指修长，但对长度和边缘强度要求更高。
- 芭蕾甲适合中长到长甲，适合高级感、韩系、婚礼和装饰型风格。

来源：
- how to choose the right nail shape for you: https://www.essie.com/inspiration/nail-shapes
- How to Shape Nails: https://www.opi.com/professionals/how-to-shape-nails

## 底胶、色胶、封层与质感

标准流程通常由底层附着、颜色层表达和封层保护构成，顶部质感决定成品风格与维护周期。

- 底胶的主要作用是增强附着力和防染色，纯色、法式、猫眼、渐变都建议建立稳定底层。
- 颜色层通常需要 2 层表达主色，适合在 metadata 中记录主色、辅色、透明度与饱和度。
- 封层可分高光、哑光等质感，适合作为检索字段 finish。
- 光泽、磨砂、果冻、镜面、猫眼、亮片等质感应独立于图案类型记录，避免都挤进 category。

来源：
- The perfect at home DIY manicure!: https://www.essie.com/inspiration/tips-and-trends/how-to-prep-nail-for-manicure

## 美甲化学品与通风安全

美甲场景涉及多种挥发性和刺激性化学品，通风、本地排风、容器密封和 SDS 管理是门店与培训知识库的重要组成。

- 常见风险化学品包括 acetone、ethyl acetate、formaldehyde、toluene、EMA、MMA 等。
- OSHA 将 toluene、formaldehyde、dibutyl phthalate 归为行业常提到的 toxic trio。
- 通风是降低暴露的首选措施，本地排风、下吸式工作台和持续 HVAC 运行都能降低暴露。
- SDS 应随产品提供并便于技师获取，店内应保留危害信息、储存与应急处理说明。
- 手术口罩不能替代针对化学蒸汽的呼吸防护。

来源：
- Health Hazards in Nail Salons - Chemical Hazards: https://www.osha.gov/nail-salons/chemical-hazards
- Nail Technicians: Workplace Safety and Health: https://www.cdc.gov/niosh/nail-technicians/about/index.html

## 感染控制与工具消毒

美甲知识库不应只有款式，还应覆盖感染控制。对有创处理、感染指甲、出血情况的判断会直接影响门店 SOP。

- 若客户存在开放性伤口、起泡、明显感染或渗血，通常不应继续常规美甲服务。
- 工具应在每位客户后清洗并按说明浸泡 EPA 注册消毒剂，之后冲洗、擦干、洁净存储。
- UV 盒适合存放已完成清洁消毒的金属工具，但本身不等于完整消毒流程。
- 员工若可能接触血液或其他潜在感染物，应遵循 bloodborne pathogens 相关要求。

来源：
- Health Hazards in Nail Salons - Biological Hazards: https://www.osha.gov/nail-salons/biological-hazards

## 适合 RAG / 检索的美甲标签体系建议

为了让向量检索与过滤稳定工作，款式图应至少按颜色、图案、质感、甲型、长度、场景、风格做多维标签。

- 颜色字段建议拆成 base_color、accent_color、color_group、saturation、brightness。
- 图案字段建议拆成 pattern_type、pattern_density、pattern_layout、accent_finger。
- 质感字段建议单独记录 finish 或 texture，如 glossy、matte、jelly、cat_eye、chrome、glitter。
- 形态字段建议记录 nail_shape、length、natural_or_extension。
- 风格字段建议记录 style_genre、occasion、season、complexity，便于个性化推荐与 prompt 增强。

来源：
- Internal synthesis from fetched manicure guidance: https://www.essie.com/inspiration/nail-shapes
