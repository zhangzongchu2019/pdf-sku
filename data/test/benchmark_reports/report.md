# Benchmark 对比报告

## 汇总

| 数据集 | 期望 | 实际 | 匹配 | Precision | Recall | F1 | 字段匹配率 |
|--------|------|------|------|-----------|--------|-----|-----------|
| 2024图册-WS系列 | 111 | 186 | 111 | 59.7% | 100.0% | 74.7% | 30.1% |
| 2024禧月【夏日贝壳】--30个商品0.6H | 30 | 47 | 30 | 63.8% | 100.0% | 77.9% | 20.0% |
| 2025new catalog沙发图册--65个商品 | 65 | 72 | 65 | 90.3% | 100.0% | 94.9% | 19.3% |
| 2025主卧床合集图册 | 48 | 57 | 48 | 84.2% | 100.0% | 91.4% | 31.8% |
| 2025佛山户外沙发家具图册 | 62 | 62 | 62 | 100.0% | 100.0% | 100.0% | 28.1% |
| 2025卡奇尔 白色--26个商品0.5H（PDF有一个商品重复，花了点时间确认） | 28 | 40 | 28 | 70.0% | 100.0% | 82.4% | 51.0% |
| 2025图册 -HQ系列 | 403 | 469 | 403 | 85.9% | 100.0% | 92.4% | 35.3% |
| 2025年报价单下(5) | 144 | 153 | 144 | 94.1% | 100.0% | 97.0% | 17.7% |
| 2025梳妆台&斗柜图册 | 96 | 103 | 96 | 93.2% | 100.0% | 96.5% | 25.7% |
| 2025梳妆台系列 | 77 | 74 | 74 | 100.0% | 96.1% | 98.0% | 25.7% |
| 2025相约餐饮家具 | 29 | 253 | 29 | 11.5% | 100.0% | 20.6% | 40.9% |
| Elysium宾利摩卡 | 72 | 69 | 69 | 100.0% | 95.8% | 97.9% | 30.8% |
| Elysium富誉 | 129 | 259 | 129 | 49.8% | 100.0% | 66.5% | 41.5% |
| Elysium开物里 | 166 | 162 | 162 | 100.0% | 97.6% | 98.8% | 39.2% |
| Elysium目居 | 404 | 504 | 404 | 80.2% | 100.0% | 89.0% | 28.0% |
| Elysium知如 | 132 | 137 | 132 | 96.4% | 100.0% | 98.1% | 40.8% |
| Ely北美轻奢硬体系列（RH风格） | 256 | 274 | 256 | 93.4% | 100.0% | 96.6% | 26.7% |
| Ely北美轻奢软体系列（RH风格） | 475 | 650 | 475 | 73.1% | 100.0% | 84.4% | 29.5% |
| 一涧物 | 523 | 556 | 523 | 94.1% | 100.0% | 96.9% | 63.2% |
| 2025新款电子版 | 45 | 78 | 45 | 57.7% | 100.0% | 73.2% | 30.8% |
| 2025秋季新款电子画册 | 8 | 45 | 8 | 17.8% | 100.0% | 30.2% | 30.4% |
| 万日红2025中古风家具 | 58 | 72 | 58 | 80.6% | 100.0% | 89.2% | 46.8% |
| 万日红实木家具 | 52 | 79 | 52 | 65.8% | 100.0% | 79.4% | 44.0% |
| 万日红实木家具2 | 116 | 114 | 114 | 100.0% | 98.3% | 99.1% | 22.8% |
| 万日红家具B软床图册)宝丽 (1)(1) | 181 | 67 | 67 | 100.0% | 37.0% | 54.0% | 38.0% |
| 万日红家具—原创设计师合集(1) | 155 | 151 | 151 | 100.0% | 97.4% | 98.7% | 31.7% |
| 万日红家具美式中古图册 | 81 | 122 | 81 | 66.4% | 100.0% | 79.8% | 40.2% |
| 万日红极简现代沙发(1) | 42 | 81 | 42 | 51.9% | 100.0% | 68.3% | 44.9% |
| 万日红现代简约图册 | 87 | 187 | 87 | 46.5% | 100.0% | 63.5% | 30.9% |
| 万日红现代软床Y图册 | 251 | 261 | 251 | 96.2% | 100.0% | 98.0% | 34.0% |
| 万日红美式轻奢BAIGAT(1) | 57 | 146 | 57 | 39.0% | 100.0% | 56.2% | 38.8% |
| 万日红美式轻奢画册2024.1.1 | 139 | 412 | 139 | 33.7% | 100.0% | 50.5% | 37.8% |
| 万日红美式香槟图册 | 42 | 73 | 42 | 57.5% | 100.0% | 73.0% | 42.9% |
| 万鑫休闲椅 全 | 95 | 165 | 95 | 57.6% | 100.0% | 73.1% | 44.2% |
| 万鑫休闲椅-货号WX-01开始 | 0 | 163 | 0 | 0.0% | 0.0% | 0.0% | 0.0% |
| 万鑫极简沙发图(2) | 81 | 81 | 81 | 100.0% | 100.0% | 100.0% | 65.3% |
| 中古系列-沙发(纳威) | 28 | 65 | 28 | 43.1% | 100.0% | 60.2% | 23.5% |
| 2025现代地毯图册（压缩） | 296 | 409 | 296 | 72.4% | 100.0% | 84.0% | 41.2% |
| 常规款式图册2025.9.16- | 90 | 434 | 90 | 20.7% | 100.0% | 34.4% | 45.4% |
| 2025.乐适佳家具电子图册 | 24 | 35 | 24 | 68.6% | 100.0% | 81.4% | 44.6% |
| 2025客厅家具系列 | 255 | 416 | 255 | 61.3% | 100.0% | 76.0% | 51.4% |
| 乐适佳产品图册20250710 | 66 | 129 | 66 | 51.2% | 100.0% | 67.7% | 33.8% |
| **总计** | **5499** | **7912** | **5369** | **67.9%** | **97.6%** | **80.1%** | |

## 页面分类分布

| 分类 | 页数 | 占比 | SKU数 | SKU/页 |
|------|------|------|-------|--------|
| SINGLE_TALL | 577 | 20.3% | 1912 | 3.3 |
| MULTI_SPARSE | 533 | 18.8% | 762 | 1.4 |
| IMG_LABEL | 440 | 15.5% | 1449 | 3.3 |
| MIXED_OTHER | 396 | 13.9% | 629 | 1.6 |
| IMG_DENSE | 344 | 12.1% | 1913 | 5.6 |
| SINGLE_LARGE | 288 | 10.1% | 758 | 2.6 |
| SINGLE_STD | 139 | 4.9% | 162 | 1.2 |
| TABLE | 117 | 4.1% | 321 | 2.7 |
| MIXED_TABLE | 4 | 0.1% | 6 | 1.5 |
| BLANK | 3 | 0.1% | 0 | 0.0 |

## 多余 SKU 来源分析

| 页面分类 | 多余数 | 占比 |
|----------|--------|------|
| SINGLE_TALL | 770 | 30.3% |
| IMG_DENSE | 729 | 28.7% |
| MULTI_SPARSE | 332 | 13.1% |
| SINGLE_LARGE | 308 | 12.1% |
| IMG_LABEL | 244 | 9.6% |
| MIXED_OTHER | 114 | 4.5% |
| TABLE | 23 | 0.9% |
| SINGLE_STD | 21 | 0.8% |
| MIXED_TABLE | 2 | 0.1% |

## 详细差异

### 2024图册-WS系列

**多余 SKU (75):**

- 诺尔沙发
- 沙发
- 沙发
- 沙发
- 茶几
- 电视柜
- 餐桌
- 沙发
- 沙发
- 沙发
- 沙发
- 沙发
- 沙发
- 沙发
- 茶几
- 沙发
- 茶几
- 茶几
- 沙发
- 沙发
- 沙发
- 茶几
- 椅子
- 椅子
- 椅子
- 椅子
- 椅子
- 椅子
- 椅子
- 椅子
- 茶几
- 沙发
- 茶几
- 沙发
- 沙发
- 沙发
- 沙发
- 铁艺茶几(乌金石盘)
- 火烧石茶几系列
(不带柜)
- 铁艺功夫茶几(乌金石茶盘)
- 功夫茶几
- 功夫茶几
- 火烧石茶几
- 火烧石茶几
- 功夫茶几
- 黑色岩板面功夫茶几
- 白色岩板面功夫茶几
- 乌金石面功夫茶几
- 白色岩板面功夫茶几
- 乌金石面功夫茶几
- 茶几
- 茶几
- 乌金石面功夫茶几
- 功夫茶几
- 功夫茶几
- 功夫茶几
- 乌金石功夫茶几
- 乌金石功夫茶几
- 乌金石功夫茶几
- 乌金石功夫茶几
- 茶几
- 茶几
- 茶几
- 茶几
- 茶几
- 茶几
- 茶几系列
- 茶几系列
- 茶几
- 茶几
- 功夫茶几
- 茶几
- 茶几
- 茶几
- 茶几

**字段差异 (前10):**

- **型号：A105#铁艺功夫茶几(胶盘)
规格：130x70x55cm** (匹配方法: model_prefix)
  - product_name: `型号：A105#铁艺功夫茶几(胶盘)` → `铁艺功夫茶几(胶盘)`
  - tag: `茶几` → ``
  - source: `2024图册-WS系列` → `区域 1`
- **型号：A116#(圆7分角、组合方茶几)
规格：
70x70x43cm
60x60x37cm** (匹配方法: model_prefix)
  - product_name: `型号：A116#(圆7分角、组合方茶几)` → `圆7分角、组合方茶几`
  - specs: `70x70x43cm
60x60x37cm` → `70x70x43cm, 60x60x37cm`
  - tag: `茶几` → ``
  - source: `2024图册-WS系列` → `image`
- **WS-X202#（沙发）
单人位：110x83x80cm
双人位：158x83x80cm
三人位：208x83x80cm** (匹配方法: model_prefix)
  - product_name: `WS-X202#（沙发）` → `WS-X202 (沙发)`
  - specs: `单人位110x83x80cm
双人位158x83x80cm
三人位208x83x80cm` → `110 x 83 x 80cm`
  - tag: `沙发` → ``
  - source: `2024图册-WS系列` → ``
- **型号：A106#铁艺功夫茶几
规格：130x70x55cm** (匹配方法: model_prefix)
  - product_name: `型号：A106#铁艺功夫茶几` → `铁艺功夫茶几`
  - tag: `茶几` → ``
  - source: `2024图册-WS系列` → `区域 4`
- **型号：A106-1#铁艺功夫茶几
规格：130x70x55cm** (匹配方法: model_prefix)
  - product_name: `型号：A106-1#铁艺功夫茶几` → `铁艺功夫茶几`
  - tag: `茶几` → ``
  - source: `2024图册-WS系列` → `区域 4`
- **型号：A118-1#(灰色、组合双黑色架)
规格：
80x80x45cm
70x70x40cm** (匹配方法: model_prefix)
  - product_name: `型号：A118-1#(灰色、组合双黑色架)` → `灰色、组合双黑色架`
  - specs: `80x80x45cm
70x70x40cm` → `80x80x45cm, 70x70x40cm`
  - tag: `茶几` → ``
  - source: `2024图册-WS系列` → `OCR`
- **型号：A115#（圆3分角台面雪山白）
小方几：60x60x40cm
大方几：70x70x45cm** (匹配方法: model_prefix)
  - product_name: `型号：A115#（圆3分角台面雪山白）` → `圆3分角台面雪山白`
  - specs: `小方几60x60x40cm
大方几70x70x45cm` → `小方几: 60x60x40cm, 大方几: 70x70x45cm`
  - tag: `茶几` → `圆3分角`
  - source: `2024图册-WS系列` → `GuDingMei 137`
- **型号：P03#（功夫茶几）
规格：130x70cm** (匹配方法: model_prefix)
  - product_name: `型号：P03#（功夫茶几）` → `功夫茶几`
  - tag: `茶几` → ``
  - source: `2024图册-WS系列` → `OCR`
- **型号：A102*铁艺功夫茶几
规格：130x70x55cm
颜色：香奈儿乌金石盘** (匹配方法: model_prefix)
  - product_name: `型号：A102*铁艺功夫茶几` → `铁艺功夫茶几`
  - tag: `茶几` → ``
  - source: `2024图册-WS系列` → `区域 1`
- **型号：A02-2#(功夫茶几)
规格：130x70x55cm** (匹配方法: model_prefix)
  - product_name: `型号：A02-2#(功夫茶几)` → `功夫茶几`
  - tag: `茶几` → ``
  - source: `2024图册-WS系列` → `GuDingMei 109`

### 2024禧月【夏日贝壳】--30个商品0.6H

**多余 SKU (17):**

- 贝壳 SHELL
- 床头靠垫
- Bk(贝壳)01#
- 床
- Bed
- Bk (贝壳) 12#
- 地板
- Bk (贝壳) 02#
- 贝壳 SHELL
- Bed with arched headboard
- 床
- 床
- 床
- 地板
- Bed
- Bk (贝壳) 08#
- Bedside table / Side table

**字段差异 (前10):**

- **Bk( 贝壳 )09 # 床头柜 / 边几** (匹配方法: name_as_model)
  - product_name: `Bk( 贝壳 )09 # 床头柜 / 边几` → `床头柜/边几`
  - tag: `奶油中古风系列` → ``
  - source: `2024禧月【夏日贝壳】` → `image`
- **Bk( 贝壳 )11 #** (匹配方法: name_as_model)
  - product_name: `Bk( 贝壳 )11 #` → `Bedside cabinet`
  - tag: `奶油中古风系列` → ``
  - source: `2024禧月【夏日贝壳】` → ``
- **冬夏两用-贝壳床
3个颜色 原木色/高级灰/奶油白
3个规格 1200mm/1500mm/1800mm
5个款式 可自由搭配软靠** (匹配方法: product_name)
  - specs: `1800mm,1500mm,1200mm` → `冬夏两用,可拆卸软包,自由搭配,百搭风格,床头含8cm置物空间
3个规格:1200mm,1500mm,1800mm
5个款式:可自由搭配软靠`
  - tag: `奶油中古风系列` → ``
  - source: `2024禧月【夏日贝壳】` → `区域 1`
- **Bk（贝壳）12# 1800/1500/1200mm 原木色** (匹配方法: product_name)
  - product_name: `Bk（贝壳）12# 1800/1500/1200mm 原木色` → `贝壳`
  - specs: `1800mm,1500mm,1200mm` → ``
  - color: `原木色` → ``
  - tag: `奶油中古风系列` → `SUMMER SEA SHELLS`
  - source: `2024禧月【夏日贝壳】` → `image`
- **Bk（贝壳）03# 1800/1500mm 原木色** (匹配方法: product_name)
  - product_name: `Bk（贝壳）03# 1800/1500mm 原木色` → `Bk（贝壳）03#`
  - specs: `1800mm,1500mm` → `1800/1500mm`
  - color: `原木色` → `高级灰`
  - tag: `奶油中古风系列` → ``
  - source: `2024禧月【夏日贝壳】` → `page`
- **Bk（贝壳）01# 1800/1500/1200mm 原木色** (匹配方法: position)
  - product_name: `Bk（贝壳）01# 1800/1500/1200mm 原木色` → `防污防抓表面`
  - specs: `1800mm,1500mm,1200mm` → `表面疏水涂层, 能隔绝大部分日常污渍, 轻擦即净; 面层抗刮经磨, 密度高不易撕裂`
  - color: `原木色` → ``
  - tag: `奶油中古风系列` → `猫抓皮`
  - source: `2024禧月【夏日贝壳】` → `image`
- **Bk（贝壳）02# 1800/1500mm 原木色** (匹配方法: position)
  - product_name: `Bk（贝壳）02# 1800/1500mm 原木色` → `细腻自然感纹理`
  - specs: `1800mm,1500mm` → `模拟奢品工艺裁剪拼接, 加工尽可能保留纹理顺衔`
  - color: `原木色` → ``
  - tag: `奶油中古风系列` → ``
  - source: `2024禧月【夏日贝壳】` → `image`
- **Bk（贝壳）06# 1800/1500mm 原木色** (匹配方法: position)
  - product_name: `Bk（贝壳）06# 1800/1500mm 原木色` → `Nightstand`
  - specs: `1800mm,1500mm` → ``
  - color: `原木色` → ``
  - tag: `奶油中古风系列` → ``
  - source: `2024禧月【夏日贝壳】` → ``
- **Bk（贝壳）01# 1800/1500/1200mm 原木色+浅灰** (匹配方法: position)
  - product_name: `Bk（贝壳）01# 1800/1500/1200mm 原木色+浅灰` → `Wooden bed with integrated headboard shelf`
  - specs: `1800mm,1500mm,1200mm` → ``
  - color: `原木色+浅灰` → `Original wood color`
  - tag: `奶油中古风系列` → ``
  - source: `2024禧月【夏日贝壳】` → ``
- **Bk（贝壳）01# 1800/1500/1200mm 原木色+酒红** (匹配方法: position)
  - product_name: `Bk（贝壳）01# 1800/1500/1200mm 原木色+酒红` → `地板`
  - specs: `1800mm,1500mm,1200mm` → `1800/1500/1200mm`
  - color: `原木色+酒红` → `原木色`
  - tag: `奶油中古风系列` → ``
  - source: `2024禧月【夏日贝壳】` → `image`

### 2025new catalog沙发图册--65个商品

**多余 SKU (7):**

- I shape design
沙发
- 沙发
- sofa
- I shape design
- I shape with ottoman
- 沙发
- sofa

**字段差异 (前10):**

- **Model:Y03#
Size:3390*1730*960mm** (匹配方法: model_prefix)
  - product_name: `Model:Y03#` → `Corner sofa`
  - specs: `3390*1730*960mm` → ``
  - tag: `沙发` → ``
  - source: `2025new catalog沙发图册` → `image`
- **Model:HJG9360
Size:3350*1050*840mm** (匹配方法: model_prefix)
  - product_name: `Model:HJG9360` → `沙发`
  - tag: `沙发` → ``
  - source: `2025new catalog沙发图册` → ``
- **Model:8163** (匹配方法: name_as_model)
  - product_name: `Model:8163` → `沙发`
  - tag: `沙发` → ``
  - source: `2025new catalog沙发图册` → `image`
- **Model:9013#** (匹配方法: name_as_model)
  - product_name: `Model:9013#` → `功能沙发`
  - tag: `沙发` → ``
  - source: `2025new catalog沙发图册` → `OCR`
- **Newmodel:3012（reclinersofa）
Size:2480*1010*950mm** (匹配方法: product_name)
  - product_name: `Newmodel:3012（reclinersofa）` → `New model:3012 (recliner sofa)`
  - specs: `2480*1010*950mm` → `recliner sofa; Size: 2480*1010*950mm; Middle table with USB charger and storage.`
  - tag: `沙发` → `Hot sale design`
  - source: `2025new catalog沙发图册` → `page_1_of_3`
- **Newmodel:3011(sofabed)
Size:W3060*D650/1010*H920mm** (匹配方法: product_name)
  - product_name: `Newmodel:3011(sofabed)` → `sofa`
  - specs: `W3060*D650,1010*H920mm` → ``
  - tag: `沙发` → ``
  - source: `2025new catalog沙发图册` → ``
- **Model:9285
Size:3630*1200*880mm** (匹配方法: position)
  - product_name: `Model:9285` → `2025新款 沙发`
  - tag: `沙发` → `2025新款`
  - source: `2025new catalog沙发图册` → `image`
- **Model:3056
Size:3200*1060*980mm** (匹配方法: position)
  - product_name: `Model:3056` → `2025新款沙发床`
  - specs: `3200*1060*980mm` → `W3060*D650/1010*H920mm`
  - tag: `沙发` → `New model`
  - source: `2025new catalog沙发图册` → `image`
- **Model:8176
Size:3160*1060*860mm** (匹配方法: position)
  - product_name: `Model:8176` → `沙发`
  - specs: `3160*1060*860mm` → `3200*1060*980mm`
  - tag: `沙发` → ``
  - source: `2025new catalog沙发图册` → `image`
- **Model:8128#
Size:2950*960*900mm
CBM:2.3** (匹配方法: position)
  - product_name: `Model:8128#` → `沙发`
  - specs: `2950*960*900mm` → `3160*1060*860mm`
  - tag: `沙发` → ``
  - source: `2025new catalog沙发图册` → `page_2_of_2`

### 2025主卧床合集图册

**多余 SKU (9):**

- DESIREE ZENIT BED
- FLOU NEW BOND BED
<绷带床>
- CIERRE CRYSTAL BED
- LIVING DIVANI
EXTRASOFT BED
矮屏床
- Visionnaire Bastian Bed
<信封床>
- Bed
- Bed
- COEHIDE BED
<黑巧牛皮床>
- 宽屏款-单床

**字段差异 (前10):**

- **色号：HOT9120-1** (匹配方法: model_prefix)
  - product_name: `色号：HOT9120-1` → `床`
  - model_number: `zwc036` → `HOT9120-1`
  - tag: `主卧床` → ``
  - source: `2025主卧床合集图册.pdf` → ``
- **HOT9180-2** (匹配方法: model_prefix)
  - product_name: `HOT9180-2` → `bed`
  - model_number: `zwc037` → `HOT9180-2`
  - tag: `主卧床` → ``
  - source: `2025主卧床合集图册.pdf` → ``
- **色号：MD05-1** (匹配方法: model_prefix)
  - product_name: `色号：MD05-1` → `床`
  - model_number: `zwc038` → `MD05-1`
  - tag: `主卧床` → ``
  - source: `2025主卧床合集图册.pdf` → ``
- **NA407** (匹配方法: model_prefix)
  - product_name: `NA407` → `床垫`
  - model_number: `zwc042` → `NA407`
  - tag: `主卧床` → ``
  - source: `2025主卧床合集图册.pdf` → ``
- **劳伦斯床** (匹配方法: product_name)
  - product_name: `劳伦斯床` → `床`
  - model_number: `zwc001` → `形态-1`
  - tag: `主卧床` → ``
  - source: `2025主卧床合集图册.pdf` → ``
- **巧克力床** (匹配方法: product_name)
  - product_name: `巧克力床` → `床`
  - model_number: `zwc002` → `形态-2`
  - tag: `主卧床` → ``
  - source: `2025主卧床合集图册.pdf` → ``
- **Tatlin 床** (匹配方法: product_name)
  - product_name: `Tatlin 床` → `床`
  - model_number: `zwc003` → `EDRA-3`
  - tag: `主卧床` → ``
  - source: `2025主卧床合集图册.pdf` → ``
- **Tatlin "Soft"床** (匹配方法: product_name)
  - product_name: `Tatlin "Soft"床` → `床`
  - model_number: `zwc004` → `EDRA-3`
  - tag: `主卧床` → ``
  - source: `2025主卧床合集图册.pdf` → ``
- **地平线床** (匹配方法: product_name)
  - model_number: `zwc010` → ``
  - tag: `主卧床` → ``
  - source: `2025主卧床合集图册.pdf` → `MINOTTI HORIZONTE BED`
- **大黑牛床** (匹配方法: product_name)
  - model_number: `zwc013` → `CHATEAU D’AX AVENYE BED`
  - tag: `主卧床` → ``
  - source: `2025主卧床合集图册.pdf` → `CHATEAU D’AX AVENYE BED`

### 2025佛山户外沙发家具图册

**字段差异 (前10):**

- **XY-12铝合金沙发
单人:700*700*700
双人:1400*700*700
三人:2000*700*700** (匹配方法: model_prefix)
  - model_number: `HW013` → `XY-12`
  - specs: `单人:700*700*700
双人:1400*700*700
三人:2000*700*700` → `单人：700*700*700`
  - tag: `户外家具` → ``
  - source: `2025佛山户外沙发家具图册` → `printed`
- **XY-24铝合金实木沙发
单人:750*750*750
双人:1500*750*750
三人:2000*750*750
茶几:600*600*400** (匹配方法: model_prefix)
  - model_number: `HW025` → `XY-24`
  - specs: `单人:750*750*750
双人:1500*750*750
三人:2000*750*750
茶几:600*600*400` → `单人：750*750*750`
  - tag: `户外家具` → ``
  - source: `2025佛山户外沙发家具图册` → `XY-24铝合金实木沙发
单人：750*750*750`
- **XY-104桌椅组合** (匹配方法: model_prefix)
  - model_number: `HW029` → `XY-104`
  - tag: `户外家具` → ``
  - source: `2025佛山户外沙发家具图册` → ``
- **XY-106桌椅组合** (匹配方法: model_prefix)
  - model_number: `HW031` → `XY-106`
  - tag: `户外家具` → ``
  - source: `2025佛山户外沙发家具图册` → ``
- **XY-107桌椅组合** (匹配方法: model_prefix)
  - model_number: `HW032` → `XY-107`
  - tag: `户外家具` → ``
  - source: `2025佛山户外沙发家具图册` → ``
- **XY-109桌椅组合** (匹配方法: model_prefix)
  - model_number: `HW034` → `XY-109`
  - tag: `户外家具` → ``
  - source: `2025佛山户外沙发家具图册` → `original_image`
- **XY-110桌椅组合** (匹配方法: model_prefix)
  - model_number: `HW035` → `XY-110`
  - tag: `户外家具` → ``
  - source: `2025佛山户外沙发家具图册` → `image`
- **XY-111桌椅组合** (匹配方法: model_prefix)
  - product_name: `XY-111桌椅组合` → `XY-111 桌椅组合`
  - model_number: `HW036` → `XY-111`
  - tag: `户外家具` → ``
  - source: `2025佛山户外沙发家具图册` → ``
- **XY-112桌椅组合** (匹配方法: model_prefix)
  - model_number: `HW037` → `XY-112`
  - tag: `户外家具` → ``
  - source: `2025佛山户外沙发家具图册` → ``
- **XY-102桌椅组合** (匹配方法: model_prefix)
  - product_name: `XY-102桌椅组合` → `桌椅组合`
  - model_number: `HW027` → `XY-102`
  - tag: `户外家具` → ``
  - source: `2025佛山户外沙发家具图册` → `image`

### 2025卡奇尔 白色--26个商品0.5H（PDF有一个商品重复，花了点时间确认）

**多余 SKU (12):**

- 现代极简系列
- Modern Minimalist Collection
- Modern House Exterior
- 床头柜
- 床头柜
- 大床
- 床头柜
- 床头柜
- 床头柜
- 大床
- 床头柜
- 床头柜

**字段差异 (前10):**

- **大床** (匹配方法: model_number)
  - specs: `规格：1500/1800*2000mm 颜色：奶油风` → `1500/1800*2000mm`
  - tag: `奶油中古风实木床` → ``
  - source: `2025卡奇尔 白色` → `OCR`
- **床头柜** (匹配方法: model_number)
  - model_number: `201` → `201#`
  - specs: `规格：1500/1800*2000mm 颜色：奶油风` → ``
  - tag: `奶油中古风实木床` → ``
  - source: `2025卡奇尔 白色` → ``
