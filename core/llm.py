"""Gemini LLM client for memory operations."""

from google import genai
from google.genai import types
from typing import Optional, List
from config import config


class GeminiClient:
    """Wrapper for Google Generative AI client (使用新版 SDK)."""

    def __init__(self):
        """Initialize Gemini client."""
        if not config.gemini.api_key:
            raise ValueError("GEMINI_API_KEY is required")

        self.client = genai.Client(api_key=config.gemini.api_key)
        self.model_name = config.gemini.model

    def _generate_text(self, prompt: str) -> str:
        """Generate text from prompt using new SDK."""
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt
        )
        # Extract text from response
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text') and part.text:
                    return part.text
        return ""

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text from prompt."""
        return self._generate_text(prompt)

    def generate_answer(self, question: str, memory_context: List[str]) -> str:
        """Generate answer based on retrieved memory fragments.

        Args:
            question: User's question
            memory_context: List of retrieved memory fragments

        Returns:
            Generated answer
        """
        if not memory_context:
            context_str = "（没有检索到相关记忆）"
        else:
            context_str = "\n".join([f"- {mem}" for mem in memory_context])

        prompt = f"""你是一个智能助手，需要根据以下检索到的记忆片段来回答用户的问题。

【用户问题】
{question}

【检索到的记忆片段】
{context_str}

【回答要求】
1. 必须**仅基于**上述记忆片段回答问题
2. 如果记忆片段中没有相关信息，请明确说明"根据记忆中没有找到相关信息"
3. 不要编造或添加记忆片段中没有的内容
4. 回答要简洁、准确

请回答："""

        try:
            return self._generate_text(prompt).strip()
        except Exception as e:
            return f"[生成答案失败: {str(e)}]"

    def generate_graph_enhanced_answer(
        self,
        question: str,
        memories: List[str],
        relations: List[dict]
    ) -> str:
        """Generate answer enhanced with graph relationships.

        Args:
            question: User's question
            memories: List of retrieved memory texts from vector search
            relations: List of graph relations from graph search

        Returns:
            Generated answer that combines memory and relationship context
        """
        if not memories and not relations:
            return "根据记忆中没有找到相关信息。"

        # Build memory context
        if memories:
            memory_str = "\n".join([f"{i+1}. {mem}" for i, mem in enumerate(memories)])
        else:
            memory_str = "（没有检索到相关记忆）"

        # Build relations context
        if relations:
            relation_str = "\n".join([
                f"- {r.get('source', '')} —[{r.get('relationship', '')}]→ {r.get('destination', '')}"
                for r in relations[:15]  # Limit to 15 relations
            ])
            if len(relations) > 15:
                relation_str += f"\n... 还有 {len(relations) - 15} 条关系"
        else:
            relation_str = "（没有检索到相关关系）"

        prompt = f"""你是一个智能助手，需要根据用户的记忆和知识图谱中的实体关系来回答问题。

【用户问题】
{question}

【向量检索到的记忆】
{memory_str}

【知识图谱中的实体关系】
{relation_str}

【回答要求】
1. 综合记忆片段和实体关系来回答
2. 实体关系可以帮助理解记忆之间的关联（例如：人物关系、时间序列变化、属性更新等）
3. 如果记忆中有冲突或变化（如"以前不吃香菜"→"现在能吃香菜了"），请说明时间上的演变
4. 如果相关信息不足，明确说明
5. 回答要自然流畅，像对话一样

请回答："""

        try:
            return self._generate_text(prompt).strip()
        except Exception as e:
            return f"[生成答案失败: {str(e)}]"

    def extract_entities(self, text: str) -> list[dict]:
        """Extract entities from text for graph construction."""
        prompt = f"""Extract entities and relationships from the following text.
Return as JSON list with format: {{"entity": "name", "type": "PERSON|LOCATION|EVENT|CONCEPT", "description": "brief description"}}

Text: {text}"""
        try:
            import json
            response_text = self._generate_text(prompt)
            return json.loads(response_text)
        except Exception:
            return []

    def extract_entities_and_relations(self, text: str) -> tuple[list[dict], list[dict]]:
        """Extract entities and relationships from text for graph construction.

        Args:
            text: Input text to extract from

        Returns:
            Tuple of (entities, relations) where:
            - entities: list of {"name": str, "type": str, "description": str}
            - relations: list of {"source": str, "target": str, "relation": str, "description": str}
        """
        prompt = f"""Extract entities and relationships from the following text.
Return as JSON with format:
{{
  "entities": [{{"name": "entity_name", "type": "PERSON|LOCATION|ORGANIZATION|CONCEPT|EVENT", "description": "brief description"}}],
  "relations": [{{"source": "entity1", "target": "entity2", "relation": "relationship_type", "description": "brief description"}}]
}}

Text: {text}"""
        try:
            import json
            response_text = self._generate_text(prompt)
            result = json.loads(response_text)
            entities = result.get("entities", [])
            relations = result.get("relations", [])
            return entities, relations
        except Exception as e:
            return [], []

    def embed_text(self, text: str) -> list[float]:
        """Get embedding for text using new SDK."""
        config = types.EmbedContentConfig(output_dimensionality=768)
        response = self.client.models.embed_content(
            model="models/text-embedding-004",
            contents=text,
            config=config
        )
        return response.embeddings[0].values


# Singleton instance
_llm_client: Optional[GeminiClient] = None


def get_llm_client() -> GeminiClient:
    """Get or create LLM client singleton."""
    global _llm_client
    if _llm_client is None:
        _llm_client = GeminiClient()
    return _llm_client
