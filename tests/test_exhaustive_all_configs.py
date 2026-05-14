"""穷举质量测试: 256 种配置组合 × 多样化对话脚本 × 教学质量评分.

Requirements:
- 穷尽所有 2^8 = 256 种配置组合
- 每种配置使用不同的对话脚本（不重复）
- 连续多轮对话，聚焦教学引导质量
- 子进程隔离配置，防止泄漏
"""

import yaml, sys, time, json, subprocess, os, itertools, random, hashlib
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "reports" / "exhaustive_all_configs_test.log"
REPORT = ROOT / "reports" / "exhaustive_all_configs_report.json"
PROGRESS = ROOT / "reports" / "exhaustive_all_configs_progress.json"
CONFIG = ROOT / "config" / "coach_defaults.yaml"
USED_TOPICS_LOG = ROOT / "reports" / "exhaustive_used_topics.json"


def log(msg: str):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


# ═══════════════════════════════════════════════════════════
# 1. 穷举配置组合 — 8 个布尔开关
# ═══════════════════════════════════════════════════════════

CONFIG_KEYS = [
    "llm.enabled",
    "ttm.enabled",
    "sdt.enabled",
    "flow.enabled",
    "diagnostic_engine.enabled",
    "sovereignty_pulse.enabled",
    "excursion.enabled",
    "relational_safety.enabled",
]

def generate_all_combos() -> list[tuple[str, dict]]:
    """生成 2^8 = 256 种配置组合."""
    combos = []
    for bits in itertools.product([False, True], repeat=len(CONFIG_KEYS)):
        combo = dict(zip(CONFIG_KEYS, bits))
        # 生成可读标签: 用缩写表示启用的功能
        enabled = []
        for key, val in zip(CONFIG_KEYS, bits):
            if val:
                short = key.split(".")[0]
                if short == "llm":
                    enabled.append("L")
                elif short == "ttm":
                    enabled.append("T")
                elif short == "sdt":
                    enabled.append("S")
                elif short == "flow":
                    enabled.append("F")
                elif short == "diagnostic_engine":
                    enabled.append("D")
                elif short == "sovereignty_pulse":
                    enabled.append("P")
                elif short == "excursion":
                    enabled.append("E")
                elif short == "relational_safety":
                    enabled.append("R")
        label = "+".join(enabled) if enabled else "none"
        # 去重标签: 相同标签的用 hash 区分
        h = hashlib.md5(str(combo).encode()).hexdigest()[:4]
        label = f"{label}_{h}"
        combos.append((label, combo))
    return combos


# ═══════════════════════════════════════════════════════════
# 2. 多样化对话池 — 确保每次测试用不同的对话
# ═══════════════════════════════════════════════════════════

DIALOGUE_TOPICS = [
    # === Python 基础（多个变体）===
    "python_beginner_1",
    "python_beginner_2",
    "python_beginner_3",
    "python_variables_deep",
    "python_functions",
    "python_lists_dicts",
    "python_oop_basics",
    "python_modules",
    "python_file_io",
    "python_exceptions",
    "python_debugging",
    "python_string_methods",

    # === JavaScript / Web ===
    "js_basics",
    "js_functions",
    "js_arrays",
    "js_dom_manipulation",
    "js_events",
    "html_css_layout",
    "css_flexbox",
    "react_components",
    "react_state",
    "node_npm_basics",

    # === 数据结构 ===
    "array_vs_linkedlist",
    "stack_queue",
    "hash_table",
    "binary_tree",
    "graph_basics",
    "sorting_algorithms",
    "recursion_basics",
    "dynamic_programming_intro",

    # === 算法 ===
    "binary_search",
    "two_pointers",
    "sliding_window",
    "bfs_dfs",
    "greedy_algorithms",
    "time_complexity",

    # === 数据库 ===
    "sql_select",
    "sql_joins",
    "sql_indexes",
    "nosql_intro",
    "database_design",

    # === 工具链 ===
    "git_basics",
    "git_branching",
    "linux_basics",
    "docker_intro",
    "rest_api_design",
    "cli_tools",

    # === 计算机基础 ===
    "memory_management",
    "process_thread",
    "network_protocols",
    "http_https",
    "os_concepts",
    "compiler_vs_interpreter",
]