- **大床** (匹配方法: model_number)
  - specs: `规格：1500/1800*2000mm 颜色：奶油风` → `1500/1800*2000mm`
  - tag: `奶油中古风实木床` → ``
  - source: `2025卡奇尔 白色` → ``
- **床头柜** (匹配方法: model_number)
  - specs: `规格：1500/1800*2000mm 颜色：奶油风` → ``
  - tag: `奶油中古风实木床` → ``
  - source: `2025卡奇尔 白色` → ``
- **大床** (匹配方法: model_number)
  - model_number: `3001` → `3001#`
  - specs: `规格：1500/1800*2000mm 颜色：奶油风` → `1500/1800*2000mm`
  - tag: `奶油中古风实木床` → ``
  - source: `2025卡奇尔 白色` → `OCR`
- **大床** (匹配方法: model_number)
  - model_number: `3006` → `3006#`
  - specs: `规格：1500/1800*2000mm 颜色：奶油风` → `1500/1800*2000mm`
  - tag: `奶油中古风实木床` → ``
  - source: `2025卡奇尔 白色` → `OCR`
- **大床** (匹配方法: model_number)
  - specs: `规格：1500/1800*2000mm 颜色：奶油风` → `1500/1800*2000mm`
  - tag: `奶油中古风实木床` → ``
  - source: `2025卡奇尔 白色` → `OCR`
- **大床** (匹配方法: model_number)
  - specs: `规格：1500/1800*2000mm 颜色：奶油风` → `1500/1800*2000mm`
  - tag: `奶油中古风实木床` → ``
  - source: `2025卡奇尔 白色` → `OCR`
- **大床** (匹配方法: model_number)
  - model_number: `6062` → `6062#`
  - specs: `规格：1500/1800*2000mm 颜色：奶油风` → `1500/1800*2000mm`
  - tag: `奶油中古风实木床` → ``
  - source: `2025卡奇尔 白色` → `OCR`
- **大床** (匹配方法: model_number)
  - specs: `规格：1500/1800*2000mm 颜色：奶油风` → `1500/1800*2000mm`
  - tag: `奶油中古风实木床` → ``
  - source: `2025卡奇尔 白色` → `OCR`

### 2025图册 -HQ系列

**多余 SKU (66):**

- GOLDEN SILK WOOD 金丝玉
- PURPLE WOOD 紫金木
- CAMPHOR WOOD 香樟木
- EBONY WOOD 乌金木
- TEENO SERIES 天籁系列
- chocolate
- Munich
- 天籁
- 东风EAST
- 金粉世家
- 巧克力
- 极光系列
- 极光系列
- Office Desk
- Office Desk with Power Outlets
- 六人位办公桌
- 金丝玉
- 路易斯
- 卡其色
- 设计空间- 灵感办公
- 延伸位职员桌
- 四人位职员桌
- 紫金木
- 卡其色
- 黑石纹
- 白石纹
- 班台
- 班台
- 班台
- 班台
- 班台
- 班台
- 班台
- 主管桌
- 主管桌
- 主管桌
- 会议桌
- 职员桌
- 职员桌
- 职员桌
- 职员桌
- 职员桌
- 职员桌
- 职员桌
- 职员桌
- 职员桌
- 职员桌
- 职员桌
- 职员桌
- 财务桌
- 香樟木
- 白石纹
- 卡其色
- 巧克力
- 乌金木
- 班台
- 班台
- 班台
- 边柜
- 办公椅
- 沙发
- 沙发
- 沙发
- 沙发
- 沙发
- Text: 敬请期待下期更精彩! Stay tuned for more exciting next issue!

**字段差异 (前10):**

- **Y02 主席台
4900Wx600Dx800Hmm P4933** (匹配方法: model_prefix)
  - product_name: `Y02 主席台` → `主席台`
  - specs: `主席台4900Wx600Dx800Hmm` → `4900Wx600Dx800Hmm`
  - tag: `乌金木系列` → ``
  - source: `2025图册 -HQ系列` → `区域 8`
- **Y01 演讲台
700Wx500Dx1050Hmm P1600** (匹配方法: model_prefix)
  - product_name: `Y01 演讲台` → `演讲台`
  - specs: `演讲台700Wx500Dx1050Hmm` → `700Wx500Dx1050Hmm`
  - tag: `乌金木系列` → ``
  - source: `2025图册 -HQ系列` → `区域 6`
- **E010 洽谈桌
1000Wx1000Dx750Hmm P1167** (匹配方法: model_prefix)
  - product_name: `E010 洽谈桌` → `洽谈桌`
  - specs: `洽谈桌1000Wx1000Dx750Hmm` → `1000W×1000Dx750Hmm`
  - tag: `极光系列` → ``
  - source: `2025图册 -HQ系列` → `区域 6`
- **S621 文件柜
3000Wx400Dx2000Hmm P 8667** (匹配方法: model_prefix)
  - product_name: `S621 文件柜` → `文件柜`
  - specs: `文件柜3000Wx400Dx2000Hmm` → `3000Wx400Dx2000Hmm`
  - tag: `金丝玉系列` → ``
  - source: `2025图册 -HQ系列` → `区域 2`
- **S937 文件柜
2400Wx400Dx2000Hmm P3933** (匹配方法: model_prefix)
  - product_name: `S937 文件柜` → `文件柜`
  - specs: `文件柜2400Wx400Dx2000Hmm` → `2400Wx400Dx2000Hmm`
  - tag: `香樟木系列` → ``
  - source: `2025图册 -HQ系列` → `区域 1`
- **S927 文件柜
2000Wx400Dx2000Hmm P3266** (匹配方法: model_prefix)
  - product_name: `S927 文件柜` → `文件柜`
  - specs: `文件柜2000Wx400Dx2000Hmm` → `2000Wx400Dx2000Hmm`
  - tag: `香樟木系列` → ``
  - source: `2025图册 -HQ系列` → `区域 1`
- **Z99A 职员桌
2400Wx1200Dx750Hmm P2997** (匹配方法: model_prefix)
  - product_name: `Z99A 职员桌` → `职员桌`
  - specs: `职员桌2400Wx1200Dx750Hmm` → `2400W×1200Dx750Hmm`
  - tag: `香樟木系列` → ``
  - source: `2025图册 -HQ系列` → `区域 4`
- **Z99B 职员桌
1200Wx1200Dx750Hmm P2300** (匹配方法: model_prefix)
  - product_name: `Z99B 职员桌` → `职员桌`
  - specs: `职员桌1200Wx1200Dx750Hmm` → `1200W×1200Dx750Hmm`
  - tag: `香樟木系列` → ``
  - source: `2025图册 -HQ系列` → `区域 5`
- **Z99C 职员桌
1200Wx1200Dx750Hmm P2000** (匹配方法: model_prefix)
  - product_name: `Z99C 职员桌` → `职员桌`
  - specs: `职员桌1200Wx1200Dx750Hmm` → `1200Wx1200Dx750Hmm`
  - tag: `香樟木系列` → ``
  - source: `2025图册 -HQ系列` → `区域 6`
- **S901A 文件柜
3430Wx400Dx2000Hmm P7500** (匹配方法: model_prefix)
  - product_name: `S901A 文件柜` → `文件柜`
  - specs: `文件柜3430Wx400Dx2000Hmm` → `3430Wx400Dx2000Hmm`
  - tag: `紫金木系列` → ``
  - source: `2025图册 -HQ系列` → `区域 5`

### 2025年报价单下(5)

**多余 SKU (9):**

- 餐桌
- 餐桌
- 餐桌
- 3226茶台
- 茶台
- 茶台
- 茶台
- 茶台
- 茶台

**字段差异 (前10):**

- **型号：C864#餐桌
规格：135+80
材质：不锈钢灰钛拉丝底架+天然石铂金钻台面** (匹配方法: model_prefix)
  - product_name: `型号：C864#餐桌` → `C864#餐桌`
  - model_number: `bjd057` → `C864#`
  - source: `2025年报价单下` → `不锈钢灰钛拉丝底架+天然石铂金钻台面`
- **型号：C712#餐桌
规格：135+80
材质：不锈钢灰钛拉丝底架+天然石芬迪白台面** (匹配方法: model_prefix)
  - product_name: `型号：C712#餐桌` → `C712#餐桌`
  - model_number: `bjd060` → `C712#`
  - source: `2025年报价单下` → `不锈钢灰钛拉丝底架+天然石芬迪白台面`
- **型号：C656#餐桌
规格：135+80
材质：不锈钢+白蜡木底架+天然石云母绿台面** (匹配方法: model_prefix)
  - product_name: `型号：C656#餐桌` → `C656#餐桌`
  - model_number: `bjd062` → `C656#`
  - source: `2025年报价单下` → `不锈钢+白蜡木底架+天然石云母绿台面`
- **型号：C693#餐桌
规格：135+80
材质：不锈钢+黑色木皮底架+天然石钻石白台面** (匹配方法: model_prefix)
  - product_name: `型号：C693#餐桌` → `C693#餐桌`
  - model_number: `bjd063` → `C693#`
  - source: `2025年报价单下` → `不锈钢+黑色木皮底架+天然石钻石白台面`
- **型号：C605#餐桌
规格：135+80
材质：不锈钢镜面+红古铜拉丝底架+天然石皇家白玉台面** (匹配方法: model_prefix)
  - product_name: `型号：C605#餐桌` → `C605#餐桌`
  - model_number: `bjd059` → `C605#`
  - source: `2025年报价单下` → `不锈钢镜面+红古铜拉丝底架+天然石皇家白玉台面`
- **型号：C680#餐桌
规格：135+80
材质：不锈钢灰钛拉丝+黑色木皮底架+天然石梦幻星河台面** (匹配方法: model_prefix)
  - product_name: `型号：C680#餐桌` → `C680#餐桌`
  - model_number: `bjd058` → `C680#`
  - source: `2025年报价单下` → `不锈钢灰钛拉丝+黑色木皮底架+天然石梦幻星河台面`
- **型号：C695#餐桌
规格：135+80
材质：不锈钢灰钛拉丝+黑色木皮底架+天然石雪山飞狐台面** (匹配方法: model_prefix)
  - product_name: `型号：C695#餐桌` → `C695#餐桌`
  - model_number: `bjd061` → `C695#`
  - source: `2025年报价单下` → `不锈钢灰钛拉丝+黑色木皮底架+天然石雪山飞狐台面`
- **型号：C855#餐桌
规格：1600*900*750
1800*900*750
材质：不锈钢灰钛拉丝底架+天然石铂金钻台面** (匹配方法: model_prefix)
  - product_name: `型号：C855#餐桌` → `C855#餐桌`
  - model_number: `bjd066` → `C855#`
  - specs: `1600*900*750
1800*900*750` → `1600*900*750`
  - source: `2025年报价单下` → ``
- **型号：C659#餐桌
规格：1600*900*750
1800*900*750
材质：不锈钢灰钛拉丝底架+天然石钻石白台面** (匹配方法: model_prefix)
  - product_name: `型号：C659#餐桌` → `C659#餐桌`
  - model_number: `bjd070` → `C659#`
  - specs: `1600*900*750
1800*900*750` → `1600*900*750`
  - source: `2025年报价单下` → ``
- **型号：C679#餐桌
规格：1600*900*750
1800*900*750
材质：不锈钢灰钛拉丝+黑色木皮底架+天然石云母绿台面** (匹配方法: model_prefix)
  - product_name: `型号：C679#餐桌` → `C679#餐桌`
  - model_number: `bjd068` → `C679#`
  - specs: `1600*900*750
1800*900*750` → `1600*900*750`
  - source: `2025年报价单下` → ``

### 2025梳妆台&斗柜图册

**多余 SKU (7):**

- 九斗柜
- 九斗柜
- 六斗柜
- 八斗柜
- 六斗柜
- 八斗柜
- 九斗柜

**字段差异 (前10):**

- **YM-723#
马鞍皮/实木框架/不锈钢支架/岩板面
台面：80/100/120*45*78cm
副柜：50*40*60cm** (匹配方法: model_prefix)
  - specs: `台面:80*45*78cm
台面:100*45*78cm
台面:120*45*78cm
副柜:50*40*60cm` → `Material: Saddle leather/Solid wood frame/Stainless steel bracket/Slab top; Tabletop: 80/100/120*45*78cm; Side cabinet: 50*40*60cm`
  - tag: `梳妆台` → ``
  - source: `2025梳妆台&斗柜图册.pdf` → ``
- **YM-13#
马鞍皮/ 实木框架/不锈钢底架/岩板面
台面：80/100/120*45*78cm
副柜：50*45*55cm** (匹配方法: model_prefix)
  - specs: `台面:80*45*78cm
台面:100*45*78cm
台面:120*45*78cm
副柜:50*45*55cm` → `Material: Saddle leather/Solid wood frame/Stainless steel base/Slab top; Tabletop: 80/100/120*45*78cm; Side cabinet: 50*45*55cm`
  - tag: `梳妆台` → ``
  - source: `2025梳妆台&斗柜图册.pdf` → ``
- **YM-12#
马鞍皮/实木框架/不锈钢支架/岩板面
台面：80/100/120*45*75cm
副柜：50*45cm** (匹配方法: model_prefix)
  - specs: `台面:80*45*75cm
台面:100*45*75cm
台面:120*45*75cm
副柜:50*45cm` → `Material: Saddle leather/Solid wood frame/Stainless steel bracket/Slab; Tabletop: 80/100/120*45*75cm; Side cabinet: 50*45cm`
  - tag: `梳妆台` → ``
  - source: `2025梳妆台&斗柜图册.pdf` → ``
- **YM-721#
马鞍皮/实木框架/不锈钢支架/岩板面
台面：120*45*75cm
副柜：50*45cm** (匹配方法: model_prefix)
  - specs: `台面:120*45*75cm
副柜:50*45cm` → `Material: Saddle leather/Solid wood frame/Stainless steel bracket/Slab; Tabletop: 120*45*75cm; Side cabinet: 50*45cm`
  - tag: `梳妆台` → ``
  - source: `2025梳妆台&斗柜图册.pdf` → ``
- **YM011#
实木扪皮/不锈钢/岩板面
台面：80/100/120*40*75cm
副柜：50*40cm** (匹配方法: model_prefix)
  - product_name: `YM011#` → `YM011#电视柜`
  - specs: `台面:80*40*75cm
台面:100*40*75cm
台面:120*40*75cm
副柜:50*40cm` → `实木扪皮/不锈钢/岩板面
台面:80/100/120*40*75cm
副柜:150*40cm`
  - tag: `梳妆台` → ``
  - source: `2025梳妆台&斗柜图册.pdf` → `OCR`
- **K610#
实木多层烤漆茶色玻璃台面
尺寸：140*40*80H** (匹配方法: model_prefix)
  - product_name: `K610#` → `实木多层烤漆茶色玻璃台面`
  - tag: `梳妆台` → ``
  - source: `2025梳妆台&斗柜图册.pdf` → `OCR`
- **S403#6斗全实木马鞍皮工艺微晶石面
台面: 80/100/120*40*75cm
副柜: 100/150*40cm** (匹配方法: model_prefix)
  - specs: `台面: 80*40*75cm
台面: 100*40*75cm
台面: 120*40*75cm
副柜: 100*40cm
副柜: 150*40cm` → `台面:80/100/120*40*75cm`
  - tag: `梳妆台` → ``
  - source: `2025梳妆台&斗柜图册.pdf` → `OCR`
- **S832#3斗
全实木扪皮工艺
台面：80/100/120*40*75cm
副柜：50*40cm** (匹配方法: model_prefix)
  - specs: `台面:80*40*75cm
台面:100*40*75cm
台面:120*40*75cm
副柜:50*40cm` → `台面: 80/100/120*40*75cm; 副柜: 50*40cm`
  - tag: `梳妆台` → ``
  - source: `2025梳妆台&斗柜图册.pdf` → ``
- **S041#
全实木扪皮工艺
台面：80/100/120*40*75cm
副柜：50*40cm** (匹配方法: model_prefix)
  - specs: `台面:80*40*75cm
台面:100*40*75cm
台面:120*40*75cm
副柜:50*40cm` → `台面: 80/100/120*40*75cm; 副柜: 50*40cm`
  - tag: `梳妆台` → ``
  - source: `2025梳妆台&斗柜图册.pdf` → ``
- **S135#多层实木烤漆
台面：100/120*40*75cm
副柜：40*40cm** (匹配方法: model_prefix)
  - product_name: `S135#多层实木烤漆` → `多层实木烤漆`
  - specs: `台面:100*40*75cm
台面:120*40*75cm
副柜:40*40cm` → `台面：100/120*40*75cm; 副柜：40*40cm`
  - tag: `梳妆台` → ``
  - source: `2025梳妆台&斗柜图册.pdf` → `区域 1`

### 2025梳妆台系列

**缺失 SKU (3):**

- Model：903#
八斗柜款:120x40x90cm 
柜体颜色：奶油白/灰色 (行 76)
- Model：105#
三斗:70*40*75.2cm
四斗:70*40*94.5cm
五斗:70*40*113.8cm
柜体颜色:奶油白 (行 77)
- Model：355#
八斗柜:120/140/160*40*80cm
五斗柜:70*40*98cm
三斗柜:60*40*62cm (行 78)

**字段差异 (前10):**

- **Model：P001#
妆台:100/120*40*76cm
地柜:120*40*61.5cm 
柜体颜色:灰色/奶白色** (匹配方法: model_prefix)
  - product_name: `Model：P001#` → `地柜`
  - model_number: `A2025-031` → `P001#`
  - specs: `妆台100*40*76cm,妆台120*40*76cm,地柜120*40*61.5cm` → `120*40*61.5 cm`
  - tag: `梳妆台` → ``
  - source: `2025梳妆台系列` → ``
- **Model：388#
妆台:80/100/120*40*74cm 
地柜:120*40*58cm** (匹配方法: position)
  - product_name: `Model：388#` → `地柜`
  - model_number: `A2025-001` → `388#`
  - specs: `妆台80*40*74cm,妆台100*40*74cm,妆台120*40*74cm,地柜120*40*58cm` → `120*40*58cm`
  - tag: `梳妆台` → ``
  - source: `2025梳妆台系列` → ``
- **Model：388#
妆台:100/120*40*75cm
斗柜:45*40*58cm** (匹配方法: position)
  - product_name: `Model：388#` → `斗柜`
  - model_number: `A2025-002` → ``
  - specs: `妆台100*40*75cm,妆台120*40*75cm,斗柜45*40*58cm` → `45*40*58cm`
  - tag: `梳妆台` → ``
  - source: `2025梳妆台系列` → `OCR`
- **Model：388#
妆台:100/120*40*75cm
斗柜:45*40*58cm** (匹配方法: position)
  - product_name: `Model：388#` → `地柜`
  - model_number: `A2025-003` → `119#`
  - specs: `妆台100*40*75cm,妆台120*40*75cm,斗柜45*40*58cm` → `130*40*63cm`
  - tag: `梳妆台` → ``
  - source: `2025梳妆台系列` → ``
- **Model：119#
妆台:80/100/120*40*76cm 
地柜:130*40*63cm
柜体颜色：奶油白/灰色** (匹配方法: position)
  - product_name: `Model：119#` → `妆台`
  - model_number: `A2025-004` → `119#`
  - specs: `妆台80*40*76cm,妆台100*40*76cm,妆台120*40*76cm,地柜130*40*63cm` → `80/100/120*40*76cm`
  - color: `奶油白/灰色` → `Cream White/Grey`
  - tag: `梳妆台` → ``
  - source: `2025梳妆台系列` → ``
- **Model：119#
妆台:80/100/120*40*76cm 
斗柜:60*40*63cm
柜体颜色：奶油白/灰色** (匹配方法: position)
  - product_name: `Model：119#` → `Cabinet`
  - model_number: `A2025-005` → `119#`
  - specs: `妆台80*40*76cm,妆台100*40*76cm,妆台120*40*76cm,斗柜60*40*63cm` → ``
  - color: `奶油白/灰色` → ``
  - tag: `梳妆台` → ``
  - source: `2025梳妆台系列` → ``
- **Model：359#
妆台:100/120*40*75cm
斗柜:45*40*58cm
柜体颜色：奶油白/灰色** (匹配方法: position)
  - product_name: `Model：359#` → `斗柜`
  - model_number: `A2025-006` → `359#`
  - specs: `妆台100*40*75cm,妆台120*40*75cm,斗柜45*40*58cm` → `45*40*58cm`
  - tag: `梳妆台` → ``
  - source: `2025梳妆台系列` → ``
- **Model：362#
妆台:100/120*40*76cm
二斗:50*40*60cm
柜体颜色：奶油白/灰色** (匹配方法: position)
  - product_name: `Model：362#` → `妆台`
  - model_number: `A2025-007` → `362#`
  - specs: `妆台100*40*76cm,妆台120*40*76cm,二斗50*40*60cm` → `100/120*40*76 cm`
  - tag: `梳妆台` → ``
  - source: `2025梳妆台系列` → ``
- **Model：360#
妆台:100/120*40*76cm
地柜:120*40*60cm(含3公分脚)
柜体颜色：奶油白/灰色** (匹配方法: position)
  - product_name: `Model：360#` → `地柜`
  - model_number: `A2025-008` → `360#`
  - specs: `妆台100*40*76cm,妆台120*40*76cm,地柜120*40*60cm(含3公分脚)` → `120*40*60cm(含3公分脚)`
  - tag: `梳妆台` → ``
  - source: `2025梳妆台系列` → ``
- **Model：387#
妆台:80/100/120*40*76cm
地柜:130*40*60cm
柜体颜色：奶油白/灰色** (匹配方法: position)
  - product_name: `Model：387#` → `地柜`
  - model_number: `A2025-009` → `387#`
  - specs: `妆台80*40*76cm,妆台100*40*76cm,妆台120*40*76cm,地柜130*40*60cm` → `130*40*60cm`
  - tag: `梳妆台` → ``
  - source: `2025梳妆台系列` → `printed_text`

### 2025相约餐饮家具

**多余 SKU (224):**

- 实木包岩板长桌
- 实木包岩板方桌
- 长条沙发
- 卡座沙发
- 卡座餐桌
- 壁挂装饰画
- 圆形壁挂装饰
- 1.2米直排卡座
- 实木编藤餐椅
- 实木包岩板长桌
- 实木包岩板方桌
- 实木包岩板圆桌
- 沙发卡座
- 装饰花瓶
- 1.2米直排卡座
- 编藤半圆卡座
- 实木编藤餐椅
- 实木包岩板长桌
- 实木包岩板方桌
- 实木包岩板圆桌
- 卡座沙发
- 实木包岩板长桌
- 长条沙发
- 吊灯
- 直排卡座
- 实木编藤餐椅
- 实木包岩板长桌
- 实木包岩板方桌
- 多层实木板长桌
- 多层实木板方桌
- 编藤直排卡座
- 编藤半圆卡座
- 实木编藤餐椅
- 多层实木板长桌
- 多层实木板方桌
- 多层实木板圆桌
- 弧形沙发
- 圆形餐桌
- 卡座沙发
- 方形餐桌
- Restaurant interior with booth seating and tables
- Restaurant interior with individual tables and chairs
- 1.2米编藤直排卡座
- 实木编藤餐椅
- 实木包夹板长桌
- 实木包夹板方桌
- 实木包夹板方桌带抽屉
- 实木包夹板方桌带抽屉
- 卡座沙发
- 卡座沙发
- 1.2米板式直排卡座
- 白蜡木实木餐椅
- 多层实木板长桌
- 多层实木板方桌
- 高硬岩板长桌
- 高硬岩板方桌
- 卡座沙发
- 吊灯
- 装饰植物
- 储物柜
- 台灯
- 卡座沙发
- 吊灯
- 台灯
- 装饰植物
- 免漆板方桌
- 免漆板圆桌
- 海洋板方桌
- 海洋板圆桌
- 电镀金属单人椅
- 电镀金属单人椅
- 直排板式卡座
- 实木餐椅不带扶手
- 实木餐椅带扶手
- 多层实木板长桌带抽屉
- 多层实木板方桌带抽屉
- 多层实木板圆桌带抽屉
- 墙面装饰画
- PAGE - 61
- PAGE - 62
- 直排板式卡座
- 板式半圆卡座
- 实木餐椅
- 多层实木板长桌
- 多层实木板圆桌
- 石英石圆桌
- 弧形沙发
- 卡座沙发
- 圆形餐桌
- 圆形沙发
- 实木框架卡座
- 实木编绳Y椅
- 实木编藤扶手椅
- 多层实木板长桌
- 多层实木板方桌
- 台灯
- 装饰画
- 绿植
- 直排海洋板卡座
- 实木餐椅
- 多层实木板长桌
- 多层实木板方桌
- 吊灯
- 壁画
- 卡座沙发
- 直排多层板卡座
- 实木餐椅
- 多层实木板长桌
- 卡座沙发
- 植物
- 吊灯
- 直排板式卡座
- 实木多层板餐椅
- 实木软包坐垫餐椅
- 实木软包靠背餐椅
- 多层实木板长桌
- 多层实木板方桌
- 卡座沙发
- 卡座沙发
- 直排板式卡座
- 板式U形卡座
- 铁艺烤漆软包餐椅
- 不锈钢软包餐椅
- 多层实木板长桌
- 多层实木板方桌
- 方桌内置抽屉
- 多层实木板长桌
- 多层实木板方桌
- 餐厅卡座
- 吊灯
- 卡座沙发
- 直排板式卡座
- 实木软包餐椅
- 咖啡厅桌椅
- 咖啡厅卡座
- 墙面装饰画
- 铁艺烤漆餐椅
- 实木包岩板长桌
- 卡座沙发
- 壁灯
- 吊灯
- 桌面台灯
- 1.2米直排板式卡座
- 铁艺烤漆餐椅
- 实木包瓷砖方桌
- 实木包瓷砖圆桌
- 多层实木板长桌
- 多层实木板方桌
- 卡座沙发
- 圆桌
- 方桌
- 直排不锈钢卡座
- 半圆不锈钢卡座
- 金属软包餐椅
- 卡座沙发
- 圆形餐桌
- 弧形卡座沙发
- 植物装饰
- 吊灯
- 壁灯
- 卡座沙发
- 餐边柜
- 直排不锈钢卡座
- 半圆不锈钢卡座
- 不锈钢软包餐椅
- 不锈钢火锅长桌
- 不锈钢火锅方桌
- 不锈钢火锅圆桌
- 卡座沙发
- 卡座沙发
- 直排板式卡座
- 直排板式双面卡座
- 金属软包餐椅
- 不锈钢包岩板圆桌
- 吊灯
- 长条沙发
- 壁灯
- 圆形餐桌
- 盆栽
- 挂毯
- 海洋板直排卡座
- 海洋板不带靠背卡座
- 海洋板软包餐椅
- 海洋板长桌
- 海洋板方桌
- 海洋板圆桌
- 海洋板直排卡座
- 海洋板不带靠背卡座
- 海洋板软包餐椅
- 海洋板小茶几方桌
- 海洋板小茶几圆桌
- 咖啡店桌椅
- coffee table
- 咖啡馆桌椅
- 海洋板直排卡座
- 海洋板餐椅
- 不锈钢罗马椅
- 多层板直排卡座
- 不锈钢软包餐椅
- 海洋板方桌
- 猫抓皮
- 苏拉皮
- QF爽肤皮
- 猫爪油蜡皮
- 黄钛
- 玫瑰金
- 黑钛
- 银白色
- 浅胡桃色 SHALLOW WALNUT
- 胡桃色 PEACH COLORED
- 黑胡桃色 BLACK WALNUT
- 黑色 BLACK
- 鱼肚白 FISH BELLY WHITE
- 香奈儿 CHANEL
- 安娜灰 ANNA GREY
- 潘多拉 PANDORA
- 鎏金白 GILDED WHITE
- 劳伦金 LAUREN KING
- 寒江雪 COLD RIVER SNOW
- 百达翡丽 CALATRAVA REF
- 亚马逊绿 AMAZON GREEN
- 阿玛尼灰 ARMANI GREY
- 冷翡翠 COLD JADE
- 雪花白 ALABASTER

