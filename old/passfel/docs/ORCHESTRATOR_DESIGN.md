# Orchestrator Service Design

## Overview

The Orchestrator service is the central component of PASSFEL that coordinates all user interactions, tool calling, and response generation. It uses the self-hosted Qwen3-Next-80B-A3B-Thinking LLM to understand user intent, select appropriate tools, execute actions, and generate responses.

## Architecture

### Core Components

1. **Intent Classifier**: Determines user intent from query
2. **Tool Selector**: Selects appropriate tools based on intent
3. **Tool Executor**: Executes selected tools with proper parameters
4. **Response Generator**: Generates final response using LLM
5. **Conversation Manager**: Manages conversation state and history

### Tool Categories

The Orchestrator integrates with multiple tool categories:

1. **Weather Tools**: NOAA/NWS, Open-Meteo
2. **News Tools**: RSS feeds, Ground.news
3. **Calendar Tools**: Google Calendar, Apple Calendar, Joplin
4. **Task Tools**: Joplin, Notion, Obsidian
5. **Q&A Tools**: Wikipedia, arXiv, Wikidata, web search
6. **Financial Tools**: yfinance, CoinGecko, Frankfurter
7. **Smart Home Tools**: Home Assistant, Apple HomeKit, RTSP/ONVIF
8. **Multi-Device Tools**: PWA, Capacitor, Chromecast/AirPlay

## Implementation

### Intent Classifier

```python
from typing import Dict, Any, List
from enum import Enum

class Intent(Enum):
    """User intent categories"""
    WEATHER = "weather"
    NEWS = "news"
    CALENDAR = "calendar"
    TASKS = "tasks"
    QA = "qa"
    FINANCIAL = "financial"
    SMART_HOME = "smart_home"
    GENERAL = "general"
    MULTI_STEP = "multi_step"

class IntentClassifier:
    """Classifies user intent from query"""
    
    def __init__(self, llm_client: Any):
        self.llm = llm_client
    
    def classify_intent(self, query: str, context: str = "") -> Dict[str, Any]:
        """
        Classify user intent from query
        
        Args:
            query: User's query text
            context: Additional context (conversation history, user profile)
        
        Returns:
            Dictionary containing intent, confidence, and extracted entities
        """
        # Use LLM with tool calling to classify intent
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "classify_intent",
                    "description": "Classify the user's intent and extract relevant entities",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "intent": {
                                "type": "string",
                                "enum": [intent.value for intent in Intent],
                                "description": "The primary intent of the user's query"
                            },
                            "confidence": {
                                "type": "number",
                                "description": "Confidence score between 0 and 1"
                            },
                            "entities": {
                                "type": "object",
                                "description": "Extracted entities (location, date, time, etc.)"
                            },
                            "requires_multi_step": {
                                "type": "boolean",
                                "description": "Whether the query requires multi-step reasoning"
                            }
                        },
                        "required": ["intent", "confidence"]
                    }
                }
            }
        ]
        
        messages = [
            {
                "role": "system",
                "content": "You are an intent classifier for a personal assistant. Analyze the user's query and classify their intent."
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuery: {query}\n\nClassify the intent and extract relevant entities."
            }
        ]
        
        response = self.llm.chat_completion(messages, tools=tools)
        
        # Extract tool call result
        if response.get("tool_calls"):
            tool_call = response["tool_calls"][0]
            function_args = eval(tool_call["function"]["arguments"])
            return function_args
        
        # Fallback to general intent
        return {
            "intent": Intent.GENERAL.value,
            "confidence": 0.5,
            "entities": {},
            "requires_multi_step": False
        }
```

### Tool Selector