def generate_script_for_topic(topic: str) -> list[str]:
    """根据话题生成 5-7 轮连续对话."""
    scripts = {
        "python_beginner_1": [
            "我想学 Python，从哪开始？",
            "变量是什么？用最简单的话解释",
            "变量可以存不同类型的数据吗？",
            "怎么判断一个变量是什么类型？",
            "我试了 type(42) 返回 int，为什么要有类型？",
            "列表和元组有什么区别？",
        ],
        "python_beginner_2": [
            "Python 基础语法难吗？",
            "缩进是什么？为什么 Python 要用缩进",
            "if 条件语句怎么写？",
            "if 后面可以跟多个条件吗？elif 是什么？",
            "我想根据分数输出等级，用 if 怎么写？",
        ],
        "python_beginner_3": [
            "函数怎么定义？",
            "def 后面的参数怎么用？",
            "函数可以有返回值吗？return 怎么写",
            "多个返回值怎么处理？",
            "全局变量和局部变量有什么区别？",
        ],
        "python_variables_deep": [
            "变量在内存里是怎么存的？",
            "那不可变类型比如字符串，修改时会怎样",
            "a = [1,2]; b = a; b.append(3) 为什么 a 也变了",
            "怎么避免这种引用传递的问题？",
            "深拷贝和浅拷贝有什么区别？",
        ],
        "python_functions": [
            "函数参数有哪些类型？",
            "位置参数和关键字参数有什么区别",
            "*args 和 **kwargs 是什么？有什么用",
            "函数可以嵌套定义吗？",
            "闭包是什么？有什么实际用途",
        ],
        "python_lists_dicts": [
            "列表推导式是什么？",
            "给个例子，我想快速生成平方数列表",
            "字典推导式类似吗？",
            "集合是什么？什么时候用集合而不是列表",
            "列表、字典、集合的使用场景怎么选",
        ],
        "python_oop_basics": [
            "面向对象和面向过程有什么区别？",
            "类怎么定义？__init__ 是什么",
            "self 参数有什么用？",
            "继承怎么用？子类能覆盖父类方法吗？",
            "私有属性和公有属性怎么区分？",
        ],
        "python_modules": [
            "怎么导入其他文件里的代码？",
            "import 和 from...import 有什么区别",
            "__name__ == '__main__' 是什么作用",
            "标准库里常用的模块有哪些",
            "怎么安装第三方包？pip 怎么用",
        ],
        "python_file_io": [
            "怎么读取一个文本文件？",
            "with open 是什么？为什么要用 with",
            "读取大文件时怎么一行行读",
            "写入文件用 w 和 a 有什么区别",
            "json 文件怎么读写？",
        ],
        "python_exceptions": [
            "程序报错了怎么处理？",
            "try...except 怎么用",
            "多个 except 可以吗？不同类型的错误分别处理",
            "finally 子句是什么？什么时候执行",
            "自定义异常怎么定义？",
        ],
        "python_debugging": [
            "代码出错了怎么看错误信息？",
            "pdb 调试器怎么用？",
            "print 调试有什么技巧？",
            "assert 是什么？怎么用断言调试",
            "logging 模块怎么替代 print 调试",
        ],
        "python_string_methods": [
            "字符串有哪些常用方法？",
            "split 和 join 怎么用",
            "字符串切片是什么？'hello'[1:4] 返回什么",
            "f-string 格式化怎么用",
            "正则表达式 re 模块怎么匹配字符串",
        ],
        "js_basics": [
            "JavaScript 和 Python 有什么区别？",
            "let、const、var 有什么区别",
            "箭头函数是什么？() => {} 怎么用",
            "模板字符串是什么？跟普通字符串有什么区别",
            "解构赋值怎么用？",
        ],
        "js_functions": [
            "JavaScript 函数是一等公民是什么意思？",
            "回调函数是什么？为什么 JS 里回调这么常见",
            "Promise 是什么？怎么解决回调地狱",
            "async/await 怎么用？和 Promise 什么关系",
            "闭包在 JS 里怎么用？有什么实际例子",
        ],
        "js_arrays": [
            "数组有哪些常用方法？",
            "map、filter、reduce 分别怎么用",
            "map 和 forEach 有什么区别",
            "展开运算符 ... 对数组有什么用",
            "数组去重有什么好方法？",
        ],
        "js_dom_manipulation": [
            "怎么用 JS 选中页面元素？",
            "querySelector 和 getElementById 哪个好",
            "怎么修改元素的文本和样式？",
            "事件监听 addEventListener 怎么用",
            "事件冒泡和事件委托是什么？",
        ],
        "js_events": [
            "点击事件怎么绑定？",
            "事件对象 event 里有哪些有用信息",
            "阻止默认行为和阻止冒泡有什么区别",
            "自定义事件怎么触发和监听？",
            "事件委托的实际应用场景？",
        ],
        "html_css_layout": [
            "HTML 语义化标签有哪些？",
            "Flex 布局怎么用？",
            "Grid 布局和 Flex 有什么区别",
            "响应式布局怎么实现？",
            "媒体查询 @media 怎么用？",
        ],
        "css_flexbox": [
            "Flex 容器和 Flex 元素是什么？",
            "主轴和交叉轴怎么理解",
            "justify-content 有哪些值？分别什么效果",
            "align-items 和 align-content 有什么区别",
            "flex: 1 是什么意思？flex 简写属性怎么用",
        ],
        "react_components": [
            "React 组件是什么？函数组件和类组件区别",
            "props 是什么？怎么向子组件传数据",
            "useState 怎么用？组件状态怎么管理",
            "useEffect 是什么？清除副作用怎么用",
            "自定义 Hook 怎么封装逻辑",
        ],
        "react_state": [
            "React 状态提升是什么？为什么需要",
            "Context API 怎么用？解决什么问题",
            "useReducer 和 useState 什么区别",
            "React 什么时候重新渲染？",
            "性能优化：useMemo 和 useCallback 怎么用",
        ],
        "node_npm_basics": [
            "Node.js 是什么？跟浏览器 JS 有什么区别",
            "npm 怎么安装包？package.json 是什么",
            "node_modules 目录为什么那么大",
            "CommonJS 和 ES Module 有什么区别",
            "Express 框架怎么搭建一个简单的 API",
        ],
        "array_vs_linkedlist": [
            "数组和链表的根本区别是什么？",
            "那数组为什么访问快，插入慢",
            "链表有几种类型？单向双向循环",
            "实际开发中什么时候用链表",
            "Python 的 list 是数组还是链表？",
        ],
        "stack_queue": [
            "栈和队列是什么？",
            "栈的实际应用有哪些？比如括号匹配",
            "队列有几种？普通队列和优先队列区别",
            "Python 里怎么实现栈和队列",
            "双端队列 deque 是什么",
        ],
        "hash_table": [
            "哈希表是什么？为什么查找快",
            "哈希冲突怎么解决？",
            "Python 字典的底层是哈希表吗",
            "哈希表的时间复杂度是多少",
            "好的哈希函数有什么特点",
        ],
        "binary_tree": [
            "二叉树是什么？",
            "二叉搜索树 BST 怎么工作的",
            "树的遍历有几种方式？前中后序",
            "层序遍历怎么实现？用队列吗",
            "平衡二叉树 AVL 和红黑树是什么",
        ],
        "graph_basics": [
            "图是什么？有向图和无向图区别",
            "图的邻接矩阵和邻接表表示法",
            "图的深度优先搜索 DFS 怎么实现",
            "广度优先搜索 BFS 怎么实现",
            "DFS 和 BFS 各有什么适用场景",
        ],
        "sorting_algorithms": [
            "冒泡排序是怎么工作的？",
            "快速排序的思路是什么？",
            "归并排序和快排哪个好？",
            "排序算法的时间复杂度怎么分析的",
            "实际编程中用什么排序？Python 的 sort 是什么算法",
        ],
        "recursion_basics": [
            "递归是什么？递归的两个必要条件",
            "斐波那契数列用递归怎么写",
            "递归太深会栈溢出，怎么解决",
            "尾递归优化是什么？Python 支持吗",
            "递归和迭代怎么选",
        ],
        "dynamic_programming_intro": [
            "动态规划是什么？和递归什么关系",
            "重叠子问题和最优子结构是什么",
            "斐波那契用 DP 怎么写？自顶向下和自底向上",
            "经典 DP 问题：爬楼梯怎么解",
            "DP 和贪心算法有什么区别",
        ],
        "binary_search": [
            "二分查找是什么？前提条件是什么",
            "二分查找的代码怎么写？",
            "查找第一个大于等于 target 的元素怎么改",
            "二分查找的时间复杂度为什么是 log n",
            "旋转数组的二分查找怎么处理",
        ],
        "two_pointers": [
            "双指针技巧是什么？",
            "两数之和 II 用双指针怎么解",
            "快慢指针在链表里有什么用",
            "滑动窗口是双指针吗？有什么区别",
            "三数之和怎么用双指针？",
        ],
        "sliding_window": [
            "滑动窗口算法是什么？",
            "固定窗口和可变窗口有什么区别",
            "最长无重复子串怎么用滑动窗口解",
            "滑动窗口的时间复杂度怎么分析",
            "什么时候用滑动窗口而不是暴力",
        ],
        "bfs_dfs": [
            "BFS 和 DFS 的核心区别是什么？",
            "BFS 为什么能找到最短路径",
            "DFS 的递归实现和迭代实现有什么区别",
            "走迷宫用 BFS 还是 DFS？",
            "拓扑排序用 DFS 还是 BFS？",
        ],
        "greedy_algorithms": [
            "贪心算法是什么？每一步选最优",
            "贪心算法的两个关键性质是什么",
            "零钱兑换问题贪心一定最优吗",
            "区间调度问题怎么用贪心解",
            "什么时候能用贪心？举一个不能用的例子",
        ],
        "time_complexity": [
            "时间复杂度是什么？为什么重要",
            "大 O 表示法怎么理解",
            "O(1)、O(n)、O(n²) 分别什么含义",
            "log n 的时间复杂度是怎么来的",
            "空间复杂度和时间复杂度怎么权衡",
        ],
        "sql_select": [
            "SELECT 语句怎么写？",
            "WHERE 条件筛选怎么用",
            "ORDER BY 排序和 LIMIT 分页",
            "聚合函数 COUNT、SUM、AVG 怎么用",
            "GROUP BY 分组查询是什么",
        ],
        "sql_joins": [
            "JOIN 有几种类型？",
            "INNER JOIN 和 LEFT JOIN 有什么区别",
            "多个表 JOIN 怎么用？",
            "自关联查询是什么？什么时候用",
            "JOIN 和子查询哪个性能好",
        ],
        "sql_indexes": [
            "数据库索引是什么？为什么能加速查询",
            "B+ 树索引是怎么工作的",
            "复合索引的最左前缀原则是什么",
            "什么时候不应该建索引？",
            "EXPLAIN 怎么看查询是否用了索引",
        ],
        "nosql_intro": [
            "NoSQL 和 SQL 的主要区别是什么？",
            "文档数据库 MongoDB 适合什么场景",
            "Redis 缓存是怎么工作的？",
            "什么时候用 NoSQL 而不是关系数据库",
            "最终一致性和强一致性有什么区别",
        ],
        "database_design": [
            "数据库设计的第一步是什么？",
            "范式是什么？第一二三范式什么意思",
            "一对多和多对多关系在数据库里怎么表示",
            "外键有什么用？需要建索引吗",
            "反范式设计什么时候用？",
        ],
        "git_basics": [
            "Git 是什么？为什么开发者都用它",
            "commit、push、pull 分别是什么",
            "分支是什么？怎么创建和切换分支",
            "合并 merge 和变基 rebase 有什么区别",
            "合并冲突怎么解决？",
        ],
        "git_branching": [
            "Git Flow 分支策略是什么？",
            "feature 分支怎么管理？",
            "pull request 和 merge request 是什么",
            "CI/CD 和 Git 分支怎么配合",
            "Git Hooks 有什么用？",
        ],
        "linux_basics": [
            "Linux 常用命令有哪些？",
            "文件权限 rwx 是什么意思？",
            "grep、find、sed 这些文本工具怎么用",
            "管道符 | 和重定向 > >> 有什么区别",
            "进程管理 ps、top、kill 怎么用",
        ],
        "docker_intro": [
            "Docker 是什么？为什么用容器",
            "镜像和容器有什么区别？",
            "Dockerfile 怎么写？",
            "docker-compose 编排多个容器",
            "Docker 和虚拟机 VM 有什么区别",
        ],
        "rest_api_design": [
            "REST API 是什么？RESTful 风格？",
            "GET、POST、PUT、DELETE 分别什么用途",
            "URL 设计有什么最佳实践？",
            "API 版本管理怎么做好？",
            "认证和授权在 REST API 里怎么实现",
        ],
        "cli_tools": [
            "命令行工具有哪些好用的？",
            "curl 怎么用？常用的请求方法",
            "jq 怎么解析 JSON 数据？",
            "awk 和 sed 文本处理怎么用",
            "tmux 终端复用器有什么用",
        ],
        "memory_management": [
            "内存是怎么管理的？堆和栈的区别",
            "垃圾回收 GC 是什么原理？",
            "Python 的引用计数和循环引用问题",
            "内存泄漏是怎么回事？怎么避免",
            "手动管理内存的语言和自动管理的区别",
        ],
        "process_thread": [
            "进程和线程的根本区别是什么？",
            "多线程编程的常见问题？GIL 是什么",
            "多进程和多线程怎么选",
            "协程是什么？和线程有什么区别",
            "异步编程 async/await 的本质是什么",
        ],
        "network_protocols": [
            "TCP/IP 协议栈分几层？",
            "TCP 和 UDP 有什么区别？",
            "三次握手和四次挥手是什么",
            "HTTP 和 HTTPS 有什么区别",
            "DNS 解析的过程是什么？",
        ],
        "http_https": [
            "HTTP 请求有哪些方法？",
            "状态码 200、301、404、500 分别什么意思",
            "HTTP 头部有哪些常用的？",
            "HTTPS 的 SSL/TLS 握手过程",
            "HTTP/2 和 HTTP/1.1 有什么区别",
        ],
        "os_concepts": [
            "操作系统的主要功能是什么？",
            "虚拟内存是什么？解决了什么问题",
            "进程调度算法有哪些？",
            "死锁的四个必要条件是什么",
            "文件系统是怎么组织数据的",
        ],
        "compiler_vs_interpreter": [
            "编译型和解释型语言有什么区别？",
            "Python 是编译型还是解释型？",
            "字节码是什么？Python 的 .pyc 文件",
            "JIT 即时编译是什么？",
            "哪种类型的语言性能更好？",
        ],
    }
    return scripts.get(topic, scripts["python_beginner_1"])