**字段差异 (前10):**

- **** (匹配方法: position)
  - specs: `1.2米直排卡座` → ``
  - tag: `餐厅` → ``
- **** (匹配方法: position)
  - specs: `1.2米直排卡座` → ``
  - tag: `餐厅` → ``
- **** (匹配方法: position)
  - specs: `1.2米直排卡座` → ``
  - tag: `餐厅` → ``
- **** (匹配方法: position)
  - specs: `1.2米直排卡座` → `2025第一版`
  - tag: `餐厅` → ``
- **** (匹配方法: position)
  - specs: `1.2米直排卡座` → `13798629708`
  - tag: `餐厅` → ``
- **** (匹配方法: position)
  - specs: `1.2米直排卡座` → `13927290543`
  - tag: `餐厅` → ``
- **** (匹配方法: position)
  - specs: `1.2米直排卡座` → `13622526010`
  - tag: `餐厅` → ``
- **** (匹配方法: position)
  - specs: `1.2米直排卡座` → `18024919870`
  - tag: `餐厅` → ``
- **** (匹配方法: position)
  - specs: `1.2米直排卡座` → `03-44页`
  - tag: `餐厅` → ``
- **** (匹配方法: position)
  - specs: `1.2米直排卡座` → `45-74页`
  - tag: `餐厅` → ``

### Elysium宾利摩卡

**缺失 SKU (3):**

- AR1181 (行 71)
- AR1182 (行 72)
- AR1183 (行 73)

**字段差异 (前10):**

- **MODEL:C64** (匹配方法: model_prefix)
  - product_name: `MODEL:C64` → `Round dining table`
  - model_number: `AR1141` → `C64`
  - tag: `餐桌` → ``
  - source: `Elysium宾利摩卡Dining table and chairs.pdf` → ``
- **MODEL:C68** (匹配方法: model_prefix)
  - product_name: `MODEL:C68` → `Solid wood vintage dining table`
  - model_number: `AR1147` → `C68`
  - tag: `餐桌` → ``
  - source: `Elysium宾利摩卡Dining table and chairs.pdf` → `image`
- **MODEL:b23** (匹配方法: model_prefix)
  - product_name: `MODEL:b23` → `Solid wood vintage dining table`
  - model_number: `AR1158` → `b23`
  - tag: `餐桌` → ``
  - source: `Elysium宾利摩卡Dining table and chairs.pdf` → `image`
- **MODEL:M11** (匹配方法: model_prefix)
  - product_name: `MODEL:M11` → `Sideboard`
  - model_number: `AR1174` → `M11`
  - tag: `柜子` → ``
  - source: `Elysium宾利摩卡Dining table and chairs.pdf` → ``
- **MODEL:MK08** (匹配方法: model_prefix)
  - product_name: `MODEL:MK08` → `Sideboard`
  - model_number: `AR1171` → `MK08`
  - tag: `柜子` → ``
  - source: `Elysium宾利摩卡Dining table and chairs.pdf` → ``
- **MODEL:MK09** (匹配方法: model_prefix)
  - product_name: `MODEL:MK09` → `Sideboard`
  - model_number: `AR1172` → `MK09`
  - tag: `柜子` → ``
  - source: `Elysium宾利摩卡Dining table and chairs.pdf` → ``
- **MODEL:MK04** (匹配方法: model_prefix)
  - product_name: `MODEL:MK04` → `Sideboard`
  - model_number: `AR1175` → `MK04`
  - tag: `柜子` → ``
  - source: `Elysium宾利摩卡Dining table and chairs.pdf` → ``
- **MODEL:C65** (匹配方法: model_prefix)
  - product_name: `MODEL:C65` → `Solid Wood Dining Table`
  - model_number: `AR1135` → `C65`
  - tag: `餐桌` → ``
  - source: `Elysium宾利摩卡Dining table and chairs.pdf` → ``
- **MODEL:C40** (匹配方法: model_prefix)
  - product_name: `MODEL:C40` → `Dining table and chairs`
  - model_number: `AR1139` → `C40`
  - tag: `餐桌` → ``
  - source: `Elysium宾利摩卡Dining table and chairs.pdf` → ``
- **MODEL:C81** (匹配方法: model_prefix)
  - product_name: `MODEL:C81` → `Dining Table`
  - model_number: `AR1142` → `C81`
  - tag: `餐桌` → ``
  - source: `Elysium宾利摩卡Dining table and chairs.pdf` → ``

### Elysium富誉

**多余 SKU (130):**

- 边桌
- 屏风
- 抱枕
- 边桌
- 台灯
- 装饰罐
- 扶手椅
- 坐垫
- 1105#转角沙发
- 转角沙发
- 吊灯
- 筒灯
- 台灯
- 扶手椅
- 边几
- 1106#沙发
- Brasilia Sofa
- 吊灯
- 抱枕
- 单人沙发
- 木质格栅墙面
- 白色大理石纹墙面
- 白色弧形装饰板
- 边几
- 地毯
- 贵妃脚踏
- 抱枕
- 边几
- 花瓶
- 地毯
- 吊灯
- 抱枕
- 花瓶
- 装饰画
- 边几
- 沙发
- 装饰画
- 边几
- 单人椅
- 地毯
- 沙发
- 沙发
- 墙面装饰板
- 木质收纳柜
- 台灯
- 边几
- 勃朗沙发
- 落地灯
- 单人椅
- 花瓶
- 边几
- 单人沙发椅
- 地毯
- 1127#沙发
- 落地灯
- 单人沙发
- 边桌
- 休闲椅
- 落地灯
- 装饰画
- 抽象画
- 边几
- 音箱
- 抽屉柜
- 摇椅
- 抽象画
- 边几
- 功能长茶几
- 小边几
- 电视柜
- 电视柜
- 抽象画
- 木质电视柜
- Marshall 音箱
- 咖啡研磨机
- 黑色小雕塑
- 衣帽架
- 梳妆台
- 梳妆凳
- 床尾凳
- 地毯
- 台灯
- 花瓶
- 衣帽架
- 吊灯
- 地毯
- 装饰画
- 绿植
- 地毯
- 编织篮
- 装饰碗
- 衬衫
- 手提包
- 珍珠项链
- 地毯
- 墙面装饰
- 窗帘
- 大理石纹墙面
- 床头柜
- 吊灯
- 装饰画
- 床头柜
- 台灯
- 落地灯
- Wisdom
- 餐边柜
- 台灯
- 圆餐台
- 吊灯
- 岛台
- 置物架
- 台灯
- 展示柜
- 花瓶
- 干花
- 卷帘
- 组合书柜
- 置物架
- 台灯
- 装饰花瓶
- 装饰盒
- 置物架
- 花瓶
- 水壶
- 茶椅
- 矮凳
- 花瓶
- 茶具
- 茶椅
- 茶椅

**字段差异 (前10):**

- **1307#长餐台** (匹配方法: name_as_model)
  - tag: `餐桌` → ``
  - source: `Elysium富誉 North American black walnut wood.pdf` → `image`
- **1306#长餐台** (匹配方法: name_as_model)
  - tag: `餐桌` → ``
  - source: `Elysium富誉 North American black walnut wood.pdf` → `image`
- **1351#餐边柜** (匹配方法: name_as_model)
  - tag: `柜子` → ``
  - source: `Elysium富誉 North American black walnut wood.pdf` → `image`
- **1352#酒柜** (匹配方法: name_as_model)
  - tag: `柜子` → ``
  - source: `Elysium富誉 North American black walnut wood.pdf` → `image`
- **1602#茶桌** (匹配方法: name_as_model)
  - product_name: `1602#茶桌` → `1602# 茶桌`
  - tag: `茶几` → ``
  - source: `Elysium富誉 North American black walnut wood.pdf` → `image`
- **1132#功能长茶几** (匹配方法: name_as_model)
  - product_name: `1132#功能长茶几` → `功能长茶几`
  - tag: `茶几` → ``
  - source: `Elysium富誉 North American black walnut wood.pdf` → `image`
- **1158#不规则边几** (匹配方法: name_as_model)
  - product_name: `1158#不规则边几` → `不规则边几`
  - tag: `茶几` → ``
  - source: `Elysium富誉 North American black walnut wood.pdf` → `image`
- **1252#妆台+妆镜** (匹配方法: name_as_model)
  - product_name: `1252#妆台+妆镜` → `妆台+妆镜`
  - tag: `妆台` → ``
  - source: `Elysium富誉 North American black walnut wood.pdf` → `OCR`
- **1253#妆台+妆镜** (匹配方法: name_as_model)
  - product_name: `1253#妆台+妆镜` → `妆台+妆镜`
  - tag: `妆台` → ``
  - source: `Elysium富誉 North American black walnut wood.pdf` → `OCR`
- **1316#水滴圆餐台** (匹配方法: name_as_model)
  - product_name: `1316#水滴圆餐台` → `水滴圆餐台`
  - tag: `餐桌` → ``
  - source: `Elysium富誉 North American black walnut wood.pdf` → `image`

### Elysium开物里

**缺失 SKU (4):**

- 餐桌
MATERIALS:
材质:靠背：北美黑胡桃木实木扶手：马鞍牛皮坐垫：进口头层牛皮框架：亮光不锈钢
尺寸：
L: 180cm W:90cm H: 74cm (行 165)
- 餐椅
MATERIALS:
材质:油蜡皮+回弹海绵+不锈钢铁架
尺寸：
L:45 cm W:65cm H:72 cm (行 166)
- 餐椅
MATERIALS:
材质:雪尼尔绒布+回弹海绵+不锈钢铁架
尺寸：
L:45 cm W:65cm H:72 cm (行 167)
- 餐桌
MATERIALS:
材质:实木多层贴黑胡桃木皮
尺寸：
直径：135cmH:725cm (行 168)

**字段差异 (前10):**

- **MATERIALS:
面料：复古油蜡皮
填充：高密度海绵框架：实木松木框架+实木多层板脚：五金脚
型号：S112
全复古油蜡皮，体现出不同凡响的高级感，它
独特的线条设计，将简约调性与自然的舒适韵
味，组合的恰到好处，给人带来明朗清新的感觉。** (匹配方法: model_prefix)
  - product_name: `MATERIALS:` → `全复古油蜡皮床`
  - tag: `床` → ``
  - source: `Elysium开物里.pdf` → ``
- **cj-04
MATERIALS:
材质：深灰水泥漆
尺寸：
直径：95cm** (匹配方法: model_prefix)
  - product_name: `cj-04` → `Side table`
  - tag: `茶几` → ``
  - source: `Elysium开物里.pdf` → `PRODUCTS/Sidetable/2024`
- **cz-01
MATERIALS:
材质：榆木
尺寸：
L: 200cm W:88cm H: 76cm** (匹配方法: model_prefix)
  - product_name: `cz-01` → `Table`
  - tag: `茶几` → ``
  - source: `Elysium开物里.pdf` → `PRODUCTS/Table/2024`
- **Y-13
MATERIALS:
材质:榉木+海绵+全皮
尺寸：
L: 66cm W:90cmH:100 cm** (匹配方法: model_prefix)
  - product_name: `Y-13` → `chair`
  - tag: `沙发` → ``
  - source: `Elysium开物里.pdf` → ``
- **CJ0011
Price range:¥3892-9812
MATER  IALS:           
  
面料: 古油蜡皮复 座包 :羽绒 +丝绵 +高回弹海绵 靠包 :羽绒 +丝绵 +高回弹海绵 框架 :进口松木实木框架
脚:脚实木
油蜡皮的复古质感给人一种怀旧和沧桑的感觉
扶手和靠背位置的褶皱又透出一些可爱，看似
简单，却是它的小心机设计。** (匹配方法: model_prefix)
  - product_name: `CJ0011` → `沙发`
  - tag: `沙发` → ``
  - source: `Elysium开物里.pdf` → ``
- **Hug怀抱沙发
Price range:¥4226-11800
  
MATER IALS:       
面料: 古油蜡皮复 座包 /靠包 :羽绒 +绒丝棉 +海绵 框架 :进口松木实木框架 +实木多层板
脚:15cm铁脚
这款沙发的坐感 不仅仅是柔软 ，而是一种坐下
去就不想起来的包裹感，就跟它的名字一样，
全方位的“拥抱你 ”** (匹配方法: product_name)
  - tag: `沙发` → ``
  - source: `Elysium开物里.pdf` → `区域 1, 区域 2`
- **无头牛沙发
Price range:¥3540-11212
MATERIALS:
面料:复古油蜡皮
脚:实木脚
靠包/座包:羽绒+丝棉+高回弹海绵
框架:进口松木实木框架
干净利落的线条，饱满立体的外观，以简驭繁，没有过多的元素堆积，座包、靠包填上适量羽绒，柔软而又有支撑力。** (匹配方法: product_name)
  - tag: `沙发` → ``
  - source: `Elysium开物里.pdf` → `区域 1`
- **豆袋沙发
Price range:¥3372-10568
   
MAT ER  IALS:
面料: 古油蜡皮复 座包 :高回弹海绵 靠包 :高回弹海绵 框架 :口松木实木进   脚:实木脚
经典的设计款，休闲的风格，结合复杂的十字
拉扣设计和舒适的柔软皮革，创造一个诱
和放纵舒适的时光。超深的座位和特殊斜度的
靠背，提供一个慵懒的下沉式体验，舒适而又     
不失奢华。** (匹配方法: product_name)
  - tag: `沙发` → ``
  - source: `Elysium开物里.pdf` → `区域 1, 区域 3`
- **华夫格
Price range:¥2070-6928
  
MATER IALS:                          
面料 : 古油蜡皮复 座包 :高回弹海绵 靠包 :高回弹海绵 框架 :进口松木实木框架
脚:脚实木
外型脱离了传统沙发“坐面 +靠背 +扶手 +腿”
组合形式，各部分无缝衔接，浑然一体，没有
多余的设计，甚至连个扶手也没有，组合丰富
，拥有更多布置可能性。** (匹配方法: product_name)
  - tag: `沙发` → ``
  - source: `Elysium开物里.pdf` → `区域 7`
- **钢圈沙发
Price range:¥6480-11520
    
MATER IALS:   
面料 : 古油蜡皮复填充：一体定型海绵 五金 ：不锈钢 框架： 实木松木 +实木夹 板 脚：实 木脚
这款沙发采用一体定型 海棉填充，所以不管是
从外观还是舒适度都能达到和原版 1:1的契合
，可以看到扶手的圆润还有角落的这种褶皱，
是非常考究师傅的手艺的。** (匹配方法: product_name)
  - product_name: `钢圈沙发` → `沙发`
  - tag: `沙发` → ``
  - source: `Elysium开物里.pdf` → `image`

### Elysium目居

**多余 SKU (100):**

- 木质边柜
- 装饰碗
- 目居
- MUJU目居
- MUJU
- 华润涂料
- 目居核心技术
- 工厂车间实况记录
- 新宜美(Ⅱ)亚光清面漆(三分光)
- 底材封闭剂
- 涂料
- 裙摆沙发
- 大裙摆沙发
- 布拉格沙发
- 马德里沙发
- 三人位
- 双人位
- 单人位
- 脚踏位
- 大转角位
- 转角位
- 单人位
- 脚踏位
- 新版普拉达沙发
- 裙摆沙发
- 棉花糖沙发
- 云朵沙发
- 空治沙发
- 多纳沙发
- 维多利亚沙发
- 贝壳沙发
- Nightstand
- Bed with patterned bedding
- 吊灯
- 扶手椅
- 边桌
- 台灯
- 小凳子
- 壁灯
- 浴室柜
- 浴室镜
- 浴室凳
- 阿尔贝洛床
- 喀布尔床
- 阿尔萨斯床
- 阿尔巴诺床
- 普拉达床
- 亚利桑床
- 桑托斯床
- 马泰拉床
- Dining room products
- Dining table
- Dining chair
- Candlestick
- 餐边柜
- 吊灯
- 地毯
- 波浪实木条
- 拱门造型
- 莱伊餐桌
- 古川餐桌
- 古诺尔大理石餐桌
- 小南斯餐桌
- 沃斯圆餐桌
- 多伦多餐桌
- 雕花实木餐边柜
- 莱恩德边柜
- 埃丝特边柜
- 纳维亚斯边柜
- 巧克力斗柜
- 维多利亚高柜
- 斑马边柜
- 斯德哥尔摩边柜
- 木质茶几
- 单人沙发
- 木质边桌
- 单人扶手椅
- 扶手椅
- 咖啡桌
- 地毯
- 盆栽植物
- 长凳
- 装饰品
- 抱枕
- 雪恩岛单椅
- 酋长椅
- 普拉达单椅
- 麦兜茶几
- 麦兜边几
- 月亮茶几
- 边几
- 斯耐山茶几
- 涟叶床头柜
- 莱恩德床头柜
- 布胡斯床头柜
- 巧克力床头柜
- 目之所及 · 心之所居
- Address
- 目之所及 · 心之所居
- Address

**字段差异 (前10):**

- **Model:MJ-CT01
午观茶台
材质:大花绿天然奢石+实木多层板贴天然白橡木皮+天然火烧石茶盘** (匹配方法: model_prefix)
  - product_name: `Model:MJ-CT01` → `午观茶台`
  - tag: `茶几` → ``
  - source: `Elysium目居.pdf` → ``
- **Model:MJ-CT02
勒拿河茶台
材质:宝格丽黑岩板\宝格丽黑天然奢石+实木多层板贴天然白橡木支** (匹配方法: model_prefix)
  - product_name: `Model:MJ-CT02` → `勒拿河茶台`
  - tag: `茶几` → ``
  - source: `Elysium目居.pdf` → ``
- **Model:MJ-S63
PORADA沙发
面料:泰迪绒** (匹配方法: model_prefix)
  - product_name: `Model:MJ-S63` → `PORADA沙发`
  - tag: `沙发` → ``
  - source: `Elysium目居.pdf` → `image`
- **Model:MJ-CJ40
宝格丽大\中\小茶几
材质:宝格丽天然奢石** (匹配方法: model_prefix)
  - product_name: `Model:MJ-CJ40` → `宝格丽大\中\小茶几`
  - tag: `茶几` → ``
  - source: `Elysium目居.pdf` → `image`
- **Model:MJ-S52
宽扶手豆腐块沙发
面料:头层牛皮** (匹配方法: model_prefix)
  - product_name: `Model:MJ-S52` → `宽扶手豆腐块沙发`
  - tag: `沙发` → ``
  - source: `Elysium目居.pdf` → `image`
- **Model:MJ-S51
窄扶手豆腐块沙发
面料:头层牛皮** (匹配方法: model_prefix)
  - product_name: `Model:MJ-S51` → `窄扶手豆腐块沙发`
  - tag: `沙发` → ``
  - source: `Elysium目居.pdf` → `image`
- **Model:MJ-X38
乌德勒支休闲椅
面料:布艺** (匹配方法: model_prefix)
  - product_name: `Model:MJ-X38` → `乌德勒支休闲椅`
  - tag: `沙发` → ``
  - source: `Elysium目居.pdf` → `OCR`
- **Model:MJ-X36
巴塞罗那休闲椅
面料:超纤皮** (匹配方法: model_prefix)
  - product_name: `Model:MJ-X36` → `巴塞罗那休闲椅`
  - tag: `沙发` → ``
  - source: `Elysium目居.pdf` → ``
- **Model:MJ-S06
新版普拉达沙发
面料:针织面料** (匹配方法: model_prefix)
  - product_name: `Model:MJ-S06` → `新版普拉达沙发`
  - tag: `沙发` → ``
  - source: `Elysium目居.pdf` → `image`
- **Model:MJ-X09
布里甘丁休闲椅
面料:进口布艺** (匹配方法: model_prefix)
  - product_name: `Model:MJ-X09` → `布里甘丁休闲椅`
  - tag: `沙发` → ``
  - source: `Elysium目居.pdf` → ``

### Elysium知如

**多余 SKU (5):**

- 圆桌
- 边柜
- 好材为底 无限创造
- 佛山市如知家具有限公司
- 佛山市南海区敦上大道与龙高路交叉路口6楼如知家具

**字段差异 (前10):**

- **边柜
Model：XL4296
材质：红橡木实木板
尺寸（mm）：
2000*400*650** (匹配方法: model_prefix)
  - tag: `柜子` → ``
  - source: `Elysium知如dining table.pdf` → `材质:红橡木实木板`
- **边柜
Model：XL4295
材质：红橡木实木板
尺寸（mm）：
1800*395*820** (匹配方法: model_prefix)
  - tag: `柜子` → ``
  - source: `Elysium知如dining table.pdf` → `材质:红橡木实木板`
- **边柜
Model：XL4294
材质：红橡木实木板
尺寸（mm）：
1000*400*1100** (匹配方法: model_prefix)
  - tag: `柜子` → ``
  - source: `Elysium知如dining table.pdf` → ``
- **实木床
Model：WC9181
床框架：北美FAS白蜡木实木
辅材：实木多层板
床铺板：松木实木
尺寸（mm）：
1800*2000** (匹配方法: model_prefix)
  - product_name: `实木床` → `实木床 Model:WC9181`
  - tag: `床` → ``
  - source: `Elysium知如dining table.pdf` → ``
- **实木床
Model：WC9159
床框架：北美FAS白蜡木实木
辅材：实木多层板
床铺板：松木实木
尺寸（mm）：
1800*2000
（2090*1890*1450)** (匹配方法: model_prefix)
  - product_name: `实木床` → `实木床 Model:WC9159`
  - tag: `床` → ``
  - source: `Elysium知如dining table.pdf` → `image`
- **XL4355
Model：CT6039
材质：实木多层板
尺寸（mm）：
480*380*620** (匹配方法: model_prefix)
  - tag: `床头柜` → ``
  - source: `Elysium知如dining table.pdf` → `image`
- **休闲椅
Model：CY2162
材质：实木多层板
尺寸（mm）：
660*860*880** (匹配方法: model_prefix)
  - tag: `餐椅` → ``
  - source: `Elysium知如dining table.pdf` → `OCR`
- **床头柜
Model：WT1102
框架：北美FAS白蜡木实木
辅材：实木多层板
尺寸（mm）：
500*500** (匹配方法: model_prefix)
  - tag: `床头柜` → ``
  - source: `Elysium知如dining table.pdf` → `image`
- **休闲椅
Model：SF8275
面料：棉麻
材质：北美FAS白蜡木实木
尺寸（mm）：
630*830*770** (匹配方法: model_prefix)
  - tag: `沙发` → ``
  - source: `Elysium知如dining table.pdf` → `OCR`
- **休闲椅
Model：SF8270
面料：提花
材质：北美FAS白蜡木实木
尺寸（mm）：
800*830*920** (匹配方法: model_prefix)
  - tag: `沙发` → ``
  - source: `Elysium知如dining table.pdf` → `OCR`

### Ely北美轻奢硬体系列（RH风格）

**多余 SKU (18):**

- FRANÇOIS OPEN NIGHTSTAND
- FRENCH CONTEMPORARY CLOSED NIGHTSTAND
- GAEL OAK CLOSED NIGHTSTAND
- GAEL OAK OPEN NIGHTSTAND
- PADUA CLOSED NIGHTSTAND
- PADUA OPEN NIGHTSTAND
- FRENCH CONTEMPORARY OPEN NIGHTSTAND
- GAEL OAK CLOSED NIGHTSTAND
- GAEL OAK OPEN NIGHTSTAND
- PADUA CLOSED NIGHTSTAND
- PADUA OPEN NIGHTSTAND
- FRENCH CONTEMPORARY OPEN NIGHTSTAND
- SONMA NIGHTSTAND
- SONMA NIGHTSTAND
- SONMA NIGHTSTAND
- SONMA NIGHTSTAND
- SONMA NIGHTSTAND
- Armchair

**字段差异 (前10):**

- **ROMEO** (匹配方法: product_name)
  - model_number: `ARET37` → ``
  - tag: `茶几` → ``
  - source: `Ely北美轻奢硬体系列（RH风格）2.pdf` → `image`
- **CUPOLA CARVED** (匹配方法: product_name)
  - model_number: `ARET39` → ``
  - tag: `茶几` → ``
  - source: `Ely北美轻奢硬体系列（RH风格）2.pdf` → ``
- **ROCCO** (匹配方法: product_name)
  - product_name: `ROCCO` → `MARCO`
  - model_number: `ARET40` → ``
  - tag: `茶几` → ``
  - source: `Ely北美轻奢硬体系列（RH风格）2.pdf` → `image`
- **VITOLO CARVED** (匹配方法: product_name)
  - model_number: `ARET41` → ``
  - tag: `茶几` → ``
  - source: `Ely北美轻奢硬体系列（RH风格）2.pdf` → ``
- **SONMA SERIES** (匹配方法: product_name)
  - product_name: `SONMA SERIES` → `SONMA SIDE TABLE`
  - model_number: `ARET42` → ``
  - tag: `茶几` → ``
  - source: `Ely北美轻奢硬体系列（RH风格）2.pdf` → `区域 2`
- **SONMA COFFEE TABLE** (匹配方法: product_name)
  - product_name: `SONMA COFFEE TABLE` → `COFFEE TABLE`
  - model_number: `ARET48` → ``
  - tag: `茶几` → ``
  - source: `Ely北美轻奢硬体系列（RH风格）2.pdf` → `image`
- **SONMA COFFEE TABLE** (匹配方法: product_name)
  - product_name: `SONMA COFFEE TABLE` → `COFFEE TABLE`
  - model_number: `ARET49` → ``
  - tag: `茶几` → ``
  - source: `Ely北美轻奢硬体系列（RH风格）2.pdf` → ``