```python
from typing import List, Dict, Any

class ToolSelector:
    """Selects appropriate tools based on intent"""
    
    def __init__(self, llm_client: Any):
        self.llm = llm_client
        self.tool_registry = self._initialize_tool_registry()
    
    def _initialize_tool_registry(self) -> Dict[str, List[Dict[str, Any]]]:
        """Initialize registry of available tools"""
        return {
            Intent.WEATHER.value: [
                {
                    "name": "get_weather_noaa",
                    "description": "Get weather data from NOAA/NWS (US only)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "latitude": {"type": "number"},
                            "longitude": {"type": "number"}
                        },
                        "required": ["latitude", "longitude"]
                    }
                },
                {
                    "name": "get_weather_openmeteo",
                    "description": "Get weather data from Open-Meteo (global)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "latitude": {"type": "number"},
                            "longitude": {"type": "number"},
                            "forecast_days": {"type": "integer", "default": 7}
                        },
                        "required": ["latitude", "longitude"]
                    }
                }
            ],
            Intent.NEWS.value: [
                {
                    "name": "get_news_rss",
                    "description": "Get news from RSS feeds",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source": {"type": "string", "enum": ["cnn", "bbc", "reuters"]},
                            "limit": {"type": "integer", "default": 10}
                        },
                        "required": ["source"]
                    }
                },
                {
                    "name": "get_news_groundnews",
                    "description": "Get news from Ground.news with bias analysis",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "limit": {"type": "integer", "default": 5}
                        }
                    }
                }
            ],
            Intent.CALENDAR.value: [
                {
                    "name": "get_calendar_events",
                    "description": "Get upcoming calendar events",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_date": {"type": "string", "format": "date"},
                            "end_date": {"type": "string", "format": "date"},
                            "calendar_source": {"type": "string", "enum": ["google", "apple", "all"]}
                        }
                    }
                },
                {
                    "name": "create_calendar_event",
                    "description": "Create a new calendar event",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "start_time": {"type": "string", "format": "date-time"},
                            "end_time": {"type": "string", "format": "date-time"},
                            "description": {"type": "string"},
                            "location": {"type": "string"}
                        },
                        "required": ["title", "start_time", "end_time"]
                    }
                }
            ],
            Intent.TASKS.value: [
                {
                    "name": "get_tasks",
                    "description": "Get active tasks",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "enum": ["pending", "in_progress", "all"]},
                            "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent", "all"]}
                        }
                    }
                },
                {
                    "name": "create_task",
                    "description": "Create a new task",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                            "due_date": {"type": "string", "format": "date"}
                        },
                        "required": ["title"]
                    }
                },
                {
                    "name": "update_task",
                    "description": "Update an existing task",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string"},
                            "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "cancelled"]},
                            "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]}
                        },
                        "required": ["task_id"]
                    }
                }
            ],
            Intent.QA.value: [
                {
                    "name": "search_wikipedia",
                    "description": "Search Wikipedia for information",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "limit": {"type": "integer", "default": 5}
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "search_arxiv",
                    "description": "Search arXiv for research papers",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "max_results": {"type": "integer", "default": 5}
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "search_web",
                    "description": "Search the web using Bing or Google",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "num_results": {"type": "integer", "default": 5}
                        },
                        "required": ["query"]
                    }
                }
            ],
            Intent.FINANCIAL.value: [
                {
                    "name": "get_stock_price",
                    "description": "Get current stock price",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string"},
                            "period": {"type": "string", "enum": ["1d", "5d", "1mo", "3mo", "1y"]}
                        },
                        "required": ["symbol"]
                    }
                },
                {
                    "name": "get_crypto_price",
                    "description": "Get cryptocurrency price",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string"},
                            "currency": {"type": "string", "default": "usd"}
                        },
                        "required": ["symbol"]
                    }
                },
                {
                    "name": "get_exchange_rate",
                    "description": "Get currency exchange rate",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "from_currency": {"type": "string"},
                            "to_currency": {"type": "string"}
                        },
                        "required": ["from_currency", "to_currency"]
                    }
                }
            ],
            Intent.SMART_HOME.value: [
                {
                    "name": "get_device_state",
                    "description": "Get smart home device state",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "device_id": {"type": "string"},
                            "device_type": {"type": "string"}
                        },
                        "required": ["device_id"]
                    }
                },
                {
                    "name": "control_device",
                    "description": "Control smart home device",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "device_id": {"type": "string"},
                            "action": {"type": "string"},
                            "parameters": {"type": "object"}
                        },
                        "required": ["device_id", "action"]
                    }
                },
                {
                    "name": "get_camera_stream",
                    "description": "Get camera stream URL",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "camera_id": {"type": "string"}
                        },
                        "required": ["camera_id"]
                    }
                }
            ]
        }
    
    def select_tools(
        self,
        intent: str,
        query: str,
        entities: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Select appropriate tools based on intent
        
        Args:
            intent: Classified intent
            query: User's query text
            entities: Extracted entities
        
        Returns:
            List of selected tools with parameters
        """
        # Get available tools for this intent
        available_tools = self.tool_registry.get(intent, [])
        
        if not available_tools:
            return []
        
        # Use LLM to select and parameterize tools
        messages = [
            {
                "role": "system",
                "content": "You are a tool selector for a personal assistant. Select the appropriate tools to fulfill the user's request."
            },
            {
                "role": "user",
                "content": f"Query: {query}\nIntent: {intent}\nEntities: {entities}\n\nSelect the appropriate tools and provide parameters."
            }
        ]
        
        response = self.llm.chat_completion(messages, tools=available_tools)
        
        # Extract tool calls
        selected_tools = []
        if response.get("tool_calls"):
            for tool_call in response["tool_calls"]:
                selected_tools.append({
                    "name": tool_call["function"]["name"],
                    "parameters": eval(tool_call["function"]["arguments"])
                })
        
        return selected_tools
```