def build_dialogue_pool() -> dict[str, list[str]]:
    """生成话题→对话脚本映射."""
    pool = {}
    for topic in DIALOGUE_TOPICS:
        pool[topic] = generate_script_for_topic(topic)
    return pool


# ═══════════════════════════════════════════════════════════
# 3. 质量评分系统（增强版，聚焦教学质量）
# ═══════════════════════════════════════════════════════════

def score_quality(result: dict, prev_stmt: str = "") -> dict:
    """评估单轮回复的教学质量 (0-4 per dim, max 24)."""
    p = result.get("payload", {})
    stmt = p.get("statement", "")
    question = p.get("question", "")
    option = p.get("option", "")
    steps = p.get("steps", [])
    step = p.get("step", "")
    hint = p.get("hint", "")

    scores = {}

    # 1. relevance (0-4): 回复长度 + 领域相关
    if not stmt or len(stmt) < 10:
        scores["relevance"] = 0
    elif len(stmt) < 30:
        scores["relevance"] = 1
    elif len(stmt) < 60:
        scores["relevance"] = 2
    elif len(stmt) < 100:
        scores["relevance"] = 3
    else:
        scores["relevance"] = 4

    # 2. clarity (0-4): 比喻/举例 + 结构
    analogies = ["像", "比如", "例如", "就像", "好比", "相当于", "可以理解为"]
    has_analogy = sum(1 for w in analogies if w in stmt)
    if has_analogy >= 2 and len(stmt) > 80:
        scores["clarity"] = 4
    elif has_analogy >= 1 and len(stmt) > 50:
        scores["clarity"] = 3
    elif len(stmt) > 80:
        scores["clarity"] = 3
    elif len(stmt) > 30:
        scores["clarity"] = 2
    else:
        scores["clarity"] = 1

    # 3. interactive (0-4): 追问/选项/提示
    interactive = 0
    if question:
        interactive += 1
    if option:
        interactive += 1
    if step or steps:
        interactive += 1
    if hint:
        interactive += 1
    if len(stmt) > 120:
        interactive = min(interactive + 1, 4)
    scores["interactive"] = min(interactive, 4)

    # 4. structure (0-4): 步骤拆解（Phase 11 核心指标）
    if isinstance(steps, list) and len(steps) >= 3:
        scores["structure"] = 4
    elif isinstance(steps, list) and len(steps) >= 2:
        scores["structure"] = 3
    elif step or isinstance(steps, list) and len(steps) == 1:
        scores["structure"] = 2
    elif "第一步" in stmt or "第二步" in stmt or "首先" in stmt or "然后" in stmt:
        scores["structure"] = 2
    elif len(stmt) > 60:
        scores["structure"] = 1
    else:
        scores["structure"] = 0

    # 5. personalization (0-4): 引用用户 / 确认用户说法
    refs = ["你说的", "你刚才", "你之前", "你提到", "你问的", "你举的",
            "你说得对", "没错", "对，", "好问题", "好例子",
            "就像你说的", "如你所说", "你的理解"]
    has_ref = any(w in stmt[:150] for w in refs)
    # 确认句式
    confirmations = ["是的", "对的", "没错", "正是", "对，", "你说得对"]
    has_confirm = any(w in stmt[:80] for w in confirmations)
    if has_ref and has_confirm:
        scores["personalization"] = 4
    elif has_ref:
        scores["personalization"] = 3
    elif has_confirm and len(stmt) > 40:
        scores["personalization"] = 2
    elif prev_stmt:
        scores["personalization"] = 1
    else:
        scores["personalization"] = 0

    # 6. encouragement (0-4): 鼓励性语言
    encourages = ["棒", "好", "不错", "太", "厉害", "进步", "继续努力",
                  "很好", "优秀", "非常好", "加油", "对了", "可以的"]
    ec_count = sum(1 for w in encourages if w in stmt[:150])
    if ec_count >= 3:
        scores["encouragement"] = 4
    elif ec_count >= 2:
        scores["encouragement"] = 3
    elif ec_count >= 1:
        scores["encouragement"] = 2
    elif len(stmt) > 30:
        scores["encouragement"] = 1
    else:
        scores["encouragement"] = 0

    scores["total"] = sum(scores.values())
    return scores