- **SONMA COFFEE TABLE** (匹配方法: product_name)
  - model_number: `ARET50` → ``
  - tag: `茶几` → ``
  - source: `Ely北美轻奢硬体系列（RH风格）2.pdf` → `区域 1`
- **SONMA COFFEE TABLE** (匹配方法: product_name)
  - product_name: `SONMA COFFEE TABLE` → `FENG COFFEE TABLE`
  - model_number: `ARET51` → ``
  - tag: `茶几` → ``
  - source: `Ely北美轻奢硬体系列（RH风格）2.pdf` → `区域 9`
- **FENG COFFEE TABLE** (匹配方法: product_name)
  - product_name: `FENG COFFEE TABLE` → `COFFEE TABLE & SIDE TABLE`
  - model_number: `ARET52` → ``
  - tag: `茶几` → ``
  - source: `Ely北美轻奢硬体系列（RH风格）2.pdf` → `image`

### Ely北美轻奢软体系列（RH风格）

**多余 SKU (175):**

- KENSINGTON CHAIR
- RILEY CHAIR
- RYELAND CHAIR
- RIVELLI CHAIR
- LYON CHAIR
- PROFESSOR'S CHAIR WITH NAILHEADS
- RILEY CHAIR
- RYELAND CHAIR
- RIVELLI CHAIR
- LYON CHAIR
- PROFESSOR'S CHAIR WITH NAILHEADS
- RIVOLI CHAIR
- BLAIR LOUNGE CHAIR
- BALI CHAIR
- RIVOLI CHAIR
- ALESSIA LOUNGE CHAIR
- BLAIR LOUNGE CHAIR
- BALI CHAIR
- RIVOLI CHAIR
- ALESSIA LOUNGE CHAIR
- BLAIR LOUNGE CHAIR
- LANZO SWIVEL CHAIR
- LUCIO SWIVEL CHAIR
- LARIO CHAIR
- BOSON CHAIR
- LANZO SWIVEL CHAIR
- LUCIO SWIVEL CHAIR
- LARIO CHAIR
- BOSON CHAIR
- FRONTIER CHAIR
- FINO CHAIR
- CHLOE CHAIR
- JAKOB CANE LOUNGE CHAIR
- LANZO SWIVEL CHAIR
- LUCIO SWIVEL CHAIR
- LARIO CHAIR
- BOSON CHAIR
- FRONTIER CHAIR
- FINO CHAIR
- CHLOÉ CHAIR
- JAKOB CANE LOUNGE CHAIR CUSHION
- JAKOB CANE LOUNGE CHAIR
- LUKAS CHAIR
- BOSON CHAIR
- LUKAS CHAIR
- ASPRE CHAIR
- HESTIA CHAIR
- SAINT-GERMAIN CHAIR
- ALISTAIR CHAIR
- CLAUDE CHAIR
- FAIRFAX CHAIR
- BREU CHAIR
- MANDARIN CHAIR
- MONTMARTRE CHAIR
- BUNGALOW CHAIR
- GARRET CHAIR
- LOVETT CHAIR
- MARENCO CHAIR
- THURLEAH CHAIR
- OTIS CHAIR
- LUCA CHAIR
- WULFF CHAIR
- SYDNEY CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- THEODORE CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- THEODORE CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- THEODORE CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- JAKOB
- EVA
- JAKOB FRAMED
- CHLOÉ
- ALESSIA
- BLAIR
- ARRONDI SLOPE ARM
- CORTA
- INÉS
- HAYWARD CHAIR
- HAYWARD CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- SONMA CHAIR
- Bedside table
- Bed with headboard
- FRANÇOIS FABRIC SHELTER BED
- FRANÇOIS FABRIC SHELTER BED WITH FOOTBOARD
- FRANÇOIS FABRIC SHELTER BED
- FRANÇOIS FABRIC SHELTER BED
- FRANÇOIS FABRIC SHELTER BED WITH FOOTBOARD
- FRANÇOIS PANEL BED
- FRANÇOIS SHELTER BED WITH FOOTBOARD
- FRANÇOIS PANEL BED
- FRANÇOIS SHELTER BED WITH FOOTBOARD
- FRANÇOIS PANEL BED
- FRANÇOIS SHELTER BED WITH FOOTBOARD
- MONTECITO PANEL BED
- MODENA FABRIC PANEL PLATFORM BED
- CORTA FULLY UPHOLSTERED FABRIC SHELTER BED
- MODENA FABRIC VERTICAL CHANNEL PANEL PLATFORM BED
- MODENA FABRIC EXTENDED PANEL PLATFORM BED
- MODENA FABRIC VERTICAL CHANNEL EXTENDED PANEL PLATFORM BED
- MULHOLLAND EXTENDED FULLY UPHOLSTERED FABRIC PANEL BED
- MULHOLLAND FULLY UPHOLSTERED FABRIC PANEL BED
- FRANÇOIS FABRIC CANOPY BED
- PADUA CANOPY BED
- FRENCH CONTEMPORARY FABRIC PANEL CANOPY BED
- FRENCH CONTEMPORARY FABRIC PANEL CANOPY BED
- GAEL OAK CANOPY BED
- FRENCH CONTEMPORARY LEATHER DIAMOND-TUFTED PANEL CANOPY BED
- ATELIER BED

**字段差异 (前10):**

- **THE ORIGINAL CLOUD
GUARANTEEDFORLIFE
SFTSOFASSTARTNGAT
$3730MEMBER/$5330REGULAR** (匹配方法: product_name)
  - model_number: `AW1155` → ``
  - tag: `沙发` → `GUARANTEED FOR LIFE`
  - source: `Ely北美轻奢软体系列（RH风格）.pdf` → `image`
- **CLOUD
MODULARTRACKARM
GUARANTEEDFORLIFE
SPECE SOFA STARTINGAT
$6240 MEMBER/S8920 REGULAR
STOOXCDIN7RAORICS,DCLVERCDIN2 7DAYS
AWALADLEIN1SS：SPCCALOFOCRFASRICS,DCUVCRCON46WCEKG** (匹配方法: product_name)
  - model_number: `AW1156` → ``
  - tag: `沙发` → `GUARANTEED FOR LIFE`
  - source: `Ely北美轻奢软体系列（RH风格）.pdf` → `image`
- **LUGANO
MADEINIIALY
GLARANIEEDFORLIFE
DESGNEDHY ANTELNIHO** (匹配方法: product_name)
  - product_name: `LUGANO` → `BURANO`
  - model_number: `AW1157` → ``
  - tag: `沙发` → ``
  - source: `Ely北美轻奢软体系列（RH风格）.pdf` → ``
- **LUGANO
MODULAR
MADEINITALY
GUARANTEED FORLIFE
DESKNEDHYANIELNIHO** (匹配方法: product_name)
  - product_name: `LUGANO` → `LUGANO CHAIR`
  - model_number: `AW1158` → ``
  - tag: `沙发` → ``
  - source: `Ely北美轻奢软体系列（RH风格）.pdf` → ``
- **MAXWELL
HANDASSEMBLEDINNORIHCAROUINA
GUARANTEEDFORLIFE** (匹配方法: product_name)
  - product_name: `MAXWELL` → `MAXIME`
  - model_number: `AW1159` → ``
  - tag: `沙发` → `SAVE 35%-40% ON ALL ITEMS
AVAILABLE IN 155 SPECIAL ORDER FABRICS, DELIVERED IN 8-10 WEEKS`
  - source: `Ely北美轻奢软体系列（RH风格）.pdf` → `image`
- **MAXWELI
MODULAR
HANDASSEMBLEDINNORIHCAROLINA
GUARANIEEDFORLIFE** (匹配方法: product_name)
  - product_name: `MAXWELI` → `AXEL CHAIR`
  - model_number: `AW1160` → ``
  - tag: `沙发` → ``
  - source: `Ely北美轻奢软体系列（RH风格）.pdf` → ``
- **MODENA
TRACKARM
HANDASSFMBLFDINNORIHAMERICA
GUARANTEEDFORLIFE** (匹配方法: product_name)
  - model_number: `AW1161` → `TRACK ARM`
  - tag: `沙发` → ``
  - source: `Ely北美轻奢软体系列（RH风格）.pdf` → ``
- **COPENHAGEN
HANDASSEMBLEDINNORIHCAROLINA
GUARANTEEDFORLIFE** (匹配方法: product_name)
  - model_number: `AW1162` → `INTRODUCING`
  - tag: `沙发` → ``
  - source: `Ely北美轻奢软体系列（RH风格）.pdf` → ``
- **DILLON
MODULAR
GUARANTEEDFORLIFE** (匹配方法: product_name)
  - model_number: `AW1163` → `MODULAR`
  - tag: `沙发` → ``
  - source: `Ely北美轻奢软体系列（RH风格）.pdf` → ``
- **MODENA
CHESTERFIELD
HANDASSEMBLEDINNORTHAMERICA
GUARANTEEDFORLIFE** (匹配方法: product_name)
  - model_number: `AW1165` → `CHESTERFIELD`
  - tag: `沙发` → ``
  - source: `Ely北美轻奢软体系列（RH风格）.pdf` → ``

### 一涧物

**多余 SKU (33):**

- 皮革
- 木工机械
- 玛格里椅
- 远山椅
- 卡尔椅
- Armchair
- 网遥椅
- 昌迪椅
- 老虎油蜡椅
- Armchair
- 亲屋边柜
- 层彷置物架
- 朱颜柜
- 方块柜
- 艺术拼花柜
- 拱门柜
- 开曼柜
- 雎颢柜
- 欢欣柜
- 茶几边几系列
- 知遇桌
- 晨光桌
- 丹霞圆桌
- 富雅桌
- 今昔桌
- 梅林方桌
- 度吧椅
- 摩卡椅
- 蒙德里床
- 月轮床
- 澹延床
- 涟漪床
- 凡达梳妆台

**字段差异 (前10):**

- **GZ134 云鹤电视柜
颜色：胡桃色
220*40*52
材质：实木+饰面板+不锈钢** (匹配方法: model_prefix)
  - source: `一涧物家具全系列图册2025` → `printed`
- **Gz132电视柜
颜色：中古色
220*40*48
材质：实木+饰面板+不锈钢** (匹配方法: model_prefix)
  - product_name: `Gz132电视柜` → `Gz132 电视柜`
  - source: `一涧物家具全系列图册2025` → `image`
- **Gz133云鹤柜
颜色：中古色
材质：实木+饰面板+不锈钢
200*40*52** (匹配方法: model_prefix)
  - product_name: `Gz133云鹤柜` → `Gz133 云鹤柜`
  - source: `一涧物家具全系列图册2025` → `image`
- **Gz332南窗电视柜
颜色：中古色
180*40*63
材质：实木+饰面板+不锈钢** (匹配方法: model_prefix)
  - product_name: `Gz332南窗电视柜` → `南窗电视柜`
  - source: `一涧物家具全系列图册2025` → `OCR`
- **GZ121本初电视柜
颜色：中古色
材质：实木+饰面板+不锈钢
200*40*52** (匹配方法: model_prefix)
  - product_name: `GZ121本初电视柜` → `本初电视柜`
  - source: `一涧物家具全系列图册2025` → ``
- **GZ123脉络边柜
材质：实木+饰面板
颜色：中古色
150*40*90** (匹配方法: model_prefix)
  - product_name: `GZ123脉络边柜` → `脉络边柜`
  - source: `一涧物家具全系列图册2025` → ``
- **GZ122本初边柜
颜色：中古色
材质：实木＋饰面板＋不锈钢
65*40*100** (匹配方法: model_prefix)
  - product_name: `GZ122本初边柜` → `本初边柜`
  - source: `一涧物家具全系列图册2025` → ``
- **CJ239乐家茶几可折叠
颜色：中古色
材质：杨木
95*45*49** (匹配方法: model_prefix)
  - product_name: `CJ239乐家茶几可折叠` → `乐家茶几可折叠`
  - source: `一涧物家具全系列图册2025` → `image`
- **JY902卡西那单人沙发
颜色：面料颜色可选
材质：不锈钢＋仿晨皮
99*73*68** (匹配方法: model_prefix)
  - product_name: `JY902卡西那单人沙发` → `卡西那单人沙发`
  - source: `一涧物家具全系列图册2025` → `OCR`
- **Gz103阿道夫餐边柜
颜色：拼色
材质：实木多层板
180*40*90** (匹配方法: model_prefix)
  - product_name: `Gz103阿道夫餐边柜` → `阿道夫餐边柜`
  - source: `一涧物家具全系列图册2025` → ``

### 2025新款电子版

**多余 SKU (33):**

- 茶几系列
- 茶几
- 边几
- 边几
- 边几
- 边几
- Side Table
- 边几
- 边几
Φ500xH470mm
- 茶几
- 茶几
- 电视柜
- 电视柜搭板
- 角几
- 角几
- 茶几
- 茶几
- 茶几
角几
- 茶几
- 角几
- 边几
- 边几
- 功夫茶几
- 茶具套装
- 脚凳
- 茶几
- 角几
- 半圆茶几
- 组合茶几
- 茶几
- 电视柜
- 电视柜
- 组合茶几

**字段差异 (前10):**

- **型号：WT-57#
规格：Φ900xH300mm(大圆)
Φ 600xH420mm (小圆)** (匹配方法: model_prefix)
  - product_name: `型号：WT-57#` → `WT-57*`
  - tag: `25新款电子版` → ``
  - source: `2025新款电子版.pdf` → ``
- **型号：WT-95
规格：1280x700xH350mm(茶几)
Φ500xH470mm(边几)** (匹配方法: model_prefix)
  - product_name: `型号：WT-95` → `茶几`
  - tag: `25新款电子版` → ``
  - source: `2025新款电子版.pdf` → ``
- **型号：WT-68
规格：950x950xH300mm（大方几）
500x500xH450mm（小方几）** (匹配方法: model_prefix)
  - product_name: `型号：WT-68` → `大方几`
  - tag: `25新款电子版` → ``
  - source: `2025新款电子版.pdf` → ``
- **型号：WT-28#餐台
规格：Φ1350xH780mm
餐椅：WT-28#** (匹配方法: model_prefix)
  - product_name: `型号：WT-28#餐台` → `餐台`
  - tag: `25新款电子版` → ``
  - source: `2025新款电子版.pdf` → ``
- **型号：WT-96
规格：Φ900xH350mm（茶几)
Φ500xH450mm（边几)** (匹配方法: model_prefix)
  - product_name: `型号：WT-96` → `茶几`
  - tag: `25新款电子版` → ``
  - source: `2025新款电子版.pdf` → ``
- **型号：WT-78#
规格：1500x800xH430mm
1600x900xH430mm** (匹配方法: model_prefix)
  - product_name: `型号：WT-78#` → `茶几`
  - tag: `25新款电子版` → ``
  - source: `2025新款电子版.pdf` → ``
- **型号：WT-72
规格：900x900xH330mm（茶几)
500x500xH400mm（边几)** (匹配方法: model_prefix)
  - product_name: `型号：WT-72` → `茶几`
  - tag: `25新款电子版` → ``
  - source: `2025新款电子版.pdf` → ``
- **型号：WT-81#
规格：1500x900xH330mm(茶几)
600x420xH470mm (边几)** (匹配方法: model_prefix)
  - product_name: `型号：WT-81#` → `茶几`
  - tag: `25新款电子版` → ``
  - source: `2025新款电子版.pdf` → ``
- **型号：WT-05”花瓣茶几
规格： Φ900x780xH360mm
Φ630x600xH420mm** (匹配方法: model_prefix)
  - product_name: `型号：WT-05”花瓣茶几` → `花瓣茶几`
  - tag: `25新款电子版` → ``
  - source: `2025新款电子版.pdf` → `OCR`
- **型号：WT-17#
规格：800x800xH350mm(大方几)
600x600xH450mm（小方几)** (匹配方法: model_prefix)
  - product_name: `型号：WT-17#` → `WT-17* Coffee Table`
  - tag: `25新款电子版` → ``
  - source: `2025新款电子版.pdf` → ``

### 2025秋季新款电子画册

**多余 SKU (37):**

- 边几
- 方几
- 边几
- 边几
- 边几
- 椭圆茶几
- 椭圆茶几
- 方几
- 转动茶几
- 边几
- 转动茶几
- 边几
- 装饰画
- 花瓶
- 装饰鱼摆件
- 茶杯
- 金色镂空果盘
- 边几
- 抱枕
- 盆栽
- 装饰碗
- 咖啡杯碟
- 边几
- 边几
- 边几
- 圆几
- 圆几
- 茶几
- 边几
- 茶几
- 茶几
- 茶几
- 边几
- 拉伸茶车
- 转动茶车
- 装饰画
- 装饰摆件

**字段差异 (前10):**

- **型号：2533#圆几规格：Φ900x300mm
型号：2526#/胡桃色边几：Φ450x450mm** (匹配方法: product_name)
  - product_name: `型号：2533#圆几规格：Φ900x300mm` → `圆几`
  - tag: `25秋季新款画册` → ``
  - source: `2025秋季新款电子画册.pdf` → `OCR`
- **型号：2527#胡桃色转动茶几：1050-1300x700x370mm
型号：2526#胡桃色边几：Φ450x450mm** (匹配方法: product_name)
  - product_name: `型号：2527#胡桃色转动茶几：1050-1300x700x370mm` → `转动茶几`
  - tag: `25秋季新款画册` → ``
  - source: `2025秋季新款电子画册.pdf` → `OCR`
- **型号：2530#圆几：Φ850x310mm
圆几铁底座
型号：2528#胡桃色边几：Φ450x450mm** (匹配方法: product_name)
  - product_name: `型号：2530#圆几：Φ850x310mm` → `圆几`
  - tag: `25秋季新款画册` → ``
  - source: `2025秋季新款电子画册.pdf` → ``
- **型号：2526#
长几：1300x750x370mm（胡桃色）
边几：Φ450x450mm（深色）** (匹配方法: position)
  - product_name: `型号：2526#` → `边几`
  - tag: `25秋季新款画册` → ``
  - source: `2025秋季新款电子画册.pdf` → `image`
- **型号：2526#
方几：900x900x330mm（胡桃色）
边几：Φ450x450mm（深色)** (匹配方法: position)
  - product_name: `型号：2526#` → `边几`
  - tag: `25秋季新款画册` → ``
  - source: `2025秋季新款电子画册.pdf` → ``
- **型号：2533#胡桃色
型号：2526#胡桃色
椭圆茶几：1400x800x310mm
边几：Φ450x450mm** (匹配方法: position)
  - product_name: `型号：2533#胡桃色` → `长几`
  - tag: `25秋季新款画册` → ``
  - source: `2025秋季新款电子画册.pdf` → `OCR`
- **型号：2523#
拉伸茶车：800-1300x450x650mm** (匹配方法: position)
  - product_name: `型号：2523#` → `边几`
  - tag: `25秋季新款画册` → ``
  - source: `2025秋季新款电子画册.pdf` → `OCR`
- **型号：2537#
转动茶车：1010x440x740mm** (匹配方法: position)
  - product_name: `型号：2537#` → `长几`
  - tag: `25秋季新款画册` → ``
  - source: `2025秋季新款电子画册.pdf` → `OCR`

### 万日红2025中古风家具

**多余 SKU (14):**

- 休闲椅
- 茶几
- 茶几
- 茶几
- 茶几
- 小圆几
- 角几
- 六斗柜
- 六斗柜
- 休闲椅
- 休闲椅
- 蝴蝶椅
- 餐椅
- 餐边柜

**字段差异 (前10):**

- **A310#K椅
A19#圆几
600*600*670mm
颜色:中古色/烟熏色
材质:白蜡木** (匹配方法: model_prefix)
  - product_name: `A310#K椅` → `A310#K 椅`
  - specs: `K椅,圆几600*600*670mm` → ``
  - color: `中古色/烟熏色` → `中古色/ 烟熏色`
  - tag: `中古风` → ``
  - source: `万日红2025中古风家具` → ``
- **A22#蝴蝶椅
颜色:中古色/烟熏色
材质:白蜡木** (匹配方法: model_prefix)
  - product_name: `A22#蝴蝶椅` → `蝴蝶椅`
  - specs: `蝴蝶椅` → `材质：白蜡木`
  - color: `中古色/烟熏色` → `中古色/ 烟熏色`
  - tag: `中古风` → ``
  - source: `万日红2025中古风家具` → `image`
- **A36#餐边柜
1500*400*1900mm
颜色:中古色/烟熏色
材质:白蜡木** (匹配方法: model_prefix)
  - product_name: `A36#餐边柜` → `餐边柜`
  - specs: `餐边柜1500*400*1900mm` → `1500*400*1900mm`
  - tag: `中古风` → ``
  - source: `万日红2025中古风家具` → ``
- **A11#角几 580*580*580mm
颜色:中古色/烟熏色
材质:白蜡木** (匹配方法: model_prefix)
  - product_name: `A11#角几 580*580*580mm` → `角几`
  - specs: `角几580*580*580mm` → `580*580*580mm`
  - color: `中古色/烟熏色` → `中古色/ 烟熏色`
  - tag: `中古风` → ``
  - source: `万日红2025中古风家具` → `page`
- **A01#茶几
1400*750*400mm
颜色:中古色/烟熏色
材质:白蜡木** (匹配方法: model_prefix)
  - product_name: `A01#茶几` → `茶几`
  - specs: `茶几1400*750*400mm` → `1400*750*400mm`
  - tag: `中古风` → ``
  - source: `万日红2025中古风家具` → ``
- **A28#高柜1000*400*1580mm
颜色:中古色/烟熏色
材质:白蜡木** (匹配方法: model_prefix)
  - product_name: `A28#高柜1000*400*1580mm` → `高柜`
  - specs: `高柜1000*400*1580mm` → `1000*400*1580mm`
  - tag: `中古风` → ``
  - source: `万日红2025中古风家具` → `OCR`
- **床头柜** (匹配方法: model_number)
  - specs: `床1820*2112*1410mm,床头柜420*400*540mm,六斗柜1400*400*850mm` → `420*400*540mm`
  - color: `中古色 / 烟熏色` → `中古色/烟熏色`
  - tag: `中古风` → ``
  - source: `万日红2025中古风家具` → `image`
- **六斗柜** (匹配方法: model_number)
  - specs: `颜色： 中古色 / 烟熏色` → `1400*400*850mm`
  - tag: `中古风` → ``
  - source: `万日红2025中古风家具` → `image`
- **妆台** (匹配方法: model_number)
  - specs: `颜色:中古色/烟熏色` → `1000*400*750mm/1000*400*730mm`
  - tag: `中古风` → ``
  - source: `万日红2025中古风家具` → `OCR`
- **床** (匹配方法: model_number)
  - product_name: `床` → `软包床`
  - specs: `床1820*2112*1275mm,床头柜480*400*510mm,装饰柜1500*400*760mm` → `1820*2112*1275mm`
  - tag: `中古风` → ``
  - source: `万日红2025中古风家具` → ``

### 万日红实木家具

**多余 SKU (27):**

- 大茶几
- 休闲椅
- 休闲椅
- 长茶几
- 圆凳
- 长茶几
- 茶水柜
- 电视柜
- 小茶几
- 休闲椅
- 直排沙发
- 长茶几
- 餐椅
- 转盘
- 餐边柜
- W15# 软包椅
- 书椅
- W29#副椅
- 休闲椅
- 副椅
- 副椅
- 休闲椅
- 玄关柜
- 书桌
- 长条凳
- 床头柜
- 软包床

**字段差异 (前10):**

- **W86#组合电视柜
中柜:1800*430*370mm
边柜:980*430*630mm** (匹配方法: model_prefix)
  - product_name: `W86#组合电视柜` → `组合电视柜`
  - specs: `中柜:1800*430*370mm,边柜:980*430*630mm` → `中柜:1800*430*370mm;边柜:980*430*630mm`
  - tag: `实木家具` → ``
  - source: `万日红实木家具` → `image`
- **沙发** (匹配方法: model_number)
  - specs: `双人位:2040*920*1100mm` → `双人位：2040*920*1100mm; 四人位：2940*920*1100mm`
  - color: `黑檀色` → ``
  - tag: `实木家具` → ``
  - source: `万日红实木家具` → `OCR`
- **休闲椅** (匹配方法: model_number)
  - specs: `颜色:黑檀色` → ``
  - color: `黑檀色` → ``
  - tag: `实木家具` → ``
  - source: `万日红实木家具` → `OCR`
- **沙发** (匹配方法: model_number)
  - specs: `单人位:1320*910*950mm` → `单人位: 1320*910*950mm
双人位: 1950*910*950mm
三人位: 2450*910*950mm
五人位: 2850*910*950mm`
  - tag: `实木家具` → ``
  - source: `万日红实木家具` → `OCR`
- **沙发** (匹配方法: model_number)
  - specs: `单人位:1420*920*1030mm` → `单人位：1420*920*1030mm; 双人位：2030*920*1030mm; 三人位：2530*920*1030mm; 五人位：3200*920*1040mm`
  - tag: `实木家具` → ``
  - source: `万日红实木家具` → `OCR`
- **沙发** (匹配方法: model_number)
  - model_number: `W8809#` → `W8809`
  - specs: `单人位:1320*910*1090mm` → `单人位:1320*910*1090mm;双人位:1950*910*1090mm;三人位:2450*910*1090mm`
  - tag: `实木家具` → ``
  - source: `万日红实木家具` → `image`
- **小茶几** (匹配方法: model_number)
  - model_number: `W01#` → `W01`
  - specs: `W#圆凳410*410*420mm` → `610*610*610mm`
  - tag: `实木家具` → ``
  - source: `万日红实木家具` → `image`
- **沙发** (匹配方法: model_number)
  - specs: `双人位:2040*920*1100mm` → `双人位:2040*920*1100mm; 四人位:2940*920*1100mm`
  - color: `黑檀色` → ``
  - tag: `实木家具` → ``
  - source: `万日红实木家具` → `OCR`
- **大茶几** (匹配方法: model_number)
  - color: `黑檀色` → ``
  - tag: `实木家具` → ``
  - source: `万日红实木家具` → `OCR`
- **休闲椅** (匹配方法: model_number)
  - specs: `颜色:黑檀色` → ``
  - tag: `实木家具` → ``
  - source: `万日红实木家具` → `OCR`

### 万日红实木家具2

**缺失 SKU (2):**

- 503# 1+2+3沙发80#(棉麻布包)
单位:890*900*730mm
双位:1540*900*730mm
三位:2040*900*730mm

503#转角沙发81#(科技布包)
3250*1900*730mm (行 129)
- 505#1+2+3高箱沙发83#(棉麻布包)
单位:830*865*730mm
双位:1480*865*730mm
三位:1980*865*730mm

505#转角高箱沙发83#(棉麻布包)
2930*1865*730mm (行 130)

**字段差异 (前10):**

- **205# 衣帽架
450*1850mm** (匹配方法: name_as_model)
  - product_name: `205# 衣帽架` → `衣帽架`
  - specs: `衣帽架450*1850mm` → `450*1850mm`
  - tag: `实木家具` → ``
  - source: `万日红实木家具2` → `OCR`