### Tool Executor

```python
from typing import Dict, Any, List
import asyncio

class ToolExecutor:
    """Executes selected tools"""
    
    def __init__(self):
        self.tool_implementations = self._initialize_tool_implementations()
    
    def _initialize_tool_implementations(self) -> Dict[str, callable]:
        """Initialize tool implementations"""
        return {
            # Weather tools
            "get_weather_noaa": self._get_weather_noaa,
            "get_weather_openmeteo": self._get_weather_openmeteo,
            
            # News tools
            "get_news_rss": self._get_news_rss,
            "get_news_groundnews": self._get_news_groundnews,
            
            # Calendar tools
            "get_calendar_events": self._get_calendar_events,
            "create_calendar_event": self._create_calendar_event,
            
            # Task tools
            "get_tasks": self._get_tasks,
            "create_task": self._create_task,
            "update_task": self._update_task,
            
            # Q&A tools
            "search_wikipedia": self._search_wikipedia,
            "search_arxiv": self._search_arxiv,
            "search_web": self._search_web,
            
            # Financial tools
            "get_stock_price": self._get_stock_price,
            "get_crypto_price": self._get_crypto_price,
            "get_exchange_rate": self._get_exchange_rate,
            
            # Smart home tools
            "get_device_state": self._get_device_state,
            "control_device": self._control_device,
            "get_camera_stream": self._get_camera_stream
        }
    
    async def execute_tools(
        self,
        tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Execute selected tools in parallel
        
        Args:
            tools: List of tools with parameters
        
        Returns:
            List of tool execution results
        """
        tasks = []
        for tool in tools:
            tool_name = tool["name"]
            parameters = tool["parameters"]
            
            if tool_name in self.tool_implementations:
                tasks.append(self._execute_tool(tool_name, parameters))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Format results
        formatted_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                formatted_results.append({
                    "tool": tools[i]["name"],
                    "success": False,
                    "error": str(result)
                })
            else:
                formatted_results.append({
                    "tool": tools[i]["name"],
                    "success": True,
                    "result": result
                })
        
        return formatted_results
    
    async def _execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Any:
        """Execute a single tool"""
        tool_func = self.tool_implementations[tool_name]
        return await tool_func(**parameters)
    
    # Weather tool implementations
    async def _get_weather_noaa(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """Get weather from NOAA/NWS"""
        # Implementation here
        pass
    
    async def _get_weather_openmeteo(
        self,
        latitude: float,
        longitude: float,
        forecast_days: int = 7
    ) -> Dict[str, Any]:
        """Get weather from Open-Meteo"""
        # Implementation here
        pass
    
    # News tool implementations
    async def _get_news_rss(self, source: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get news from RSS feeds"""
        # Implementation here
        pass
    
    async def _get_news_groundnews(
        self,
        query: str = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get news from Ground.news"""
        # Implementation here
        pass
    
    # Calendar tool implementations
    async def _get_calendar_events(
        self,
        start_date: str = None,
        end_date: str = None,
        calendar_source: str = "all"
    ) -> List[Dict[str, Any]]:
        """Get calendar events"""
        # Implementation here
        pass
    
    async def _create_calendar_event(
        self,
        title: str,
        start_time: str,
        end_time: str,
        description: str = None,
        location: str = None
    ) -> Dict[str, Any]:
        """Create calendar event"""
        # Implementation here
        pass
    
    # Task tool implementations
    async def _get_tasks(
        self,
        status: str = "all",
        priority: str = "all"
    ) -> List[Dict[str, Any]]:
        """Get tasks"""
        # Implementation here
        pass
    
    async def _create_task(
        self,
        title: str,
        description: str = None,
        priority: str = "medium",
        due_date: str = None
    ) -> Dict[str, Any]:
        """Create task"""
        # Implementation here
        pass
    
    async def _update_task(
        self,
        task_id: str,
        status: str = None,
        priority: str = None
    ) -> Dict[str, Any]:
        """Update task"""
        # Implementation here
        pass
    
    # Q&A tool implementations
    async def _search_wikipedia(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search Wikipedia"""
        # Implementation here
        pass
    
    async def _search_arxiv(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Search arXiv"""
        # Implementation here
        pass
    
    async def _search_web(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """Search web"""
        # Implementation here
        pass
    
    # Financial tool implementations
    async def _get_stock_price(self, symbol: str, period: str = "1d") -> Dict[str, Any]:
        """Get stock price"""
        # Implementation here
        pass
    
    async def _get_crypto_price(self, symbol: str, currency: str = "usd") -> Dict[str, Any]:
        """Get crypto price"""
        # Implementation here
        pass
    
    async def _get_exchange_rate(
        self,
        from_currency: str,
        to_currency: str
    ) -> Dict[str, Any]:
        """Get exchange rate"""
        # Implementation here
        pass
    
    # Smart home tool implementations
    async def _get_device_state(
        self,
        device_id: str,
        device_type: str = None
    ) -> Dict[str, Any]:
        """Get device state"""
        # Implementation here
        pass
    
    async def _control_device(
        self,
        device_id: str,
        action: str,
        parameters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Control device"""
        # Implementation here
        pass
    
    async def _get_camera_stream(self, camera_id: str) -> Dict[str, Any]:
        """Get camera stream"""
        # Implementation here
        pass
```

