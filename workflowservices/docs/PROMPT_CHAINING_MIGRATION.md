# LLMChain to Prompt Chaining Migration Guide

## Overview

This document details the migration from using `LLMChain` to **prompt chaining** with LangChain Expression Language (LCEL) in the Report Writing Agent.

## What Changed

### Before: Using LLMChain

```python
from langchain.chains import LLMChain

class ContentQualityEvaluator:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.quality_prompt = PromptTemplate(
            input_variables=["content", "context", "criteria"],
            template="..."  # Your prompt template
        )
    
    def evaluate_content(self, content: str, context: str, criteria: List[str]) -> Dict[str, Any]:
        try:
            # Create new LLMChain instance on each call
            chain = LLMChain(llm=self.llm, prompt=self.quality_prompt)
            result = chain.run({
                "content": content,
                "context": context,
                "criteria": "\n".join(criteria)
            })
            
            return json.loads(result)
        except Exception as e:
            logger.error(f"Error evaluating content quality: {e}")
            return {"overall_score": 0.5, "feedback": "Error in quality evaluation"}
```

### After: Using Prompt Chaining

```python
class ContentQualityEvaluator:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.quality_prompt = PromptTemplate(
            input_variables=["content", "context", "criteria"],
            template="..."  # Your prompt template
        )
        
        # Create prompt chain using LCEL - done once during initialization
        self.quality_chain = self.quality_prompt | self.llm
    
    def evaluate_content(self, content: str, context: str, criteria: List[str]) -> Dict[str, Any]:
        try:
            # Use the pre-created prompt chain
            result = self.quality_chain.invoke({
                "content": content,
                "context": context,
                "criteria": "\n".join(criteria)
            })
            
            return json.loads(result.content)
        except Exception as e:
            logger.error(f"Error evaluating content quality: {e}")
            return {"overall_score": 0.5, "feedback": "Error in quality evaluation"}
```

## Key Differences

| Aspect | LLMChain | Prompt Chaining |
|--------|-----------|-----------------|
| **Initialization** | Creates chain on each call | Creates chain once during init |
| **Memory Usage** | Higher (new objects each time) | Lower (reuses objects) |
| **Performance** | Slower (recreation overhead) | Faster (no recreation) |
| **Syntax** | `LLMChain(llm, prompt).run()` | `(prompt \| llm).invoke()` |
| **Maintainability** | Harder to modify prompts | Easier to modify prompts |
| **Error Handling** | Scattered throughout code | Centralized in chain setup |
| **Extensibility** | Limited | Easy to add new chains |

## Migration Steps

### Step 1: Remove LLMChain Import

```python
# Before
from langchain.chains import LLMChain

# After
# No import needed - LCEL is built into LangChain
```

### Step 2: Update Class Initialization

```python
# Before
class ReportWritingAgent:
    def __init__(self, llm: ChatOpenAI = None):
        self.llm = llm or ChatOpenAI(temperature=0.1)
        # No prompt setup here

# After
class ReportWritingAgent:
    def __init__(self, llm: ChatOpenAI = None):
        self.llm = llm or ChatOpenAI(temperature=0.1)
        # Setup all prompt chains during initialization
        self._setup_prompt_chains()
    
    def _setup_prompt_chains(self):
        """Setup all prompt chains using LCEL"""
        self.outline_prompt = PromptTemplate(...)
        self.outline_chain = self.outline_prompt | self.llm
        
        self.content_prompt = PromptTemplate(...)
        self.content_chain = self.content_prompt | self.llm
```

### Step 3: Update Method Calls

```python
# Before
def _generate_report_outline(self, state: ReportWritingState) -> ReportOutline:
    outline_prompt = PromptTemplate(...)  # Created each time
    
    try:
        chain = LLMChain(llm=self.llm, prompt=outline_prompt)
        result = chain.run({
            "components": self._format_components_for_prompt(state.thread_components),
            "actor": state.writer_actor.value,
            "goal": state.business_goal.dict()
        })
        
        return json.loads(result)
    except Exception as e:
        logger.error(f"Error generating outline: {e}")
        return self._create_fallback_outline(state)

# After
def _generate_report_outline(self, state: ReportWritingState) -> ReportOutline:
    try:
        # Use pre-created prompt chain
        result = self.outline_chain.invoke({
            "components": self._format_components_for_prompt(state.thread_components),
            "actor": state.writer_actor.value,
            "goal": state.business_goal.dict()
        })
        
        return json.loads(result.content)  # Note: .content access
    except Exception as e:
        logger.error(f"Error generating outline: {e}")
        return self._create_fallback_outline(state)
```

