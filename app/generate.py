from app.retrieve import RetrievedChunk


def generate_answer(question: str, chunks: list[RetrievedChunk]) -> str:
    """将问题与召回片段发送给 DeepSeek，并返回答案文本。

    提示词约束：只能依据提供片段回答；片段不足或冲突时明确说明；
    不得编造制度、步骤、成绩或来源。
    本模块不负责检索、命中判断，也不负责生成来源链接。
    """
    raise NotImplementedError