- **21# 床头柜
520*420*480mm** (匹配方法: name_as_model)
  - product_name: `21# 床头柜` → `床头柜`
  - specs: `床头柜520*420*480mm` → `520*420*480mm`
  - tag: `实木家具` → ``
  - source: `万日红实木家具2` → `OCR`
- **28# 床头柜
520*400*520mm** (匹配方法: name_as_model)
  - product_name: `28# 床头柜` → `床头柜`
  - specs: `床头柜520*400*520mm` → `520*400*520mm`
  - tag: `实木家具` → ``
  - source: `万日红实木家具2` → `OCR`
- **23# 床头柜
505*425*500mm** (匹配方法: name_as_model)
  - product_name: `23# 床头柜` → `床头柜`
  - specs: `床头柜505*425*500mm` → `505*425*500mm`
  - tag: `实木家具` → ``
  - source: `万日红实木家具2` → `OCR`
- **22# 床头柜
400*350*490mm** (匹配方法: name_as_model)
  - product_name: `22# 床头柜` → `床头柜`
  - specs: `床头柜400*350*490mm` → `400*350*490mm`
  - tag: `实木家具` → ``
  - source: `万日红实木家具2` → `OCR`
- **26# 床头柜
510*420*480mm** (匹配方法: name_as_model)
  - product_name: `26# 床头柜` → `床头柜`
  - specs: `床头柜510*420*480mm` → `510*420*480mm`
  - tag: `实木家具` → ``
  - source: `万日红实木家具2` → `OCR`
- **12# 餐椅
850*470*460mm** (匹配方法: name_as_model)
  - product_name: `12# 餐椅` → `餐椅`
  - specs: `餐椅850*470*460mm` → `470*460*850mm`
  - tag: `实木家具` → ``
  - source: `万日红实木家具2` → `OCR`
- **13# 餐椅
630*530*760mm** (匹配方法: name_as_model)
  - product_name: `13# 餐椅` → `餐椅`
  - specs: `餐椅630*530*760mm` → `420*400*870mm`
  - tag: `实木家具` → ``
  - source: `万日红实木家具2` → `OCR`
- **16# 餐椅
630*530*760mm** (匹配方法: name_as_model)
  - product_name: `16# 餐椅` → `餐椅`
  - specs: `餐椅630*530*760mm` → `470*460*850mm`
  - tag: `实木家具` → ``
  - source: `万日红实木家具2` → `OCR`
- **15# 书椅
630*530*760mm** (匹配方法: name_as_model)
  - product_name: `15# 书椅` → `书椅`
  - specs: `书椅630*530*760mm` → `630*530*760mm`
  - tag: `实木家具` → ``
  - source: `万日红实木家具2` → `OCR`

### 万日红家具B软床图册)宝丽 (1)(1)

**缺失 SKU (114):**

- T31#
长宽高
236*205*112cm
面料：头层牛皮
填充：5A羽绒充包
内材：全实木框架
骨架：钢木10Cm
脚高:5CM落地脚
围边：可改齐边 (行 15)
- T35#
长宽高
228*208*105cm
面料：泰迪布
填充：高回弹海绵
内材：全实木框架
骨架：钢木10Cm
脚高:15CM悬浮脚
围边：可改齐边 (行 16)
- T33#
长宽高
240*268*115cm
面料：羊绒棉麻
填充：高回弹海绵
内材：全实木框架
骨架：钢木10Cm
脚高:5CM脚 
围边：可改齐边 (行 18)
- T32#
长宽高
220*222*107cm
面料：棉麻
填充：高回弹海绵
内材：全实木框架
骨架：钢木10Cm
脚高:15CM悬浮脚
围边：可改齐边 (行 19)
- T23#
长宽高
220*203*115
面料：头层黄牛皮
材质：羽绒包
内材：全实木框架
骨架：钢木10CM
脚高：15分脚 齐边：可改围边
气动：可加气动 (行 20)
- B829#
长宽高
228*205*110
面料：头层黄牛皮
材质：紫罗兰海棉
内材：全实木框架
骨架：钢木10CM
脚高：5分落地脚
围边：可改齐边
气动：可加气动 (行 21)
- T15#
长宽高
225*190*116cm
面料：头层黄牛皮
填充：羽绒包
内材：全实木框架
骨架：钢木10Cm
脚高:5CM木脚 
齐边：可改围边 (行 22)
- T16#
长宽高
230*200*96cm
面料：泰迪绒
材质：高回弹绵
内材：全实木框架
骨架：钢木10Cm
脚高:5CM木脚
围边：可改齐边 (行 23)
- 235#
长宽高
225*192*118
面料：头层黄牛皮
材质：高回弹绵
内材：全实木框架
骨架：钢木10Cm
脚高:5CM落地脚
齐边：可改围边 (行 25)
- 大黑牛#
长宽高
238*203*88
面料:头层牛皮
材质:紫罗兰海绵
内衬:全实木框架
骨架:钢木10CM
脚高:12不锈钢
围边:可改齐边
气动:可加气动 (行 26)
- 009#
长宽高
235*200*116cm
面料：头层黄牛皮
填充：羽绒包 
内材：全实木框架
骨架：钢木10Cm
脚高:5CM木脚 
围边：可改齐边 (行 28)
- T17#
长宽高
238*200*107cm
面料：头层黄牛皮
填充：羽绒包
内材：全实木框架
骨架：钢木10Cm
脚高:5CM木脚
围边：可改齐边 (行 29)
- G03 - A#
长宽高
210*183*110
有模型.高清图
面料: 头层黄牛皮
靠背: 高回弹海绵
内材: 全实木框架
骨架: 钢木10CM
脚高: 15CM整体架
齐边: 可改围边
气动: 可加气动 (行 30)
- T03#
长宽高
237*205*105
面料:头层黄牛皮
靠背:紫罗兰海绵
内衬:全实木框架
骨架:钢木10CM
脚高:15分不锈钢
齐边:可改齐边
气动:可加气动 (行 31)
- B691#
长宽高
224*203*105
面料: 头层黄牛皮
(拼接)
材质: 紫罗兰绵内
材: 全实木框架
骨架: 钢木10CM
脚高: 15分悬浮脚
围边: 可改齐边
气动: 可加气动 (行 33)
- 2317#
长宽高
230*210*116
面料：头层黄牛皮
材质：高回弹绵
内材：全实木框架
骨架：钢木10CM
脚高：13分三叉脚
围边：可改齐边
气动：可加气动 (行 34)
- #80T
长宽高
210*186*106
面料:头层黄牛皮
靠背:紫罗兰海绵
内材:全实木框架
骨架:加密榉木
脚高:18分不锈钢 (行 36)
- T09#
长宽高
210*186*105
面料:头层黄牛皮
靠背:紫罗兰海绵
内材:全实木框架
骨架:加密榉木
脚高:18分不锈钢 (行 37)
- 长宽高
220*185*98
面料：头层黄牛皮
材质：高回弹绵
内材：全实木框架
骨架：钢木10Cm
脚高:15c不锈钢脚
齐边：不可改围边
特定：三角斜边
鸭掌脚 (行 38)
- 215#
长宽高
225*195*98
面料：头层黄牛皮
材质：高回弹绵
填充：羽绒填充
内材：全实木框架
骨架：钢木10Cm
脚高:15分 
特点：悬浮加灯
水晶脚 (行 39)
- 2309#
长宽高
238*210*105
面料：头层黄牛皮
材质：紫罗兰绵
内材：全实木框架
骨架：钢木10CM
脚高：5分实木脚
围边：可改齐边
气动：可加气动 (行 40)
- 833#
长宽高
220*187*118
面料：头层黄牛皮
材质：高回弹绵
内材：全实木框架
骨架：钢木10CM
脚高：5分实木脚
围边：可改齐边
气动：可加气动 (行 41)
- B835#
长宽高
218*185*92
面料:头层黄牛
皮材质:紫罗兰靠
背内衬:全实木框
架骨架:进口松木
板脚高:15分实木
脚齐边:可改脚边
气动:可加气动 (行 42)
- 219#
长宽高
223*182*110
面料: 头层黄牛皮
材质: 高回弹绵
内材: 全实木框架
骨架: 钢木10Cm
脚高:5CM落地脚
齐边: 可改围边 (行 45)
- 2312#
长宽高
230*195*75
面料：头层牛皮
材质：紫罗兰海绵
内材：全实木框架
骨架：钢木10CM
脚高：5分实木脚
围边：可改齐边
气动：可加气动 (行 46)
- 2315
长宽高
230*195*115
面料：头层牛皮
材质：紫罗兰海绵
内材：全实木框架
骨架：钢木10CM
脚高：15分脚
围边：可改齐边
气动：可加气动 (行 47)
- B2308#
长宽高
220*189*99
面料：羊羔绒
材质：高回弹海绵
内材：全实木框架
骨架：钢木10CM
脚高：5分实木脚
齐边：可改围边
气动：可加气动 (行 50)
- B2309#
长宽高
223*202*96
面料：头层牛皮
材质：高回弹海绵
内材：全实木框架
骨架：钢木10CM
脚高：5分实木脚
围边：可改齐边
气动：可加气动 (行 51)
- T07#
长宽高
208*187*99
面料:头层黄牛皮
靠背:紫罗兰海绵
内材:全实木框架
骨架:加密榉木
脚高:18分不锈钢
床边:白蜡木 (行 53)
- B826#
长宽高
225*188*113
面料:头层黄牛皮
内材:全实木框架
骨架:钢木10CM
脚高:15分黑钛
齐边:可改围边
气动:可加气动 (行 54)
- B695#
长宽高
218*182*110
面料：头层黄牛皮
材质：紫罗兰海绵
内材：全实木框架
骨架：钢木10CM 脚
高：15分金属脚齐边
：可改围边
气动：可加气动
五金：可取消 (行 55)
- 216#
长宽高
218*192*120
面料：头层黄牛皮
材质：高回弹海绵
框架：全实木框架
骨架：10分钢木架
脚高：15分脚 
齐边：可改围边
气动：可加气动 (行 57)
- 2311#
长宽高
230*210*116
面料：头层黄牛皮
材质：高回弹绵
内材：全实木框架
骨架：钢木10CM
脚高：10分三叉脚
围边：可改齐边
气动：可加气动 (行 58)
- 2313#
长宽高
232*196*110
面料：头层黄牛皮
材质：高回弹绵
内材：全实木框架
骨架：钢木10CM
脚高：5分实木脚
围边：可改齐边
气动：可加气动 (行 59)
- 2316#
长宽高
220*189*115
面料：头层黄牛皮
材质：羽绒内包
内材：全实木框架
骨架：钢木10CM
脚高：15分金属脚
齐边：可改围边
气动：可加气动 (行 60)
- 2405#
长宽高
225*202*117
面料：头层黄牛皮
材质：羽绒内包
内材：全实木框架
骨架：钢木10CM
脚高：15分金属脚
围边：可改齐边
气动：可加气动 (行 61)
- 2315#
长宽高
220*196*117
面料：头层黄牛皮
材质：高回弹绵
内材：全实木框架
骨架：钢木10CM
脚高：15分三叉脚
齐边：可改围边
气动：可加气动 (行 62)
- 2312#
长宽高
220*200*117
面料：头层黄牛皮
材质：高回弹绵
内材：全实木框架
骨架：钢木10CM
脚高：15分三叉脚
齐边：可改围边
气动：可加气动 (行 63)
- B690#
长宽高
226*195*105
面料：头层黄牛皮
材质：紫罗兰海棉
内材：全实木框架
骨架：钢木10CM
脚高：悬浮脚
围边：可改齐边
气动：可加气动 (行 64)
- B957#
长宽高
230*210*113
面料：头层黄牛皮
材质：紫罗兰绵
内材：全实木框架
骨架：钢木10CM
脚高：10分镜面脚
围边：可改齐边
气动：可加气动 (行 65)
- 836#
长宽高
218*188*116
面料：头层黄牛皮
材质：高回弹海棉
内材：全实木框架
骨架：钢木10CM
脚高：15分三叉脚
齐边：可改围边
气动：可加气动 (行 66)
- 861#
长宽高
218*186*113
面料：头层黄牛皮
材质：羽绒靠包
内材：全实木框架
骨架：钢木10CM
脚高：15三叉脚
围边：可改齐边
气动：可加气动 (行 67)
- 2402#
长宽高
226*235*108
面料：头层黄牛皮
材质：高回弹海绵
内材：全实木框架
骨架：钢木10CM
脚高：落地脚 围边：可改齐边
气动：可加气动 (行 68)
- 2318#
长宽高
225*205*105
面料：头层黄牛皮
材质：高回弹海绵
内材：全实木框架
骨架：钢木10CM
脚高：15悬浮脚
围边：可改齐边
气动：可加气动 (行 69)
- B830#
长宽高
225*217*105
面料：头层牛皮
材质：紫罗兰海绵
内材：全实木框架
骨架：钢木10CM
脚高：5分实木脚
围边：可改齐边
气动：可加气动 (行 70)
- B2305#
长宽高
237*210*93
面料：头层牛皮
材质：羽绒靠包
内材：全实木框架
骨架：钢木10CM
脚高：5分实木脚
围边：可改齐边
气动：可加气动 (行 71)
- 687-B#
长宽高
225*193*110
面料：头层黄牛皮
材质：羽绒靠包
内材：全实木框架
骨架：钢木10CM
脚高：12CM飞机脚
齐边：可改围边
气动：可加气动 (行 72)
- B857#
长宽高
218*186*110
面料：加厚黄牛皮
材质：5A鹅绒靠包
内材：全抛光实木
骨架：钢木10CM
脚高：图片五金脚
齐边：可改围边
气动：可加气动 (行 73)
- B855#
长宽高
226*206*106
面料：加厚黄牛皮
材质：羽绒靠包
内材：全实木框架
骨架：钢木10CM
脚高：图片五金脚
围边：可改齐边
气动：不可加气动 (行 74)
- 952#
长宽高
224*208*110
面料：头层黄牛皮
材质：高回弹海绵
内材：全实木框架
骨架：钢木10CM
脚高：12CM飞机脚
齐边：可改围边
气动：可加气动 (行 75)
- B839#
长宽高
231*204*115
面料：头层牛皮
材质：紫罗兰海绵
内材：全实木框架
骨架：钢木10CM
脚高：15镜面脚
围边：可改齐边
气动：不可加气动 (行 76)
- B815-A#
长宽高
216*182*105
面料：头层牛皮
特点：悬浮感应灯
材质：羽绒靠包
内材：全实木框架
骨架：10分钢木
脚高：15分悬浮脚
齐边：可改围边
悬浮：可改落地脚
气动：不可加气动 (行 77)
- 2310#
长宽高
220*225*95
面料：头层黄牛皮
材质：高回弹海绵
内材：全实木框架
骨架：钢木10CM
脚高：15分脚 齐边：可改围边
气动：可加气动 (行 78)
- T21#
长宽高
230*192*112cm
面料：头层牛皮
材质：高回弹海绵
内材：全实木框架
骨架：钢木10CM
脚高：15分脚
齐边：可改围边
气动：可加气动 (行 79)
- B956#
长宽高
218*186*117
面料：头层黄牛皮
填充：羽绒包床头
内材：全实木框架
骨架：配10分钢木
脚高：15碳素钢脚
齐边：可改围边
气动：可加气动 (行 80)
- B837#
长宽高
231*213*115
面料：摔纹黄牛皮
特点：精工刺绣
材质：紫罗兰海绵
内材：全实木框架
骨架：钢木10CM
脚高：15枪黑脚
齐边：可改齐边
气动：可加气动 (行 81)
- 2316#
长宽高
210*192*110
面料：头层黄牛皮
材质：高回弹绵
内材：全实木框架
骨架：钢木10CM
脚高：15分三叉脚
齐边：可改围边
气动：可加气动 (行 82)
- 2318#
长宽高
215*187*116
面料：头层黄牛皮
材质：高回弹绵
内材：全实木框架
骨架：钢木10CM
脚高：15分三叉脚
齐边：可改围边
气动：可加气动 (行 83)
- #长宽高
220*190*115
面料：头层牛皮
特点：悬浮感应灯
材质：高回弹海绵
内材：全实木框架
骨架：10分钢木
脚高：15分脚 齐边：可改围边
气动：可加气动 (行 84)
- 158#
长宽高
230*205*115
面料: 水性真皮
材质: 紫罗兰海绵
内材: 全实木弯板
骨架: 钢木10CM
脚高:15分脚
围边:不可改齐边
气动:不可加气动 (行 86)
- 135#
长宽高
218*189*115
面料:头层真皮
材质:羽绒靠包
内衬:全实木雪板
骨架:钢木10CM
脚高:15分脚
齐边:可改围边
气动:不可加气动 (行 87)
- B696#
长宽高
225*196*100
面料：头层黄牛皮
填充：超软高回弹
内材：全实木框架
骨架：配10分钢木
脚高：5分实木脚
围边：可改齐边
气动：可加气动 (行 88)
- B869#
长宽高
226*196*105
面料：头层黄牛皮
填充：超软高回弹
内材：全实木框架
骨架：配10分钢木
脚高：15碳素钢脚
围边：可改齐边
气动：可加气动 (行 89)
- G32#
长宽高
242*223*98
面料：头层黄牛皮
特点：大靠背设计
材质：紫罗兰海绵
内材：全实木框架
骨架：钢木10CM
脚高：5分镜面脚
围边：不可改齐边
气动：不可加气动 (行 90)
- 2306#
长宽高
209*182*100
面料：头层黄牛皮
材质：紫罗兰海绵
内材：全实木框架
骨架：钢木10CM
脚高：12CM飞机脚
齐边：可改围边
气动：可加气动 (行 91)
- B825#
长宽高
218*186*116
面料：头层黄牛皮
填充：高回弹海绵
内材：全实木框架
骨架：钢木10CM
脚高：5分镜面脚
围边：不可改齐边
气动：不可加气动 (行 95)
- B809#
长宽高
230*212*105
面料：头层黄牛皮
靠包：紫罗兰海绵
内材：全实木框架
骨架：钢木10CM
脚高：15分黑钛
围边：可改齐边
气动：可加气动 (行 96)
- B2319
长宽高
226*203*100
特点：人体感应灯
面料：头层黄牛皮
靠包：5A羽绒靠包
内材：全实木框架
骨架：钢木10CM
脚高：15分黑钛
齐边：可改围边
气动：可加气动 (行 97)
- B618#
长宽高
216*182*110
面料：磨砂绒布
靠包：高回弹海绵
内材：全实木框架
骨架：钢木10CM
脚高：15分悬浮脚
悬浮：可做落地
气动：可做气动 (行 98)
- B693#
长宽高
220*188*105
面料：头层黄牛皮
材质：高弹绵靠包
内材：全实木框架
骨架：钢木10CM
脚高：15CM飞机脚
大齐边：可做围边
气动：可加气动 (行 99)
- 长宽高
225*182*110
908 - A
面料：头层黄牛皮
材质：紫罗兰海绵
内衬：全实木框架
脚高：15分飞机脚
齐边：可改围边
气动：可加气动 (行 100)
- M0089#
长宽高
233*230*102
面料：头层黄牛
皮特点：不分左右
材质：紫罗兰海绵
内材：全实木框架
骨架：钢木10CM
脚高;10CM三叉脚
床尾：可改齐边
气动：可加气动 (行 101)
- B558#
长宽高
226*181*113
有模型
面料：头层黄牛材
质：紫罗兰海绵内
材：全实木框架骨
架：钢木10CM 脚
高：15分高脚围
边：可改齐边气
动：可加气动 (行 102)
- B510#
面料：头层黄牛
材质：高回弹海绵
内材：全实木框架
骨架：钢木10CM
脚高：15分三叉脚
齐边：可改围边
210*182*1
长宽高
10
气动：可加气动 (行 104)
- B635#
长宽高
218*202*112
面料：头层黄牛皮
材质：5A羽绒包
内材：全实木框架
骨架：钢木10CM
脚高：15分脚 围边：可改齐边
气动：可加气动 (行 105)
- B687A#
长宽高
224*206*106
面料：头层黄牛皮
靠包：羽绒棉 工艺：一体弯板
内材：全实木框架
骨架：5D静音铺板
脚高：15CM隐形脚
齐边：可改围边
气动：不可加气动 (行 106)
- G03-C#
长宽高
213*184*98
面料：头层黄牛皮
靠包：紫罗兰海绵
特点：悬浮感应灯
特点：一体式床架
工艺：扶手冲孔
内材：全实木框架
骨架：钢木10CM
脚高：12CM黑钛脚
齐边：可改围边
气动：可加气动 (行 107)
- B815#
长宽高
224*208*115
面料：头层黄牛皮
靠包：紫罗兰海绵
工艺：手工拉点
内材：全实木框架
骨架：钢木10CM
脚高：18CM隐形脚
齐边：可改围边
气动：不可加气动 (行 108)
- G29#
长宽高
223*192*105
面料：头层牛皮
材质：紫罗兰海绵
内材：全实木框架
骨架：钢木10CM
脚高：10分悬浮脚
齐边：可改围边
气动：可加气动 (行 111)
- 815#
长宽高
212*185*105
面料：头层黄牛
皮特点：网红悬浮
床材质：5A鸭绒靠
包内材：全实木框
架骨架：钢木10CM
脚高：悬浮17CM
齐边：不可改围边
气动：不可加气动 (行 115)
- B836#
长宽高
233*202*106
面料：头层黄牛
皮特点：大牌同款
材质：紫罗兰海棉
内材：全实木框架
骨架：钢木10CM
脚高：5分七字脚
围边：可改齐边
气动：可加气动 (行 116)
- S135#
长宽高
202*185*17
特点：网红悬浮床
材质：白蜡木框架
内材：白蜡木框架
骨架：加厚白蜡木
脚高：悬浮14CM (行 117)
- B853#
长宽高
217*194*115
面料：头层黄牛皮
靠包：紫罗兰海绵
内材：全实木框架
骨架：钢木10CM
脚高：悬浮17CM
齐边：不可改围边
气动：不可加气动 (行 118)
- B608#
长宽高
218*186*116
面料：头层黄牛皮
靠包：高弹棉靠包
内材：全实木框架
骨架：钢木10CM
脚高：15分脚
齐边：可改围边
气动：可加气动 (行 119)
- B832#
长宽高
225*205*120
面料：头层黄牛皮
靠包：紫罗兰海绵
内材：全实木框架
骨架：钢木10CM
脚高：15分镜面脚
围边：可改齐边
气动：可加气动 (行 120)
- B601#
长宽高
225*193*111
面料：头层黄牛皮
靠包：超软羽绒棉
内材：全实木框架
骨架：钢木10CM
脚高：15分黑钛
齐边：可改围边
气动：可加气动 (行 121)
- B851#
长宽高
230*195*118
面料:头层黄牛皮
材质:5A鸭绒填充
内衬:全实木框架
骨架:钢木10CM
脚高:15分飞机脚
齐边:可改围边
气动:可加气动 (行 122)
- B850#
长宽高
225*206*118
面料:头层黄牛皮
材质:紫罗兰海绵
内衬:全实木框架
骨架:钢木10CM
脚高:5分实木脚
围边:可改齐边
围边:可改齐边
气动:可加气动 (行 123)
- BG03#
长宽高
210*181*105
面料：头层黄牛
皮材质：高回弹海
绵内材：全实木框
架骨架：钢木10CM
脚高：15CM碳钢脚
齐边：可改围边
气动：可加气动 (行 124)
- B150#
长宽高
213*182*112
面料：硅胶皮
靠背：紫罗兰海绵
内材：全实木框架
骨架：钢木10CM
脚高：15cm三叉脚
齐边：可改围边
气动：可加气动 (行 126)
- B602#
长宽高
220*188*110
面料：头层黄牛皮
靠背：5A羽绒包
内材：全实木框架
骨架：钢木10CM
脚高：15分三叉脚
齐边：可改围边
气动：可加气动 (行 127)
- B806#
长宽高
228*205*109
面料：头层黄牛皮
靠包：羽绒棉 内材：全实木框架
骨架：钢木10CM
脚高：15分黑钛
围边：可改齐边 (行 128)
- B817#
长宽高
225*210*118
面料：头层黄牛皮
靠包：5A丝绵靠包
内材：全实木框架
骨架：钢木10CM
脚高：15分镜面脚
围边：可改齐边
气动：可加气动 (行 129)
- G01#
长宽高
220*190*120
面料：仿真皮
靠背：紫罗兰海绵 内材：全实木框架
骨架：钢木10CM
脚高：10CM金脚
齐边：可改围边
气动：可加气动 (行 131)
- G03A#
长宽高
210*180*110
面料：头层黄牛皮
特点：高箱带三抽
材质：海绵靠包
内材：全实木框架
骨架：钢木10CM
脚高：15CM飞机脚
齐边：可改围边
气动：可加气动 (行 132)
- G39#
长宽高
210*180*110
面料：头层黄牛皮
特点：侧边带三抽
材质：海绵靠包
内材：全实木框架
骨架：钢木10CM
脚高：15CM飞机脚
齐边：可改围边
气动：可加气动 (行 133)
- BG03-B#
长宽高
218*182*98
面料：头层黄牛皮
内材:全实木框架
材质：紫罗兰海棉
脚高：15CM飞机脚
围边：可改齐边
气动：可加气动 (行 134)
- B828#
长宽高
230*215*112
 面料：双面磨砂布
材质：紫罗兰海棉
内材：全实木框架
骨架：钢木10CM
脚高：15分钛黑
围边：可改齐边
气动：可加气动 (行 135)
- 805#
长宽高
225*215*115
面料：头层黄牛皮
特点：舒适柔软型
材质：高回弹海绵
内材：全实木框架
骨架：钢木10CM
脚高：15分三叉脚
围边：可改齐边
气动：可加气动 (行 136)
- G59#
长宽高
220*200*121
面料：头层黄牛皮
特点：钛金工艺
材质：紫罗兰海绵
内材：全实木框架
骨架：钢木10CM
脚高：12CM飞机脚
床尾：可改齐边
气动：可加气动 (行 137)
- B811#
长宽高
220*215*108
面料:加厚黄牛皮
材质:高回弹海绵
内材:全实木框架
骨架:钢木10CM
脚高:15CM钛黑脚
齐边:可改围边
气动:可加气动 (行 139)
- B821#
长宽高
222*182*110
面料：头层黄牛皮
材质：5A丝绵靠包
内材：全实木框架
骨架：钢木10CM
脚高：15CM飞机脚
齐边：可改围边
气动：可加气动 (行 140)
- G63#
长宽高
220*186*115
面料：头层黄牛皮
材质：5A鹅绒靠包
内材：全实木框架
骨架：钢木10CM脚
脚高：13CM
围边：不可改齐边
气动：可加气动 (行 141)
- G01B#
长宽高
215*186*120
面料：耐磨超迁皮
材质：紫罗兰海绵
内材：全实木框架
骨架：钢木10CM
脚高：15CM分机脚
齐边：可改围边
气动：可加气动 (行 145)
- 儿童床
外尺寸
1.2*2米外径:
宽123*长212*高170cm
1.35*2米外径:
宽138*长212*高170cm
1.5*2米外径:
宽153*长212*高170cm
1.8*2米外径:
宽183*长212*高170cm (行 149)
-  (行 166)
-  (行 174)
- 11号柜#(扪皮) (行 179)
- A#(皮 布) (行 180)
- 243#(皮 布) (行 181)
- T228#(皮 布) (行 182)
- T105#(烤漆) (行 183)
-  (行 186)
-  (行 187)