### Step 4: Handle Response Format

```python
# Before
result = chain.run(input_data)
# result is a string

# After
result = chain.invoke(input_data)
# result is a LangChain message object, access content with .content
result.content  # This is the string content
```

## Benefits of the Migration

### 🚀 **Performance Improvements**

- **Eliminated Chain Recreation**: No more creating new `LLMChain` instances on each call
- **Reduced Memory Allocation**: Reuses the same chain objects
- **Faster Execution**: Direct prompt-to-LLM composition
- **Better Garbage Collection**: Fewer temporary objects

### 🔧 **Maintainability Enhancements**

- **Centralized Prompt Management**: All prompts defined in one place
- **Easy Modifications**: Change prompts without touching execution logic
- **Consistent Structure**: Uniform approach across all operations
- **Better Error Handling**: Centralized error handling for prompt operations

### 🎯 **Flexibility & Extensibility**

- **Easy Chain Extension**: Simple to add new prompt chains
- **Modular Design**: Each chain can be independently modified
- **Future-Proof**: Ready for LangChain's advanced features
- **Streaming Support**: Easy to add streaming capabilities

## Advanced Prompt Chaining Examples

### Multi-Step Chain

```python
# Create a multi-step prompt chain
def _setup_advanced_chains(self):
    # Step 1: Generate outline
    self.outline_prompt = PromptTemplate(...)
    
    # Step 2: Refine outline
    self.refinement_prompt = PromptTemplate(...)
    
    # Step 3: Generate content
    self.content_prompt = PromptTemplate(...)
    
    # Create the chain: outline -> refinement -> content
    self.advanced_chain = (
        self.outline_prompt | 
        self.refinement_prompt | 
        self.content_prompt | 
        self.llm
    )
```

### Chain with Memory

```python
from langchain.memory import ConversationBufferMemory

def _setup_chains_with_memory(self):
    memory = ConversationBufferMemory()
    
    # Create chain with memory
    self.memory_chain = (
        self.prompt | 
        memory | 
        self.llm
    )
```

### Chain with Callbacks

```python
from langchain.callbacks import StreamingStdOutCallbackHandler

def _setup_chains_with_callbacks(self):
    callbacks = [StreamingStdOutCallbackHandler()]
    
    # Create chain with callbacks
    self.streaming_chain = (
        self.prompt | 
        self.llm.bind(callbacks=callbacks)
    )
```

## Testing the Migration

### Before Migration Test

```python
def test_llmchain_usage():
    """Test that LLMChain was used correctly"""
    agent = create_report_writing_agent()
    
    # This would fail after migration
    assert hasattr(agent, 'outline_chain') == False
```

### After Migration Test

```python
def test_prompt_chaining():
    """Test that prompt chaining is properly set up"""
    agent = create_report_writing_agent()
    
    # Check that prompt chains are created
    assert hasattr(agent, 'outline_chain')
    assert hasattr(agent, 'content_chain')
    assert hasattr(agent, 'outline_prompt')
    assert hasattr(agent, 'content_prompt')
    
    # Check that the chains are properly composed
    assert agent.outline_chain is not None
    assert agent.content_chain is not None
```

## Troubleshooting

### Common Issues

1. **Missing .content Access**
   ```python
   # Error: 'str' object has no attribute 'content'
   result = chain.invoke(input_data)
   return json.loads(result)  # Wrong!
   
   # Fix: Access .content
   result = chain.invoke(input_data)
   return json.loads(result.content)  # Correct!
   ```

2. **Chain Not Initialized**
   ```python
   # Error: 'ReportWritingAgent' object has no attribute 'outline_chain'
   # Fix: Make sure _setup_prompt_chains() is called in __init__
   ```

3. **Prompt Template Mismatch**
   ```python
   # Error: Missing input variables
   # Fix: Ensure all variables in template are provided in invoke()
   ```

### Debug Tips

1. **Check Chain Setup**: Verify `_setup_prompt_chains()` is called
2. **Validate Prompts**: Ensure prompt templates have correct variables
3. **Test Individual Chains**: Test each chain separately before integration
4. **Monitor Performance**: Use timing to verify performance improvements

## Conclusion

The migration from `LLMChain` to prompt chaining provides significant benefits:

- **Better Performance**: Eliminates chain recreation overhead
- **Improved Maintainability**: Centralized prompt management
- **Enhanced Flexibility**: Easy to extend and modify
- **Modern Architecture**: Uses latest LangChain patterns

The migration is straightforward and provides immediate benefits while setting up the codebase for future LangChain features and improvements.
