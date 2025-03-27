from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import logfire

logfire.configure()
logfire.instrument_pydantic_ai()

code = """
import numpy
import logfire
logfire.configure()
a = numpy.array([1, 2, 3])
print(a)
logfire.info("Hello, world!")
a
"""

from rich import print as rprint
from pprint import pprint
async def main():
    server_params = StdioServerParameters(
        command='npx', args=['-y', '@pydantic/mcp-run-python', 'stdio']
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            rprint(len(tools.tools))
            #> 1
            rprint(repr(tools.tools[0].name))
            #> 'run_python_code'
            pprint(repr(tools.tools[0].inputSchema))
            result = await session.call_tool(tools.tools[0].name, {'python_code': code})
            rprint(result.content[0].text)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