**字段差异 (前10):**

- **G03-B#
长宽高
210*181*105
面料:头层牛皮
内材:全实木框架
脚高:15分悬浮脚
齐边:可改围边
气动:可加气动** (匹配方法: model_prefix)
  - specs: `210*181*105` → `Dimensions: 210*181*105; Material: Top-grain leather; Inner frame: All solid wood frame; Leg height: 15-point floating legs; Edge: Customizable edge; Pneumatic: Can add pneumatic lift`
  - tag: `现代软床` → ``
  - source: `万日红家具B软床图册)宝丽` → ``
- **G02柜** (匹配方法: model_prefix)
  - specs: `尺寸：50*42*52` → `尺寸: 50*42*52`
  - tag: `现代软床` → ``
  - source: `万日红家具B软床图册)宝丽` → ``
- **B699#
长宽高
220*182*103
面料：头层牛皮
内材：全实木框架
骨架：钢木10CM
脚高：15CM悬浮脚
齐边：可改围边
气动：可加气动
悬浮：可做悬浮** (匹配方法: model_prefix)
  - specs: `220*182*103` → `Dimensions: 220*182*103; Material: Top-grain leather; Inner frame: All solid wood frame; Frame: Steel wood 10CM; Leg height: 15CM floating legs; Edge: Customizable edge; Pneumatic: Can add pneumatic lift; Suspension: Can be made suspended`
  - tag: `现代软床` → ``
  - source: `万日红家具B软床图册)宝丽` → ``
- **B868#
香奈儿床
长宽高
236*225*106
面料：头层黄牛皮
材质：高回弹海绵
框架：全实木框架
骨架：10分钢木架
脚高：15分镜面脚
齐边：可改围边
气动：可加气动** (匹配方法: model_prefix)
  - product_name: `B868#` → `香奈儿床`
  - specs: `236*225*106` → `长宽高: 236*225*106; 面料: 头层黄牛皮; 材质: 高回弹海绵; 框架: 全实木框架; 骨架: 10分钢木架; 脚高: 15分镜面脚; 齐边: 可改围边; 气动: 可加气动`
  - tag: `现代软床` → ``
  - source: `万日红家具B软床图册)宝丽` → `image`
- **B689#
豆腐块床
长宽高
218*182*102
面料：头层黄牛
皮特点：网红悬浮
床材质：紫罗兰靠
背内材：全实木框
架骨架：钢木10CM
脚高：悬浮17CM
齐边：可改围边
气动：不可加气动** (匹配方法: model_prefix)
  - product_name: `B689#` → `豆腐块床`
  - specs: `218*182*102` → `长宽高:218*182*102;面料:头层黄牛;皮特点:网红悬浮;床材质:紫罗兰靠背;内材:全实木框架;骨架:钢木10CM;脚高:悬浮17CM;齐边:可改围边;气动:不可加气动`
  - tag: `现代软床` → ``
  - source: `万日红家具B软床图册)宝丽` → `image`
- **T20#波浪床
长宽高
252*222*105
面料: 磨砂布/皮
材质: 高回弹绵
内材: 全实木框架
骨架: 钢木10Cm
脚高:定制铜色脚
围边: 可改齐边** (匹配方法: model_prefix)
  - product_name: `T20#波浪床` → `波浪床`
  - specs: `252*222*105` → `长宽高: 252*222*105; 面料: 磨砂布/皮; 材质: 高回弹绵; 内材: 全实木框架; 骨架: 钢木10Cm; 脚高: 定制铜色脚; 围边: 可改齐边`
  - tag: `现代软床` → ``
  - source: `万日红家具B软床图册)宝丽` → `image`
- **T02#
小黑牛
长宽高
235*210*100
面料：头层黄牛皮
材质：高回弹海绵
内材：全实木框架
骨架：钢木10CM
脚高：5分脚
齐边：可改齐边
气动：可加气动** (匹配方法: model_prefix)
  - product_name: `T02#` → `小黑牛`
  - specs: `235*210*100` → `长宽高: 235*210*100; 面料: 头层黄牛皮; 材质: 高回弹海绵; 内材: 全实木框架; 骨架: 钢木10CM; 脚高: 5分脚; 齐边: 可改齐边; 气动: 可加气动`
  - tag: `现代软床` → ``
  - source: `万日红家具B软床图册)宝丽` → `image`
- **B687#
悬浮床
长宽高
213*203*103
面料：超迁皮 材质：整体弯板
内材：全实木框架
骨架：钢木10CM
脚高：15CM三叉脚
围边：不可改齐边
气动：不可加气动** (匹配方法: model_prefix)
  - product_name: `B687#` → `悬浮床`
  - specs: `213*203*103` → `长宽高: 213*203*103; 面料: 超迁皮; 材质: 整体弯板; 内材: 全实木框架; 骨架: 钢木10CM; 脚高: 15CM三叉脚; 围边: 不可改齐边; 气动: 不可加气动`
  - tag: `现代软床` → ``
  - source: `万日红家具B软床图册)宝丽` → ``
- **B9567#
钢琴键
长宽高
220*200*104
爆款：钢琴键
面料：头层牛皮
靠背：高回弹海绵
内材：全实木框架
骨架：3D静音床板
脚高：15分三叉脚
齐边：可改围边
动：可加气动** (匹配方法: model_prefix)
  - product_name: `B9567#` → `钢琴键`
  - specs: `220*200*104` → `长宽高: 220*200*104; 面料: 头层牛皮; 靠背: 高回弹海绵; 内材: 全实木框架; 骨架: 3D静音床板; 脚高: 15分三叉脚; 齐边: 可改围边; 动: 可加气动`
  - tag: `现代软床` → `爆款`
  - source: `万日红家具B软床图册)宝丽` → `image`
- **S10#床架
尺寸可定制
面料：仿皮
内材：全实木框架
骨架：钢木10CM
脚高：15CM橡木脚
齐边：可改围边
气动：不可加气动** (匹配方法: model_prefix)
  - product_name: `S10#床架` → `床架`
  - tag: `现代软床` → ``
  - source: `万日红家具B软床图册)宝丽` → `image`

### 万日红家具—原创设计师合集(1)

**缺失 SKU (4):**

- 魔法凳 (行 155)
- XH-熊掌椅 (行 156)
- YJ-杜德椅 (行 158)
- YJ-2136 (行 159)

**字段差异 (前10):**

- **Y509** (匹配方法: model_prefix)
  - tag: `原创设计大师椅` → ``
  - source: `万日红家具—原创设计师合集` → ``
- **DY-0083脚踏** (匹配方法: model_prefix)
  - tag: `原创设计大师椅` → ``
  - source: `万日红家具—原创设计师合集` → ``
- **DY-0085** (匹配方法: model_prefix)
  - tag: `原创设计大师椅` → ``
  - source: `万日红家具—原创设计师合集` → ``
- **LY979** (匹配方法: model_prefix)
  - tag: `原创设计大师椅` → ``
  - source: `万日红家具—原创设计师合集` → `image`
- **Y550** (匹配方法: model_prefix)
  - tag: `原创设计大师椅` → ``
  - source: `万日红家具—原创设计师合集` → `OCR`
- **LY-825妈妈抱** (匹配方法: model_prefix)
  - tag: `原创设计大师椅` → ``
  - source: `万日红家具—原创设计师合集` → `image`
- **Y-2128山丘椅** (匹配方法: model_prefix)
  - tag: `原创设计大师椅` → ``
  - source: `万日红家具—原创设计师合集` → ``
- **Y-2127微笑椅** (匹配方法: model_prefix)
  - tag: `原创设计大师椅` → ``
  - source: `万日红家具—原创设计师合集` → ``
- **YJ-79** (匹配方法: model_prefix)
  - tag: `原创设计大师椅` → ``
  - source: `万日红家具—原创设计师合集` → `image`
- **YJ-2163扶手椅** (匹配方法: model_prefix)
  - tag: `原创设计大师椅` → ``
  - source: `万日红家具—原创设计师合集` → `image`

### 万日红家具美式中古图册

**多余 SKU (41):**

- 罗摩尔套几-小圆几
- 罗摩尔套几-大圆几
- 爱尼奥角几
- 休闲单位沙发
- 法式洛可可床
- 经典美式床
- 山脉单位沙发
- 黑标二位沙发
- 格莱美单位沙发
- 单椅、凳、脚踏
- 茶几、地柜、角几
- 单椅
- 书台、书椅
- 装饰柜、屏风
- 算珠凳
- 休闲沙发脚踏
- 老虎椅
- 昌迪加尔椅
- 美式休闲椅脚踏
- 悦己单椅
- 多立克茶几
- 钻石角几
- 钻石茶几
- 洛丽塔圆茶几
- 庄周圆几
- 小喇叭圆几
- 罗马边柜
- 法式浪漫床头柜
- 波浪床 布艺
- 四叶草床头柜
- 经典拉扣床尾凳
- 艾米床
- 经典美式床
- 爱尼奥床
- 法式洛可可床
- 爱德华长餐台
- 猎豹书椅
- 皇冠餐椅
- 苏格兰玄关柜
- 乔治亚双门酒柜
- 孔雀半透屏风

**字段差异 (前10):**

- **BT-BS715 艾米尼奥休闲椅
770*950*1030H** (匹配方法: model_prefix)
  - product_name: `BT-BS715 艾米尼奥休闲椅` → `艾米尼奥休闲椅`
  - specs: `770*950*1030H` → ``
  - tag: `美式中古风` → ``
  - source: `万日红家具美式中古图册` → ``
- **BT-DC720 温莎餐椅** (匹配方法: model_prefix)
  - product_name: `BT-DC720 温莎餐椅` → `温莎餐椅`
  - tag: `美式中古风` → ``
  - source: `万日红家具美式中古图册` → ``
- **BT-SF720 爱荷华单位沙发
850*950*940H** (匹配方法: model_prefix)
  - product_name: `BT-SF720 爱荷华单位沙发` → `爱荷华单位沙发`
  - tag: `美式中古风` → ``
  - source: `万日红家具美式中古图册` → `image`
- **BT-BS728 美式经典休闲椅
810*800*1150H** (匹配方法: model_prefix)
  - product_name: `BT-BS728 美式经典休闲椅` → `美式经典休闲椅`
  - specs: `810*800*1150H` → ``
  - tag: `美式中古风` → ``
  - source: `万日红家具美式中古图册` → ``
- **BT-DE711 孔雀开屏装饰柜
800*450*1600H** (匹配方法: model_prefix)
  - product_name: `BT-DE711 孔雀开屏装饰柜` → `孔雀开屏装饰柜`
  - tag: `美式中古风` → ``
  - source: `万日红家具美式中古图册` → ``
- **BT-ET715 罗马圆角几 φ420*640H** (匹配方法: model_prefix)
  - product_name: `BT-ET715 罗马圆角几 φ420*640H` → `罗马圆角几`
  - specs: `φ420*640H` → `φ420*640Η`
  - tag: `美式中古风` → ``
  - source: `万日红家具美式中古图册` → `OCR`
- **BT-DE712 经典美式七柜 1200*450*860H** (匹配方法: model_prefix)
  - product_name: `BT-DE712 经典美式七柜 1200*450*860H` → `经典美式七斗柜`
  - tag: `美式中古风` → ``
  - source: `万日红家具美式中古图册` → `image`
- **BT-GC712 爱尼奥地柜
2200*450*610H** (匹配方法: model_prefix)
  - product_name: `BT-GC712 爱尼奥地柜` → `爱尼奥地柜`
  - tag: `美式中古风` → ``
  - source: `万日红家具美式中古图册` → `page`
- **BT-PF712 枝蔓屏风 1800*2150H** (匹配方法: model_prefix)
  - product_name: `BT-PF712 枝蔓屏风 1800*2150H` → `枝蔓屏风`
  - tag: `美式中古风` → ``
  - source: `万日红家具美式中古图册` → `image`
- **BT-BS717 美人鱼椅
720*940*975H** (匹配方法: model_prefix)
  - product_name: `BT-BS717 美人鱼椅` → `美人鱼椅`
  - tag: `美式中古风` → ``
  - source: `万日红家具美式中古图册` → `OCR`

### 万日红极简现代沙发(1)

**多余 SKU (39):**

- Checkered stool
- Area rug
- Decorative fireplace
- 单人沙发
- 组合沙发
- 单人沙发
- 电视柜
- 置物架
- 单人沙发
- 置物架
- 单人沙发
- L型沙发
- 单人休闲椅
- 单人沙发
- 黑色单人沙发
- L形组合沙发
- 置物架
- Sectional Sofa
- Coffee Table
- Side Table
- Candle Holder
- Bookshelf
- Artwork
- Sideboard/Cabinet
- L型沙发
- 长条沙发
- 酒柜
- 躺椅
- 脚凳
- 单人沙发
- 单人沙发
- 装饰树
- 置物架
- Coffee table
- Side table attached to sofa
- 床尾凳
- 办公桌
- 万日红
- 万日红家具

**字段差异 (前10):**

- **** (匹配方法: position)
  - tag: `现代简约沙发` → ``
  - source: `万日红极简现代沙发` → ``
- **** (匹配方法: position)
  - tag: `现代简约沙发` → ``
  - source: `万日红极简现代沙发` → ``
- **** (匹配方法: position)
  - tag: `现代简约沙发` → ``
  - source: `万日红极简现代沙发` → ``
- **** (匹配方法: position)
  - tag: `现代简约沙发` → ``
  - source: `万日红极简现代沙发` → ``
- **** (匹配方法: position)
  - tag: `现代简约沙发` → ``
  - source: `万日红极简现代沙发` → ``
- **** (匹配方法: position)
  - tag: `现代简约沙发` → ``
  - source: `万日红极简现代沙发` → ``
- **** (匹配方法: position)
  - tag: `现代简约沙发` → `Italian minimalism`
  - source: `万日红极简现代沙发` → `page`
- **** (匹配方法: position)
  - tag: `现代简约沙发` → `Modern minimalism`
  - source: `万日红极简现代沙发` → `page`
- **** (匹配方法: position)
  - tag: `现代简约沙发` → `Solid wood style`
  - source: `万日红极简现代沙发` → `page`
- **** (匹配方法: position)
  - tag: `现代简约沙发` → ``
  - source: `万日红极简现代沙发` → ``

### 万日红现代简约图册

**多余 SKU (100):**

- Coffee table
- Side table
- 单人沙发
- 黄色扶手椅
- 白色沙发
- 电视柜
- 置物架
- Dining Table
- Dining Chair
- Display Cabinet
- 电视柜
- 电视
- 熊猫造型坐垫
- 单人沙发
- 休闲椅
- 单人沙发
- 装饰品
- 单人沙发
- 单人沙发椅
- 单人沙发
- 休闲椅
- 单人椅
- 单人沙发
- 单人沙发
- 单人椅
- 单人沙发椅
- 装饰品
- 单人沙发
- 单人沙发
- 单人沙发
- L-shaped sofa
- Armchair
- Coffee table
- Potted plant
- Decorative vase with branches
- 沙发
- L型沙发
- 三人沙发
- L型沙发
- 电视柜
- Coffee table
- Side table
- Coffee table
- Side table
- 躺椅
- 单人沙发
- Armchair
- Coffee table
- 梳妆台
- 单人沙发
- 休闲椅
- 休闲椅
- 单人沙发
- 单人沙发
- Table lamp
- Small stool
- Dining table
- Dining chairs
- Armchair
- 梳妆台
- 梳妆镜
- 斗柜
- 单人沙发
- 电视柜
- Table lamp
- Wall art
- 单人沙发
- 灭火器箱
- Bedside lamp
- Decorative figure
- 儿童书桌
- 书桌
- 装饰自行车吊灯
- 白色板材
- Bunk bed
- Single bed
- Dining table
- Dining chair
- Coffee table
- Vase with greenery
- Panda plush toy
- Dining table
- Dining chair
- 休闲椅
- Dining Table Set
- Dining Chair
- 茶桌
- Tea table with stools
- 电视柜
- Round dining table with chairs
- Potted plant
- Coffee table
- Accent table
- Dining Table Set
- Dining Chair
- Dining Table
- Dining Chair
- Dining Chair
- 万日红
- 万日红家具

**字段差异 (前10):**

- **现代简约系列
Modern minimalism** (匹配方法: product_name)
  - product_name: `现代简约系列` → `现代简约`
  - model_number: `xdjy001` → ``
  - tag: `现代简约沙发` → `Modern minimalism`
  - source: `万日红现代简约图册` → `OCR`
- **床
BED** (匹配方法: product_name)
  - product_name: `床` → `儿童床`
  - model_number: `xdjy041` → ``
  - tag: `现代简约沙发` → ``
  - source: `万日红现代简约图册` → `image`
- **床
BED** (匹配方法: product_name)
  - product_name: `床` → `儿童床`
  - model_number: `xdjy042` → ``
  - tag: `现代简约沙发` → ``
  - source: `万日红现代简约图册` → ``
- **床
BED** (匹配方法: product_name)
  - product_name: `床` → `儿童床`
  - model_number: `xdjy043` → ``
  - tag: `现代简约沙发` → ``
  - source: `万日红现代简约图册` → `image`
- **床
BED** (匹配方法: product_name)
  - product_name: `床` → `儿童床`
  - model_number: `xdjy044` → `CHI A`
  - tag: `现代简约沙发` → ``
  - source: `万日红现代简约图册` → `image`
- **床
BED** (匹配方法: product_name)
  - product_name: `床` → `儿童床`
  - model_number: `xdjy045` → ``
  - tag: `现代简约沙发` → ``
  - source: `万日红现代简约图册` → ``
- **床
BED** (匹配方法: product_name)
  - product_name: `床` → `上下铺儿童床`
  - model_number: `xdjy046` → ``
  - tag: `现代简约沙发` → ``
  - source: `万日红现代简约图册` → `image`
- **床
BED** (匹配方法: product_name)
  - product_name: `床` → `儿童床`
  - model_number: `xdjy047` → ``
  - tag: `现代简约沙发` → ``
  - source: `万日红现代简约图册` → `image`
- **床
BED** (匹配方法: product_name)
  - product_name: `床` → `上下铺床`
  - model_number: `xdjy048` → ``
  - tag: `现代简约沙发` → ``
  - source: `万日红现代简约图册` → `page`
- **床
BED** (匹配方法: product_name)
  - product_name: `床` → `儿童高低床`
  - model_number: `xdjy049` → ``
  - tag: `现代简约沙发` → ``
  - source: `万日红现代简约图册` → `image`

### 万日红现代软床Y图册

**多余 SKU (10):**

- 床头柜
- 11柜
- M306
- M8036
- M2067
- M2072
- 烤漆/高定系列床头柜
- 床头柜
- 床头柜
- 亚克力3号#

**字段差异 (前10):**

- **S128#
长宽高
235*182*110
有模型
面料：头层黄牛皮
内材:全实木框架
材质：紫罗兰海棉
脚高：12CM飞机脚
齐边：可改围边
气动：可加气动
编码：10QP3100FD1Y167** (匹配方法: model_prefix)
  - specs: `235*182*110` → ``
  - tag: `现代软床` → ``
  - source: `万日红现代软床Y图册` → ``
- **S208#
有模型.高清图
专利:2024300676786
长宽高
223*203*118
面料：粒面头层皮
特点：胡桃木配饰
材质：5A鹅绒靠包
内材：全实木框架
骨架：钢木15CM
脚高：15CM电镀脚
齐边：可改围边
气动：可加气动
编码：10QP3840FD1Y186** (匹配方法: model_prefix)
  - specs: `223*203*118` → ``
  - tag: `现代软床` → ``
  - source: `万日红现代软床Y图册` → ``
- **M0021#皮
长宽高
215*199*116
有模型.专利号
201830645826.2
面料：头层黄牛皮
特点：绣花工艺
材质：紫罗兰海绵
内材：全实木框架
骨架：钢木15CM
脚高:8CM白腊木脚
齐边：可改围边
气动：可加气动
编码：13QP4235FD1Y201** (匹配方法: model_prefix)
  - specs: `215*199*116` → ``
  - tag: `现代软床` → ``
  - source: `万日红现代软床Y图册` → ``
- **D08#皮
长宽高
220*216*140
面料：头层黄牛皮
工艺：电镀不锈钢
内架：全实木框架
脚高：9CM五金脚
床尾 ;不可改齐边
气动：可加气动** (匹配方法: model_prefix)
  - specs: `220*216*140` → ``
  - tag: `现代软床` → ``
  - source: `万日红现代软床Y图册` → ``
- **D3207#皮
长宽高
233*212*135
面料：头层黄牛皮
工艺：电镀不锈钢
内架：全实木框架
脚高：10CM床脚** (匹配方法: model_prefix)
  - specs: `233*212*135` → ``
  - tag: `现代软床` → ``
  - source: `万日红现代软床Y图册` → ``
- **D2295#皮
长宽高
230*204*111
面料：头层黄牛皮
工艺：电镀不锈钢
内架：全实木框架
脚高：12CM床脚** (匹配方法: model_prefix)
  - specs: `230*204*111` → ``
  - tag: `现代软床` → ``
  - source: `万日红现代软床Y图册` → ``
- **S219#
有模型.高清图
专利:2024300730742
长宽高
234*197*102
面料：纳帕头层皮
特点：绣花纹理
特点： 白蜡木实木
材质：紫罗兰海绵
内材：全实木框架
骨架：钢木15CM
脚高：18CM隐形脚
围边：可改齐边
气动：不可加气动
编码：13.5QP4040FD1Y143** (匹配方法: model_prefix)
  - specs: `234*197*102` → ``
  - tag: `现代软床` → ``
  - source: `万日红现代软床Y图册` → ``
- **S218#
仅限3色特价
有模型.高清图
长宽高
226*195*110
面料：头层黄牛皮
靠包：紫罗兰海绵
内材：全实木框架
骨架：钢木15CM
脚高：10CM五金脚
齐边：可改围边
气动：可加气动
编码：10QP3140FD1Y186** (匹配方法: model_prefix)
  - specs: `226*195*110` → ``
  - tag: `现代软床` → ``
  - source: `万日红现代软床Y图册` → ``
- **D2345#皮
长宽高
220*202*138
面料：头层黄牛皮
工艺：电镀不锈钢
内架：全实木框架
脚高：5CM床脚** (匹配方法: model_prefix)
  - specs: `220*202*138` → ``
  - tag: `现代软床` → ``
  - source: `万日红现代软床Y图册` → ``
- **D2379#皮
长宽高
227*193*114
面料：头层黄牛皮
工艺：电镀不锈钢
内架：全实木框架
脚高：5CM床脚** (匹配方法: model_prefix)
  - specs: `227*193*114` → ``
  - tag: `现代软床` → ``
  - source: `万日红现代软床Y图册` → ``

### 万日红美式轻奢BAIGAT(1)

**多余 SKU (89):**

- 地毯
- 边几
- 矮凳
- 单人沙发
- 边几
- 电视柜
- 装饰花瓶
- 装饰碗
- Coffee table
- Armchair
- BRANDON SOFA
- Coffee table
- Armchair
- Coffee Table
- Side Table
- 餐边柜
- bench
- Dining Table
- Dining Chair
- 餐边柜
- 置物架
- 抽屉柜
- 餐椅
- 餐椅
- 置物架
- 花瓶
- 装饰球
- Dining Table Set
- Dining Table Set
- Dining Table Set
- 装饰画
- 雕塑摆件
- side table
- 办公桌
- 办公椅
- 吊灯
- 梳妆台
- 梳妆凳
- 芬迪床
- 床尾凳
- 吊灯
- 梳妆台/边柜
- 装饰品
- 抱枕
- 床头板
- 吊灯
- 床尾凳
- 长凳
- Bed with integrated nightstands
- 梳妆台
- 床头灯
- 吊灯
- Bed with nightstand
- 台灯
- 吊灯
- 装饰画
- 地毯
- 梳妆台
- 梳妆凳
- Bed with upholstered headboard
- Vanity table with round mirror
- 床尾凳
- 装饰画
- 吊灯
- 梳妆台
- 吊灯
- Dressing Table
- Stool
- 窗帘
- 墙面装饰板
- 吊灯
- 梳妆台
- 梳妆凳
- 床尾凳
- 吊灯
- Dressing table with mirror
- 台灯
- 抱枕
- 床单
- 床盖
- 地毯
- 查奈儿#床
- 床头板
- 床头板
- 台灯
- 枕头
- 抱枕
- 地毯
- 枕头

**字段差异 (前10):**

- **QA2021-15-01#餐台
size:150*150/180*180cm** (匹配方法: model_prefix)
  - product_name: `QA2021-15-01#餐台` → `餐台`
  - specs: `餐台150*150/180*180cm` → `size: 150*150/180*180cm`
  - tag: `美式轻奢` → ``
  - source: `万日红美式轻奢BAIGAT` → ``
- **高定A86#床 224*346*137cm** (匹配方法: model_prefix)
  - product_name: `高定A86#床 224*346*137cm` → `床`
  - tag: `美式轻奢` → ``
  - source: `万日红美式轻奢BAIGAT` → ``
- **FD10 - 1#沙发 360*96*75cm** (匹配方法: name_as_model)
  - product_name: `FD10 - 1#沙发 360*96*75cm` → `沙发`
  - specs: `沙发360*96*75cm` → `360*96*75cm`
  - tag: `美式轻奢` → ``
  - source: `万日红美式轻奢BAIGAT` → ``
- **诺尔兰迪#沙发 
单位:115*103*75cm
双位:175*103*75cm
三位:225*103*75cm
四位:285*103*75cm** (匹配方法: product_name)
  - specs: `单位:115*103*75cm,双位:175*103*75cm,三位:225*103*75cm,四位:285*103*75cm` → `115*103*75cm`
  - tag: `美式轻奢` → `单位`
  - source: `万日红美式轻奢BAIGAT` → `OCR`
- **迈阿密#沙发
单位:117*103*76cm
双位:188*103*76cm
三位:242*103*76cm** (匹配方法: product_name)
  - product_name: `迈阿密#沙发` → `沙发`
  - specs: `单位:117*103*76cm,双位:188*103*76cm,三位:242*103*76cm` → `单位128*110*76cm, 二位:188*110*76cm, 三位:243*110*76cm, 四位:288*110*76cm`
  - tag: `美式轻奢` → `LIGHT LUXURY`
  - source: `万日红美式轻奢BAIGAT` → `image`
