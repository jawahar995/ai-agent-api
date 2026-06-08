from langchain_core.tools import StructuredTool
from pydantic import BaseModel, create_model
from typing import Any, Dict
import httpx

def build_api_tool(name: str, description: str, url: str, method: str = "GET", schema_dict: Dict[str, Any] = None) -> StructuredTool:
    """Builds a dynamic LangChain StructuredTool from an API definition."""
    
    args_schema = None
    if schema_dict:
        fields = {k: (v, ...) for k, v in schema_dict.items()}
        args_schema = create_model(f"{name}Args", **fields)
        
    def _execute_api(**kwargs) -> str:
        with httpx.Client() as client:
            try:
                if method.upper() == "GET":
                    response = client.get(url, params=kwargs)
                elif method.upper() == "POST":
                    response = client.post(url, json=kwargs)
                else:
                    return f"Unsupported method {method}"
                
                response.raise_for_status()
                return response.text
            except Exception as e:
                return f"API Error: {str(e)}"

    return StructuredTool.from_function(
        func=_execute_api,
        name=name,
        description=description,
        args_schema=args_schema,
    )