### Response Generator

```python
from typing import Dict, Any, List

class ResponseGenerator:
    """Generates final response using LLM"""
    
    def __init__(self, llm_client: Any):
        self.llm = llm_client
    
    def generate_response(
        self,
        query: str,
        context: str,
        tool_results: List[Dict[str, Any]],
        use_reasoning: bool = False
    ) -> Dict[str, Any]:
        """
        Generate final response using LLM
        
        Args:
            query: User's query text
            context: Context from Context Builder
            tool_results: Results from tool execution
            use_reasoning: Whether to use reasoning mode
        
        Returns:
            Dictionary containing response, thinking (if reasoning mode), and metadata
        """
        # Format tool results
        tool_results_str = self._format_tool_results(tool_results)
        
        # Build prompt
        messages = [
            {
                "role": "system",
                "content": "You are PASSFEL, a helpful personal assistant. Use the provided context and tool results to answer the user's query accurately and helpfully."
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nTool Results:\n{tool_results_str}\n\nUser Query: {query}\n\nProvide a comprehensive, helpful response."
            }
        ]
        
        # Generate response
        if use_reasoning:
            result = self.llm.reasoning_completion(messages)
            return {
                "response": result["response"],
                "thinking": result["thinking"],
                "full_content": result["full_content"]
            }
        else:
            result = self.llm.chat_completion(messages)
            return {
                "response": result["content"],
                "thinking": None,
                "full_content": result["content"]
            }
    
    def _format_tool_results(self, tool_results: List[Dict[str, Any]]) -> str:
        """Format tool results for LLM"""
        lines = []
        for result in tool_results:
            tool_name = result["tool"]
            if result["success"]:
                lines.append(f"Tool: {tool_name}")
                lines.append(f"Result: {result['result']}")
            else:
                lines.append(f"Tool: {tool_name}")
                lines.append(f"Error: {result['error']}")
            lines.append("")
        return "\n".join(lines)
```

### Conversation Manager