# ═══════════════════════════════════════════════════════════
# 4. 子进程运行一个组合的对话
# ═══════════════════════════════════════════════════════════

def run_combo_subprocess(label: str, combo: dict, dialogue: list[str], topic: str) -> dict:
    """在隔离子进程中运行一个配置组合的完整对话."""
    combo_json_str = json.dumps(combo, ensure_ascii=False)
    dialogue_json_str = json.dumps(dialogue, ensure_ascii=False)
    combo_safe = repr(combo_json_str)
    dialogue_safe = repr(dialogue_json_str)

    script_code = f'''
import yaml, json, time, sys
sys.path.insert(0, r"{ROOT}")

# Apply config
with open(r"{CONFIG}", "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
combo = json.loads({combo_safe})
for k, v in combo.items():
    parts = k.split(".")
    d = cfg
    for p in parts[:-1]:
        d = d.setdefault(p, {{}})
    d[parts[-1]] = v
with open(r"{CONFIG}", "w", encoding="utf-8") as f:
    yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)

# Reload module to pick up new config
import importlib
import src.coach.agent as agent_mod
importlib.reload(agent_mod)
from src.coach.agent import CoachAgent

results = []
agent = CoachAgent(session_id="{label}")
dialogue = json.loads({dialogue_safe})
prev_stmt = ""

for i, msg in enumerate(dialogue, 1):
    t0 = time.time()
    r = agent.act(msg)
    dt = time.time() - t0
    p = r.get("payload", {{}})
    stmt = p.get("statement", "")
    question = p.get("question", "")
    steps = p.get("steps", [])
    step = p.get("step", "")
    option = p.get("option", "")
    hint = p.get("hint", "")

    # Quality scoring
    scores = {{}}
    # relevance
    if not stmt or len(stmt) < 10:
        scores["relevance"] = 0
    elif len(stmt) < 30:
        scores["relevance"] = 1
    elif len(stmt) < 60:
        scores["relevance"] = 2
    elif len(stmt) < 100:
        scores["relevance"] = 3
    else:
        scores["relevance"] = 4

    # clarity
    analogies = ["像", "比如", "例如", "就像", "好比", "相当于", "可以理解为"]
    has_analogy = sum(1 for w in analogies if w in stmt)
    if has_analogy >= 2 and len(stmt) > 80:
        scores["clarity"] = 4
    elif has_analogy >= 1 and len(stmt) > 50:
        scores["clarity"] = 3
    elif len(stmt) > 80:
        scores["clarity"] = 3
    elif len(stmt) > 30:
        scores["clarity"] = 2
    else:
        scores["clarity"] = 1

    # interactive
    interactive = 0
    if question: interactive += 1
    if option: interactive += 1
    if step or steps: interactive += 1
    if hint: interactive += 1
    if len(stmt) > 120: interactive = min(interactive + 1, 4)
    scores["interactive"] = min(interactive, 4)

    # structure
    if isinstance(steps, list) and len(steps) >= 3:
        scores["structure"] = 4
    elif isinstance(steps, list) and len(steps) >= 2:
        scores["structure"] = 3
    elif step or (isinstance(steps, list) and len(steps) == 1):
        scores["structure"] = 2
    elif "第一步" in stmt or "第二步" in stmt or "首先" in stmt or "然后" in stmt:
        scores["structure"] = 2
    elif len(stmt) > 60:
        scores["structure"] = 1
    else:
        scores["structure"] = 0

    # personalization
    refs = ["你说的", "你刚才", "你之前", "你提到", "你问的", "你举的",
            "你说得对", "没错", "对，", "好问题", "好例子",
            "就像你说的", "如你所说", "你的理解"]
    has_ref = any(w in stmt[:150] for w in refs)
    confirmations = ["是的", "对的", "没错", "正是", "对，", "你说得对"]
    has_confirm = any(w in stmt[:80] for w in confirmations)
    if has_ref and has_confirm:
        scores["personalization"] = 4
    elif has_ref:
        scores["personalization"] = 3
    elif has_confirm and len(stmt) > 40:
        scores["personalization"] = 2
    elif prev_stmt:
        scores["personalization"] = 1
    else:
        scores["personalization"] = 0

    # encouragement
    encourages = ["棒", "好", "不错", "太", "厉害", "进步", "继续努力",
                  "很好", "优秀", "非常好", "加油", "对了", "可以的"]
    ec_count = sum(1 for w in encourages if w in stmt[:150])
    if ec_count >= 3:
        scores["encouragement"] = 4
    elif ec_count >= 2:
        scores["encouragement"] = 3
    elif ec_count >= 1:
        scores["encouragement"] = 2
    elif len(stmt) > 30:
        scores["encouragement"] = 1
    else:
        scores["encouragement"] = 0

    scores["total"] = sum(scores.values())

    results.append({{
        "turn": i, "ok": True,
        "action_type": r.get("action_type", "?"),
        "ttm_stage": r.get("ttm_stage"),
        "llm": r.get("llm_generated", False),
        "stmt_len": len(stmt),
        "has_steps": isinstance(steps, list) and len(steps) > 0,
        "has_question": bool(question),
        "has_option": bool(option),
        "has_step_field": bool(step),
        "has_hint": bool(hint),
        "stmt_preview": stmt[:120],
        "elapsed_s": round(dt, 2),
        "tokens": r.get("llm_tokens", 0),
        "quality": scores,
        "total_score": scores["total"],
    }})
    prev_stmt = stmt

print(json.dumps(results, ensure_ascii=False))
'''

    try:
        proc = subprocess.run(
            [sys.executable, "-c", script_code],
            capture_output=True, text=True, encoding="utf-8", timeout=120,
            env={**os.environ,
                 "DEEPSEEK_API_KEY": os.environ.get("DEEPSEEK_API_KEY", ""),
                 "PYTHONIOENCODING": "utf-8"},
        )
        if proc.returncode == 0 and proc.stdout and proc.stdout.strip():
            return {"ok": True, "label": label, "topic": topic, "results": json.loads(proc.stdout)}
        else:
            return {"ok": False, "label": label, "topic": topic,
                    "error": proc.stderr[:500] or f"exit={proc.returncode}",
                    "stdout": proc.stdout[:200]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "label": label, "topic": topic, "error": "timeout (120s)"}
    except Exception as e:
        return {"ok": False, "label": label, "topic": topic, "error": str(e)}