- **美杜莎#餐台
size:130*70*77cm

美杜莎#餐椅
size:52*63*99cm** (匹配方法: product_name)
  - product_name: `美杜莎#餐台` → `餐台`
  - specs: `餐台130*70*77cm,餐椅52*63*99cm` → `size: 130*70*77cm`
  - tag: `美式轻奢` → ``
  - source: `万日红美式轻奢BAIGAT` → ``
- **伊特拉斯#床 216*215*162cm** (匹配方法: product_name)
  - product_name: `伊特拉斯#床 216*215*162cm` → `伊特拉斯#床`
  - tag: `美式轻奢` → ``
  - source: `万日红美式轻奢BAIGAT` → ``
- **塔斯拉克#床 222*203*145cm** (匹配方法: product_name)
  - product_name: `塔斯拉克#床 222*203*145cm` → `塔斯拉克#床`
  - tag: `美式轻奢` → ``
  - source: `万日红美式轻奢BAIGAT` → `image`
- **香奈儿#床 235*210*132cm** (匹配方法: product_name)
  - product_name: `香奈儿#床 235*210*132cm` → `香奈儿#床`
  - tag: `美式轻奢` → ``
  - source: `万日红美式轻奢BAIGAT` → `image`
- **** (匹配方法: position)
  - tag: `美式轻奢` → ``
  - source: `万日红美式轻奢BAIGAT` → `image`

### 万日红美式轻奢画册2024.1.1

**多余 SKU (273):**

- 地毯
- 地毯
- 抱枕
- 盆栽
- 单人沙发
- 边几
- 单人沙发
- 双人沙发
- 台灯
- 边几
- 圆形镜子
- 脚凳
- 落地灯
- 吊灯
- 边桌
- 吊灯
- 台灯
- 单人沙发
- 边桌
- 边几
- 地毯
- 吊灯
- 单人沙发
- 边桌
- 台灯
- 抱枕
- 台灯
- 边桌
- 地毯
- 单人沙发
- 抱枕
- 装饰画
- 单人沙发
- 圆形沙发
- 边几
- 边几
- L型沙发
- 台灯
- 吊灯
- 地毯
- 贵妃
- 长凳
- 装饰品
- 单人沙发
- 边桌
- 落地灯
- 边几
- 扶手椅
- 单人沙发
- 边桌
- 台灯
- 落地灯
- 单人沙发
- Blue armchair
- Patterned armchair
- Teal wingback armchair
- Blue tufted armchair
- 动物造型凳
- 边桌
- 台灯
- 扶手椅
- 边桌
- 边几
- 单人沙发
- 单人沙发
- 休闲椅
- 高背扶手椅
- 扶手椅
- Orange tufted armchair
- Beige wingback armchair
- Grey upholstered armchair with clear acrylic arms
- Patterned upholstered armchair
- Accent Chair
- 单人沙发
- Armchair
- 沙发凳
- 脚凳
- Coffee Table Set
- Table lamp
- Rug
- 椭圆形茶几
- 方形茶几
- 长方形茶几
- AT HOME FURNITURE
- 抱枕
- 装饰花瓶
- 圆形茶几
- 边几
- 边桌
- 方形茶几
- 圆形茶几
- 长方形控制台
- 圆形边桌
- 方形边桌
- 圆形边桌
- 圆桌
- Side table
- Round table
- Side table with shelf
- 电视柜
- 电视柜
- 深色木质储物柜
- 米色储物柜
- 电视柜
- Pink upholstered bed
- 床头柜
- 装饰柜
- 角几
- 台灯
- 扶手椅
- 边桌
- M-NT603 床头柜
- 台灯
- 装饰画
- 茶椅
- 床头柜
- 单人沙发椅
- 装饰画
- 台灯
- 床尾凳
- 台灯
- 相框
- 窗帘
- 斗柜
- 床头灯
- 台灯
- 台灯
- 梳妆台
- 梳妆凳
- 台灯
- 五斗柜
- 地毯
- 脚凳
- 床头柜
- 餐边柜
- 台灯
- 台灯
- 吊灯
- 装饰画
- 妆台
- 床头灯
- 梳妆台
- 梳妆凳
- 床
- M-NT605 床头柜
520×420×550mm
- 落地灯
- 台灯
- 台灯
- 斗柜
- 地毯
- 台灯
- M-NT601-1床头柜
550×550×550mm
- M-DR602妆台
1100×450×770mm
- M-ST603 皮妆凳
520×420×470mm
- 床头灯
- 吊灯
- 花瓶
- 装饰花
- 床尾凳
- 长凳
- 台灯
- 窗帘
- 地毯
- 装饰画
- 台灯
- 床尾凳
- 台灯
- 地毯
- 台灯
- 窗帘
- 台灯
- 相框
- Nightstand
- Nightstand
- Nightstand
- 皮妆凳
- M-DE606 卧房电视柜
- 餐边柜
- 餐边柜
- 餐边柜
- 餐台
- 餐椅
- 酒柜
- Dining chair
- Dining table
- Chest of drawers
- 餐边柜
- 装饰画
- 装饰雕塑
- 装饰摆件
- 花瓶
- 餐台
- 扶手餐椅
- 餐椅
- 台灯
- 装饰画
- 花瓶
- 装饰花
- 果盘
- 装饰水果
- 地毯
- 装饰花瓶
- 落地灯
- 盆栽植物
- 边桌
- 餐台
- 餐椅
- 装饰画
- 花瓶
- 装饰花
- 餐边柜
- Dining table and chairs set
- Dining chair
- Dining chair
- AT HOME FURNITURE
80103
- 吊灯
- 地毯
- 花瓶
- 餐台
- 餐边柜
- 无扶手餐椅
带扶手餐椅
- 餐边柜
- 酒柜
- 餐边柜
- 装饰花瓶
- 地毯
- Dining Table Set
- Dining Chair
- 餐桌 M.D004
- 餐桌 M.The023
- 餐椅 M.D001
- 花瓶
- 小碗
- 托盘
- Dining Chair
- Dining Chair
- Dining Table
- Dining Chair
- 餐边柜
1680×460×950mm
- 玄关柜
- 圆形镜子
- 花瓶
- 斗柜
- 斗柜
- 酒柜
- 抽屉柜
- 斗柜
- 花瓶
- 装饰画
- 植物盆栽
- 抽屉柜
- 台灯
- 地毯
- 斗柜
- 三斗柜
- 实木餐桌
- 实木长凳
- 实木茶桌
- 茶具套装
- 茶桌
- 长凳
- 书桌
- 书柜
- 落地灯
- 书柜
- 单人沙发
- 书桌
- 书桌
- 二门书柜
- 带扶手餐椅
- 茶椅
- 书桌
- Dressing table

**字段差异 (前10):**

- **M-LC605-2 单椅** (匹配方法: model_prefix)
  - tag: `美式轻奢` → ``
  - source: `万日红美式轻奢画册2024.1.1` → `image`
- **M-GC602 客厅地柜 2000×450×540mm** (匹配方法: model_prefix)
  - product_name: `M-GC602 客厅地柜 2000×450×540mm` → `客厅地柜`
  - tag: `美式轻奢` → ``
  - source: `万日红美式轻奢画册2024.1.1` → ``
- **单椅** (匹配方法: model_number)
  - specs: `M-CT604+2 小茶几 600×600×400 mm` → `770×920×1140mm`
  - tag: `美式轻奢` → ``
  - source: `万日红美式轻奢画册2024.1.1` → `OCR`
- **角几** (匹配方法: model_number)
  - specs: `二人位沙2040×1080×800mm,四人位沙2850×1080×800mm,
单椅770×920×1140mm,小茶几600×600×400mm,三人位沙2420×1080×800mm,单椅760×900×1120mm,大茶几1500×750×450mm,角几φ600×600mm` → `$600×600 mm`
  - tag: `美式轻奢` → ``
  - source: `万日红美式轻奢画册2024.1.1` → `OCR`
- **单人位沙发** (匹配方法: model_number)
  - specs: `单人位沙发920×920×820mm,三人位沙发2300×950×820mm,茶几1400×900×510mm,玄关1200×400×800mm,二人位沙发1800×950×820mm,单椅730×920×930mm,角几600×600×620mm` → `920×920×820mm`
  - tag: `美式轻奢` → ``
  - source: `万日红美式轻奢画册2024.1.1` → `OCR`
- **茶几** (匹配方法: model_number)
  - specs: `单人位沙发920×920×820mm,三人位沙发2300×950×820mm,茶几1400×900×510mm,玄关1200×400×800mm,二人位沙发1800×950×820mm,单椅730×920×930mm,角几600×600×620mm` → `1400×900×510mm`
  - tag: `美式轻奢` → ``
  - source: `万日红美式轻奢画册2024.1.1` → `OCR`
- **玄关** (匹配方法: model_number)
  - specs: `单人位沙发920×920×820mm,三人位沙发2300×950×820mm,茶几1400×900×510mm,玄关1200×400×800mm,二人位沙发1800×950×820mm,单椅730×920×930mm,角几600×600×620mm` → `1200 x 400 x 800mm`
  - tag: `美式轻奢` → ``
  - source: `万日红美式轻奢画册2024.1.1` → `image`
- **单椅** (匹配方法: model_number)
  - specs: `单人位沙发920×920×820mm,三人位沙发2300×950×820mm,茶几1400×900×510mm,玄关1200×400×800mm,二人位沙发1800×950×820mm,单椅730×920×930mm,角几600×600×620mm` → `730×920×930mm`
  - tag: `美式轻奢` → ``
  - source: `万日红美式轻奢画册2024.1.1` → `OCR`
- **角几** (匹配方法: model_number)
  - specs: `单人位沙发920×920×820mm,三人位沙发2300×950×820mm,茶几1400×900×510mm,玄关1200×400×800mm,二人位沙发1800×950×820mm,单椅730×920×930mm,角几600×600×620mm` → `600×600×620mm`
  - tag: `美式轻奢` → ``
  - source: `万日红美式轻奢画册2024.1.1` → `OCR`
- **二人位沙发** (匹配方法: model_number)
  - specs: `单人位沙发830×920×1000mm,二人位沙发1640×920×1000mm,三人位沙发2080×920×1000mm,茶几1380×760×485mm,角几600×600×620mm` → `1640×920×1000mm`
  - tag: `美式轻奢` → ``
  - source: `万日红美式轻奢画册2024.1.1` → `Based On The Life Lead Trend`

### 万日红美式香槟图册

**多余 SKU (31):**

- 单人沙发
- 台灯
- 边桌
- 吊灯
- 地毯
- 吊灯
- 装饰画
- 台灯
- 单人沙发
- 地毯
- 单人沙发
- 三人沙发
- 脚凳
- 边几
- 单人沙发
- 单人沙发
- 脚凳
- 装饰画
- 餐边柜
- 斗柜
- 餐椅
- 餐边柜
- 吊灯
- 餐边柜
- 餐边柜
- 七斗柜
- 五斗柜
- 六斗柜
- 书桌
- 书椅
- 书柜

**字段差异 (前10):**

- **** (匹配方法: position)
  - tag: `美式香槟` → ``
  - source: `万日红美式香槟图册` → `image`
- **** (匹配方法: position)
  - tag: `美式香槟` → ``
  - source: `万日红美式香槟图册` → ``
- **** (匹配方法: position)
  - tag: `美式香槟` → ``
  - source: `万日红美式香槟图册` → ``
- **** (匹配方法: position)
  - tag: `美式香槟` → ``
  - source: `万日红美式香槟图册` → `image`
- **** (匹配方法: position)
  - tag: `美式香槟` → ``
  - source: `万日红美式香槟图册` → `image`
- **** (匹配方法: position)
  - tag: `美式香槟` → ``
  - source: `万日红美式香槟图册` → `image`
- **** (匹配方法: position)
  - tag: `美式香槟` → ``
  - source: `万日红美式香槟图册` → `image`
- **** (匹配方法: position)
  - tag: `美式香槟` → ``
  - source: `万日红美式香槟图册` → ``
- **** (匹配方法: position)
  - tag: `美式香槟` → ``
  - source: `万日红美式香槟图册` → `image`
- **** (匹配方法: position)
  - tag: `美式香槟` → ``
  - source: `万日红美式香槟图册` → `image`

### 万鑫休闲椅 全

**多余 SKU (70):**

- Armchair
- Armchair
- 休闲椅
- Textured style armchair
- Chinese style armchair
- Armchair
- Armchair
- Armchair
- Armchair
- Chair and table set
- Chair and table set
- Chair and table set
- 单人沙发
- 装饰品
- 休闲椅
- 休闲椅
- Lounge Chair
- Side Table
- 熊掌椅
- LOUNGE CHAIR
- LOUNGE CHAIR
- 休闲椅
- LOUNGE CHAIR
- Lounge Chair
- LOUNGE CHAIR
- 沙发
- LOUNGE CHAIR
- LOUNGE CHAIR
- Squash 壁球椅
- 智能版 LOUNGE CHAIR
- LOUNGE CHAIR
- 心形椅子
- Heart-shaped chair
- 休闲椅
- 休闲椅
- 单人沙发
- 单人沙发
- 小米椅#
- 趴趴熊
- 小绵羊
- 甜甜圈
- Donut shaped chair
- Side table
- Side table
- 小熊椅
- 小熊椅
- 小熊椅
- 小熊椅
- 小熊椅
- 沙发
- 沙发
- 沙发
- 沙发
- 沙发
- 装饰摆件
- 装饰摆件
- 小马
- 单人沙发
- 单人沙发
- 脚凳
- 沙发
- chair
- chair
- 沙发
- 单人沙发
- 脚凳/搁脚
- 南瓜椅#
- 松木凳
- 松木凳
- 松木凳

**字段差异 (前10):**

- **L74*M86*D88cm** (匹配方法: model_prefix)
  - product_name: `L74*M86*D88cm` → `白蜡木架子`
  - source: `万鑫休闲椅 全.pdf` → `image`
- **L94xW93xD95cm** (匹配方法: model_prefix)
  - product_name: `L94xW93xD95cm` → `律动沙发`
  - source: `万鑫休闲椅 全.pdf` → `image`
- **Y602压缩沙发#
L83xM102xD79cm** (匹配方法: model_prefix)
  - product_name: `Y602压缩沙发#` → `Y602压缩沙发`
  - source: `万鑫休闲椅 全.pdf` → `page`
- **LY996#
L800xW900xD1020mm** (匹配方法: model_prefix)
  - product_name: `LY996#` → `休闲椅`
  - source: `万鑫休闲椅 全.pdf` → ``
- **茶几一棕色
Y505#
L88*M88*D98cm** (匹配方法: model_prefix)
  - product_name: `茶几一棕色` → `Y505#`
  - source: `万鑫休闲椅 全.pdf` → `page_117`
- **L93*M82*D71cm** (匹配方法: model_prefix)
  - product_name: `L93*M82*D71cm` → `Leisure Chair`
  - source: `万鑫休闲椅 全.pdf` → ``
- **Y580#
L110xW90xD90cm** (匹配方法: model_prefix)
  - product_name: `Y580#` → `Leisure Chair`
  - source: `万鑫休闲椅 全.pdf` → ``
- **Y550#
L101xW100xD87cm** (匹配方法: model_prefix)
  - product_name: `Y550#` → `Leisure Chair`
  - source: `万鑫休闲椅 全.pdf` → ``
- **Y551#
L103xW102xD79cm** (匹配方法: model_prefix)
  - product_name: `Y551#` → `沙发`
  - source: `万鑫休闲椅 全.pdf` → ``
- **L90*M101*D87cm** (匹配方法: model_prefix)
  - product_name: `L90*M101*D87cm` → `沙发`
  - source: `万鑫休闲椅 全.pdf` → `page_2`

### 万鑫休闲椅-货号WX-01开始

**多余 SKU (163):**

- 兔子椅
- Green Bunny Chair
- 扶手椅
- Armchair
- 扶手椅
- 脚凳
- Ottoman
- Armchair
- Ottoman
- 扶手椅
- Armchair
- 扶手椅
- 扶手椅
- Armchair
- Swivel Armchair
- 扶手椅
- Armchair
- 休闲椅
- Armchair
- Armchair
- 单人沙发
- 休闲椅
- 休闲椅
- Black leather chair with wooden back and legs
- Armchair
- 扶手椅
- 单人沙发
- 扶手椅
- Armchair
- 单人沙发
- 扶手椅
- 脚凳
- 扶手椅
- Armchair
- 休闲椅
- 黑色软垫休闲椅
- 办公椅
- Office Chair
- 休闲椅
- 扶手椅
- 单人沙发
- 单人沙发
- Armchair
- 扶手椅
- Armchair
- Recliner
- 休闲椅
- 单人沙发
- 休闲椅
- 扶手椅
- 毛绒椅子
- 扶手椅
- 扶手椅
- 扶手椅
- 休闲椅
- 脚凳
- 扶手椅
- 休闲椅
- 脚凳
- 扶手椅
- Polka dot chair
- Striped armchair with ottoman
- Striped armchair
- Armchair
- 脚凳
- 沙发
- 扶手椅
- Armchair
- Armchair
- Armchair
- 黑色软垫扶手椅
- 黑色软垫脚凳
- 休闲椅
- Armchair
- 扶手椅
- Wingback Armchair
- 单人沙发
- Round sofa
- 黑色单人沙发
- 单人沙发
- Armchair
- 休闲椅
- Armchair
- 花瓣椅
- 红色花朵造型扶手椅
- Heart Cone Chair
- 红色心形休闲椅
- 褶皱扶手椅
- 休闲椅
- 脚凳
- 休闲椅
- Black leather armchair
- 扶手椅
- 扶手椅
- Armchair
- 休闲椅
- 休闲椅
- Chaise Lounge
- Egg Chair
- 躺椅
- Round sofa
- 扶手椅
- Armless Chair
- Armchair
- 扶手椅
- Black leather tufted lounge chair
- lounge chair
- ottoman
- Lounge Chair
- 休闲椅
- 编织沙发
- 休闲椅
- 红色折叠椅
- Armchair
- Armchair side view
- Armchair back view
- 单人沙发
- 蓝色扶手椅
- 甜甜圈沙发
- 休闲椅
- 扶手椅
- 脚凳
- 扶手椅
- Armchair
- 扶手椅
- 白色毛绒扶手椅
- 绿色毛绒扶手椅
- 北极熊沙发
- Polar Bear Sofa
- Lounge Chair
- 小熊凳
- 沙发
- 方凳
- Zebra print ottoman
- 扶手椅
- Armchair
- 休闲椅
- 休闲椅
- Lounge Chair
- 休闲椅
- 休闲椅
- 脚凳
- 摇椅
- 扶手椅
- 扶手椅
- Armchair
- 休闲椅
- Brown leather armchair
- 摇椅
- 休闲椅
- Armchair
- 休闲椅
- 休闲椅
- 扶手椅
- Armchair
- 休闲椅
- 单人沙发
- 绿色天鹅绒扶手椅
- Recliner chair
- 休闲椅
- 绿色休闲椅
- Dining chair
- 吧台椅

### 万鑫极简沙发图(2)

**字段差异 (前10):**

- **w-16** (匹配方法: model_prefix)
  - product_name: `w-16` → `沙发`
  - source: `万鑫极简沙发图(2).pdf` → `image`
- **迪兰沙发#** (匹配方法: name_as_model)
  - product_name: `迪兰沙发#` → `沙发`
  - source: `万鑫极简沙发图(2).pdf` → `image`
- **2266#** (匹配方法: name_as_model)
  - product_name: `2266#` → `沙发`
  - source: `万鑫极简沙发图(2).pdf` → `image`
- **2266#** (匹配方法: name_as_model)
  - product_name: `2266#` → `沙发`
  - source: `万鑫极简沙发图(2).pdf` → ``
- **2260#** (匹配方法: name_as_model)
  - product_name: `2260#` → `沙发`
  - source: `万鑫极简沙发图(2).pdf` → `image`
- **2260** (匹配方法: name_as_model)
  - product_name: `2260` → `沙发`
  - source: `万鑫极简沙发图(2).pdf` → ``
- **2201** (匹配方法: name_as_model)
  - product_name: `2201` → `沙发`
  - source: `万鑫极简沙发图(2).pdf` → `image`
- **2125A** (匹配方法: name_as_model)
  - product_name: `2125A` → `沙发`
  - source: `万鑫极简沙发图(2).pdf` → ``
- **2125A** (匹配方法: name_as_model)
  - product_name: `2125A` → `沙发`
  - source: `万鑫极简沙发图(2).pdf` → `OCR`
- **2125B** (匹配方法: name_as_model)
  - product_name: `2125B` → `沙发`
  - source: `万鑫极简沙发图(2).pdf` → `image`

### 中古系列-沙发(纳威)

**多余 SKU (37):**

- 沙发系列
- 沙发
- 沙发
- 沙发
- 布艺款沙发
- 布艺款沙发
- 皮艺款沙发
- 沙发
- 沙发
- 沙发
- 沙发
- 组合沙发
- 沙发
- 沙发
- 沙发
- 单人沙发
- 单人沙发
- 组合沙发
- 组合沙发
- Sofa Combination J
- Sofa Combination F
- 组合沙发
- 沙发
- 沙发
- 组合沙发
- 皮艺款沙发
- 沙发
- NAV395 Combination C Sofa
- 组合沙发
- 组合沙发
- 组合沙发
- 组合沙发
- 沙发
- 沙发
- 沙发
- 沙发
- 沙发

**字段差异 (前10):**

- **BU401** (匹配方法: model_prefix)
  - product_name: `BU401` → `沙发 BU401`
  - tag: `中古系列-沙发` → ``
  - source: `中古系列-沙发(纳威).pdf` → `image`
- **NAV395** (匹配方法: model_prefix)
  - product_name: `NAV395` → `NAV395 Combination F Sofa`
  - tag: `中古系列-沙发` → ``
  - source: `中古系列-沙发(纳威).pdf` → `image`
- **BU353** (匹配方法: model_prefix)
  - product_name: `BU353` → `Combination Sofa`
  - tag: `中古系列-沙发` → ``
  - source: `中古系列-沙发(纳威).pdf` → `image`
- **BU420** (匹配方法: model_prefix)
  - product_name: `BU420` → `Combination`
  - tag: `中古系列-沙发` → ``
  - source: `中古系列-沙发(纳威).pdf` → ``
- **BU431** (匹配方法: model_prefix)
  - product_name: `BU431` → `Fabric style sofa`
  - tag: `中古系列-沙发` → ``
  - source: `中古系列-沙发(纳威).pdf` → ``
- **BU409 / NAV409** (匹配方法: model_prefix)
  - product_name: `BU409 / NAV409` → `沙发`
  - tag: `中古系列-沙发` → ``
  - source: `中古系列-沙发(纳威).pdf` → ``
- **BU426** (匹配方法: model_prefix)
  - product_name: `BU426` → `沙发`
  - tag: `中古系列-沙发` → ``
  - source: `中古系列-沙发(纳威).pdf` → `image`
- **BU039 / NAV039** (匹配方法: model_prefix)
  - product_name: `BU039 / NAV039` → `沙发`
  - tag: `中古系列-沙发` → ``
  - source: `中古系列-沙发(纳威).pdf` → `image`
- **BU029** (匹配方法: model_prefix)
  - product_name: `BU029` → `沙发`
  - tag: `中古系列-沙发` → ``
  - source: `中古系列-沙发(纳威).pdf` → `image`
- **BU329 / NAV329** (匹配方法: model_prefix)
  - product_name: `BU329 / NAV329` → `沙发`
  - tag: `中古系列-沙发` → ``
  - source: `中古系列-沙发(纳威).pdf` → `image`

### 2025现代地毯图册（压缩）

**多余 SKU (113):**

- 地毯 CL-01
- 地毯 CL-02
- 地毯 CL-03
- 地毯 CL-04
- 地毯 CL-05
- 地毯 CL-06
- Rug
- Rug
- Rug
- DONGFANGYIJING
东方意境
- Rug DFQY-04
- Rug DFQY-05
- Rug DFQY-06
- 东方情韵
- 地毯 FY-07
- 地毯 FY-08
- 地毯 FY-09
- 浮影地毯
- QIANXUN 千寻 地毯
- QIANXUN 千寻 地毯
- QIANXUN 千寻 地毯
- 春晓
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- DELALUNTA 德拉伦塔 DLLT-01
- DELALUNTA 德拉伦塔 DLLT-02
- DELALUNTA 德拉伦塔 DLLT-03
- DELALUNTA 德拉伦塔 DLLT-04
- DELALUNTA 德拉伦塔 DLLT-05
- DELALUNTA 德拉伦塔 DLLT-06
- DELALUNTA 德拉伦塔 DLLT-10
- DELALUNTA 德拉伦塔 DLLT-11
- DELALUNTA 德拉伦塔 DLLT-12
- BLANCA 地毯
- BLANCA 地毯
- BLANCA 地毯
- BLANCA 地毯
- BLANCA 地毯
- BLANCA 地毯
- BLANCA 地毯
- BLANCA 地毯
- BLANCA 地毯
- BLANCA 地毯
- BLANCA 地毯
- BLANCA 地毯
- MODICA 地毯
- MODICA 地毯
- MODICA 地毯
- MODICA 地毯
- MODICA 地毯
- MODICA 地毯
- MODICA 地毯
- MODICA 地毯
- MODICA 地毯
- MODICA 地毯
- MODICA 地毯
- MODICA 地毯
- Rug
- Rug
- Rug
- Rug
- Rug
- Rug
- PUXI 璞玺
- 落地灯
- 脚凳
- 边桌
- 地毯
- 装饰品
- 地毯 PY-01
- 地毯 FY-04
- 地毯 FY-05
- 地毯 FY-06
- PUYU 璞玉 地毯
- 地毯 HR-04
- 地毯 HR-07
- 地毯 HR-10
- HERA 赫拉 地毯
- 地毯
- VICK 维克
- 边桌
- 脚凳
- MONROE 梦露
- 高端手工枪刺定制地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 高清尼龙印花定制地毯
- 地毯
- 扶手椅
- 边桌
- 星空下的奇幻世界
- 水面上的船只与红色倒影
- 抽象挂毯
- 鹦鹉壁画
- 金鱼艺术画
- 绿色躺椅
- 抽象人脸艺术画
- 灯泡工业景观画
- 不规则镜子
- 几何形状地毯

**字段差异 (前10):**

- **FARAZ
法拉兹
土耳其进口
材质:涤纶亮丝+涤纶收缩纱
毯厚:12mm
160×230cm
200×290cm
240×330cm
300×400cm** (匹配方法: model_number)
  - product_name: `FARAZ` → `地毯`
  - specs: `160*230cm,200*290cm,240*330cm,300*400cm` → ``
  - source: `2025现代地毯图册（压缩）` → ``
