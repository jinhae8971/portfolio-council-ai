"""JSON 파서 테스트"""
from src.core.base_agent import BaseAgent


def test_parse_clean_json():
    text = '{"analysis": "test", "confidence_score": 75}'
    result = BaseAgent.parse_json_response(text)
    assert result["confidence_score"] == 75


def test_parse_json_with_codeblock():
    text = '```json\n{"analysis": "test", "stance": "OVERWEIGHT"}\n```'
    result = BaseAgent.parse_json_response(text)
    assert result["stance"] == "OVERWEIGHT"


def test_parse_json_with_surrounding_text():
    text = 'Here is my analysis:\n{"analysis": "test"}\nEnd of response.'
    result = BaseAgent.parse_json_response(text)
    assert result["analysis"] == "test"


def test_parse_malformed_returns_empty():
    result = BaseAgent.parse_json_response("This is not JSON at all")
    assert result == {}


def test_parse_json_with_newlines():
    text = '```json\n{\n  "analysis": "line1\\nline2",\n  "score": 80\n}\n```'
    result = BaseAgent.parse_json_response(text)
    assert result["score"] == 80