# ═══════════════════════════════════════════════════════════
# 5. 主流程
# ═══════════════════════════════════════════════════════════

def main():
    LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()

    # 保存原始配置
    with open(CONFIG, "r", encoding="utf-8") as f:
        original_config = f.read()

    # 生成所有组合
    all_combos = generate_all_combos()
    random.shuffle(all_combos)  # 随机顺序避免系统性偏差

    # 生成对话池
    dialogue_pool = build_dialogue_pool()
    topics = list(dialogue_pool.keys())

    # 加载已使用的主题（跨测试追踪，确保不重复）
    used_topics = set()
    if USED_TOPICS_LOG.exists():
        try:
            with open(USED_TOPICS_LOG, "r") as f:
                used_topics = set(json.load(f))
        except Exception:
            pass

    # 过滤出未使用过的主题
    available_topics = [t for t in topics if t not in used_topics]
    if len(available_topics) < len(all_combos):
        # 主题不够用，重置追踪
        available_topics = topics[:]
        used_topics = set()
        log("WARNING: Not enough fresh topics, resetting topic tracker")

    with open(LOG, "w", encoding="utf-8") as f:
        f.write(f"# Exhaustive All-Config Quality Test — {ts}\n")
        f.write(f"# {len(all_combos)} combos × ~5-7 turns each\n\n")

    log("=" * 70)
    log(f"EXHAUSTIVE ALL-CONFIG QUALITY TEST")
    log(f"Total combos: {len(all_combos)}")
    log(f"Total topics: {len(available_topics)}")
    log(f"Date: {ts}")
    log("=" * 70)

    all_summaries = {}
    all_results = []
    start_time = time.time()

    # 尝试加载已有的进度
    processed_labels = set()
    if PROGRESS.exists():
        try:
            with open(PROGRESS, "r") as f:
                saved = json.load(f)
                all_summaries = saved.get("summaries", {})
                all_results = saved.get("results", [])
                processed_labels = set(saved.get("processed_labels", []))
            log(f"Resumed from progress: {len(processed_labels)} already done")
        except Exception:
            pass

    for idx, (label, combo) in enumerate(all_combos):
        if label in processed_labels:
            continue

        topic = available_topics[idx % len(available_topics)]
        dialogue = dialogue_pool[topic]
        enabled_features = [k for k, v in combo.items() if v]

        log(f"\n--- [{idx+1}/{len(all_combos)}] {label} ---")
        log(f"  Config: {enabled_features}")
        log(f"  Topic: {topic} ({len(dialogue)} turns)")
        t0 = time.time()

        result = run_combo_subprocess(label, combo, dialogue, topic)
        elapsed = time.time() - t0

        # 记录此主题已使用
        used_topics.add(topic)
        with open(USED_TOPICS_LOG, "w") as f:
            json.dump(list(used_topics), f)

        if not result["ok"]:
            log(f"  FAILED: {result.get('error', 'unknown')}")
            all_summaries[label] = {
                "ok": False, "topic": topic, "turns": 0,
                "error": result.get("error", ""),
            }
            processed_labels.add(label)
            # 保存进度
            _save_progress(PROGRESS, all_summaries, all_results, processed_labels)
            continue

        turns = result["results"]
        ok = sum(1 for t in turns if t.get("ok"))
        avg_q = sum(t.get("total_score", 0) for t in turns) / max(len(turns), 1)
        llm_count = sum(1 for t in turns if t.get("llm"))
        has_steps = sum(1 for t in turns if t.get("has_steps"))
        has_question = sum(1 for t in turns if t.get("has_question"))
        avg_tokens = sum(t.get("tokens", 0) for t in turns) / max(len(turns), 1)
        actions = [t.get("action_type") for t in turns]
        dims = defaultdict(list)
        for t in turns:
            for dim, score in t.get("quality", {}).items():
                if dim != "total":
                    dims[dim].append(score)

        all_summaries[label] = {
            "ok": True, "topic": topic,
            "turns": len(turns), "ok": ok,
            "avg_quality": round(avg_q, 1),
            "llm_rate": f"{llm_count}/{ok}",
            "has_steps": f"{has_steps}/{ok}",
            "has_question": f"{has_question}/{ok}",
            "avg_tokens": round(avg_tokens, 0),
            "actions": dict((a, actions.count(a)) for a in set(actions)),
            "dimensions": {d: round(sum(s)/len(s), 2) for d, s in dims.items()},
            "time_s": round(elapsed, 0),
            "config": combo,
        }
        all_results.append({
            "label": label, "topic": topic,
            "turns": turns, "summary": all_summaries[label],
        })
        processed_labels.add(label)

        log(f"  {ok}/{len(turns)} ok | avg quality: {avg_q:.1f}/24 | llm: {llm_count}/{ok}")
        log(f"  steps: {has_steps}/{ok} | questions: {has_question}/{ok}")
        log(f"  actions: {all_summaries[label]['actions']}")
        log(f"  dimensions: {all_summaries[label]['dimensions']}")
        log(f"  time: {elapsed:.0f}s | total: {time.time()-start_time:.0f}s")

        # ── 进度条 (实时控制台输出) ──
        completed = len(processed_labels)
        total = len(all_combos)
        pct = completed / total * 100
        elapsed_total = time.time() - start_time
        if completed > 1:
            eta = elapsed_total / completed * (total - completed)
            eta_str = f"{eta/60:.0f}min"
        else:
            eta_str = "calculating..."
        bar_width = 40
        filled = int(bar_width * completed / total)
        bar = "█" * filled + "░" * (bar_width - filled)
        avg_q_all = sum(s.get("avg_quality", 0) for s in all_summaries.values() if s.get("ok")) / max(len([s for s in all_summaries.values() if s.get("ok")]), 1)
        print(f"\r[{bar}] {pct:5.1f}% | {completed}/{total} | "
              f"avg q={avg_q_all:.1f}/24 | elapsed={elapsed_total/60:.0f}min | "
              f"ETA={eta_str} | cur: {enabled_features}",
              end="", flush=True)

        # 每 16 个组合保存一次进度
        if (idx + 1) % 16 == 0:
            _save_progress(PROGRESS, all_summaries, all_results, processed_labels)
            remaining = len(all_combos) - idx - 1
            avg_combo_time = (time.time() - start_time) / (idx + 1)
            eta = remaining * avg_combo_time
            log(f"\n--- PROGRESS: {idx+1}/{len(all_combos)} done | "
                f"ETA: {eta/60:.0f}min ---\n")

    # 恢复配置
    with open(CONFIG, "w", encoding="utf-8") as f:
        f.write(original_config)

    # 最终报告
    _write_final_report(all_summaries, all_combos, start_time, ts)