- **FARAZ
法拉兹
土耳其进口
材质:涤纶亮丝+涤纶收缩纱
毯厚:12mm
160×230cm
200×290cm
240×330cm
300×400cm** (匹配方法: model_number)
  - product_name: `FARAZ` → `地毯`
  - specs: `160*230cm,200*290cm,240*330cm,300*400cm` → ``
  - source: `2025现代地毯图册（压缩）` → ``
- **FARAZ
法拉兹
土耳其进口
材质:涤纶亮丝+涤纶收缩纱
毯厚:12mm
160×230cm
200×290cm
240×330cm
300×400cm** (匹配方法: model_number)
  - product_name: `FARAZ` → `地毯`
  - specs: `160*230cm,200*290cm,240*330cm,300*400cm` → ``
  - source: `2025现代地毯图册（压缩）` → ``
- **FARAZ
法拉兹
土耳其进口
材质:涤纶亮丝+涤纶收缩纱
毯厚:12mm
160×230cm
200×290cm
240×330cm
300×400cm** (匹配方法: model_number)
  - product_name: `FARAZ` → `地毯`
  - specs: `160*230cm,200*290cm,240*330cm,300*400cm` → ``
  - source: `2025现代地毯图册（压缩）` → `image`
- **FARAZ
法拉兹
土耳其进口
材质:涤纶亮丝+涤纶收缩纱
毯厚:12mm
160×230cm
200×290cm
240×330cm
300×400cm** (匹配方法: model_number)
  - product_name: `FARAZ` → `地毯`
  - specs: `160*230cm,200*290cm,240*330cm,300*400cm` → ``
  - source: `2025现代地毯图册（压缩）` → `image`
- **ZHAOYANG
朝阳
材质:超细防水丙纶+微防水涤纶收缩纱 毯厚:12mm
160×230cm 200×290cm 240×340cm 300×400cm** (匹配方法: model_number)
  - specs: `160*230cm,200*290cm,240*340cm,300*400cm` → ``
  - source: `2025现代地毯图册（压缩）` → `image`
- **ZHAOYANG
朝阳
材质:超细防水丙纶+微防水涤纶收缩纱 毯厚:12mm
160×230cm 200×290cm 240×340cm 300×400cm** (匹配方法: model_number)
  - specs: `160*230cm,200*290cm,240*340cm,300*400cm` → ``
  - source: `2025现代地毯图册（压缩）` → `image`
- **ZHAOYANG
朝阳
材质:超细防水丙纶+微防水涤纶收缩纱 毯厚:12mm
160×230cm 200×290cm 240×340cm 300×400cm** (匹配方法: model_number)
  - specs: `160*230cm,200*290cm,240*340cm,300*400cm` → ``
  - source: `2025现代地毯图册（压缩）` → `image`
- **ZHAOYANG
朝阳
材质:超细防水丙纶+微防水涤纶收缩纱 毯厚:12mm
160×230cm 200×290cm 240×340cm 300×400cm** (匹配方法: model_number)
  - specs: `160*230cm,200*290cm,240*340cm,300*400cm` → ``
  - source: `2025现代地毯图册（压缩）` → `image`
- **ZHAOYANG
朝阳
材质:超细防水丙纶+微防水涤纶收缩纱 毯厚:12mm
160×230cm 200×290cm 240×340cm 300×400cm** (匹配方法: model_number)
  - specs: `160*230cm,200*290cm,240*340cm,300*400cm` → ``
  - source: `2025现代地毯图册（压缩）` → `image`

### 常规款式图册2025.9.16-

**多余 SKU (344):**

- 杰西卡系列
- 简爱系列
- 古尔曼
- 爱丽丝系列
- 圣菲系列
- 里尔系列
- 清月系列
- 柏兰系列
- 朝夕系列
- 设计师系列
- 秋月系列
- 扶光系列
- 温迪系列
- 静韵系列
- 温妮系列
- 原木系列
- 安杰里系列
- 威尼斯系列
- 贝加尔系列
- 布鲁森系列
- 丹华系列
- 雅颂系列
- 罗马系列
- 寻川系列
- 薇古丝系列
- 繁花系列
- 米诺蒂系列
- 云朵系列
- 云海系列
- 书逸系列
- 浅色系列
- 波尔系列
- 暮影系列
- 卡迪夫系列
- 慕名系列
- 云锦系列
- BY-2系列
- 圆毯系列
- 床边毯系列
- 瑞丽系列
威尔顿机织地毯
- 瑞丽
- 瑞丽
- 瑞丽
- 瑞丽
- 瑞丽
- 瑞丽
- 威尔顿机织地毯
达芬奇系列
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 克里斯系列地毯
- 安德森系列
- 威尔顿机织地毯
线条系列
- 艾瑞克
- 慕风02
- 慕风03
- 威尔顿机织地毯
- 彩陶系列 威尔顿机织地毯
- 图兰系列 威尔顿机织地毯
- 卡米尔系列
- 地毯
卡米尔01
- 地毯
卡米尔02
- 地毯
卡米尔05
- 地毯
卡米尔08
- 威尔顿机织地毯
- 杰西卡
- 杰西卡
- 光年
- 简爱系列
- 卡琳系列 威尔顿机织地毯
- 隐山-01
- 威尔顿机织地毯 爱丽丝系列
- 地毯
- 地毯
- 地毯
- 地毯
- 古尔曼系列地毯
- 木质扶手椅
- 置物架
- 衣帽架
- 屏风
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 圣菲系列地毯 圣菲01
- 圣菲系列地毯 圣菲03
- 圣菲系列地毯 圣菲04
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 里尔系列 威尔顿机织地毯
- 里尔01
- 里尔02
- 清月系列 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 柏兰系列 威尔顿机织地毯
- 柏兰
- 柏兰
- 柏兰
- 柏兰
- 朝夕系列 威尔顿机织地毯
- 地毯
- 地毯
- 边几
- 单人沙发
- 设计师系列地毯
- YDL06
- YDL007
- YDL08
- S259
- 休闲椅
- 秋月系列 威尔顿机织地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 爱尔兰系列地毯
- 威尔顿机织地毯
- 温迪01
- 温迪02
- 布鲁塞尔系列 地毯
- 米兰达系列 威尔顿机织地毯
- 咖啡桌
- 休闲椅
- 威尔顿机织地毯
- 静韵04
- 静韵06
- 温妮01
- 温妮02
- 单人沙发
- 双人沙发
- 原木系列 威尔顿机织地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 安杰里系列地毯
- 安杰里
- 安杰里
- 安杰里
- 威尼斯系列地毯
- 地毯 威尼斯02
- 地毯 威尼斯03
- 地毯 威尼斯04
- 地毯 威尼斯05
- 威尔顿机织地毯
- 贝加尔
- 地毯
- 布鲁森系列地毯
- 布鲁森
- 布鲁森
- 布鲁森
- 布鲁森
- 布鲁森
- 单人沙发
- 威尔顿机织地毯
丹华系列
- 威尔顿机织地毯 雅颂系列
- 地毯
- 地毯
- 地毯
- 寻川系列 威尔顿机织地毯
- 卢浮宫
- 古韵
- 浮游
- 圣地
- 宝藏毯
- 曼哈顿
- 沙发
- 厨房吊柜
- 餐桌
- 厨房地柜
- 户外躺椅
- 薇古丝系列
- 薇古丝
- 薇古丝
- 薇古丝
- 薇古丝
- 威尔顿机织地毯
- 凡梦
- 凡梦
- 繁花01
- 繁花02
- 花影
- 空中花园
- 沙丘-黑色
- 绮梦巴黎—灰
- 绮梦巴黎—驼
- 纵横-黑
- 长凳
- 画框
- 米诺蒂系列 威尔顿机织地毯
- 米诺蒂
- 流金01
- 简梵03
- 云澈
- 中南海
- 幻梦
- 昆仑山色
- 昆仑山色-暖阳
- 白沙滩
- 云朵02
- 云朵03
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 书逸系列 威尔顿机织地毯
- 书逸
- 书逸—细节图
- 雅韵
- 雅韵—细节图
- 威尔顿机织地毯
- 瑞士雪松
- Pran-21726
- Pran-21736X
- 威尔顿机织地毯
- 波尔01
- 波尔02
- 威尔顿机织地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 威尔顿机织地毯
- 地毯 卡迪夫01
- 地毯 卡迪夫02
- 地毯 卡迪夫03
- 威尔顿机织地毯
慕名系列
- 慕名
- 北陌01
- 洛影
- 简墨
- 慕名,黑
- 西尔维娅
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 云锦系列
- 云锦01
- 云锦02
- 墙纸
- 墙纸
- 墙纸
- 墙纸
- 墙纸
- 墙纸
- 墙纸
- 墙纸
- 墙纸
- 墙纸
- 簇绒机织地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- 地毯
- Rug
- Rug
- Rug
- Rug
- Rug
- Rug
- Rug
- Rug
- 圆毯
- 圆毯
- 圆毯
- 圆毯
- 圆毯
- 圆毯
- 圆毯
- 圆毯
- 圆毯
- 圆毯
- MOJ06
- 圆毯
- 圆毯
- 圆毯
- 圆毯
- 圆毯
- 圆毯
- 圆毯
- 圆毯
- 圆毯
- 圆毯
- 威尔顿机织地毯
- 隐山07
- 月白
- 波西米亚白
- 波西米亚
- 繁花
- 薇古丝黑
- 书逸圆毯
- 温迪01
- 波尼斯01
- 床边毯系列
- 复古床边毯
- 复古床边毯
- 复古床边毯
- 云朵01
- COC
- 黑白格

**字段差异 (前10):**

- **克里斯系列-Kris01
材质/ Material: 超柔丙纶+涤纶收缩纱
厚度/Thickness: 12mm左右
产地/Original: 国产
工艺/Crafts: 威尔顿机织
打理/Manage: 吸尘器、地毯清洁剂、布艺清洗机
尺寸/Size
160cmx230cm 240cmx340cm
200cmx290cm 300cmx400cm** (匹配方法: model_prefix)
  - product_name: `克里斯系列-Kris01` → `地毯`
  - specs: `160cm*230cm,240cm*340cm,200cm*290cm,300cm*400cm` → ``
  - source: `常规款式图册2025.9.16-` → `image`
- **克里斯系列-Kris08
材质/ Material: 超柔丙纶+涤纶收缩纱
厚度/Thickness: 12mm左右
产地/Original: 国产
工艺/Crafts: 威尔顿机织
打理/Manage: 吸尘器、地毯清洁剂、布艺清洗机
尺寸/Size
160cmx230cm 240cmx340cm
200cmx290cm 300cmx400cm** (匹配方法: model_prefix)
  - product_name: `克里斯系列-Kris08` → `地毯`
  - specs: `160cm*230cm,240cm*340cm,200cm*290cm,300cm*400cm` → ``
  - source: `常规款式图册2025.9.16-` → `image`
- **克里斯系列-Kris09
材质/ Material: 超柔丙纶+涤纶收缩纱
厚度/Thickness: 12mm左右
产地/Original: 国产
工艺/Crafts: 威尔顿机织
打理/Manage: 吸尘器、地毯清洁剂、布艺清洗机
尺寸/Size
160cmx230cm 240cmx340cm
200cmx290cm 300cmx400cm** (匹配方法: model_prefix)
  - product_name: `克里斯系列-Kris09` → `地毯`
  - specs: `160cm*230cm,240cm*340cm,200cm*290cm,300cm*400cm` → ``
  - source: `常规款式图册2025.9.16-` → `image`
- **克里斯系列-Kris10
材质/ Material: 超柔丙纶+涤纶收缩纱
厚度/Thickness: 12mm左右
产地/Original: 国产
工艺/Crafts: 威尔顿机织
打理/Manage: 吸尘器、地毯清洁剂、布艺清洗机
尺寸/Size
160cmx230cm 240cmx340cm
200cmx290cm 300cmx400cm** (匹配方法: model_prefix)
  - product_name: `克里斯系列-Kris10` → `地毯`
  - specs: `160cm*230cm,240cm*340cm,200cm*290cm,300cm*400cm` → ``
  - source: `常规款式图册2025.9.16-` → `image`
- **克里斯系列-Kris13
材质/ Material: 超柔丙纶+涤纶收缩纱
厚度/Thickness: 12mm左右
产地/Original: 国产
工艺/Crafts: 威尔顿机织
打理/Manage: 吸尘器、地毯清洁剂、布艺清洗机
尺寸/Size
160cmx230cm 240cmx340cm
200cmx290cm 300cmx400cm** (匹配方法: model_prefix)
  - product_name: `克里斯系列-Kris13` → `地毯`
  - specs: `160cm*230cm,240cm*340cm,200cm*290cm,300cm*400cm` → ``
  - source: `常规款式图册2025.9.16-` → `image`
- **克里斯系列-Kris16
材质/ Material: 超柔丙纶+涤纶收缩纱
厚度/Thickness: 12mm左右
产地/Original: 国产
工艺/Crafts: 威尔顿机织
打理/Manage: 吸尘器、地毯清洁剂、布艺清洗机
尺寸/Size
160cmx230cm 240cmx340cm
200cmx290cm 300cmx400cm** (匹配方法: model_prefix)
  - product_name: `克里斯系列-Kris16` → `地毯`
  - specs: `160cm*230cm,240cm*340cm,200cm*290cm,300cm*400cm` → ``
  - source: `常规款式图册2025.9.16-` → `image`
- **克里斯系列-Kris17
材质/ Material: 超柔丙纶+涤纶收缩纱
厚度/Thickness: 12mm左右
产地/Original: 国产
工艺/Crafts: 威尔顿机织
打理/Manage: 吸尘器、地毯清洁剂、布艺清洗机
尺寸/Size
160cmx230cm 240cmx340cm
200cmx290cm 300cmx400cm** (匹配方法: model_prefix)
  - product_name: `克里斯系列-Kris17` → `地毯`
  - specs: `160cm*230cm,240cm*340cm,200cm*290cm,300cm*400cm` → ``
  - source: `常规款式图册2025.9.16-` → `image`
- **克里斯系列-Kris19
材质/ Material: 超柔丙纶+涤纶收缩纱
厚度/Thickness: 12mm左右
产地/Original: 国产
工艺/Crafts: 威尔顿机织
打理/Manage: 吸尘器、地毯清洁剂、布艺清洗机
尺寸/Size
160cmx230cm 240cmx340cm
200cmx290cm 300cmx400cm** (匹配方法: model_prefix)
  - product_name: `克里斯系列-Kris19` → `地毯`
  - specs: `160cm*230cm,240cm*340cm,200cm*290cm,300cm*400cm` → ``
  - source: `常规款式图册2025.9.16-` → `image`
- **克里斯系列-Kris21
材质/ Material: 超柔丙纶+涤纶收缩纱
厚度/Thickness: 12mm左右
产地/Original: 国产
工艺/Crafts: 威尔顿机织
打理/Manage: 吸尘器、地毯清洁剂、布艺清洗机
尺寸/Size
160cmx230cm 240cmx340cm
200cmx290cm 300cmx400cm** (匹配方法: model_prefix)
  - product_name: `克里斯系列-Kris21` → `地毯`
  - specs: `160cm*230cm,240cm*340cm,200cm*290cm,300cm*400cm` → ``
  - source: `常规款式图册2025.9.16-` → `image`
- **克里斯系列-Kris22
材质/ Material: 超柔丙纶+涤纶收缩纱
厚度/Thickness: 12mm左右
产地/Original: 国产
工艺/Crafts: 威尔顿机织
打理/Manage: 吸尘器、地毯清洁剂、布艺清洗机
尺寸/Size
160cmx230cm 240cmx340cm
200cmx290cm 300cmx400cm** (匹配方法: model_prefix)
  - product_name: `克里斯系列-Kris22` → `地毯`
  - specs: `160cm*230cm,240cm*340cm,200cm*290cm,300cm*400cm` → ``
  - source: `常规款式图册2025.9.16-` → `image`

### 2025.乐适佳家具电子图册

**多余 SKU (11):**

- 功能沙发
- Functional sofa
- Functional sofa
- 沙发
- Functional sofa
- Sofa
- Functional sofa
- 弧形沙发
- 沙发
- 沙发
- Functional sofa

**字段差异 (前10):**

- **L09#
300*110*80/100CM** (匹配方法: model_prefix)
  - product_name: `L09#` → `L09弧形`
  - specs: `300*110*80CM,300*110*100CM` → `390*110*80/100CM`
  - source: `2025.乐适佳家具电子图册` → ``
- **TK07A
275*112*78/100CM** (匹配方法: model_prefix)
  - product_name: `TK07A` → `Functional Sofa`
  - specs: `275*112*78CM,275*112*100CM` → `275*112*78/100CM`
  - source: `2025.乐适佳家具电子图册` → `page_1`
- **TK06
335*99*97CM** (匹配方法: model_prefix)
  - product_name: `TK06` → `Functional sofa`
  - source: `2025.乐适佳家具电子图册` → `image`
- **Y01
350*168*97CM** (匹配方法: model_prefix)
  - product_name: `Y01` → `Functional sofa`
  - source: `2025.乐适佳家具电子图册` → `OCR`
- **Y01A
275*97*93CM** (匹配方法: model_prefix)
  - product_name: `Y01A` → `Functional sofa`
  - source: `2025.乐适佳家具电子图册` → ``
- **TK08B
280*95*98CM** (匹配方法: model_prefix)
  - product_name: `TK08B` → `Functional sofa`
  - source: `2025.乐适佳家具电子图册` → ``
- **TK13#
310*95*92CM** (匹配方法: model_prefix)
  - product_name: `TK13#` → `Functional sofa`
  - source: `2025.乐适佳家具电子图册` → ``
- **TK15
315*102*96CM** (匹配方法: model_prefix)
  - product_name: `TK15` → `Functional sofa`
  - source: `2025.乐适佳家具电子图册` → `image`
- **TK17
275*103*91CM** (匹配方法: model_prefix)
  - product_name: `TK17` → `Functional sofa`
  - source: `2025.乐适佳家具电子图册` → `page`
- **TK16
275*105*93CM** (匹配方法: model_prefix)
  - product_name: `TK16` → `Functional sofa`
  - source: `2025.乐适佳家具电子图册` → `image`

### 2025客厅家具系列

**多余 SKU (161):**

- 芬迪白
- 蓝水晶
- 云母绿
- 宝格丽黑
- 米兰白玉
- 水晶白
- 雪山兰
- 范思哲黑
- 宇宙黑
- 餐台
- 餐台
- 餐台
- 餐台
- 餐台
- 餐台
- 保温转盘
- 餐台
- 餐台
- 餐椅
- 转盘
- 转盘
- 餐台
- 转盘
- 转盘
- 餐台
- 餐台
- 餐台
- 餐椅
- 餐台
- 餐台
- 餐台
- 餐台
- 餐台
- 餐台
- 餐台
- 餐台
- 餐椅
- 餐台
- 餐台
- 餐台
- 餐台
- 餐椅
- 餐台
- 餐台
- 餐台
- 餐台
- 电视柜
- 餐台
- 边几
- 脚凳
- 木皮板边几
- 电视柜
- 功夫茶几
- 功夫茶几
- 功夫茶几
- 功夫茶几
- 功夫茶几
- 功夫茶几
- 边几
- 边几
- 边几
- 升降茶几
- 边几
- 茶几
- 升降茶几
- 茶几
- 升降茶几 旋转面
- 边几
- 升降茶几: 旋转抽屉
- 茶几
- 边几
- 茶几
- 升降茶几
- 边几
- 茶几
- 茶几
- 边几
- 茶几
- 茶几
- 升降茶几
- 茶几
- 茶几
- 茶几
- 茶几
- 茶几
- 茶几
- 茶几
- 茶几
- 茶几
- 茶几
- 茶几
- 茶几
- 茶几
- 茶几
- 功能茶几
- 茶几
- 茶几
- 边几
- 边几
- 边几
- 边几
- 茶几
- 茶几
- 茶几
- 茶几
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅
- 餐椅

**字段差异 (前10):**

- **茶几:2147#
规格:130x70x37cm** (匹配方法: model_prefix)
  - product_name: `茶几:2147#` → `茶几`
  - specs: `130*70*37CM` → `130x70x35cm`
  - source: `2025客厅家具系列` → `OCR`
- **A08#牛角椅** (匹配方法: model_prefix)
  - product_name: `A08#牛角椅` → `牛角椅`
  - source: `2025客厅家具系列` → `image`
- **茶几：2532#
规格：89x89x35cm
边几：53x53x44cm** (匹配方法: model_prefix)
  - product_name: `茶几：2532#` → `茶几`
  - specs: `89*89*35CM,53*53*44CM` → `89x89x35cm`
  - source: `2025客厅家具系列` → `OCR`
- **餐台：T10#** (匹配方法: model_prefix)
  - product_name: `餐台：T10#` → `餐台`
  - source: `2025客厅家具系列` → `image`
- **餐台：T11#** (匹配方法: model_prefix)
  - product_name: `餐台：T11#` → `餐台`
  - source: `2025客厅家具系列` → `image`
- **餐台：T12#** (匹配方法: model_prefix)
  - product_name: `餐台：T12#` → `餐台`
  - source: `2025客厅家具系列` → `image`
- **型号：C1022#
茶几：110x77x30cm
      60x57x37cm
总长：135cm** (匹配方法: model_prefix)
  - product_name: `型号：C1022#` → `茶几`
  - specs: `110*77*30CM,60*57*37CM` → `110x77x30cm
60x57x37cm`
  - source: `2025客厅家具系列` → `image`
- **型号：C1028#带炉茶几
功能茶台：(130-160)x70.5x65cm** (匹配方法: model_prefix)
  - product_name: `型号：C1028#带炉茶几` → `带炉茶几`
  - specs: `（130-160）*70.5*65CM` → `(130-160)x70.5x65cm`
  - source: `2025客厅家具系列` → ``
- **茶车：C33#
规格：77x45x65cm** (匹配方法: model_prefix)
  - product_name: `茶车：C33#` → `茶车`
  - specs: `77*45*65CM` → `77x45x65cm`
  - source: `2025客厅家具系列` → `OCR`
- **茶车：C77#
规格：72x40x67cm** (匹配方法: model_prefix)
  - product_name: `茶车：C77#` → `茶车`
  - specs: `72*40*67CM` → `72x40x67cm`
  - source: `2025客厅家具系列` → `OCR`

### 乐适佳产品图册20250710

**多余 SKU (63):**

- L11 电动功能沙发
- 2025年度7系列新款
- 730 电动功能沙发
- 732 电动功能沙发
- 电动功能沙发
- 电动功能沙发
- 737 电动功能沙发
- 738 电动功能沙发
- 电动功能沙发
- Y01A电动功能沙发
- Y01A电动功能沙发
- Y01A电动功能沙发
- Y01A电动功能沙发
- Y01A电动功能沙发
- Y06手动功能沙发
- Y06手动功能沙发
- 电动功能沙发
- 电动功能沙发
- 电动功能沙发
- 电动功能沙发
- L型沙发
- 电动功能沙发
- 电动功能沙发
- 电动功能沙发
- 电动功能沙发
- 电动功能沙发
- 电动功能沙发
- 单人沙发
- 单人沙发
- 单人沙发
- 电动功能沙发
- 脚凳
- 电动功能沙发
- 电动功能沙发
- 电动功能沙发
- 电动功能沙发
- 乐适佳
- 电动功能沙发
- 电动功能沙发
- 电动功能沙发
- 电动功能沙发
- 电动功能沙发
- 电动功能沙发
- 电动功能沙发
- 电动功能沙发
- 电动平推沙发床款
- 八爪鱼 全电动功能沙发
- 825 电动功能沙发
- 单椅系列
- 单椅
- 单椅
- Recliner
- Recliner Chair
- 单人沙发
- 影院面包款系列
- 8016 电动影院沙发
- 8009 电动影院沙发
- 电动影院沙发
- Y01 电动影院沙发
- 沙发
- 功能沙发
- 功能沙发
- 功能沙发

**字段差异 (前10):**

- **产品型号：DP27
产品规格：单椅
产品尺寸：100CM×90CM×95CM** (匹配方法: model_prefix)
  - product_name: `产品型号：DP27` → `DP27`
  - specs: `100*90*95CM` → `单椅`
  - source: `乐适佳产品图册20250710` → `image`
- **产品型号：L16电动功能沙发
产品规格：组合沙发** (匹配方法: model_prefix)
  - product_name: `产品型号：L16电动功能沙发` → `L16 电动功能沙发`
  - source: `乐适佳产品图册20250710` → `image`
- **产品型号：L18靠背电动平移
产品规格：组合** (匹配方法: model_prefix)
  - product_name: `产品型号：L18靠背电动平移` → `L18 靠背电动平移 沙发`
  - source: `乐适佳产品图册20250710` → `OCR`
- **产品型号：Y58零靠墙电动头枕升降
产品规格：直排+储物茶几
产品尺寸：310CM×98CM×85CM** (匹配方法: model_prefix)
  - product_name: `产品型号：Y58零靠墙电动头枕升降` → `Y58 零靠墙 电动头枕升降 直排+储物茶几`
  - specs: `310*98*85CM` → `310CMX98CMX85CM`
  - source: `乐适佳产品图册20250710` → `original_image`
- **产品型号：TK13电动功能沙发
产品规格：边+中+边
产品尺寸：300CM** (匹配方法: model_prefix)
  - product_name: `产品型号：TK13电动功能沙发` → `TK13 电动功能沙发`
  - source: `乐适佳产品图册20250710` → ``
- **产品型号：TK15电动功能沙发
产品规格：边+中+边
产品尺寸：310CM** (匹配方法: model_prefix)
  - product_name: `产品型号：TK15电动功能沙发` → `TK15 电动功能沙发`
  - source: `乐适佳产品图册20250710` → `image`
- **产品型号：Y53电动功能沙发(异型直排)
产品规格：边+中+斜边双位
产品尺寸：325CM×95CM×120CM** (匹配方法: model_prefix)
  - product_name: `产品型号：Y53电动功能沙发(异型直排)` → `Y53 电动功能沙发(异型直排)`
  - specs: `325*95*120CM` → `边+中+斜边双位`
  - source: `乐适佳产品图册20250710` → ``
- **产品型号：TK16平推电动床
产品规格：边+中+边
产品尺寸：275CM** (匹配方法: model_prefix)
  - product_name: `产品型号：TK16平推电动床` → `TK16 平推电动床`
  - source: `乐适佳产品图册20250710` → `OCR`
- **产品型号：TK17平推电动床
产品规格：边+中+边
产品尺寸：275CM** (匹配方法: model_prefix)
  - product_name: `产品型号：TK17平推电动床` → `TK17 平推电动床`
  - source: `乐适佳产品图册20250710` → `OCR`
- **产品型号：L10电动功能沙发羽绒款
产品规格：边+中+边
产品尺寸：300CM×105CM80CM** (匹配方法: model_prefix)
  - product_name: `产品型号：L10电动功能沙发羽绒款` → `L10 电动功能沙发 羽绒款`
  - specs: `300*105*80CM` → `边+中+边`
  - source: `乐适佳产品图册20250710` → ``
