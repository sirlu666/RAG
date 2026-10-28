"""Only local files and fake prompts: persistent C quota, including concurrent calls."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import sys

import pytest

scripts=Path(__file__).resolve().parents[2]/'scripts'
sys.path.insert(0,str(scripts))
from c_integration_budget import PersistentBudget,BASE_USD

MESSAGES=[{'role':'user','content':'测试函数单调性'}]


def test_restart_does_not_reset_reserved_or_failed_calls(tmp_path):
    path=tmp_path/'budget.json'
    first=PersistentBudget(path).reserve(MESSAGES)
    # Reservations remain charged even if the network operation subsequently failed.
    second=PersistentBudget(path).reserve(MESSAGES)
    assert first['total_calls']==67 and second['total_calls']==68
    assert Decimal(second['total_reserved_upper_usd'])>Decimal(first['total_reserved_upper_usd'])


def test_concurrent_instances_cannot_exceed_100_calls(tmp_path):
    path=tmp_path/'budget.json';instances=[PersistentBudget(path) for _ in range(4)]
    def send(n):
        try:return instances[n%4].reserve(MESSAGES)
        except ValueError:return None
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(send,range(50)))
    assert sum(r is not None for r in results)==34
    assert json.loads(path.read_text())['total_calls']==100
    with pytest.raises(ValueError):PersistentBudget(path).reserve(MESSAGES)


def test_cost_limit_rejects_before_reserving(tmp_path):
    path=tmp_path/'budget.json';budget=PersistentBudget(path)
    record=json.loads(path.read_text());record['total_reserved_upper_usd']='0.9999'
    record['reserved_upper_usd']=str(Decimal('0.9999')-Decimal(BASE_USD))
    path.write_text(json.dumps(record));before=path.read_bytes()
    with pytest.raises(ValueError):budget.reserve(MESSAGES)
    assert path.read_bytes()==before


def test_inconsistent_ledger_is_not_silently_reset(tmp_path):
    path=tmp_path/'budget.json';PersistentBudget(path)
    record=json.loads(path.read_text());record['total_calls']=0
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError):PersistentBudget(path)


def test_launcher_check_uses_explicit_models_and_preserves_demo_paths(tmp_path,monkeypatch):
    import argparse
    spec=importlib.util.spec_from_file_location('c_launcher',scripts/'start-c-integration.py')
    launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)
    monkeypatch.setattr(launcher,'CONFIG',tmp_path/'absent.env')
    for key in ('DATABASE_URL','UPLOAD_DIR','CHROMA_DIR','DEEPSEEK_API_KEY','DEEPSEEK_MODEL','MOCK_LLM',
                'EMBED_LOCAL_MODEL','RERANK_LOCAL_MODEL','LLM_MAX_TOKENS','LLM_MAX_RETRIES'):
        monkeypatch.setenv(key,'')
    monkeypatch.setenv('DEEPSEEK_API_KEY','test-local-placeholder')
    args=argparse.Namespace(data_dir=tmp_path/'isolated',embedding_dir=tmp_path/'bge',reranker_dir=tmp_path/'rerank')
    data,missing=launcher.prepare(args)
    assert not data.exists() and len([m for m in missing if 'Local model files' in m])==2
    import os
    assert os.environ['MOCK_LLM']=='false' and os.environ['DEEPSEEK_MODEL']=='deepseek-flash'
    assert os.environ['LLM_MAX_RETRIES']=='0' and data.as_posix() in os.environ['DATABASE_URL']
