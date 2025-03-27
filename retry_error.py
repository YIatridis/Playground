import asyncio
from rich import print as rprint
from pydantic_ai import Agent, RunContext, ModelRetry, capture_run_messages
from pydantic_ai.models.openai import OpenAIModel
from pydantic import BaseModel
from typing import Optional, Union
openai_model = OpenAIModel('gpt-4o-mini')


class QueryGenError(BaseModel):
    """Error response model for query generator."""
    error_message: str
    error_type: str
    suggestion: Optional[str] = None

class QueryGenResponse(BaseModel):
    sql_query: str
    
QueryFinal = Union[QueryGenResponse, QueryGenError]

agent = Agent(openai_model, result_type=QueryFinal)

QueryGenDeps = ''

@agent.result_validator
async def validate_query(ctx: RunContext, result: QueryFinal) -> QueryFinal:
            """Validates the generated SQL query using EXPLAIN."""
            if isinstance(result, QueryGenError):
                raise ModelRetry(f'Please retry again and pay attantion to fixing the error message:{QueryGenError}')
            
            try:
                  if result.sql_query:
                        raise ModelRetry(f'Please retry again and pay attention to fixing the error message:{QueryGenError}')
            except Exception as e:
                  raise ModelRetry(f'Please retry again and pay attention to fixing the error message:{QueryGenError}')
            
async def main():
      with capture_run_messages() as messages:
            try:
                result = await agent.run('What is the capital of France?')
                #rprint(result.data)
            except Exception as e:
                  print(e, 'Max retries reached')
      rprint(messages)
      
if __name__ == '__main__':
      asyncio.run(main())
            