```python
from typing import List, Dict, Any
import redis
import json

class ConversationManager:
    """Manages conversation state and history"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.max_history = 20  # Maximum conversation turns to keep
    
    def add_turn(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        metadata: Dict[str, Any] = None
    ):
        """Add a conversation turn"""
        turn = {
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat()
        }
        
        key = f"conversation:{user_id}:{session_id}"
        self.redis.lpush(key, json.dumps(turn))
        self.redis.ltrim(key, 0, self.max_history - 1)
        self.redis.expire(key, 86400)  # 24 hour TTL
    
    def get_history(
        self,
        user_id: str,
        session_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get conversation history"""
        key = f"conversation:{user_id}:{session_id}"
        history = self.redis.lrange(key, 0, limit - 1)
        
        return [
            json.loads(turn.decode('utf-8'))
            for turn in history
        ]
    
    def clear_history(self, user_id: str, session_id: str):
        """Clear conversation history"""
        key = f"conversation:{user_id}:{session_id}"
        self.redis.delete(key)
```

### Complete Orchestrator Service

```python
from typing import Dict, Any
import asyncio

class OrchestratorService:
    """Complete Orchestrator service"""
    
    def __init__(
        self,
        llm_client: Any,
        context_builder: Any,
        redis_client: redis.Redis
    ):
        self.llm = llm_client
        self.context_builder = context_builder
        self.intent_classifier = IntentClassifier(llm_client)
        self.tool_selector = ToolSelector(llm_client)
        self.tool_executor = ToolExecutor()
        self.response_generator = ResponseGenerator(llm_client)
        self.conversation_manager = ConversationManager(redis_client)
    
    async def process_query(
        self,
        query: str,
        user_id: str,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Process user query through complete orchestration pipeline
        
        Args:
            query: User's query text
            user_id: User identifier
            session_id: Session identifier
        
        Returns:
            Dictionary containing response and metadata
        """
        # 1. Get conversation history
        history = self.conversation_manager.get_history(user_id, session_id)
        
        # 2. Build context
        context = await self.context_builder.build_context(
            query,
            user_id,
            max_tokens=4000
        )
        
        # 3. Classify intent
        intent_result = self.intent_classifier.classify_intent(query, context)
        intent = intent_result["intent"]
        entities = intent_result.get("entities", {})
        requires_multi_step = intent_result.get("requires_multi_step", False)
        
        # 4. Select tools
        selected_tools = self.tool_selector.select_tools(intent, query, entities)
        
        # 5. Execute tools
        tool_results = []
        if selected_tools:
            tool_results = await self.tool_executor.execute_tools(selected_tools)
        
        # 6. Generate response
        response_result = self.response_generator.generate_response(
            query,
            context,
            tool_results,
            use_reasoning=requires_multi_step
        )
        
        # 7. Save conversation turn
        self.conversation_manager.add_turn(
            user_id,
            session_id,
            "user",
            query,
            metadata={"intent": intent, "entities": entities}
        )
        
        self.conversation_manager.add_turn(
            user_id,
            session_id,
            "assistant",
            response_result["response"],
            metadata={
                "tools_used": [t["tool"] for t in tool_results],
                "thinking": response_result.get("thinking")
            }
        )
        
        # 8. Return complete result
        return {
            "response": response_result["response"],
            "thinking": response_result.get("thinking"),
            "intent": intent,
            "tools_used": selected_tools,
            "tool_results": tool_results,
            "context_used": context
        }
```

## API Interface

### REST API

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="PASSFEL Orchestrator API")

class QueryRequest(BaseModel):
    query: str
    user_id: str
    session_id: str

class QueryResponse(BaseModel):
    response: str
    thinking: Optional[str]
    intent: str
    tools_used: list
    metadata: dict