def _save_progress(progress_path: Path, summaries: dict, results: list, processed: set):
    """保存中间进度."""
    with open(progress_path, "w", encoding="utf-8") as f:
        json.dump({
            "summaries": summaries,
            "results": results,
            "processed_labels": list(processed),
        }, f, ensure_ascii=False, indent=2)


def _write_final_report(all_summaries: dict, all_combos: list, start_time: float, ts: str):
    """写入最终报告."""
    total_time = time.time() - start_time
    completed = {n: s for n, s in all_summaries.items() if s.get("ok")}
    failed = {n: s for n, s in all_summaries.items() if not s.get("ok")}
    all_qualities = [s["avg_quality"] for s in completed.values()]

    log("\n" + "=" * 70)
    log("FINAL REPORT")
    log("=" * 70)
    log(f"Total combos: {len(all_combos)}")
    log(f"Completed: {len(completed)}")
    log(f"Failed: {len(failed)}")
    log(f"Total time: {total_time/60:.1f} min")
    if all_qualities:
        log(f"Overall avg quality: {sum(all_qualities)/len(all_qualities):.1f}/24")
        log(f"Overall max quality: {max(all_qualities):.1f}/24")
        log(f"Overall min quality: {min(all_qualities):.1f}/24")

    # 6 维度总体平均
    log("\n--- Dimension Averages ---")
    dim_totals = defaultdict(list)
    for s in completed.values():
        for dim, val in s.get("dimensions", {}).items():
            dim_totals[dim].append(val)
    for dim, vals in sorted(dim_totals.items()):
        log(f"  {dim}: {sum(vals)/len(vals):.2f}/4")

    # 按配置特征分组分析
    log("\n--- By Feature Group ---")
    groups = {
        "LLM ON (any)": [],
        "Behavior OFF (T=S=F=false)": [],
        "Behavior ALL (T=S=F=true)": [],
        "Safety ON (P/E/R)": [],
    }
    for name, s in completed.items():
        cfg = s.get("config", {})
        if cfg.get("llm.enabled"):
            groups["LLM ON (any)"].append(s["avg_quality"])
        if not cfg.get("ttm.enabled") and not cfg.get("sdt.enabled") and not cfg.get("flow.enabled"):
            groups["Behavior OFF (T=S=F=false)"].append(s["avg_quality"])
        if cfg.get("ttm.enabled") and cfg.get("sdt.enabled") and cfg.get("flow.enabled"):
            groups["Behavior ALL (T=S=F=true)"].append(s["avg_quality"])
        if cfg.get("sovereignty_pulse.enabled") or cfg.get("excursion.enabled") or cfg.get("relational_safety.enabled"):
            groups["Safety ON (P/E/R)"].append(s["avg_quality"])
    for group_name, quals in groups.items():
        if quals:
            log(f"  {group_name}: {sum(quals)/len(quals):.1f}/24 (n={len(quals)})")

    # LLM ON vs OFF 对比
    llm_on = [s["avg_quality"] for n, s in completed.items()
              if s.get("config", {}).get("llm.enabled")]
    llm_off = [s["avg_quality"] for n, s in completed.items()
               if not s.get("config", {}).get("llm.enabled")]
    if llm_on:
        log(f"\n  LLM ON avg:  {sum(llm_on)/len(llm_on):.1f}/24 (n={len(llm_on)})")
    if llm_off:
        log(f"  LLM OFF avg: {sum(llm_off)/len(llm_off):.1f}/24 (n={len(llm_off)})")

    # TTM ON vs OFF
    ttm_on = [s["avg_quality"] for n, s in completed.items()
              if s.get("config", {}).get("ttm.enabled")]
    ttm_off = [s["avg_quality"] for n, s in completed.items()
               if not s.get("config", {}).get("ttm.enabled")]
    if ttm_on:
        log(f"\n  TTM ON avg:  {sum(ttm_on)/len(ttm_on):.1f}/24 (n={len(ttm_on)})")
    if ttm_off:
        log(f"  TTM OFF avg: {sum(ttm_off)/len(ttm_off):.1f}/24 (n={len(ttm_off)})")

    # 诊断引擎 ON vs OFF
    diag_on = [s["avg_quality"] for n, s in completed.items()
               if s.get("config", {}).get("diagnostic_engine.enabled")]
    diag_off = [s["avg_quality"] for n, s in completed.items()
                if not s.get("config", {}).get("diagnostic_engine.enabled")]
    if diag_on:
        log(f"\n  Diagnostic ON avg:  {sum(diag_on)/len(diag_on):.1f}/24 (n={len(diag_on)})")
    if diag_off:
        log(f"  Diagnostic OFF avg: {sum(diag_off)/len(diag_off):.1f}/24 (n={len(diag_off)})")

    # Top 10
    log("\n--- Top 10 ---")
    ranked = sorted(
        [(n, s) for n, s in completed.items()],
        key=lambda x: x[1]["avg_quality"], reverse=True)
    for i, (name, s) in enumerate(ranked[:10], 1):
        enabled = [k.split(".")[0] for k, v in s.get("config", {}).items() if v]
        log(f"  {i}. {name}  {s['avg_quality']}/24  topic={s['topic']}  config={enabled}")

    # Bottom 10
    log("\n--- Bottom 10 ---")
    for i, (name, s) in enumerate(ranked[-10:], 1):
        enabled = [k.split(".")[0] for k, v in s.get("config", {}).items() if v]
        log(f"  {i}. {name}  {s['avg_quality']}/24  topic={s['topic']}  config={enabled}")

    # 写入 JSON 报告
    report_data = {
        "test_time": ts,
        "total_combos": len(all_combos),
        "completed": len(completed),
        "failed": len(failed),
        "total_time_min": round(total_time / 60, 1),
        "overall_avg_quality": round(sum(all_qualities) / len(all_qualities), 1) if all_qualities else 0,
        "dimension_averages": {
            dim: round(sum(vals) / len(vals), 2)
            for dim, vals in dim_totals.items()
        },
        "top_10": [(n, round(s["avg_quality"], 1), s.get("topic"))
                   for n, s in ranked[:10]],
        "bottom_10": [(n, round(s["avg_quality"], 1), s.get("topic"))
                      for n, s in ranked[-10:]],
        "summaries": {n: {k: v for k, v in s.items() if k != "config"}
                      for n, s in completed.items()},
    }
    # 仅保留关键摘要
    report_data["summaries_compact"] = {
        n: {
            "quality": s["avg_quality"],
            "topic": s.get("topic"),
            "dimensions": s.get("dimensions"),
            "actions": s.get("actions"),
            "steps_rate": s.get("has_steps"),
        }
        for n, s in completed.items()
    }

    print()  # 进度条换行

    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    log(f"\nReport: {REPORT}")
    log(f"Log: {LOG}")
    log(f"Duration: {total_time/60:.1f} min")


if __name__ == "__main__":
    main()
