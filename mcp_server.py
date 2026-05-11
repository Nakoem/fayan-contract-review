"""
法眼 · MCP Server
将法眼的合同审查搜索工具暴露为 MCP 协议标准接口。

用法：
    python mcp_server.py

其他 AI 应用（Claude Code、Cursor 等）通过 stdio 连接到这个 Server，
即可调用法眼的法规搜索、判例搜索、地方政策查询、税务规则查询等工具。
"""

import asyncio
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

from tools import (
    search_regulation,
    search_case_law,
    check_local_policy,
    lookup_tax_rule,
    web_search,
)

server = Server("fayan")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="search_regulation",
            description="查询中国法律法规原文和司法实践。当需要判断合同条款是否合法时调用。"
            "关键词如：押金退还、违约金上限、合同解除条件、竞业限制、试用期、民间借贷利率等。",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "法规搜索关键词",
                    },
                },
                "required": ["keyword"],
            },
        ),
        types.Tool(
            name="search_case_law",
            description="搜索相关法院判例，了解类似纠纷法院怎么判。"
            "关键词如：押金纠纷、过高违约金、提前解除、试用期纠纷、加班费争议等。",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "案例关键词",
                    },
                },
                "required": ["keyword"],
            },
        ),
        types.Tool(
            name="check_local_policy",
            description="查询特定城市的房屋租赁地方政策。"
            "支持城市：北京、上海、深圳、广州、成都。",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名，如'北京'、'上海'",
                    },
                    "keyword": {
                        "type": "string",
                        "description": "可选的子关键词，如'备案'、'押金'",
                    },
                },
                "required": ["city"],
            },
        ),
        types.Tool(
            name="lookup_tax_rule",
            description="查询与合同相关的税务规则。"
            "主题如：房屋出租、印花税、买卖合同增值税、服务合同增值税、工资薪金个税、社保费率等。",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "税务主题",
                    },
                },
                "required": ["topic"],
            },
        ),
        types.Tool(
            name="web_search",
            description="联网搜索最新法规动态和行业资讯。关键词如：民法典、租赁新规。",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词",
                    },
                },
                "required": ["keyword"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "search_regulation":
        result = search_regulation(arguments["keyword"])
    elif name == "search_case_law":
        result = search_case_law(arguments["keyword"])
    elif name == "check_local_policy":
        result = check_local_policy(
            arguments["city"],
            arguments.get("keyword", ""),
        )
    elif name == "lookup_tax_rule":
        result = lookup_tax_rule(arguments["topic"])
    elif name == "web_search":
        result = web_search(arguments["keyword"])
    else:
        raise ValueError(f"未知工具: {name}")

    # 截断过长的结果
    if len(result) > 8000:
        result = result[:8000] + "\n...（结果已截断）"

    return [types.TextContent(type="text", text=result)]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