@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """Process user query"""
    try:
        result = await orchestrator.process_query(
            request.query,
            request.user_id,
            request.session_id
        )
        
        return QueryResponse(
            response=result["response"],
            thinking=result.get("thinking"),
            intent=result["intent"],
            tools_used=[t["name"] for t in result["tools_used"]],
            metadata={
                "tool_results": result["tool_results"],
                "context_used": result["context_used"]
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
```

## Performance Considerations

### Optimization Strategies

1. **Parallel Execution**: Execute tools in parallel using asyncio
2. **Caching**: Cache tool results and LLM responses
3. **Streaming**: Stream LLM responses for better UX
4. **Rate Limiting**: Implement rate limiting per user
5. **Timeout Handling**: Set timeouts for tool execution
6. **Retry Logic**: Retry failed tool executions

### Monitoring

```python
import time
from typing import Dict, Any

class OrchestratorMetrics:
    """Metrics collection for Orchestrator"""
    
    def __init__(self):
        self.query_count = 0
        self.intent_distribution = {}
        self.tool_usage = {}
        self.response_times = []
    
    def record_query(
        self,
        intent: str,
        tools_used: List[str],
        response_time: float
    ):
        """Record query metrics"""
        self.query_count += 1
        
        # Intent distribution
        if intent not in self.intent_distribution:
            self.intent_distribution[intent] = 0
        self.intent_distribution[intent] += 1
        
        # Tool usage
        for tool in tools_used:
            if tool not in self.tool_usage:
                self.tool_usage[tool] = 0
            self.tool_usage[tool] += 1
        
        # Response times
        self.response_times.append(response_time)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        avg_response_time = sum(self.response_times) / len(self.response_times) if self.response_times else 0
        
        return {
            "total_queries": self.query_count,
            "intent_distribution": self.intent_distribution,
            "tool_usage": self.tool_usage,
            "average_response_time": avg_response_time
        }
```

## Testing

### Unit Tests

```python
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.mark.asyncio
async def test_intent_classifier():
    """Test intent classification"""
    llm_mock = Mock()
    llm_mock.chat_completion.return_value = {
        "tool_calls": [{
            "function": {
                "name": "classify_intent",
                "arguments": '{"intent": "weather", "confidence": 0.95}'
            }
        }]
    }
    
    classifier = IntentClassifier(llm_mock)
    result = classifier.classify_intent("What's the weather today?")
    
    assert result["intent"] == "weather"
    assert result["confidence"] == 0.95

@pytest.mark.asyncio
async def test_tool_executor():
    """Test tool execution"""
    executor = ToolExecutor()
    
    tools = [
        {"name": "get_weather_noaa", "parameters": {"latitude": 37.7749, "longitude": -122.4194}}
    ]
    
    results = await executor.execute_tools(tools)
    
    assert len(results) == 1
    assert results[0]["tool"] == "get_weather_noaa"

@pytest.mark.asyncio
async def test_orchestrator_service():
    """Test complete orchestration pipeline"""
    llm_mock = Mock()
    context_builder_mock = Mock()
    redis_mock = Mock()
    
    orchestrator = OrchestratorService(
        llm_mock,
        context_builder_mock,
        redis_mock
    )
    
    result = await orchestrator.process_query(
        "What's the weather today?",
        "user-123",
        "session-456"
    )
    
    assert "response" in result
    assert "intent" in result
    assert "tools_used" in result
```

## Deployment

### Docker Configuration

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose API port
EXPOSE 8080

# Run orchestrator service
CMD ["uvicorn", "orchestrator.api:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: passfel-orchestrator
spec:
  replicas: 3
  selector:
    matchLabels:
      app: passfel-orchestrator
  template:
    metadata:
      labels:
        app: passfel-orchestrator
    spec:
      containers:
      - name: orchestrator
        image: passfel/orchestrator:latest
        ports:
        - containerPort: 8080
        env:
        - name: LLM_BASE_URL
          value: "http://qwen-llm:8000"
        - name: REDIS_HOST
          value: "redis"
        - name: POSTGRES_HOST
          value: "postgres"
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
---
apiVersion: v1
kind: Service
metadata:
  name: passfel-orchestrator
spec:
  selector:
    app: passfel-orchestrator
  ports:
  - port: 8080
    targetPort: 8080
  type: LoadBalancer
```

## Conclusion

The Orchestrator service provides a robust, scalable architecture for coordinating all user interactions, tool calling, and response generation in PASSFEL. It leverages the self-hosted Qwen3-Next-80B-A3B-Thinking LLM's excellent tool-calling capabilities (72.0% BFCL-v3) to intelligently route user queries to appropriate tools and generate helpful responses.

**Key Features:**
- Intent classification with LLM
- Intelligent tool selection and parameterization
- Parallel tool execution for performance
- Reasoning mode for complex queries
- Conversation state management
- Comprehensive monitoring and metrics
- RESTful API interface
- Scalable deployment architecture

---

*Last Updated: 2025-10-29*
*Design document for PASSFEL Orchestrator Service*
